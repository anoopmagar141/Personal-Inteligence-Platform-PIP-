import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

import pytest

from backend.core import session_lifecycle, trace
from backend.memory import pending_observer
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider


@pytest.fixture(autouse=True)
def isolated_trace(tmp_path, monkeypatch):
    # run_observer_now() logs to trace_log.json (added after finding live that
    # Observer session-end runs had zero debugging visibility). Without this,
    # every test here writes into the real backend/logs/trace_log.json instead
    # of an isolated tmp_path - same class of test-pollution bug already found
    # and fixed for ChromaDB paths elsewhere in this suite.
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    yield


class FakeProvider(BaseLLMProvider):
    def __init__(self, is_local=True):
        self._is_local = is_local

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None) -> Iterator[str]:
        yield '{"memory_candidates": [], "decision_candidates": [], "session_snapshot": {}}'

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": "fake", "is_local": self._is_local, "model_name": "fake"}


def _seed_fake_provider_consent(conn) -> None:
    # stage_11's Rule 4 check now cross-verifies is_local against
    # provider_consent, not just get_model_info()'s self-report (security
    # fix) - FakeProvider's provider_id="fake" has no seed row in
    # config/provider_consent.json (only ollama/web_search do), so every test
    # that runs the real Observer flow through it needs one here.
    conn.execute(
        "INSERT INTO provider_consent (provider_id, is_cloud, user_consented, consent_scope, revoked) "
        "VALUES ('fake', 0, 1, 'full_inference', 0)"
    )
    conn.commit()


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    _seed_fake_provider_consent(conn)
    yield conn
    conn.close()


@pytest.fixture
async def executor_conn(tmp_path, db_key):
    """
    A (conn, executor) pair where conn is opened ON the executor's own worker
    thread - not the main test thread. sqlite3/sqlcipher3 connections can only
    be used on the thread that created them (the same production constraint
    documented in backend/api/server.py's WS thread-safety note); handing a
    main-thread-created connection to a *different* executor thread hits the
    exact same "SQLite objects created in a thread can only be used in that
    same thread" error the production code was fixed for.
    """
    db_path = str(tmp_path / "test.db")
    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    def _open():
        c = get_connection(db_path, db_key=db_key)
        initialize_schema(c)
        _seed_fake_provider_consent(c)
        return c

    conn = await loop.run_in_executor(executor, _open)
    yield conn, executor
    await loop.run_in_executor(executor, conn.close)
    executor.shutdown(wait=True)


def test_format_transcript_labels_roles():
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    assert session_lifecycle.format_transcript(history) == "User: hello\nAssistant: hi there"


def test_format_transcript_empty_history():
    assert session_lifecycle.format_transcript([]) == ""


@pytest.mark.asyncio
async def test_session_registry_register_and_unregister():
    registry = session_lifecycle.SessionRegistry()
    await registry.register(1, conn="conn1", executor="exec1", conversation_history=[])
    snapshot = await registry.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["conn"] == "conn1"

    await registry.unregister(1)
    assert await registry.snapshot() == []


