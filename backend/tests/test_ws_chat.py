import pytest
from fastapi.testclient import TestClient

from backend.api import server


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)  # plain sqlite for tests, no key needed
    yield


def _fake_pipeline_events(response_text="Hello there"):
    yield {"type": "stage_hint", "data": {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}}
    for word in response_text.split():
        yield {"type": "token", "data": word + " "}
    yield {"type": "done", "data": None}
    yield {"type": "pipeline_complete", "data": {"trace_id": "t1", "response_text": response_text + " ", "status": "success", "stage_hints": {}}}


def test_ws_chat_streams_events_and_hides_pipeline_complete(monkeypatch):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events("Hi there"))

    client = TestClient(server.app)
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({"message": "hello"})
        events = [ws.receive_json() for _ in range(4)]  # stage_hint + 2 tokens + done

    types = [e["type"] for e in events]
    assert types == ["stage_hint", "token", "token", "done"]
    assert "pipeline_complete" not in types  # internal sentinel never reaches the client


def test_ws_chat_missing_message_sends_error(monkeypatch):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect("/ws/chat") as ws:
        ws.send_json({})
        event = ws.receive_json()
        assert event == {"type": "error", "data": "message is required"}


def test_ws_chat_accumulates_conversation_history_across_turns(monkeypatch):
    captured_history = []

    def fake_run(conn, user_message, *, conversation_history=None, project_id=None, **kw):
        captured_history.append(list(conversation_history or []))
        return _fake_pipeline_events(f"reply to {user_message}")

    monkeypatch.setattr(server.pipeline, "run", fake_run)

    client = TestClient(server.app)
    with client.websocket_connect("/ws/chat") as ws:
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


def test_ws_chat_connection_closes_db_on_disconnect(monkeypatch):
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
    with client.websocket_connect("/ws/chat") as ws:
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
