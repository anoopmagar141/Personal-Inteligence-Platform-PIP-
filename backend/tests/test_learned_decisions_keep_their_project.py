"""
A decision the Observer learns from a chat keeps that chat's project and the
chat it came from (BLUEPRINT C-14, issue #14 of the final plan, Promise 9).

What was wrong: the Observer was called without the chat's project (the end-
of-chat triggers passed only the chat's id; the startup queue and crash
recovery passed nothing), so route_observer_decision logged project_id NULL;
a decision queued to ask the user had no project column at all, so promoting
it wrote NULL too. Stage 3 searches a project chat's decisions with
`project_id = ?`, so a project never found a decision learned in its own
chats. And nothing recorded which chat a decision came from, which one record
per chat (#13) needs.

One source for "the chat's project": the conversation row, which the app
creates with the project it sends. These tests run the real Observer path
(Stage 11 to decision_log) with a provider that answers in the shape the
model does, and look at what was stored and what the next chat is shown.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.core import pipeline, response_cache, session_lifecycle
from backend.memory import conversation_store, decision_log, profile_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider

QUOTE = "We decided to use Postgres for the Lanternfish database because SQLite could not handle concurrent writes"
CHAT = [
    {"role": "user", "content": QUOTE + ", and we looked at MySQL too."},
    {"role": "assistant", "content": "Postgres it is, then."},
]


def _answer(signals):
    return json.dumps({
        "memory_candidates": [],
        "decision_candidates": [{
            "decision_text": "Use Postgres for the Lanternfish database",
            "signals_found": signals,
            "raw_quote": QUOTE,
        }],
        "session_snapshot": {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
    })


class _Model(BaseLLMProvider):
    """Answers like the model: one decision, with the signals given."""

    def __init__(self, signals=("commitment_language", "explicit_reasoning_in_conversation")):
        self.signals = list(signals)

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield _answer(self.signals)

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


class _Recorder(_Model):
    """The chat model for the NEXT chat: records the prompt it is given."""

    def __init__(self):
        super().__init__()
        self.prompts = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield "answer"


@pytest.fixture
async def executor_conn(tmp_path, db_key):
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


@pytest.fixture
def conn(tmp_path, db_key):
    c = get_connection(str(tmp_path / "plain.db"), db_key=db_key)
    initialize_schema(c)
    yield c
    c.close()


def _project_and_chat(conn, project_name="Lanternfish"):
    project_id = profile_store.create_project(conn, project_name, "Budgeting app for student hostels") if project_name else None
    chat_id = conversation_store.create_conversation(conn, project_id)
    for m in CHAT:
        conversation_store.append_message(conn, chat_id, m["role"], m["content"])
    return project_id, chat_id


def _logged(conn):
    return [dict(r) for r in conn.execute(
        "SELECT decision_text, project_id, conversation_id FROM decision_log WHERE state = 'active'")]


# --- the end of a chat (idle and disconnect triggers) -----------------------


@pytest.mark.asyncio
async def test_a_decision_learned_at_the_end_of_a_project_chat_keeps_its_project_and_chat(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    project_id, chat_id = await loop.run_in_executor(executor, _project_and_chat, conn)

    # Exactly what server.ws_chat's triggers pass: the chat's id, no project.
    await session_lifecycle.run_observer_now(loop, executor, conn, list(CHAT), _Model(), conversation_id=chat_id)

    logged = await loop.run_in_executor(executor, _logged, conn)
    assert [(d["project_id"], d["conversation_id"]) for d in logged] == [(project_id, chat_id)]


@pytest.mark.asyncio
async def test_the_next_chat_in_that_project_is_shown_the_decision(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    project_id, chat_id = await loop.run_in_executor(executor, _project_and_chat, conn)
    await session_lifecycle.run_observer_now(loop, executor, conn, list(CHAT), _Model(), conversation_id=chat_id)

    def next_chat():
        response_cache.clear()
        recorder = _Recorder()
        pipeline.run_sync(conn, "what did we decide about the database", project_id=project_id, providers=[recorder])
        response_cache.clear()
        return recorder.prompts[-1]

    prompt = await loop.run_in_executor(executor, next_chat)
    assert "Use Postgres for the Lanternfish database" in prompt


@pytest.mark.asyncio
async def test_a_chat_with_no_project_logs_its_decision_with_no_project(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    _, chat_id = await loop.run_in_executor(executor, _project_and_chat, conn, None)

    await session_lifecycle.run_observer_now(loop, executor, conn, list(CHAT), _Model(), conversation_id=chat_id)

    logged = await loop.run_in_executor(executor, _logged, conn)
    assert [(d["project_id"], d["conversation_id"]) for d in logged] == [(None, chat_id)]


# --- a decision queued to ask the user ---------------------------------------


@pytest.mark.asyncio
async def test_a_queued_decision_keeps_its_project_and_chat_when_promoted(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    project_id, chat_id = await loop.run_in_executor(executor, _project_and_chat, conn)

    # One signal is below the Observer's threshold: queued, not logged.
    await session_lifecycle.run_observer_now(
        loop, executor, conn, list(CHAT), _Model(signals=["commitment_language"]), conversation_id=chat_id)

    def promote():
        pending = decision_log.list_pending(conn)
        assert len(pending) == 1
        decision_log.promote_pending(conn, pending[0]["id"])
        return _logged(conn)

    logged = await loop.run_in_executor(executor, promote)
    assert [(d["project_id"], d["conversation_id"]) for d in logged] == [(project_id, chat_id)]


# --- the startup queue and crash recovery -----------------------------------


@pytest.mark.asyncio
async def test_a_transcript_queued_at_shutdown_keeps_its_project_and_chat(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()
    project_id, chat_id = await loop.run_in_executor(executor, _project_and_chat, conn)
    session = {
        "conn": conn, "executor": executor, "conversation_history": list(CHAT),
        "session_state": {"has_unobserved_turns": True, "observed_prefix": 0, "conversation_id": chat_id},
    }
    await session_lifecycle.enqueue_for_shutdown(loop, session)

    await loop.run_in_executor(executor, session_lifecycle.drain_pending_on_startup, conn, _Model())

    logged = await loop.run_in_executor(executor, _logged, conn)
    assert [(d["project_id"], d["conversation_id"]) for d in logged] == [(project_id, chat_id)]


def test_a_chat_recovered_after_a_crash_keeps_its_project_and_chat(conn):
    project_id, chat_id = _project_and_chat(conn)
    assert session_lifecycle.recover_unobserved_conversations(conn) == [chat_id]

    session_lifecycle.drain_pending_on_startup(conn, _Model())

    assert [(d["project_id"], d["conversation_id"]) for d in _logged(conn)] == [(project_id, chat_id)]


# --- an existing database -----------------------------------------------------


def test_an_old_queued_decision_is_kept_and_promotes_as_before(conn):
    # A database from before the columns: the queue row cannot say where it
    # came from, so it promotes with no project and no chat, as it always did.
    conn.execute("ALTER TABLE decision_candidates_pending DROP COLUMN project_id")
    conn.execute("ALTER TABLE decision_candidates_pending DROP COLUMN conversation_id")
    conn.execute("ALTER TABLE decision_log DROP COLUMN conversation_id")
    conn.execute(
        "INSERT INTO decision_candidates_pending (decision_text, signals_found, raw_quote, confidence, state, created_at) "
        "VALUES ('Use Postgres', '[\"commitment_language\"]', 'we use Postgres', 0.4, 'pending', '2026-10-01T00:00:00Z')"
    )
    conn.commit()

    added = profile_store.apply_column_migrations(conn)
    assert {"decision_candidates_pending.project_id", "decision_candidates_pending.conversation_id",
            "decision_log.conversation_id"} <= set(added)

    pending = decision_log.list_pending(conn)
    decision_log.promote_pending(conn, pending[0]["id"])
    assert [(d["project_id"], d["conversation_id"]) for d in _logged(conn)] == [(None, None)]
