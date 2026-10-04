"""
D-16 (docs/FREEZE_LIST.md §7.23): every chat turn ends, on the socket, with
exactly one terminal event - done, error or stopped. The Flutter client keeps
its composer locked until one arrives (chat_view.dart, _isStreaming), so a turn
that ends without one leaves the chat "writing" until the user leaves it.

Through the real /ws/chat and the real pipeline. test_ws_chat.py replaces
pipeline.run with a fake in every test, and the fake always ends in "done" -
which is how a pipeline path that ended with no terminal event at all went
unseen: when Stage 8 left no provider to ask, the pipeline returned its error
result to the server, which keeps that result for bookkeeping and forwards
nothing.

Events are read on a background thread. TestClient's receive_json() blocks with
no timeout, and the defect under test is an event that never comes.

The second half is D-22 (§7.25): a pipeline that raises instead of returning.
The exception left ws_chat's loop and closed the socket mid-turn, so the client
got no terminal event there either - and lost the connection with it.
"""

import queue
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, response_cache
from backend.memory import conversation_store, llm_endpoint_store, vector_store
from backend.providers.base_provider import ProviderUnavailableError
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_06_web_search as stage_06
from backend.tests.test_consent_before_sending import _Stub

TERMINAL = ("done", "error", "stopped")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)


@pytest.fixture(autouse=True)
def token(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))
    return auth.get_or_create_token(tmp_path / "api_token")


@pytest.fixture(autouse=True)
def no_real_observer_calls(monkeypatch):
    # Every turn here leaves the connection with unobserved turns, so closing
    # it would run the Observer against whatever model is on this machine.
    async def fake_run_observer_now(*args, **kwargs):
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    # A cached answer would end the turn without consulting any provider.
    response_cache.clear()
    monkeypatch.setattr(stage_06, "_cache", {})
    yield
    response_cache.clear()


@pytest.fixture
def ollama_down(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise ProviderUnavailableError("Ollama is not running")
        yield  # pragma: no cover - makes this a generator like the real chat

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)
    monkeypatch.setattr(OllamaProvider, "chat", refuse)


@pytest.fixture
def stub():
    s = _Stub()
    yield s
    s.close()


def _add_remote_endpoint(tmp_path, url):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        llm_endpoint_store.add_endpoint(
            conn, provider_id="cloud-box", label="cloud box", base_url=url,
            model_name="m", is_local=False,
        )
    finally:
        conn.close()


def _grant(tmp_path, provider_id):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        server.api_grant_consent(conn, provider_id, "full_inference")
    finally:
        conn.close()


class _Events:
    """Everything the server sends, read off the socket as it arrives."""

    def __init__(self, ws):
        self._queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, args=(ws,), daemon=True).start()

    def _read(self, ws):
        try:
            while True:
                self._queue.put(ws.receive_json())
        except Exception:
            pass  # the socket closed

    def next(self, timeout=20.0):
        return self._queue.get(timeout=timeout)

    def turn(self, timeout=20.0):
        """Every event up to and including the first terminal one."""
        events = []
        deadline = time.monotonic() + timeout
        while True:
            try:
                event = self._queue.get(timeout=max(deadline - time.monotonic(), 0.01))
            except queue.Empty:
                pytest.fail(
                    f"the turn never ended: no done, error or stopped within {timeout}s "
                    f"(received {[e['type'] for e in events]})"
                )
            events.append(event)
            if event["type"] in TERMINAL:
                return events


def _terminals(events):
    return [e for e in events if e["type"] in TERMINAL]


def test_a_turn_no_provider_may_answer_ends_with_one_error(tmp_path, token, stub, ollama_down):
    """
    Ollama is down, so the chain is the one remote endpoint - which has no
    consent. Stage 8 removes it and nothing is left to ask. The user must be
    told so, once, and must be able to send the next message: the second turn
    starts clean, with no stray terminal event left over from the first.
    """
    _add_remote_endpoint(tmp_path, stub.url)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()

    for turn in (first, second):
        assert [e["type"] for e in _terminals(turn)] == ["error"]
        assert "consent" in turn[-1]["data"].lower()
        assert not any(e["type"] == "token" for e in turn)
    # The second turn begins with its own work, not with a late event from the first.
    assert second[0]["type"] == "stage"
    assert stub.sent == [], "an unconsented endpoint was sent the prompt"


def test_control_ollama_down_with_nothing_else_configured_ends_with_one_error(token, ollama_down):
    """Ollama stays in the chain when it is the only provider, so Stage 9
    tries it and reports the failure. This path already ended properly."""
    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()

    assert [e["type"] for e in _terminals(turn)] == ["error"]
    assert "All providers failed" in turn[-1]["data"]


