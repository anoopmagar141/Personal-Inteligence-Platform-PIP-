import time

import pytest

from backend.memory.profile_store import get_connection, initialize_schema
from backend.memory import conversation_store
from backend.memory.session_snapshot import (
    SessionSnapshot,
    delete_chat_record,
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
    # First-ever run: no chat record has been written yet.
    assert load_snapshot(conn) is None


def test_a_chats_second_write_replaces_its_own_record(conn):
    # Since #13 a chat has one record: a second write for the same chat
    # replaces it rather than erroring or duplicating it (this test used to
    # pin the profile's single session_snapshot row the same way).
    chat = conversation_store.create_conversation(conn)
    write_snapshot(conn, _sample(), conversation_id=chat)
    second = _sample()
    second["topic"] = "a completely different topic"
    write_snapshot(conn, second, conversation_id=chat)

    assert load_snapshot(conn)["topic"] == "a completely different topic"
    assert conn.execute("SELECT COUNT(*) FROM chat_records").fetchone()[0] == 1


def test_two_chats_keep_two_records_and_the_newest_is_loaded(conn):
    first, second = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)
    write_snapshot(conn, _sample(), conversation_id=first)
    later = _sample()
    later["topic"] = "the later chat"
    later["snapshot_date"] = "2026-07-12T09:00:00Z"
    write_snapshot(conn, later, conversation_id=second)

    assert load_snapshot(conn)["topic"] == "the later chat"
    assert conn.execute("SELECT COUNT(*) FROM chat_records").fetchone()[0] == 2


def test_deleting_a_chats_record_leaves_the_others(conn):
    # A record can be actively wrong rather than merely stale, and it goes with
    # its chat. Removing one chat's record must leave every other chat's, where
    # the old clear_snapshot() removed the profile's only note (P-2).
    first, second = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)
    write_snapshot(conn, _sample(), conversation_id=first)
    later = _sample()
    later["topic"] = "the later chat"
    later["snapshot_date"] = "2026-07-12T09:00:00Z"
    write_snapshot(conn, later, conversation_id=second)

    assert delete_chat_record(conn, second) is True
    assert load_snapshot(conn)["topic"] == "pytest fixtures"


def test_deleting_reports_honestly_when_the_chat_had_no_record(conn):
    # False, so a caller can say "nothing to remove" rather than imply it undid
    # something.
    assert delete_chat_record(conn, conversation_store.create_conversation(conn)) is False


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