@pytest.mark.asyncio
async def test_run_observer_now_calls_run_session_end(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    history = [{"role": "user", "content": "I prefer Neovim"}]
    result = await session_lifecycle.run_observer_now(loop, executor, conn, history, FakeProvider())
    assert "memory_results" in result
    assert "decision_results" in result


@pytest.mark.asyncio
async def test_run_observer_now_rejects_non_local_provider(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    with pytest.raises(session_lifecycle.observer.ObserverLocalProviderError):
        await session_lifecycle.run_observer_now(
            loop, executor, conn, [{"role": "user", "content": "hi"}], FakeProvider(is_local=False),
        )


@pytest.mark.asyncio
async def test_enqueue_for_shutdown_writes_to_pending_observer(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    session = {
        "conn": conn,
        "executor": executor,
        "conversation_history": [{"role": "user", "content": "unfinished business"}],
    }
    await session_lifecycle.enqueue_for_shutdown(loop, session)

    pending = await loop.run_in_executor(executor, pending_observer.list_pending, conn)
    assert len(pending) == 1
    assert "unfinished business" in pending[0]["session_transcript"]


@pytest.mark.asyncio
async def test_enqueue_for_shutdown_noop_on_empty_history(executor_conn):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    session = {"conn": conn, "executor": executor, "conversation_history": []}
    await session_lifecycle.enqueue_for_shutdown(loop, session)

    pending = await loop.run_in_executor(executor, pending_observer.list_pending, conn)
    assert pending == []


def test_drain_pending_on_startup_processes_existing_entries(db_conn):
    pending_observer.enqueue(db_conn, "User: left over from a shutdown\nAssistant: ok")

    result = session_lifecycle.drain_pending_on_startup(db_conn, FakeProvider())

    assert len(result["completed"]) == 1
    assert result["failed"] == []
    assert pending_observer.list_pending(db_conn) == []


# --- Recovery from an unclean shutdown (force-kill / crash / power loss) ---
#
# The third failure mode: a disconnect runs the Observer immediately and a
# clean shutdown persists to pending_observer, but a process killed outright
# runs neither, because both live in code that never executes.
# conversation_history dies with the process. Found live - a session was killed
# mid-test and the conversation sat in the sidebar looking normal while nothing
# had been learned from it.


@pytest.fixture
def conv_conn(tmp_path, db_key):
    conn = get_connection(str(tmp_path / "recover.db"), db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def _conversation_with_messages(conn, *, observed: bool = False) -> str:
    from backend.memory import conversation_store

    cid = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, cid, "user", "I've decided to use SQLCipher for storage")
    conversation_store.append_message(conn, cid, "assistant", "Noted.")
    if observed:
        conversation_store.mark_observed(conn, cid)
    return cid


def test_killed_session_is_recovered_and_queued(conv_conn):
    cid = _conversation_with_messages(conv_conn)

    recovered = session_lifecycle.recover_unobserved_conversations(conv_conn)

    assert recovered == [cid]
    queued = pending_observer.list_pending(conv_conn)
    assert len(queued) == 1
    # Transcript rebuilt from the committed messages, not from the memory that died.
    assert "I've decided to use SQLCipher for storage" in queued[0]["session_transcript"]
    assert queued[0]["session_transcript"].startswith("User:")


def test_already_observed_conversation_is_not_reprocessed(conv_conn):
    _conversation_with_messages(conv_conn, observed=True)
    assert session_lifecycle.recover_unobserved_conversations(conv_conn) == []
    assert pending_observer.list_pending(conv_conn) == []


def test_recovery_does_not_requeue_on_a_second_startup(conv_conn):
    # Marked at enqueue time, so a restart before the drain finishes does not
    # queue the same conversation again on every boot.
    _conversation_with_messages(conv_conn)
    first = session_lifecycle.recover_unobserved_conversations(conv_conn)
    second = session_lifecycle.recover_unobserved_conversations(conv_conn)
    assert len(first) == 1
    assert second == []
    assert len(pending_observer.list_pending(conv_conn)) == 1


def test_empty_conversation_is_not_queued(conv_conn):
    # A row created for a connection that disconnected before sending anything
    # has nothing to extract; queueing it would only burn an Observer pass.
    from backend.memory import conversation_store

    conversation_store.create_conversation(conv_conn)
    assert session_lifecycle.recover_unobserved_conversations(conv_conn) == []
    assert pending_observer.list_pending(conv_conn) == []


def test_recovered_transcript_is_drained_by_the_existing_startup_drain(conv_conn):
    # Recovery only enqueues - it deliberately reuses the queue the shutdown
    # path already fills rather than adding a second way to process a session.
    _conversation_with_messages(conv_conn)
    session_lifecycle.recover_unobserved_conversations(conv_conn)

    seen = []
    result = pending_observer.drain(conv_conn, lambda transcript: seen.append(transcript))

    assert len(result["completed"]) == 1
    assert result["failed"] == []
    assert "SQLCipher" in seen[0]


@pytest.mark.asyncio
async def test_successful_observer_run_marks_the_conversation_observed(executor_conn):
    loop = asyncio.get_event_loop()
    # conn is opened on the executor's worker thread and can only be used
    # there, so every touch of it goes through run_in_executor - the same
    # constraint the production WS handler works under.
    conn, executor = executor_conn
    cid = await loop.run_in_executor(executor, _conversation_with_messages, conn)

    await session_lifecycle.run_observer_now(
        loop, executor, conn,
        [{"role": "user", "content": "hello there friend"}],
        FakeProvider(), conversation_id=cid,
    )

    still_unobserved = await loop.run_in_executor(
        executor, session_lifecycle.recover_unobserved_conversations, conn
    )
    assert still_unobserved == []


@pytest.mark.asyncio
async def test_failed_observer_run_leaves_it_for_startup_recovery(executor_conn):
    # If extraction raised, the conversation genuinely has not been processed.
    # Marking it anyway would write the session off permanently - the opposite
    # of what this recovery path exists to prevent.
    loop = asyncio.get_event_loop()
    conn, executor = executor_conn
    cid = await loop.run_in_executor(executor, _conversation_with_messages, conn)

    class Exploding(FakeProvider):
        def chat(self, *a, **k):
            raise RuntimeError("model unavailable")
            yield  # pragma: no cover - generator marker

    with pytest.raises(Exception):
        await session_lifecycle.run_observer_now(
            loop, executor, conn,
            [{"role": "user", "content": "hello there friend"}],
            Exploding(), conversation_id=cid,
        )

    still_unobserved = await loop.run_in_executor(
        executor, session_lifecycle.recover_unobserved_conversations, conn
    )
    assert still_unobserved == [cid]


# --- Observation happens per SEGMENT, not per conversation -------------------
#
# observed_at could only say yes or no for a whole conversation. Two ordinary
# flows leave one marked observed while carrying turns that never were: an idle
# timeout runs the Observer and the same connection keeps taking turns, and
# resuming from the sidebar adds turns to a conversation a previous disconnect
# already marked. A kill in either state lost those turns silently - the same
# failure the recovery tests above exist for, narrowed to conversations that
# had been observed once already. conversations.observed_upto_message_id is the
# high-water mark that tells the two apart.


def test_only_the_turns_since_the_last_observer_pass_are_recovered(conv_conn):
    from backend.memory import conversation_store

    cid = _conversation_with_messages(conv_conn, observed=True)
    conversation_store.append_message(conv_conn, cid, "user", "and I've switched to Ollama for inference")
    conversation_store.append_message(conv_conn, cid, "assistant", "Understood.")

    recovered = session_lifecycle.recover_unobserved_conversations(conv_conn)

    assert recovered == [cid], "turns added after an Observer pass must still be recoverable"
    queued = pending_observer.list_pending(conv_conn)
    assert len(queued) == 1
    transcript = queued[0]["session_transcript"]
    assert "switched to Ollama" in transcript
    # The already-extracted turn must not be sent through the Observer twice -
    # that is a full ~130s pass to re-derive memory that already exists.
    assert "SQLCipher" not in transcript


def test_recovering_a_segment_advances_the_mark_rather_than_replaying_it(conv_conn):
    from backend.memory import conversation_store

    cid = _conversation_with_messages(conv_conn, observed=True)
    conversation_store.append_message(conv_conn, cid, "user", "one more thing")

    assert session_lifecycle.recover_unobserved_conversations(conv_conn) == [cid]
    assert session_lifecycle.recover_unobserved_conversations(conv_conn) == []
    assert len(pending_observer.list_pending(conv_conn)) == 1


def test_a_conversation_observed_before_the_high_water_mark_existed_is_left_alone(conv_conn):
    # The compatibility case: rows written before observed_upto_message_id
    # existed carry observed_at and nothing else. Reading them as fully
    # unobserved would queue every conversation in the history for
    # re-extraction on the first launch after the upgrade.
    cid = _conversation_with_messages(conv_conn, observed=True)
    conv_conn.execute(
        "UPDATE conversations SET observed_upto_message_id = NULL WHERE id = ?", (cid,)
    )
    conv_conn.commit()

    assert session_lifecycle.recover_unobserved_conversations(conv_conn) == []
    assert pending_observer.list_pending(conv_conn) == []


@pytest.mark.asyncio
async def test_shutdown_enqueues_only_the_unobserved_tail(executor_conn):
    # A resumed conversation replays its whole history into
    # conversation_history for LLM context. Only what came after the resume is
    # new evidence; persisting the replayed turns would re-extract them on the
    # next start.
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    session = {
        "conn": conn,
        "executor": executor,
        "conversation_history": [
            {"role": "user", "content": "replayed from the previous session"},
            {"role": "assistant", "content": "replayed reply"},
            {"role": "user", "content": "brand new this session"},
        ],
        "observed_upto_index": 2,
    }
    await session_lifecycle.enqueue_for_shutdown(loop, session)

    pending = await loop.run_in_executor(executor, pending_observer.list_pending, conn)
    assert len(pending) == 1
    assert "brand new this session" in pending[0]["session_transcript"]
    assert "replayed" not in pending[0]["session_transcript"]


@pytest.mark.asyncio
async def test_shutdown_of_a_fully_observed_session_enqueues_nothing(executor_conn):
    # Reopening a conversation and closing it again without saying anything.
    # The old code saw a non-empty conversation_history and queued the entire
    # replayed transcript for an Observer pass with no new evidence in it.
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    session = {
        "conn": conn,
        "executor": executor,
        "conversation_history": [
            {"role": "user", "content": "replayed from the previous session"},
            {"role": "assistant", "content": "replayed reply"},
        ],
        "observed_upto_index": 2,
    }
    await session_lifecycle.enqueue_for_shutdown(loop, session)

    pending = await loop.run_in_executor(executor, pending_observer.list_pending, conn)
    assert pending == []
