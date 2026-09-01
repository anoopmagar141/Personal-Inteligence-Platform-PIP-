import time

import pytest

from backend.memory.profile_store import get_connection, initialize_schema
from backend.memory.session_snapshot import (
    SessionSnapshot,
    clear_snapshot,
    load_snapshot,
    write_snapshot,
)


@pytest.fixture
def conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    connection = get_connection(db_path, db_key=db_key)
    initialize_schema(connection)
    yield connection
    connection.close()


def _sample() -> SessionSnapshot:
    return {
        "topic": "pytest fixtures",
        "open_problems": ["need to test performance"],
        "last_decisions": ["use pytest fixtures for setup"],
        "suggested_next_step": "write the performance test",
        "snapshot_date": "2026-07-11T14:30:00Z",
    }


def test_load_and_write_success(conn):
    snapshot = _sample()
    write_snapshot(conn, snapshot)

    loaded = load_snapshot(conn)
    assert loaded == snapshot


def test_no_row_yet_fails_open(conn):
    # First-ever run: no session_snapshot row has been written yet.
    assert load_snapshot(conn) is None


def test_write_is_a_singleton_upsert(conn):
    # Security regression test: session_snapshot is now a DB table (singleton
    # row id=1), not a file that gets overwritten - confirms a second write
    # actually replaces the first row rather than erroring or duplicating it.
    write_snapshot(conn, _sample())
    second = _sample()
    second["topic"] = "a completely different topic"
    write_snapshot(conn, second)

    assert load_snapshot(conn)["topic"] == "a completely different topic"
    assert conn.execute("SELECT COUNT(*) FROM session_snapshot").fetchone()[0] == 1


def test_clear_returns_the_store_to_its_genuine_empty_state(conn):
    # A snapshot can be actively wrong rather than merely stale - one written
    # from a conversation in which PIP failed to recall anything will be handed
    # to every later session as established context. Clearing has to leave
    # load_snapshot() reading None, not a row of empty strings that merely
    # looks like none.
    write_snapshot(conn, _sample())

    assert clear_snapshot(conn) is True
    assert load_snapshot(conn) is None
    assert conn.execute("SELECT COUNT(*) FROM session_snapshot").fetchone()[0] == 0


def test_clear_reports_honestly_when_there_was_nothing_to_clear(conn):
    # False, so a caller can say "nothing to clear" rather than imply it undid
    # something. This is the whole reason clear_snapshot returns a bool.
    assert clear_snapshot(conn) is False


def test_writing_after_a_clear_starts_clean(conn):
    # The clear must not leave the singleton id in a state that blocks the next
    # upsert - the next real session has to be able to write normally.
    write_snapshot(conn, _sample())
    clear_snapshot(conn)

    fresh = _sample()
    fresh["topic"] = "what the next real session was actually about"
    write_snapshot(conn, fresh)

    assert load_snapshot(conn)["topic"] == "what the next real session was actually about"
    assert conn.execute("SELECT COUNT(*) FROM session_snapshot").fetchone()[0] == 1


def test_load_fails_open_on_unexpected_db_error():
    # sqlite3/sqlcipher3 Connection methods are read-only C-extension
    # attributes - can't monkeypatch .execute directly onto a real instance
    # (same workaround needed elsewhere in this suite, e.g. test_ws_chat.py's
    # ClosingTracker). A tiny stand-in object is enough here since
    # load_snapshot only ever calls conn.execute(...).fetchone().
    class BoomingConn:
        def execute(self, *args, **kwargs):
            raise RuntimeError("simulated DB error")

    assert load_snapshot(BoomingConn()) is None


def test_load_under_5ms(conn):
    # backend/config/settings.json performance_targets.snapshot_load_ms == 5.
    write_snapshot(conn, _sample())

    # Warm up.
    _ = load_snapshot(conn)

    start = time.perf_counter()
    _ = load_snapshot(conn)
    duration_ms = (time.perf_counter() - start) * 1000

    assert duration_ms < 5.0, f"Load took {duration_ms:.2f}ms, which exceeds 5ms budget"
