import os

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, trace
from backend.memory import vector_store


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


def _expect_session_info(ws) -> dict:
    # Sent once, immediately after every successful connect (conversation
    # history feature) - before the stage_hint -> token* -> done/error/stopped
    # sequence any of these tests actually care about. Every test below that
    # gets past the auth/origin checks needs to consume this first.
    event = ws.receive_json()
    assert event["type"] == "session_info"
    return event["data"]


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    # These tests were running against the real data/chroma directory - the
    # developer's own vector store - because this file never got the isolation
    # fixture test_api_server.py has. Nothing here queries RAG (pipeline.run is
    # faked throughout), but the app's startup path opens the store, so a test
    # run touched real data and two runs at once contended on the same SQLite
    # file underneath it. Same class of pollution bug this suite already fixed
    # for ChromaDB paths elsewhere; this file was simply missed.
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
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
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "hello"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for this message
        events = [ws.receive_json() for _ in range(4)]
    assert events[0]["type"] == "stage_hint"


def test_ws_chat_streams_events_and_hides_pipeline_complete(monkeypatch, token):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events("Hi there"))

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "hello"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for this message
        events = [ws.receive_json() for _ in range(4)]  # stage_hint + 2 tokens + done

    types = [e["type"] for e in events]
    assert types == ["stage_hint", "token", "token", "done"]
    assert "pipeline_complete" not in types  # internal sentinel never reaches the client


def test_ws_chat_missing_message_sends_error(monkeypatch, token):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
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
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "first"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for "first"
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


