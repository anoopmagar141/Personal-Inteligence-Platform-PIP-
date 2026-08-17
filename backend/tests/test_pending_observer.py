import pytest
from backend.memory import pending_observer
from backend.memory.profile_store import get_connection, initialize_schema


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def test_enqueue_creates_pending_row(db_conn):
    entry_id = pending_observer.enqueue(db_conn, "user: hello\nassistant: hi")
    row = db_conn.execute("SELECT * FROM pending_observer WHERE id = ?", (entry_id,)).fetchone()
    assert row["status"] == "pending"
    assert row["session_transcript"] == "user: hello\nassistant: hi"
    assert row["session_ended_at"] is not None
    assert row["created_at"] is not None


def test_list_pending_orders_oldest_first(db_conn):
    id1 = pending_observer.enqueue(db_conn, "first", session_ended_at="2026-01-01T00:00:00Z")
    id2 = pending_observer.enqueue(db_conn, "second", session_ended_at="2026-01-02T00:00:00Z")
    pending = pending_observer.list_pending(db_conn)
    assert [p["id"] for p in pending] == [id1, id2]


def test_list_pending_excludes_non_pending(db_conn):
    entry_id = pending_observer.enqueue(db_conn, "transcript")
    pending_observer.mark_completed(db_conn, entry_id)
    assert pending_observer.list_pending(db_conn) == []


def test_drain_processes_all_pending_and_marks_completed(db_conn):
    pending_observer.enqueue(db_conn, "session A")
    pending_observer.enqueue(db_conn, "session B")

    processed = []
    result = pending_observer.drain(db_conn, lambda transcript: processed.append(transcript))

    assert processed == ["session A", "session B"]
    assert len(result["completed"]) == 2
    assert result["failed"] == []
    assert pending_observer.list_pending(db_conn) == []

    statuses = [r["status"] for r in db_conn.execute("SELECT status FROM pending_observer")]
    assert statuses == ["completed", "completed"]


def test_drain_one_failure_does_not_block_the_rest(db_conn):
    pending_observer.enqueue(db_conn, "good session")
    pending_observer.enqueue(db_conn, "bad session")
    pending_observer.enqueue(db_conn, "another good session")

    def runner(transcript):
        if transcript == "bad session":
            raise RuntimeError("simulated extraction failure")

    result = pending_observer.drain(db_conn, runner)

    assert len(result["completed"]) == 2
    assert len(result["failed"]) == 1
    assert result["failed"][0]["error"] == "simulated extraction failure"

    failed_row = db_conn.execute(
        "SELECT status, error_detail FROM pending_observer WHERE session_transcript = 'bad session'"
    ).fetchone()
    assert failed_row["status"] == "failed"
    assert failed_row["error_detail"] == "simulated extraction failure"


def test_drain_retries_stale_processing_rows_from_a_crashed_drain(db_conn):
    entry_id = pending_observer.enqueue(db_conn, "interrupted session")
    # Simulate a previous drain() that crashed mid-run: marked processing, never
    # reached completed/failed.
    pending_observer.mark_processing(db_conn, entry_id)
    assert pending_observer.list_pending(db_conn) == []  # not visible via list_pending

    processed = []
    result = pending_observer.drain(db_conn, lambda t: processed.append(t))

    assert processed == ["interrupted session"]
    assert result["completed"] == [entry_id]


def test_failed_entries_are_never_hard_deleted(db_conn):
    pending_observer.enqueue(db_conn, "will fail")

    def always_fails(transcript):
        raise ValueError("boom")

    pending_observer.drain(db_conn, always_fails)
    assert db_conn.execute("SELECT COUNT(*) FROM pending_observer").fetchone()[0] == 1
    row = db_conn.execute("SELECT status FROM pending_observer").fetchone()
    assert row["status"] == "failed"


def test_drain_with_nothing_pending_is_a_noop(db_conn):
    result = pending_observer.drain(db_conn, lambda t: (_ for _ in ()).throw(AssertionError("should not run")))
    assert result == {"completed": [], "failed": []}
