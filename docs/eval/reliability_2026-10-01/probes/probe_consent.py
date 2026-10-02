"""
PROBE (not part of the suite) - Promise 6: nothing leaves the machine without
recorded consent. Asserted on requests that actually reach a counting HTTP
stub and on calls to the web-search function, through the real pipeline
(_default_providers -> _gate_providers -> Stage 9), never on gate return values.
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


class Stub:
    def __init__(self):
        self.posts = []
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps({"data": [{"id": "m"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                stub.posts.append(json.loads(self.rfile.read(n) or b"{}"))
                chunk = {"choices": [{"delta": {"content": "STUB-REPLY"}}]}
                body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.close()


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    c = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield c
    c.close()


@pytest.fixture
def ollama_down(monkeypatch):
    def refuse(self, *a, **k):
        raise AssertionError("ollama called")
        yield  # pragma: no cover

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)
    monkeypatch.setattr(OllamaProvider, "chat", refuse)


@pytest.fixture(autouse=True)
def no_cache():
    response_cache._cache.clear() if hasattr(response_cache, "_cache") else None
    yield


def _ask(conn, msg):
    return pipeline.run_sync(conn, msg)


def consent_row(conn, pid):
    r = conn.execute("SELECT * FROM provider_consent WHERE provider_id=?", (pid,)).fetchone()
    return dict(r) if r else None


# ---------- remote endpoint -------------------------------------------------

def test_C1_unconsented_remote_endpoint_receives_nothing(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(conn, provider_id="remote-x", label="x",
                                    base_url=stub.url, model_name="m", is_local=False)
    out = _ask(conn, "explain how a hash map works")
    assert stub.posts == [], "unconsented cloud endpoint was sent the conversation"
    assert out["status"] == "error"


def test_C2_granted_then_revoked(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(conn, provider_id="remote-x", label="x",
                                    base_url=stub.url, model_name="m", is_local=False)
    server.api_grant_consent(conn, "remote-x", "full_inference")
    _ask(conn, "explain how a hash map works")
    assert len(stub.posts) == 1
    server.api_revoke_consent(conn, "remote-x")
    _ask(conn, "explain how a binary tree works")
    assert len(stub.posts) == 1, "revoked endpoint still received a request"


def test_C3_consent_for_A_does_not_authorize_B(conn, stub, ollama_down):
    other = Stub()
    try:
        llm_endpoint_store.add_endpoint(conn, provider_id="remote-a", label="a",
                                        base_url=other.url, model_name="m", is_local=False, priority=10)
        llm_endpoint_store.add_endpoint(conn, provider_id="remote-b", label="b",
                                        base_url=stub.url, model_name="m", is_local=False, priority=5)
        server.api_grant_consent(conn, "remote-a", "full_inference")
        _ask(conn, "explain how a hash map works")
        assert stub.posts == [], "B (unconsented, higher priority) received the conversation"
        assert len(other.posts) == 1
    finally:
        other.close()


def test_C4_resaving_a_local_endpoint_as_remote_keeps_it_consent_free(conn, stub, ollama_down):
    """Reverse of FREEZE §7.2 finding 2: local -> remote re-save."""
    llm_endpoint_store.add_endpoint(conn, provider_id="box", label="box",
                                    base_url="http://127.0.0.1:9", model_name="m", is_local=True)
    # The user re-points the same id at a remote host and says it is NOT local.
    llm_endpoint_store.add_endpoint(conn, provider_id="box", label="box",
                                    base_url=stub.url, model_name="m", is_local=False)
    ep = [e for e in llm_endpoint_store.list_endpoints(conn) if e["provider_id"] == "box"][0]
    row = consent_row(conn, "box")
    print("endpoint.is_local=", ep["is_local"], "consent=", row)
    _ask(conn, "explain how a hash map works")
    assert stub.posts == [], (
        f"endpoint recorded is_local=0 received {len(stub.posts)} request(s) with no consent; "
        f"consent row still says is_cloud={row['is_cloud']}"
    )


def test_C5_endpoint_reusing_the_ollama_id_inherits_local_status(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(conn, provider_id="ollama", label="remote",
                                    base_url=stub.url, model_name="m", is_local=False)
    print("consent row for 'ollama':", consent_row(conn, "ollama"))
    _ask(conn, "explain how a hash map works")
    assert stub.posts == [], "a non-local endpoint named 'ollama' passed the gate as local"


def test_C6_revoked_then_resaved_stays_revoked(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(conn, provider_id="remote-x", label="x",
                                    base_url=stub.url, model_name="m", is_local=False)
    server.api_grant_consent(conn, "remote-x", "full_inference")
    server.api_revoke_consent(conn, "remote-x")
    llm_endpoint_store.add_endpoint(conn, provider_id="remote-x", label="x2",
                                    base_url=stub.url, model_name="m", is_local=False)
    _ask(conn, "explain how a hash map works")
    assert stub.posts == []


def test_C7_wrong_scope_is_refused(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(conn, provider_id="remote-x", label="x",
                                    base_url=stub.url, model_name="m", is_local=False)
    server.api_grant_consent(conn, "remote-x", "web_search_only")
    _ask(conn, "explain how a hash map works")
    assert stub.posts == [], "web_search_only consent authorised full inference"


# ---------- web search ------------------------------------------------------

@pytest.fixture
def search_spy(monkeypatch):
    calls = []

    def fake(query, limit, timeout):
        calls.append(query)
        return [{"title": "t", "url": "https://e.example", "snippet": "s"}]

    monkeypatch.setattr(stage_06, "_duckduckgo_search", fake)
    if hasattr(stage_06, "_search_cache"):
        stage_06._search_cache.clear()
    return calls


def test_W1_fresh_install_web_search_not_called(conn, search_spy, ollama_down, stub):
    llm_endpoint_store.add_endpoint(conn, provider_id="loc", label="l",
                                    base_url=stub.url, model_name="m", is_local=True)
    print("web_search consent:", consent_row(conn, "web_search"))
    _ask(conn, "what is the latest news on rust today")
    assert search_spy == [], "web search ran without consent on a fresh install"


def test_W2_grant_then_revoke_web_search(conn, search_spy, ollama_down, stub):
    llm_endpoint_store.add_endpoint(conn, provider_id="loc", label="l",
                                    base_url=stub.url, model_name="m", is_local=True)
    server.api_grant_consent(conn, "web_search", "web_search_only")
    _ask(conn, "what is the latest news on rust today")
    assert len(search_spy) == 1
    server.api_revoke_consent(conn, "web_search")
    _ask(conn, "what is the latest news on python today")
    assert len(search_spy) == 1, "web search ran after revocation"


def test_W3_personal_question_triggers_search_payload(conn, search_spy, ollama_down, stub):
    """FREEZE §7.5 side note: what text reaches the search provider for a personal question?"""
    llm_endpoint_store.add_endpoint(conn, provider_id="loc", label="l",
                                    base_url=stub.url, model_name="m", is_local=True)
    server.api_grant_consent(conn, "web_search", "web_search_only")
    _ask(conn, "what is my current project right now")
    print("SEARCH QUERIES SENT:", search_spy)
