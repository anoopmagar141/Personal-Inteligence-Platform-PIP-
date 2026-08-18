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

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30) -> Iterator[str]:
        yield '{"memory_candidates": [], "decision_candidates": [], "session_snapshot": {}}'

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": "fake", "is_local": self._is_local, "model_name": "fake"}


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
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
async def test_run_observer_now_calls_run_session_end(executor_conn, tmp_path):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    history = [{"role": "user", "content": "I prefer Neovim"}]
    result = await session_lifecycle.run_observer_now(
        loop, executor, conn, history, FakeProvider(),
        snapshot_path=str(tmp_path / "session_snapshot.json"),
    )
    assert "memory_results" in result
    assert "decision_results" in result


@pytest.mark.asyncio
async def test_run_observer_now_rejects_non_local_provider(executor_conn, tmp_path):
    conn, executor = executor_conn
    loop = asyncio.get_event_loop()

    with pytest.raises(session_lifecycle.observer.ObserverLocalProviderError):
        await session_lifecycle.run_observer_now(
            loop, executor, conn, [{"role": "user", "content": "hi"}], FakeProvider(is_local=False),
            snapshot_path=str(tmp_path / "session_snapshot.json"),
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


def test_drain_pending_on_startup_processes_existing_entries(db_conn, tmp_path):
    pending_observer.enqueue(db_conn, "User: left over from a shutdown\nAssistant: ok")

    result = session_lifecycle.drain_pending_on_startup(
        db_conn, FakeProvider(), snapshot_path=str(tmp_path / "session_snapshot.json")
    )

    assert len(result["completed"]) == 1
    assert result["failed"] == []
    assert pending_observer.list_pending(db_conn) == []
