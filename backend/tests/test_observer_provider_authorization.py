"""
Promise 5 (docs/FREEZE_LIST.md, Track 1): the Observer runs only against
providers recorded as local, and a session it cannot run on is kept for the
next launch rather than sent anywhere else.

Asserted on what leaves the process and what is left in the database, not on
the exception the gate raises. The provider is a real OpenAICompatibleProvider
pointed at a counting HTTP stub on 127.0.0.1 - a loopback address on purpose,
because locality is attested by the stored record and never inferred from the
hostname, and a stub on localhost is exactly the case a hostname check would
wave through.

Ollama is made unavailable by patching the provider class rather than by
hoping it is not running on the machine the suite happens to be on.

Where locality lives: llm_endpoints.is_local (what the provider object reports
about itself) and provider_consent.is_cloud (the operator record). Stage 11's
gate requires both to say local, so "marking the endpoint local" below sets
both - that is the configuration under which the Observer is meant to run.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.memory import llm_endpoint_store, vector_store
from backend.providers.ollama_provider import OllamaProvider

STUB_ID = "loopback-stub"

_EMPTY_EXTRACTION = json.dumps(
    {"memory_candidates": [], "decision_candidates": [], "session_snapshot": {}}
)


class _CountingStub:
    """An OpenAI-compatible server that records every request it receives."""

    def __init__(self):
        self.requests: list[tuple[str, str]] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                stub.requests.append(("GET", self.path))
                body = json.dumps({"data": [{"id": "stub-model"}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                stub.requests.append(("POST", self.path))
                chunk = {"choices": [{"delta": {"content": _EMPTY_EXTRACTION}}]}
                body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "pip.db")
    monkeypatch.setenv("PIP_DB_PATH", path)
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    return path


@pytest.fixture
def ollama_down(monkeypatch):
    ollama_calls = []

    def refuse_chat(self, *args, **kwargs):
        ollama_calls.append(self.host)
        raise AssertionError("Ollama was called although it is unavailable")
        yield  # pragma: no cover - makes this a generator like the real chat

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)
    monkeypatch.setattr(OllamaProvider, "chat", refuse_chat)
    return ollama_calls


@pytest.fixture
def stub():
    with _CountingStub() as s:
        yield s


def _connect(db_path):
    return server.open_app_connection(db_path, None)


def _register_stub(db_path, stub, *, is_local: bool) -> None:
    conn = _connect(db_path)
    try:
        llm_endpoint_store.add_endpoint(
            conn,
            provider_id=STUB_ID,
            label="Loopback stub",
            base_url=stub.base_url,
            model_name="stub-model",
            is_local=is_local,
        )
    finally:
        conn.close()


def _fake_pipeline_events(response_text="Noted."):
    # Generation is not under test; only the Observer's provider choice is.
    yield {"type": "stage_hint", "data": {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}}
    yield {"type": "token", "data": response_text}
    yield {"type": "done", "data": None}
    yield {"type": "pipeline_complete", "data": {"trace_id": "t1", "response_text": response_text, "status": "success", "stage_hints": {}}}


def _hold_one_session(monkeypatch, tmp_path) -> tuple[str, list[str]]:
    """
    One real WS session with a substantive user turn, ended by the idle
    timeout, which runs the real Observer path. Returns the conversation id.

    The idle trigger, not the disconnect: under TestClient the disconnect
    path's executor work is not reliably run once the connection has written
    to the database (see test_ws_chat's after-activity test). A first draft of
    this file used the disconnect, and it kept passing with the locality gate
    removed - the Observer was never reached, so zero requests proved nothing.

    run_observer_now is wrapped, not replaced, so the test can wait for the
    real call to finish and see how it ended. Returns (conversation id, one
    outcome per Observer attempt).
    """
    from backend.core import auth

    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    monkeypatch.setattr(server, "_idle_timeout_seconds", lambda: 0.2)

    outcomes: list[str] = []
    real_run_observer_now = server.session_lifecycle.run_observer_now

    async def observed_run_observer_now(*args, **kwargs):
        try:
            result = await real_run_observer_now(*args, **kwargs)
        except Exception as e:
            outcomes.append(type(e).__name__)
            raise
        outcomes.append("ran")
        return result

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", observed_run_observer_now)
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        assert ws.receive_json()["type"] == "session_info"
        ws.send_json({"message": "I've moved my thesis backend from Flask to FastAPI and I'm writing the tests in pytest now."})
        info = ws.receive_json()
        assert info["type"] == "session_info"
        conversation_id = info["data"]["conversation_id"]
        while ws.receive_json()["type"] != "done":
            pass

        deadline = time.monotonic() + 30.0
        while not outcomes and time.monotonic() < deadline:
            time.sleep(0.05)

    return conversation_id, outcomes


def _observed_at(db_path, conversation_id):
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT observed_at FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return row["observed_at"]
    finally:
        conn.close()


def _queue_statuses(db_path) -> list[str]:
    conn = _connect(db_path)
    try:
        return [r["status"] for r in conn.execute("SELECT status FROM pending_observer ORDER BY id")]
    finally:
        conn.close()


def _mark_stub_local(db_path) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE llm_endpoints SET is_local = 1 WHERE provider_id = ?", (STUB_ID,))
        conn.execute(
            "UPDATE provider_consent SET is_cloud = 0, user_consented = 1 WHERE provider_id = ?",
            (STUB_ID,),
        )
        conn.commit()
    finally:
        conn.close()


def _run_startup_catch_up(db_path, timeout=60.0) -> list[str]:
    """Starts the app's real lifespan and waits for its background catch-up to
    move every queued session out of 'pending'/'processing' or give up."""
    with TestClient(server.app):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            task = server._catch_up_task
            if task is not None and task.done():
                break
            time.sleep(0.1)
        else:
            pytest.fail("startup catch-up did not finish")
    return _queue_statuses(db_path)


def test_observer_never_calls_a_loopback_provider_recorded_as_not_local(
    db_path, tmp_path, monkeypatch, stub, ollama_down
):
    _register_stub(db_path, stub, is_local=False)

    conversation_id, outcomes = _hold_one_session(monkeypatch, tmp_path)

    assert stub.requests == []
    assert ollama_down == []
    # One Observer attempt, which reached the gate and was refused there - not
    # skipped, and not failed for some unrelated reason.
    assert outcomes == ["ObserverLocalProviderError"]
    # Pending-Observer: the conversation was not marked learned-from, so the
    # next start's recovery will find it.
    assert _observed_at(db_path, conversation_id) is None


def test_a_session_refused_for_locality_is_observed_at_the_next_start_once_the_provider_is_local(
    db_path, tmp_path, monkeypatch, stub, ollama_down
):
    _register_stub(db_path, stub, is_local=False)
    conversation_id, outcomes = _hold_one_session(monkeypatch, tmp_path)
    assert stub.requests == []
    assert outcomes == ["ObserverLocalProviderError"]
    assert _observed_at(db_path, conversation_id) is None

    _mark_stub_local(db_path)

    statuses = _run_startup_catch_up(db_path)

    assert _observed_at(db_path, conversation_id) is not None
    # Left the queue by being processed - 'failed' also leaves 'pending', and
    # observed_at alone is set by recovery before the Observer ever runs.
    assert statuses == ["completed"]
    assert [r for r in stub.requests if r[0] == "POST"] == [("POST", "/v1/chat/completions")]
    assert ollama_down == []


def test_a_session_refused_at_startup_for_locality_stays_queued_for_a_later_start(
    db_path, tmp_path, monkeypatch, stub, ollama_down
):
    """
    Promise 5's "queued for the next launch" held for exactly one launch
    (FREEZE_LIST §7.2 finding 1). Startup recovery marks the conversation
    observed as it queues it; the drain then got ObserverLocalProviderError,
    which it filed as 'failed' - terminal, never retried. So a session caught
    by a start with no local provider was never learned from, even after one
    was added. It must stay queued instead, still with nothing sent anywhere.
    """
    _register_stub(db_path, stub, is_local=False)
    conversation_id, outcomes = _hold_one_session(monkeypatch, tmp_path)
    assert outcomes == ["ObserverLocalProviderError"]

    first = _run_startup_catch_up(db_path)

    assert first != ["failed"], "a locality refusal at startup was filed as terminal"
    assert first == ["processing"], "the session did not stay queued"
    assert stub.requests == []

    _mark_stub_local(db_path)
    second = _run_startup_catch_up(db_path)

    assert second == ["completed"]
    assert [r for r in stub.requests if r[0] == "POST"] == [("POST", "/v1/chat/completions")]
    assert ollama_down == []