def test_disconnect_cleanup_never_wedges_the_server(monkeypatch, token):
    """
    What the disconnect path actually guarantees - which is not what this test
    used to assert.

    It used to wait for conn.close() to be observed. server.py bounds that call
    with asyncio.wait_for(..., timeout=5.0) and ABANDONS it on timeout,
    deliberately and with a comment saying so: a cleanup step must never hang
    the connection's handler, and the OS reclaiming the fd is an acceptable
    backstop for a local single-user app. So "the connection was closed" is not
    a promise this system makes, and asserting it fails whenever the machine is
    busy enough that the executor thread misses that 5s budget.

    Measured: the old assertion failed at 80s under a loaded suite, having
    passed in ~9s four times running on an idle one. Raising its timeout - which
    is what I tried first - cannot fix that, because the close may correctly
    never happen at all. The sibling test below had already reached the same
    conclusion for the after-activity case and asserts something else instead.

    What IS guaranteed is that the handler finishes and the server stays usable.
    That is the bug the 5s bound was added to prevent ("the bug this guards is
    the entire ASGI task wedging"), it is not covered anywhere else, and it is
    deterministic: if the disconnect had wedged the ASGI task or its executor,
    the second connection below would hang or fail instead of completing a turn.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    client = TestClient(server.app)

    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
        # Connect and drop without sending anything.

    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "still alive?"})
        assert ws.receive_json()["type"] == "session_info"
        assert ws.receive_json()["type"] == "stage_hint"


def test_ws_chat_connection_after_activity_reaches_disconnect_cleanup(monkeypatch, token):
    # What this test CAN'T verify and why: after a connection sends a real
    # message (any DB write happens - conversation history persistence),
    # disconnecting it reliably leaves conn.close() never observed to
    # complete within Starlette's TestClient, REGARDLESS of how it's
    # awaited - confirmed with asyncio.wait_for(..., timeout=5.0) around it
    # in server.py's finally: block (a real, permanent safeguard - it stops
    # a stuck close() from hanging the connection's own handler forever in
    # production), which still didn't let this specific test observe
    # completion within 30s+ of polling. That rules out "the await never
    # resolves due to my own code" - something in TestClient's WS-disconnect
    # bridging itself doesn't get a chance to run further work on this
    # connection's task once a write happened earlier in its life. Not
    # something reasonable to keep chasing from application code.
    #
    # What IS verified here instead: _session_registry.unregister() (an
    # asyncio.Lock-protected call, not an executor submission) DOES reliably
    # fire after disconnect even in this exact scenario - proving the
    # finally: block starts executing and makes real progress, just not
    # all the way through the conn.close() step, observably, in this harness.
    # The actual "does conn.close() eventually run in a real client" question
    # is covered by manual/live testing instead (confirmed working against a
    # real Edge session this session), not by an automated assertion here.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    calls = {"unregistered": None}
    real_unregister = server._session_registry.unregister

    async def tracking_unregister(session_id):
        calls["unregistered"] = session_id
        await real_unregister(session_id)

    monkeypatch.setattr(server._session_registry, "unregister", tracking_unregister)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "hello"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for this message
        for _ in range(4):
            ws.receive_json()

    import time
    deadline = time.monotonic() + 15.0
    while calls["unregistered"] is None and time.monotonic() < deadline:
        time.sleep(0.05)

    assert calls["unregistered"] is not None


def test_idle_timeout_triggers_observer_and_clears_history(monkeypatch, token):
    monkeypatch.setattr(server, "_idle_timeout_seconds", lambda: 0.05)
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    observer_calls = []

    async def fake_run_observer_now(
        loop, executor, conn, conversation_history, provider, project_id=None,
        conversation_id=None, observed_prefix=0,
    ):
        observer_calls.append((list(conversation_history), observed_prefix))
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "hello"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for this message
        for _ in range(4):
            ws.receive_json()

        # No further messages sent - the 0.05s idle timeout should fire and
        # trigger an Observer run without the client doing anything else.
        import time
        deadline = time.monotonic() + 2.0
        while not observer_calls and time.monotonic() < deadline:
            time.sleep(0.05)

    assert len(observer_calls) == 1
    history, observed_prefix = observer_calls[0]
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Hello there "},
    ]
    # A fresh connection was handed nothing, so every turn here is its own and
    # all of it counts as evidence.
    assert observed_prefix == 0


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

    async def fake_register(session_id, conn, executor, conversation_history, session_state=None):
        calls["registered"] = (session_id, conversation_history, session_state)

    async def fake_unregister(session_id):
        calls["unregistered"] = session_id

    monkeypatch.setattr(server._session_registry, "register", fake_register)
    monkeypatch.setattr(server._session_registry, "unregister", fake_unregister)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)  # conversation_id: null - fresh connection
        ws.send_json({"message": "hello"})
        _expect_session_info(ws)  # conversation_id: <real id> - lazily created for this message
        for _ in range(4):
            ws.receive_json()
        assert calls["registered"] is not None
        session_id, history_ref, state_ref = calls["registered"]
        assert state_ref is not None

        # The 4 received events end at "done", but ws_chat only appends to
        # conversation_history (and persists it to conversation_store) after
        # consuming the internal pipeline_complete sentinel that follows it -
        # never sent over the wire, so the client has no signal to wait for.
        # A polling deadline here flaked under full-suite load even at 10s
        # (client-visible events finishing doesn't mean the server's own
        # post-streaming bookkeeping has too) - deterministic instead: send a
        # second message and wait for ITS stage_hint. ws_chat()'s main loop
        # processes one turn fully, including this append, before looping
        # back to accept the next input, so seeing the second turn start
        # guarantees the first turn's append already happened.
        ws.send_json({"message": "second"})
        assert ws.receive_json()["type"] == "stage_hint"

        # Handed over by reference like the history is, and flipped by the same
        # append the sync above waits for. Shutdown reads it to tell a
        # connection that added turns from one that only had a past
        # conversation open on screen - the latter must not be re-observed.
        assert state_ref["has_unobserved_turns"] is True

        # The registry was handed the SAME list object ws_chat mutates, not a
        # copy - so it stays live-updated without ws_chat needing to re-register.
        #
        # A PREFIX, not equality. That same liveness is why: waiting for the
        # second turn's stage_hint proves the first turn's appends have landed,
        # but it does not stop the second turn landing its own. With a fake
        # pipeline that returns instantly, turn two can finish and append its
        # user message before this line runs - which is exactly how this failed
        # under a loaded machine, asserting two entries against a list that had
        # grown to three. The first two are fixed once turn one is done; what
        # follows them is a race with no winner worth picking.
        assert history_ref[:2] == [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "Hello there "},
        ]

    assert calls["unregistered"] == session_id


def test_lifespan_startup_clears_a_previous_runs_shutdown_flag(monkeypatch, tmp_path):
    """
    shutting_down gates the disconnect-time Observer run, and the registry is a
    module-level singleton. Setting it at shutdown without clearing it at
    startup made it a one-way latch for the life of the interpreter: after any
    lifespan had ended, every later disconnect skipped the Observer.

    One process serving one user never noticed - it runs a single lifespan and
    exits. The suite runs dozens in one interpreter, which is where it showed:
    a test asserting a disconnect triggers the Observer passed alone and failed
    inside its own file.
    """
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))

    server._session_registry.shutting_down = True  # as a previous lifespan left it

    with TestClient(server.app):
        assert server._session_registry.shutting_down is False

    # And set again on the way out, which is the half that always worked.
    assert server._session_registry.shutting_down is True


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
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            yield '{"memory_candidates": [], "decision_candidates": [], "session_snapshot": {}}'

        def get_model_info(self):
            return {"provider_id": "fake", "is_local": True, "model_name": "fake"}

    monkeypatch.setattr(server, "_default_observer_provider", lambda conn: FakeLocalProvider())

    with TestClient(server.app):  # __enter__ runs the lifespan startup phase
        pass

    conn = server.open_app_connection(db_path, None)
    try:
        assert pending_observer.list_pending(conn) == []  # drained on startup
    finally:
        conn.close()


def test_ws_chat_lazily_creates_conversation_on_first_message(monkeypatch, token, tmp_path):
    # See _resolve_connection_state's docstring / ws_chat()'s main loop: a
    # fresh connection (no ?conversation_id=...) gets conversation_id: null
    # in its first session_info, then a SECOND session_info with the real,
    # now-persisted id once an actual message triggers creation.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        first_info = _expect_session_info(ws)
        assert first_info["conversation_id"] is None
        assert first_info["messages"] == []

        ws.send_json({"message": "hello"})
        second_info = ws.receive_json()
        assert second_info["type"] == "session_info"
        assert second_info["data"]["conversation_id"] is not None
        conversation_id = second_info["data"]["conversation_id"]

        # The rest of the turn (stage_hint, token, token, done) still follows.
        for _ in range(4):
            ws.receive_json()

        # Send a second message and wait for its stage_hint before
        # disconnecting - ws_chat()'s main loop processes one turn fully
        # (including the first turn's post-streaming persist calls) before
        # looping back to accept the next one, so seeing the second turn
        # start guarantees the first turn's assistant message was already
        # persisted. Disconnecting right after receiving "done" instead (as
        # this test first tried) races the client's own disconnect against
        # the server's not-yet-run persist call - a correctness edge rather
        # than a fixable test-timing issue. (No second session_info here -
        # conversation_id is already set after the first turn, so the lazy-
        # create branch that sends one doesn't run again.)
        ws.send_json({"message": "second"})
        assert ws.receive_json()["type"] == "stage_hint"

    from backend.memory import conversation_store
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        messages = conversation_store.get_messages(conn, conversation_id)
        assert [(m["role"], m["content"]) for m in messages] == [
            ("user", "hello"),
            ("assistant", "Hello there "),
        ]
    finally:
        conn.close()


def test_ws_chat_resumes_a_known_conversation_id(monkeypatch, token, tmp_path):
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    from backend.memory import conversation_store
    seed_conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    conversation_id = conversation_store.create_conversation(seed_conn)
    conversation_store.append_message(seed_conn, conversation_id, "user", "earlier question")
    conversation_store.append_message(seed_conn, conversation_id, "assistant", "earlier answer")
    seed_conn.close()

    client = TestClient(server.app)
    with client.websocket_connect(f"/ws/chat?token={token}&conversation_id={conversation_id}") as ws:
        info = _expect_session_info(ws)
        assert info["conversation_id"] == conversation_id
        assert info["messages"] == [
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ]


def test_resuming_marks_the_carried_history_as_already_observed(monkeypatch, token, tmp_path):
    """
    The turns a resumed connection is HANDED must not be counted as evidence a
    second time - they were extracted from, under their own session number, on
    the day they were said. The Observer is still shown them (a resumed chat's
    closing turns rarely stand alone); observed_prefix is what tells it where
    this session's own contribution starts.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    from backend.memory import conversation_store
    seed_conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    conversation_id = conversation_store.create_conversation(seed_conn)
    conversation_store.append_message(seed_conn, conversation_id, "user", "said this last week")
    conversation_store.append_message(seed_conn, conversation_id, "assistant", "answered last week")
    seed_conn.close()

    observer_calls = []

    async def fake_run_observer_now(
        loop, executor, conn, conversation_history, provider, project_id=None,
        conversation_id=None, observed_prefix=0,
    ):
        observer_calls.append((list(conversation_history), observed_prefix))
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)

    # `with TestClient(...)`, not a bare TestClient: the disconnect-time
    # Observer is gated on _session_registry.shutting_down, which lifespan
    # STARTUP clears. Without the lifespan this test passes alone and fails
    # after any test that ran one - see the registry's flag for why that was a
    # real bug and not just a test-setup detail.
    with TestClient(server.app) as client, client.websocket_connect(
        f"/ws/chat?token={token}&conversation_id={conversation_id}"
    ) as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "and this is today"})
        for _ in range(4):
            ws.receive_json()
        # Sync on the next turn's first event, so the first turn's appends have
        # landed before the disconnect - same reasoning as the registry test.
        ws.send_json({"message": "second"})
        assert ws.receive_json()["type"] == "stage_hint"

    # The disconnect Observer runs in the handler's finally block, which the
    # `with` exiting only STARTS - polling is what the idle-timeout test above
    # does for the same reason. Asserting straight after the block passed this
    # test when run alone and failed it inside the file, which is the shape of
    # a race, not of a bug in what it is testing.
    import time
    deadline = time.monotonic() + 5.0
    while not observer_calls and time.monotonic() < deadline:
        time.sleep(0.02)

    assert len(observer_calls) == 1
    history, observed_prefix = observer_calls[0]
    assert observed_prefix == 2, "the two carried turns were not marked as already observed"
    # The whole transcript still goes to the Observer - the prefix says what
    # may COUNT, not what may be read.
    assert history[:2] == [
        {"role": "user", "content": "said this last week"},
        {"role": "assistant", "content": "answered last week"},
    ]
    assert len(history) > 2


