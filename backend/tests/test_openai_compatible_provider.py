"""
Tests for the provider that speaks OpenAI's chat-completions protocol.

The interesting cases here are not "does it parse a token". They are the three
places this protocol differs from Ollama's in ways that break Stage 9 quietly:
server-sent events rather than newline-delimited JSON, content-free frames that
are normal rather than erroneous, and a secret that must not travel into the
trace log.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from backend.providers.base_provider import (
    ProviderExecutionError,
    ProviderUnavailableError,
)
from backend.providers.openai_compatible_provider import OpenAICompatibleProvider


def sse(*objects) -> list[bytes]:
    """A server-sent-event stream, as urlopen yields it: one line at a time."""
    lines = []
    for obj in objects:
        lines.append(f"data: {json.dumps(obj)}\n".encode("utf-8"))
        lines.append(b"\n")  # the blank separator a real stream includes
    lines.append(b"data: [DONE]\n")
    return lines


def delta(content) -> dict:
    return {"choices": [{"delta": {"content": content}}]}


def make(**kwargs) -> OpenAICompatibleProvider:
    defaults = dict(
        model_name="test-model",
        base_url="http://localhost:1234",
        provider_id="test-endpoint",
    )
    defaults.update(kwargs)
    return OpenAICompatibleProvider(**defaults)


# --- identity and consent ---------------------------------------------------


def test_get_model_info_reports_the_configured_provider_id():
    """
    Stage 8 looks consent up by this id. If the class reported one shared id
    for every endpoint, consenting to a local server would silently consent to
    a cloud key added afterwards.
    """
    info = make(provider_id="lm-studio-local").get_model_info()
    assert info["provider_id"] == "lm-studio-local"
    assert info["model_name"] == "test-model"


def test_get_model_info_never_carries_the_api_key():
    """
    The regression this guards: get_model_info() is read by the pipeline and
    its contents reach the trace log, which is written to the database. A key
    that appears here is a secret stored in plaintext - the exact outcome the
    project's password-derived key handling exists to prevent.
    """
    info = make(api_key="sk-super-secret-value").get_model_info()
    assert "sk-super-secret-value" not in json.dumps(info)


def test_is_local_is_recorded_as_told_not_guessed_from_the_url():
    """
    A localhost URL is not proof of a local model (it may be a tunnel), and a
    remote one is not proof of a public service (it may be a private gateway).
    Guessing would make get_model_info state something false about where the
    user's data goes.
    """
    assert make(base_url="http://localhost:1234", is_local=False).get_model_info()["is_local"] is False
    assert make(base_url="https://gateway.internal", is_local=True).get_model_info()["is_local"] is True


def test_the_api_key_header_is_omitted_when_there_is_no_key():
    """A local llama.cpp server needs no key, and some reject a malformed
    Authorization header they would have accepted the absence of."""
    assert "Authorization" not in make()._headers()
    assert make(api_key="k")._headers()["Authorization"] == "Bearer k"


# --- streaming --------------------------------------------------------------


@patch("urllib.request.urlopen")
def test_chat_parses_a_server_sent_event_stream(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(delta("Hello "), delta("World!"))
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert list(make().chat([{"role": "user", "content": "hi"}])) == ["Hello ", "World!"]


@patch("urllib.request.urlopen")
def test_content_free_frames_yield_nothing_rather_than_empty_strings(mock_urlopen):
    """
    The first frame of a real stream announces the assistant role and carries
    no content, and the last carries a finish reason with content null. Both
    are normal. Yielding "" for them would be worse than dropping them: Stage 9
    treats a provider that yields nothing usable as having broken its contract
    and fails over mid-answer.
    """
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(
        {"choices": [{"delta": {"role": "assistant"}}]},
        delta("real content"),
        delta(None),
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    )
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert list(make().chat([{"role": "user", "content": "hi"}])) == ["real content"]


@patch("urllib.request.urlopen")
def test_the_done_sentinel_and_blank_lines_are_not_treated_as_content(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__iter__.return_value = [
        b"\n",
        b"data: " + json.dumps(delta("x")).encode() + b"\n",
        b"\n",
        b"data: [DONE]\n",
    ]
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert list(make().chat([{"role": "user", "content": "hi"}])) == ["x"]


@patch("urllib.request.urlopen")
def test_a_torn_frame_does_not_discard_the_tokens_before_it(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__iter__.return_value = [
        b"data: " + json.dumps(delta("kept")).encode() + b"\n",
        b"data: {not valid json\n",
        b"data: " + json.dumps(delta(" also kept")).encode() + b"\n",
    ]
    mock_urlopen.return_value.__enter__.return_value = mock_response

    assert list(make().chat([{"role": "user", "content": "hi"}])) == ["kept", " also kept"]


# --- structured output ------------------------------------------------------


@patch("urllib.request.urlopen")
def test_response_format_is_dropped_by_default(mock_urlopen):
    """
    BaseLLMProvider.chat requires that asking for structure never becomes a
    hard failure. Support for this field is genuinely uneven across the
    protocol, and several local servers answer 400 to an unknown field - which
    is precisely the hard failure the contract forbids. So it is opt-in.
    """
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(delta("x"))
    mock_urlopen.return_value.__enter__.return_value = mock_response

    list(make().chat([{"role": "user", "content": "hi"}], response_format={"type": "object"}))

    sent = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
    assert "response_format" not in sent


@patch("urllib.request.urlopen")
def test_response_format_is_forwarded_when_the_endpoint_declares_support(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(delta("x"))
    mock_urlopen.return_value.__enter__.return_value = mock_response

    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    list(
        make(supports_response_format=True).chat(
            [{"role": "user", "content": "hi"}], response_format=schema
        )
    )

    sent = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
    assert sent["response_format"]["json_schema"]["schema"] == schema


# --- failure modes ----------------------------------------------------------


@patch("urllib.request.urlopen")
def test_a_connection_failure_is_unavailable_not_execution(mock_urlopen):
    """
    Stage 9's fallback chain runs on this distinction. Unavailable means try
    the next provider; an execution error means the request itself was wrong
    and the next provider would fail the same way.
    """
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    with pytest.raises(ProviderUnavailableError):
        list(make().chat([{"role": "user", "content": "hi"}]))


@pytest.mark.parametrize(
    "code,expected",
    [(401, "rejected the API key"), (404, "has no model"), (500, "returned 500")],
)
@patch("urllib.request.urlopen")
def test_http_errors_say_what_the_user_has_to_change(mock_urlopen, code, expected):
    error = urllib.error.HTTPError(
        url="http://localhost:1234/v1/chat/completions",
        code=code,
        msg="error",
        hdrs=None,
        fp=None,
    )
    error.read = MagicMock(return_value=b'{"error": "detail from the server"}')
    mock_urlopen.side_effect = error

    with pytest.raises(ProviderExecutionError) as caught:
        list(make().chat([{"role": "user", "content": "hi"}]))

    assert expected in str(caught.value)
    assert "detail from the server" in str(caught.value)


@patch("urllib.request.urlopen")
def test_an_http_error_message_does_not_leak_the_api_key(mock_urlopen):
    error = urllib.error.HTTPError(
        url="http://x/v1/chat/completions", code=401, msg="Unauthorized", hdrs=None, fp=None
    )
    error.read = MagicMock(return_value=b"{}")
    mock_urlopen.side_effect = error

    with pytest.raises(ProviderExecutionError) as caught:
        list(make(api_key="sk-secret").chat([{"role": "user", "content": "hi"}]))

    assert "sk-secret" not in str(caught.value)


@patch("urllib.request.urlopen")
def test_is_available_never_raises(mock_urlopen):
    """The base class requires this: it must answer quickly and must not
    raise, because callers use it to decide whether to bother."""
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    assert make().is_available() is False

    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.side_effect = None
    mock_urlopen.return_value.__enter__.return_value = mock_response
    assert make().is_available() is True


# --- configuration ----------------------------------------------------------


@patch("urllib.request.urlopen")
def test_a_trailing_slash_on_the_base_url_does_not_produce_a_double_slash(mock_urlopen):
    """Users type the URL both ways. '//v1/chat/completions' fails outright on
    some servers and silently 404s on others."""
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(delta("x"))
    mock_urlopen.return_value.__enter__.return_value = mock_response

    list(make(base_url="http://localhost:1234/").chat([{"role": "user", "content": "hi"}]))

    assert mock_urlopen.call_args[0][0].full_url == "http://localhost:1234/v1/chat/completions"


@patch("urllib.request.urlopen")
def test_context_is_prepended_as_a_system_message(mock_urlopen):
    mock_response = MagicMock()
    mock_response.__iter__.return_value = sse(delta("x"))
    mock_urlopen.return_value.__enter__.return_value = mock_response

    list(make().chat([{"role": "user", "content": "hi"}], context="you are helpful"))

    sent = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
    assert sent["messages"][0] == {"role": "system", "content": "you are helpful"}
    assert sent["messages"][1]["content"] == "hi"
