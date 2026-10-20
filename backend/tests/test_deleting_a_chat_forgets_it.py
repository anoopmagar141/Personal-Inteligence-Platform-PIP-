"""
Deleting a chat removes what PIP kept from it for later (BLUEPRINT card P-2,
issue #2 of the final plan, Promise 9).

The "where we left off" note (session_snapshot) is one row per profile with no
link to the chat it summarised, and deleting a chat removed its messages only.
So the deleted chat's topic, decisions and open problems kept reaching every
new chat's first prompt until another chat ended and overwrote the note.

Two more ways the deleted chat came back, found while writing this card:

- The app deletes the open chat FIRST and then leaves it (chat_view.dart
  `_delete`: deleteConversation, then `_newChat()`), and leaving a chat ends its
  connection, which runs the end-of-chat Observer pass on that chat's turns. So
  the pass read a chat that no longer existed and wrote its note straight back,
  and learned from it.
- A chat open when the server stopped, or left by a killed process, waits in
  pending_observer as a transcript with nothing saying which chat it was. The
  next start's catch-up learned from it even if the chat had been deleted in
  between, and the transcript itself stayed in that table after the chat was
  gone.

The stop-gap: deleting a chat clears the note (whichever chat wrote it: the
note does not record that, so a note from another chat is cleared too, and the
next chat to end writes a fresh one), removes the chat's queued transcripts,
and the end-of-chat pass does not run for a chat that is gone. The real fix,
one record per chat that is deleted with it, is #13: the note below is now the
deleted chat's own record, as the end-of-chat pass writes it, and only that
record goes (backend/tests/test_chat_records.py holds the rest).
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, pipeline, response_cache, session_lifecycle
from backend.memory import conversation_store, profile_store, session_snapshot
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider

TOPIC = "Zephyr warehouse migration"
CHAT = [
    {"role": "user", "content": "Let's plan the Zephyr warehouse migration"},
    {"role": "assistant", "content": "Start with the inventory tables."},
]
NOTE = {
    "topic": TOPIC,
    "open_problems": ["Zephyr cutover window"],
    "last_decisions": ["Move Zephyr inventory first"],
    "suggested_next_step": "Draft the Zephyr cutover plan",
    "snapshot_date": "2026-10-17T09:00:00Z",
}


class _Recorder(BaseLLMProvider):
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield "answer"

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


def _seed_chat(conn) -> str:
    cid = conversation_store.create_conversation(conn)
    for message in CHAT:
        conversation_store.append_message(conn, cid, message["role"], message["content"])
    return cid


@pytest.fixture
def observer_calls(monkeypatch):
    """
    Stands in for Stage 11's session-end pass and does what it does to the
    note: records that it was handed a transcript, and writes the note from it.
    """
    calls: list[str] = []

    def fake_run_session_end(conn, transcript, provider, project_id=None, unobserved_transcript=None,
                         conversation_id=None):
        calls.append(transcript)
        session_snapshot.write_snapshot(conn, NOTE, conversation_id=conversation_id)
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(session_lifecycle.observer, "run_session_end", fake_run_session_end)
    return calls


# --- the note, through the real delete route ---------------------------------


def test_a_deleted_chats_note_does_not_reach_the_next_chat(tmp_path, monkeypatch):
    db_path = tmp_path / "pip.db"
    monkeypatch.setenv("PIP_DB_PATH", str(db_path))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    conn = server.open_app_connection(str(db_path), None)
    response_cache.clear()
    try:
        cid = _seed_chat(conn)
        session_snapshot.write_snapshot(conn, NOTE, conversation_id=cid)

        # Precondition: the note does reach a new chat's first message, so the
        # assertion below cannot pass because the prompt never carries it.
        before = _Recorder()
        pipeline.run_sync(conn, "good morning", providers=[before])
        assert TOPIC in before.prompts[-1]

        response = client.delete(f"/api/v1/conversations/{cid}", headers=headers)
        assert response.status_code == 200

        after = _Recorder()
        pipeline.run_sync(conn, "what should we work on?", providers=[after])
        assert "Zephyr" not in after.prompts[-1]
        assert session_snapshot.load_snapshot(conn) is None
    finally:
        response_cache.clear()
        conn.close()


# --- the end-of-chat pass on a chat that is gone -----------------------------


@pytest.fixture
async def executor_conn(tmp_path, db_key):
    # conn is opened on the executor's own thread, as ws_chat's is: SQLite
    # connections are pinned to the thread that made them.
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    def _open():
        c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
        initialize_schema(c)
        return c

    conn = await loop.run_in_executor(executor, _open)
    yield conn, executor
    await loop.run_in_executor(executor, conn.close)
    executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_the_end_of_chat_pass_does_not_run_on_a_deleted_chat(executor_conn, observer_calls):
    # The app's own order when the open chat is deleted: the delete lands, then
    # the connection ends and its trigger runs the pass with that chat's id.
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    cid = await loop.run_in_executor(executor, _seed_chat, conn)
    await loop.run_in_executor(executor, server.api_delete_conversation, conn, cid)

    await session_lifecycle.run_observer_now(
        loop, executor, conn, list(CHAT), _Recorder(), conversation_id=cid,
    )

    assert observer_calls == []
    assert await loop.run_in_executor(executor, session_snapshot.load_snapshot, conn) is None


@pytest.mark.asyncio
async def test_a_chat_deleted_while_its_pass_runs_leaves_no_note(executor_conn, monkeypatch):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    cid = await loop.run_in_executor(executor, _seed_chat, conn)

    def pass_that_outlives_its_chat(conn, transcript, provider, project_id=None, unobserved_transcript=None,
                         conversation_id=None):
        # The delete arrives during the pass, before the pass writes the note.
        # The real pass isolates its record write, which the missing chat
        # refuses (its foreign key); so does this one.
        server.api_delete_conversation(conn, cid)
        try:
            session_snapshot.write_snapshot(conn, NOTE, conversation_id=cid)
        except Exception:
            pass
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(session_lifecycle.observer, "run_session_end", pass_that_outlives_its_chat)

    await session_lifecycle.run_observer_now(
        loop, executor, conn, list(CHAT), _Recorder(), conversation_id=cid,
    )

    assert await loop.run_in_executor(executor, session_snapshot.load_snapshot, conn) is None


@pytest.mark.asyncio
async def test_a_chat_that_still_exists_is_observed_as_before(executor_conn, observer_calls):
    # Control: the check must not stop the pass for a chat nobody deleted.
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    cid = await loop.run_in_executor(executor, _seed_chat, conn)

    await session_lifecycle.run_observer_now(
        loop, executor, conn, list(CHAT), _Recorder(), conversation_id=cid,
    )

    assert len(observer_calls) == 1
    note = await loop.run_in_executor(executor, session_snapshot.load_snapshot, conn)
    assert note is not None and note["topic"] == TOPIC


# --- a transcript queued for the next start ----------------------------------


def _queued_texts(conn) -> list[str]:
    return [row["session_transcript"] for row in conn.execute("SELECT session_transcript FROM pending_observer")]


@pytest.mark.asyncio
async def test_a_transcript_queued_at_shutdown_is_not_learned_after_its_chat_is_deleted(
    executor_conn, observer_calls,
):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    deleted = await loop.run_in_executor(executor, _seed_chat, conn)
    kept = await loop.run_in_executor(executor, conversation_store.create_conversation, conn)
    kept_chat = [{"role": "user", "content": "Notes on the garden shed"}]

    for cid, history in ((deleted, list(CHAT)), (kept, kept_chat)):
        # The shape ws_chat registers a connection in (see server.ws_chat).
        session = {
            "conn": conn,
            "executor": executor,
            "conversation_history": history,
            "session_state": {"has_unobserved_turns": True, "observed_prefix": 0, "conversation_id": cid},
        }
        await session_lifecycle.enqueue_for_shutdown(loop, session)

    await loop.run_in_executor(executor, server.api_delete_conversation, conn, deleted)
    await loop.run_in_executor(executor, session_lifecycle.drain_pending_on_startup, conn, _Recorder())

    assert not any("Zephyr" in t for t in observer_calls), "the deleted chat was learned from"
    assert any("garden shed" in t for t in observer_calls), "the other chat's transcript was lost"
    texts = await loop.run_in_executor(executor, _queued_texts, conn)
    assert not any("Zephyr" in t for t in texts), "the deleted chat's text is still stored"


def test_a_transcript_recovered_after_a_crash_is_not_learned_after_its_chat_is_deleted(
    tmp_path, db_key, observer_calls,
):
    conn = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(conn)
    try:
        cid = _seed_chat(conn)
        assert session_lifecycle.recover_unobserved_conversations(conn) == [cid]

        server.api_delete_conversation(conn, cid)
        session_lifecycle.drain_pending_on_startup(conn, _Recorder())

        assert observer_calls == []
        assert not any("Zephyr" in t for t in _queued_texts(conn))
    finally:
        conn.close()


def test_the_chat_connection_tells_the_shutdown_path_which_chat_it_is(monkeypatch, tmp_path):
    # enqueue_for_shutdown reads the chat's id from the state ws_chat registers;
    # this pins that ws_chat puts it there once the first message creates the chat.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))
    token = auth.get_or_create_token(tmp_path / "api_token")

    def fake_pipeline(*args, **kwargs):
        yield {"type": "stage_hint", "data": {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}}
        yield {"type": "token", "data": "ok "}
        yield {"type": "done", "data": None}
        yield {"type": "pipeline_complete", "data": {"trace_id": "t1", "response_text": "ok ", "status": "success", "stage_hints": {}}}

    monkeypatch.setattr(server.pipeline, "run", fake_pipeline)
    captured = {}

    async def fake_register(session_id, conn, executor, conversation_history, session_state=None):
        captured["state"] = session_state

    async def fake_unregister(session_id):
        pass

    monkeypatch.setattr(server._session_registry, "register", fake_register)
    monkeypatch.setattr(server._session_registry, "unregister", fake_unregister)

    client = TestClient(server.app)
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        assert ws.receive_json()["type"] == "session_info"
        ws.send_json({"message": "hello"})
        created = ws.receive_json()
        assert created["type"] == "session_info"
        cid = created["data"]["conversation_id"]
        assert cid
        assert captured["state"].get("conversation_id") == cid
        while ws.receive_json()["type"] != "done":
            pass


# --- an existing database ----------------------------------------------------


def test_a_queue_from_before_the_chat_link_is_kept_and_still_drained(tmp_path, db_key, observer_calls):
    conn = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(conn)
    try:
        conn.execute("ALTER TABLE pending_observer DROP COLUMN conversation_id")
        # Written as an older PIP wrote it, with no chat to name.
        conn.execute(
            "INSERT INTO pending_observer (session_transcript, session_ended_at, status, created_at) "
            "VALUES ('User: queued by an older PIP\nAssistant: ok', '2026-10-01T00:00:00Z', 'pending', "
            "'2026-10-01T00:00:00Z')"
        )
        conn.commit()

        assert "pending_observer.conversation_id" in profile_store.apply_column_migrations(conn)
        session_lifecycle.drain_pending_on_startup(conn, _Recorder())

        assert observer_calls == ["User: queued by an older PIP\nAssistant: ok"]
    finally:
        conn.close()
