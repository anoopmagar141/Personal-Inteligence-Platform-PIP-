import os

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, trace


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)  # plain sqlite for tests, no key needed
    yield


@pytest.fixture(autouse=True)
def token(tmp_path, monkeypatch):
    # The WS route now requires ?token=... on every connection (security
    # fix - it used to accept any connection at all). isolated per test, same
    # pattern as PIP_DB_PATH.
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))
    return auth.get_or_create_token(tmp_path / "api_token")


def ws_url(token: str) -> str:
    return f"/ws/chat?token={token}"


@pytest.fixture(autouse=True)
def isolated_trace(tmp_path, monkeypatch):
    # Real disconnect/idle-timeout paths now log to trace_log.json via
    # session_lifecycle.run_observer_now(). Without this, tests here would
    # write into the real backend/logs/trace_log.json instead of an isolated
    # tmp_path - same class of pollution bug already found for ChromaDB paths.
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    yield


@pytest.fixture(autouse=True)
def no_real_observer_calls(monkeypatch):
    # Every message sent in these tests leaves conversation_history non-empty,
    # which now triggers a disconnect-time Observer run (session_lifecycle
    # wiring). Without this, every test here would make a real network call to
    # Ollama (up to a 180s timeout if it's unreachable) in the background during
    # teardown - session_lifecycle itself already has its own dedicated,
    # properly-isolated tests; this file is about the WS route, not Observer.
    async def fake_run_observer_now(*args, **kwargs):
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)
    yield


def _fake_pipeline_events(response_text="Hello there"):
    yield {"type": "stage_hint", "data": {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}}
    for word in response_text.split():
        yield {"type": "token", "data": word + " "}
    yield {"type": "done", "data": None}
    yield {"type": "pipeline_complete", "data": {"trace_id": "t1", "response_text": response_text + " ", "status": "success", "stage_hints": {}}}


def test_ws_chat_rejects_connection_without_token(monkeypatch):
    # Security regression test: /ws/chat used to accept any connection at
    # all - no auth on either transport.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    client = TestClient(server.app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/chat"):
            pass


def test_ws_chat_rejects_connection_with_wrong_token(monkeypatch):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    client = TestClient(server.app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/chat?token=wrong-token"):
            pass


def test_ws_chat_rejects_mismatched_origin_even_with_a_valid_token(monkeypatch, token):
    # Defense in depth alongside the token: CORSMiddleware never covers the WS
    # upgrade at all (HTTP-only in Starlette), so there was no origin check
    # here whatsoever before this fix - a leaked token would otherwise still
    # work from anywhere.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    client = TestClient(server.app)
    with pytest.raises(Exception):
        with client.websocket_connect(ws_url(token), headers={"origin": "http://evil.example.com"}):
            pass


def test_ws_chat_accepts_connection_with_no_origin_header(monkeypatch, token):
    # Non-browser clients (a raw WebSocketChannel, tool/validate_live.dart)
    # generally don't send an Origin header at all - only a present-but-
    # mismatched Origin should be rejected, not a missing one.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "hello"})
        events = [ws.receive_json() for _ in range(4)]
    assert events[0]["type"] == "stage_hint"


def test_ws_chat_streams_events_and_hides_pipeline_complete(monkeypatch, token):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events("Hi there"))

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "hello"})
        events = [ws.receive_json() for _ in range(4)]  # stage_hint + 2 tokens + done

    types = [e["type"] for e in events]
    assert types == ["stage_hint", "token", "token", "done"]
    assert "pipeline_complete" not in types  # internal sentinel never reaches the client


def test_ws_chat_missing_message_sends_error(monkeypatch, token):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({})
        event = ws.receive_json()
        assert event == {"type": "error", "data": "message is required"}


def test_ws_chat_accumulates_conversation_history_across_turns(monkeypatch, token):
    captured_history = []

    def fake_run(conn, user_message, *, conversation_history=None, project_id=None, **kw):
        captured_history.append(list(conversation_history or []))
        return _fake_pipeline_events(f"reply to {user_message}")

    monkeypatch.setattr(server.pipeline, "run", fake_run)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "first"})
        for _ in range(4):
            ws.receive_json()

        ws.send_json({"message": "second"})
        for _ in range(4):
            ws.receive_json()

    # First call: no prior history.
    assert captured_history[0] == []
    # Second call: history has the first user turn + first assistant reply, but
    # NOT the current ("second") message - stage_07 appends that itself.
    assert captured_history[1] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply to first "},
    ]
    assert not any(m["content"] == "second" for m in captured_history[1])


def test_ws_chat_connection_closes_db_on_disconnect(monkeypatch, token):
    # sqlite3.Connection's methods are read-only C-extension attributes - can't
    # monkeypatch .close directly onto the instance. Wrap it in a delegating proxy
    # instead, same workaround needed for sqlcipher3.dbapi2.Connection elsewhere
    # in this test suite.
    closed = {"value": False}

    class ClosingTracker:
        def __init__(self, real_conn):
            self._real = real_conn

        def close(self):
            closed["value"] = True
            self._real.close()

        def __getattr__(self, name):
            return getattr(self._real, name)

    real_conn_fn = server.open_app_connection

    def tracking_conn(*args, **kwargs):
        return ClosingTracker(real_conn_fn(*args, **kwargs))

    monkeypatch.setattr(server, "open_app_connection", tracking_conn)
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "hello"})
        for _ in range(4):
            ws.receive_json()

    # The client-side socket closing doesn't guarantee the server's finally:
    # block (an async task reacting to the disconnect) has run yet - under load
    # (e.g. the full suite vs. this test in isolation) that race is real, not
    # hypothetical: this assertion flaked when the full suite ran concurrently.
    # Poll briefly instead of asserting immediately.
    import time
    deadline = time.monotonic() + 2.0
    while not closed["value"] and time.monotonic() < deadline:
        time.sleep(0.05)

    assert closed["value"] is True