def test_control_a_consented_endpoint_still_streams_its_answer(tmp_path, token, stub, ollama_down):
    _add_remote_endpoint(tmp_path, stub.url)
    _grant(tmp_path, "cloud-box")

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()

    assert [e["type"] for e in _terminals(turn)] == ["done"]
    assert "".join(e["data"] for e in turn if e["type"] == "token") == "STUB-REPLY"
    assert len(stub.sent) == 1


# --- D-22: a pipeline that raises -------------------------------------------


def _fails_at_once():
    raise ValueError("unexpected response shape from the model server")
    yield  # pragma: no cover - makes this a generator like the real chat


def _fails_after(text):
    def step():
        yield text
        raise ValueError("unexpected response shape from the model server")
    return step


def _answers(text):
    def step():
        yield text
    return step


@pytest.fixture
def ollama_script(monkeypatch):
    """
    Ollama available; each chat() call plays the next scripted step. A
    ValueError is not one of the two provider errors Stage 9 falls back on,
    so it travels out of the pipeline - the crash, from a realistic place: a
    model server answering in a shape the provider did not expect.
    """
    script = []

    def chat(self, messages, *args, **kwargs):
        yield from script.pop(0)()

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "chat", chat)
    return script


def _messages(tmp_path, conversation_id):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        return [(m["role"], m["content"]) for m in conversation_store.get_messages(conn, conversation_id)]
    finally:
        conn.close()


def _conversation_id(turn):
    return next(e["data"]["conversation_id"] for e in turn if e["type"] == "session_info")


def test_a_pipeline_that_raises_before_answering_ends_the_turn_with_one_error(token, ollama_script):
    """
    The turn ends with one error, and the connection survives it: the next
    message on the same socket is answered. The exception's own text stays in
    the backend log - an exception can carry whatever it was handed, model
    output or message text included, and the client is told only that the
    reply was abandoned.
    """
    ollama_script.extend([_fails_at_once, _answers("LOCAL-OLLAMA")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()

    assert [e["type"] for e in _terminals(first)] == ["error"]
    assert not any(e["type"] == "token" for e in first)
    assert first[-1]["data"]
    assert "unexpected response shape" not in first[-1]["data"]

    assert second[0]["type"] == "stage"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert "".join(e["data"] for e in second if e["type"] == "token") == "LOCAL-OLLAMA"


def test_a_pipeline_that_raises_mid_reply_ends_with_one_error_and_saves_no_partial_reply(tmp_path, token, ollama_script):
    """
    Part of the reply had already streamed. The client drops it when the error
    arrives (chat_view.dart's error case), so it is not saved as an assistant
    turn either: what is stored is what the user was left looking at. The
    user's own message is kept.
    """
    ollama_script.extend([_fails_after("PARTIAL"), _answers("LOCAL-OLLAMA")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()

    assert [e["type"] for e in first if e["type"] in ("token",) + TERMINAL] == ["token", "error"]
    assert [e["type"] for e in _terminals(second)] == ["done"]
    # Only the first turn's rows are certain here: the server saves a turn
    # after sending its terminal event, and the first turn's save finished
    # before the second message was taken. So: the user's first message, and
    # next to it either nothing yet or the second message - never the partial.
    rows = _messages(tmp_path, _conversation_id(first))
    assert rows[0] == ("user", "explain how a hash map works")
    assert rows[1:2] in ([], [("user", "explain how a linked list works")])
    assert ("assistant", "PARTIAL") not in rows


def test_a_pipeline_that_raises_after_its_answer_is_done_sends_nothing_more(tmp_path, token, ollama_script, monkeypatch):
    """
    The crash comes after "done" has already reached the client - here, while
    the answer is being cached. The turn has ended; a second terminal event
    would arrive at the start of the next turn and end that one before it
    began. The answer the user was shown is saved, as any finished answer is.
    """
    ollama_script.extend([_answers("FIRST-ANSWER"), _answers("SECOND-ANSWER")])

    def refuse(*args, **kwargs):
        raise RuntimeError("cache write failed")

    monkeypatch.setattr(server.pipeline.response_cache, "set", refuse)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()

    assert [e["type"] for e in _terminals(first)] == ["done"]
    assert second[0]["type"] == "stage"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert _messages(tmp_path, _conversation_id(first))[:2] == [
        ("user", "explain how a hash map works"),
        ("assistant", "FIRST-ANSWER"),
    ]