def test_ws_chat_resuming_an_unknown_conversation_id_creates_a_new_one_lazily(monkeypatch, token):
    # A stale/deleted id shouldn't break the connection - it just falls back
    # to "not created yet" exactly like no id was given at all.
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    client = TestClient(server.app)
    with client.websocket_connect(f"/ws/chat?token={token}&conversation_id=does-not-exist") as ws:
        info = _expect_session_info(ws)
        assert info["conversation_id"] is None
        assert info["messages"] == []


# --- Session counting -------------------------------------------------------


def _session_count(tmp_path) -> int:
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        row = conn.execute("SELECT session_count FROM profile_meta WHERE id = 1").fetchone()
        return row["session_count"] if row else 0
    finally:
        conn.close()


def _onboard(tmp_path) -> None:
    from backend.memory import profile_store

    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    finally:
        conn.close()


def test_ws_chat_counts_one_session_per_connection(monkeypatch, token, tmp_path):
    """
    Two messages on one connection are one session, not two - and a second
    connection is a second session. profile_meta.session_count previously sat
    at whatever onboarding wrote and never moved.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    _onboard(tmp_path)
    assert _session_count(tmp_path) == 1

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "hello"})
        assert ws.receive_json()["type"] == "session_info"
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"message": "again"})
        assert ws.receive_json()["type"] == "stage_hint"

    assert _session_count(tmp_path) == 2

    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "new connection"})
        # Second session_info first: this connection is creating its own
        # conversation lazily, same as the one above did.
        assert ws.receive_json()["type"] == "session_info"
        assert ws.receive_json()["type"] == "stage_hint"

    assert _session_count(tmp_path) == 3


def test_ws_chat_does_not_count_a_connection_that_never_sends(monkeypatch, token, tmp_path):
    """
    A socket that opens and closes without a message produces no conversation
    and no Observer pass, so it is not a session.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    _onboard(tmp_path)

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)

    assert _session_count(tmp_path) == 1