def test_idle_timeout_triggers_observer_and_clears_history(monkeypatch, token):
    monkeypatch.setattr(server, "_idle_timeout_seconds", lambda: 0.05)
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    observer_calls = []

    async def fake_run_observer_now(loop, executor, conn, conversation_history, provider, project_id=None):
        observer_calls.append(list(conversation_history))
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "hello"})
        for _ in range(4):
            ws.receive_json()

        # No further messages sent - the 0.05s idle timeout should fire and
        # trigger an Observer run without the client doing anything else.
        import time
        deadline = time.monotonic() + 2.0
        while not observer_calls and time.monotonic() < deadline:
            time.sleep(0.05)

    assert len(observer_calls) == 1
    assert observer_calls[0] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hello there "},
    ]


def test_ws_chat_registers_and_unregisters_with_session_registry(monkeypatch, token):
    # session_lifecycle.SessionRegistry's own mechanics (register/unregister/
    # snapshot, enqueue_for_shutdown) are covered in isolation by
    # test_session_lifecycle.py. What's specific to the WS route is that
    # ws_chat actually calls register() on connect and unregister() on
    # disconnect with a conversation_history that stays in sync - verified here
    # by capturing the calls rather than crossing into the live server's event
    # loop from sync test code (TestClient runs the app on its own loop; a
    # SessionRegistry's asyncio.Lock is bound to whichever loop first awaits
    # it, so reaching in from a separate loop created in the test body is a
    # real asyncio pitfall, not just extra ceremony).
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    calls = {"registered": None, "unregistered": None}

    async def fake_register(session_id, conn, executor, conversation_history):
        calls["registered"] = (session_id, conversation_history)

    async def fake_unregister(session_id):
        calls["unregistered"] = session_id

    monkeypatch.setattr(server._session_registry, "register", fake_register)
    monkeypatch.setattr(server._session_registry, "unregister", fake_unregister)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.send_json({"message": "hello"})
        for _ in range(4):
            ws.receive_json()
        assert calls["registered"] is not None
        session_id, history_ref = calls["registered"]

        # The 4 received events end at "done", but ws_chat only appends to
        # conversation_history after consuming the internal pipeline_complete
        # sentinel that follows it - which is never sent over the wire, so the
        # client has no signal to wait for. Poll briefly rather than assert
        # immediately (same class of race as the disconnect-close test above).
        import time
        deadline = time.monotonic() + 2.0
        while not history_ref and time.monotonic() < deadline:
            time.sleep(0.05)

        # The registry was handed the SAME list object ws_chat mutates, not a
        # copy - so it stays live-updated without ws_chat needing to re-register.
        assert history_ref == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hello there "},
        ]

    assert calls["unregistered"] == session_id


def test_app_startup_drains_pending_observer(monkeypatch, tmp_path):
    from backend.memory import pending_observer

    db_path = str(tmp_path / "pip.db")
    monkeypatch.setenv("PIP_DB_PATH", db_path)
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    # Lifespan startup now also touches auth.get_or_create_token() - without
    # this, TestClient's __enter__ below would read/write the real production
    # data/api_token as a side effect of this test.
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))

    # Seed a leftover pending_observer row (as if a previous shutdown enqueued
    # it) BEFORE the app starts, and patch the observer provider so startup
    # drain doesn't make a real Ollama call. FakeLocalProvider's provider_id
    # "fake" also needs a provider_consent row now - stage_11's Rule 4 check
    # cross-verifies is_local against it, not just the provider's own
    # get_model_info() claim (security fix); without this row the drain would
    # fail via ObserverLocalProviderError, which list_pending()=='' can't tell
    # apart from a real successful drain (both remove the row from 'pending').
    seed_conn = server.open_app_connection(db_path, None)
    pending_observer.enqueue(seed_conn, "User: left over from last time\nAssistant: ok")
    seed_conn.execute(
        "INSERT INTO provider_consent (provider_id, is_cloud, user_consented, consent_scope, revoked) "
        "VALUES ('fake', 0, 1, 'full_inference', 0)"
    )
    seed_conn.commit()
    seed_conn.close()

    class FakeLocalProvider:
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30):
            yield '{"memory_candidates": [], "decision_candidates": [], "session_snapshot": {}}'

        def get_model_info(self):
            return {"provider_id": "fake", "is_local": True, "model_name": "fake"}

    monkeypatch.setattr(server, "_default_observer_provider", lambda: FakeLocalProvider())

    with TestClient(server.app):  # __enter__ runs the lifespan startup phase
        pass

    conn = server.open_app_connection(db_path, None)
    try:
        assert pending_observer.list_pending(conn) == []  # drained on startup
    finally:
        conn.close()
