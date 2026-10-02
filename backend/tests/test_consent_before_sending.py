"""
Promise 6 (docs/FREEZE_LIST.md §4): nothing leaves the machine without
recorded consent - per provider, fail-closed, covering generation and web
search.

Asserted on what actually reaches a counting HTTP stub that stands in for a
provider, through the real pipeline: _default_providers builds the chain from
the stored endpoints, Stage 8 gates it, Stage 9 sends. Never on the gate's
return value. Ollama is made unavailable by patching it, not by hoping it is
down on the machine the suite runs on.

The first three are D-04 (§7.16): a provider counted as local by its consent
record alone. That record is written once, when an endpoint is first saved,
and never updated - so an endpoint saved as local and re-saved as remote kept
a "local, needs no consent" record, and an endpoint saved under the id of the
built-in Ollama borrowed Ollama's. Both were sent the full prompt. The rest
are the gate's other promises, kept here because the fix changes the gate
they pass through.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.api import server
from backend.core import pipeline, response_cache
from backend.memory import llm_endpoint_store, vector_store
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_06_web_search as stage_06


class _Stub:
    """An OpenAI-compatible server that records every request body it is sent."""

    def __init__(self):
        self.sent: list[dict] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({"data": [{"id": "stub-model"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                stub.sent.append(json.loads(self.rfile.read(length) or b"{}"))
                chunk = {"choices": [{"delta": {"content": "STUB-REPLY"}}]}
                body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def stub():
    s = _Stub()
    yield s
    s.close()


@pytest.fixture
def other_stub():
    s = _Stub()
    yield s
    s.close()


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    # A cached answer or search result would skip the providers entirely and
    # make "nothing was sent" true for the wrong reason.
    response_cache.clear()
    monkeypatch.setattr(stage_06, "_cache", {})
    yield
    response_cache.clear()


@pytest.fixture
def ollama_down(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("Ollama was called although it is unavailable")
        yield  # pragma: no cover - makes this a generator like the real chat

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)
    monkeypatch.setattr(OllamaProvider, "chat", refuse)


@pytest.fixture
def local_ollama(monkeypatch):
    """The built-in Ollama, available and answering - recorded, not real."""
    asked = []

    def answer(self, messages, *args, **kwargs):
        asked.append(messages)
        yield "LOCAL-OLLAMA"

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "chat", answer)
    return asked


def _ask(conn, question):
    return pipeline.run_sync(conn, question)


def _consent(conn, provider_id):
    return dict(conn.execute(
        "SELECT * FROM provider_consent WHERE provider_id = ?", (provider_id,)
    ).fetchone())


# --- D-04 -------------------------------------------------------------------


def test_an_endpoint_re_saved_as_remote_is_sent_nothing_without_consent(conn, stub, ollama_down):
    """
    Saved as local, the endpoint was consented by the act of adding it, and
    its consent record said "not cloud". Re-saved as remote - the same id
    pointed somewhere else and recorded as not local - the endpoint record
    changed and the consent record did not, so the gate still waved it
    through as local.
    """
    llm_endpoint_store.add_endpoint(
        conn, provider_id="box", label="box", base_url="http://127.0.0.1:9",
        model_name="m", is_local=True,
    )
    llm_endpoint_store.add_endpoint(
        conn, provider_id="box", label="box", base_url=stub.url,
        model_name="m", is_local=False,
    )

    _ask(conn, "explain how a hash map works")

    assert stub.sent == [], "an endpoint recorded as not local was sent the prompt with no consent"


@pytest.mark.parametrize("built_in", ["ollama", "web_search"])
def test_an_endpoint_cannot_take_the_id_of_a_built_in_provider(conn, stub, local_ollama, built_in):
    """
    Consent is recorded per provider_id. An endpoint saved under a built-in
    provider's id shared that provider's record: under "ollama" it was local
    by inheritance; under "web_search", consent given to web search would
    have covered a conversation endpoint. Refused when saved, so the id - and
    the consent attached to it - can only ever mean one provider. The
    conversation then goes to the built-in Ollama and nowhere else.
    """
    before = _consent(conn, built_in)

    with pytest.raises(ValueError):
        llm_endpoint_store.add_endpoint(
            conn, provider_id=built_in, label="not the built-in", base_url=stub.url,
            model_name="m", is_local=False,
        )

    assert llm_endpoint_store.get_endpoint(conn, built_in) is None
    assert _consent(conn, built_in) == before
    _ask(conn, "explain how a hash map works")
    assert stub.sent == []


def test_an_endpoint_named_ollama_from_before_the_refusal_is_sent_nothing(conn, stub, local_ollama):
    """
    A database written before the refusal can already hold such an endpoint.
    The gate itself must not trust it: it reports itself as not local, and
    the consent record it shares says local - the two records disagree, and a
    disagreement is a refusal. The built-in Ollama, which reports itself
    local, keeps working beside it - it is tried after the impostor here, so
    the gate, not the order, is what keeps the prompt local.
    """
    conn.execute(
        "INSERT INTO llm_endpoints (provider_id, label, base_url, model_name, api_key, is_local, "
        "supports_response_format, enabled, priority, created_at) "
        "VALUES ('ollama', 'impostor', ?, 'm', NULL, 0, 0, 1, 10, '2026-10-01T00:00:00+00:00')",
        (stub.url,),
    )
    conn.commit()

    result = _ask(conn, "explain how a hash map works")

    assert stub.sent == [], "a remote endpoint under the id 'ollama' was sent the prompt as if local"
    assert local_ollama, "the built-in Ollama was refused along with the impostor"
    assert result["response_text"] == "LOCAL-OLLAMA"


# --- the gate's other promises, kept through the fix -------------------------


def test_a_local_endpoint_is_used_without_consent(conn, stub, ollama_down):
    """Both records say local, so there is no third party to agree to. The fix
    must not refuse what it should not."""
    llm_endpoint_store.add_endpoint(
        conn, provider_id="lan-box", label="box", base_url=stub.url, model_name="m", is_local=True,
    )

    _ask(conn, "explain how a hash map works")

    assert len(stub.sent) == 1


def test_an_unconsented_remote_endpoint_is_sent_nothing(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(
        conn, provider_id="remote", label="r", base_url=stub.url, model_name="m", is_local=False,
    )

    result = _ask(conn, "explain how a hash map works")

    assert stub.sent == []
    assert result["status"] == "error"


def test_consent_for_one_endpoint_does_not_reach_another(conn, stub, other_stub, ollama_down):
    """B is tried first and has no consent; A has it. Only A is sent anything."""
    llm_endpoint_store.add_endpoint(
        conn, provider_id="remote-a", label="a", base_url=other_stub.url, model_name="m",
        is_local=False, priority=10,
    )
    llm_endpoint_store.add_endpoint(
        conn, provider_id="remote-b", label="b", base_url=stub.url, model_name="m",
        is_local=False, priority=5,
    )
    server.api_grant_consent(conn, "remote-a", "full_inference")

    _ask(conn, "explain how a hash map works")

    assert stub.sent == [], "B, never consented, was sent the prompt"
    assert len(other_stub.sent) == 1


def test_a_revoked_endpoint_is_sent_nothing(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(
        conn, provider_id="remote", label="r", base_url=stub.url, model_name="m", is_local=False,
    )
    server.api_grant_consent(conn, "remote", "full_inference")
    _ask(conn, "explain how a hash map works")
    assert len(stub.sent) == 1

    server.api_revoke_consent(conn, "remote")
    _ask(conn, "explain how a binary tree works")

    assert len(stub.sent) == 1, "a revoked endpoint was sent the next prompt"


def test_consent_for_web_search_only_does_not_cover_conversations(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(
        conn, provider_id="remote", label="r", base_url=stub.url, model_name="m", is_local=False,
    )
    server.api_grant_consent(conn, "remote", "web_search_only")

    _ask(conn, "explain how a hash map works")

    assert stub.sent == []


@pytest.fixture
def searches(monkeypatch):
    sent = []

    def search(query, limit, timeout):
        sent.append(query)
        return [{"title": "t", "url": "https://example.invalid", "snippet": "s"}]

    monkeypatch.setattr(stage_06, "_duckduckgo_search", search)
    return sent


def test_web_search_is_never_treated_as_local(conn, stub, ollama_down, searches):
    """
    A search engine on the internet is not local, whatever its consent
    record says. If that record were ever written as local - a hand edit, a
    bad seed - the search must still wait for consent rather than run as a
    local provider would.
    """
    llm_endpoint_store.add_endpoint(
        conn, provider_id="lan-box", label="box", base_url=stub.url, model_name="m", is_local=True,
    )
    conn.execute("UPDATE provider_consent SET is_cloud = 0 WHERE provider_id = 'web_search'")
    conn.commit()

    _ask(conn, "what is the latest news on rust today")

    assert searches == [], "web search ran without consent because its record said local"


def test_web_search_runs_only_while_consented(conn, stub, ollama_down, searches):
    """Nothing preselected: a fresh install searches nothing; granted, it
    searches; revoked, it stops."""
    llm_endpoint_store.add_endpoint(
        conn, provider_id="lan-box", label="box", base_url=stub.url, model_name="m", is_local=True,
    )

    _ask(conn, "what is the latest news on rust today")
    assert searches == [], "web search ran on a fresh install"

    server.api_grant_consent(conn, "web_search", "web_search_only")
    _ask(conn, "what is the latest news on go today")
    assert len(searches) == 1

    server.api_revoke_consent(conn, "web_search")
    _ask(conn, "what is the latest news on python today")
    assert len(searches) == 1, "web search ran after consent was revoked"