def test_ws_chat_counts_a_resumed_conversation_as_a_new_session(monkeypatch, token, tmp_path):
    """
    Resuming skips the lazy-conversation-creation branch, so counting there
    would have missed it - but a resumed conversation is a fresh connection
    with its own Observer pass at the end of it.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())
    _onboard(tmp_path)

    from backend.memory import conversation_store

    seed_conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    conversation_id = conversation_store.create_conversation(seed_conn)
    conversation_store.append_message(seed_conn, conversation_id, "user", "earlier")
    seed_conn.close()

    client = TestClient(server.app)
    with client.websocket_connect(f"{ws_url(token)}&conversation_id={conversation_id}") as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "continuing"})
        assert ws.receive_json()["type"] == "stage_hint"

    assert _session_count(tmp_path) == 2


def test_verification_loop_fires_on_the_thirtieth_session(monkeypatch, token, tmp_path):
    """
    End to end through the real connection path, because this is where a
    periodic job dies: the loop can be perfectly correct and still never run if
    nothing calls it. Session 29 is set up directly so the connection under test
    is the 30th.
    """
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: _fake_pipeline_events())

    from backend.memory import profile_store
    from backend.stages import stage_13_profile_update as stage_13

    seed = server.open_app_connection(str(tmp_path / "pip.db"), None)
    profile_store.complete_onboarding(seed, name="BatMan", language_preference="English")
    seed.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('answer_style', 'terse', 1, 'inferred', 'active')"
    )
    seed.execute("UPDATE profile_meta SET session_count = 29 WHERE id = 1")
    seed.commit()
    seed.close()

    client = TestClient(server.app)
    with client.websocket_connect(ws_url(token)) as ws:
        _expect_session_info(ws)
        ws.send_json({"message": "hello"})
        assert ws.receive_json()["type"] == "session_info"
        assert ws.receive_json()["type"] == "stage_hint"

    check = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        assert check.execute("SELECT session_count FROM profile_meta WHERE id = 1").fetchone()[0] == 30
        pending = stage_13.list_pending(check)
        assert [p["field_name"] for p in pending] == ["answer_style"]
        assert pending[0]["origin"] == "verification"
    finally:
        check.close()


def test_proactive_route_reports_a_long_gap(monkeypatch, token, tmp_path):
    import datetime

    from backend.memory import profile_store

    seed = server.open_app_connection(str(tmp_path / "pip.db"), None)
    profile_store.complete_onboarding(seed, name="BatMan", language_preference="English")
    stamp = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=72)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    seed.execute("UPDATE profile_meta SET last_session_date = ? WHERE id = 1", (stamp,))
    seed.commit()
    seed.close()

    client = TestClient(server.app)
    response = client.get("/api/v1/proactive", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [t["trigger"] for t in response.json()] == ["session_gap_exceeds_48h"]
