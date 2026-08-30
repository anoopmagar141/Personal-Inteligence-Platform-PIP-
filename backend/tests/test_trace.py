import datetime
import uuid

import pytest

from backend.core import trace
from backend.memory.profile_store import get_connection, initialize_schema


@pytest.fixture
def conn(tmp_path, db_key):
    connection = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(connection)
    yield connection
    connection.close()


def test_generate_trace_id_returns_uuid4():
    trace_id = trace.generate_trace_id()

    parsed = uuid.UUID(trace_id, version=4)
    assert str(parsed) == trace_id


def test_stage_log_writes_to_the_encrypted_database(conn):
    """
    Traces used to go to backend/logs/trace_log.json, in plaintext, outside the
    SQLCipher boundary everything else PIP records lives inside - which is why
    pipeline.py carries a security fix that had to stop recording message text.
    """
    trace_id = trace.generate_trace_id()

    trace.stage_log(conn, trace_id, "stage_01_intent_classifier", "ok", "Intent classified")
    trace.stage_log(conn, trace_id, "stage_02_router", "ok", "Context routed")

    entries = trace.get_trace(conn, trace_id)
    assert [e["stage"] for e in entries] == ["stage_01_intent_classifier", "stage_02_router"]
    assert entries[0]["trace_id"] == trace_id
    assert entries[0]["status"] == "ok"


def test_a_stage_can_log_more_than_once_in_one_trace(conn):
    """
    The table was originally keyed by (trace_id, stage), which cannot hold this
    - and the stages that log repeatedly are the error paths, so the trace would
    have lost events exactly where it was needed. stage_08 logs once per blocked
    provider, again for a blocked web search, and again if nothing consented
    remains.
    """
    trace_id = trace.generate_trace_id()

    trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", "ollama blocked")
    trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", "web_search blocked")
    trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", "no consented providers")

    entries = trace.get_trace(conn, trace_id)
    assert len(entries) == 3
    assert [e["message"] for e in entries] == [
        "ollama blocked",
        "web_search blocked",
        "no consented providers",
    ]


def test_entries_are_ordered_by_insertion_not_by_timestamp(conn):
    """
    now_utc() has second resolution and a whole pipeline run fits inside one
    second, so ordering on timestamp would tie and the stage order - the only
    thing that makes a trace readable - would come out arbitrary.
    """
    trace_id = trace.generate_trace_id()
    stages = [f"stage_{i:02d}" for i in range(12)]
    for stage in stages:
        trace.stage_log(conn, trace_id, stage, "ok", "done")

    assert [e["stage"] for e in trace.get_trace(conn, trace_id)] == stages


def test_traces_are_kept_separate(conn):
    first, second = trace.generate_trace_id(), trace.generate_trace_id()
    trace.stage_log(conn, first, "stage_01", "ok", "one")
    trace.stage_log(conn, second, "stage_01", "ok", "two")

    assert [e["message"] for e in trace.get_trace(conn, first)] == ["one"]
    assert [e["message"] for e in trace.get_trace(conn, second)] == ["two"]


def test_error_detail_is_recorded(conn):
    trace_id = trace.generate_trace_id()
    trace.stage_log(
        conn, trace_id, "stage_09_llm_streaming", "error", "status=error",
        error_detail="All providers failed: connection refused",
    )

    assert trace.get_trace(conn, trace_id)[0]["error_detail"] == "All providers failed: connection refused"


def test_stage_log_never_raises_on_a_broken_connection(conn):
    """
    A trace is a diagnostic aid. Taking down a user's response because the
    diagnostics could not be written would invert the priority entirely.
    """
    conn.close()
    trace.stage_log(conn, trace.generate_trace_id(), "stage_01", "ok", "after close")


def test_stage_log_without_a_connection_is_survivable(conn):
    trace.stage_log(None, trace.generate_trace_id(), "stage_01", "ok", "no conn")


def test_list_recent_traces_summarises_newest_first(conn):
    older, newer = trace.generate_trace_id(), trace.generate_trace_id()
    trace.stage_log(conn, older, "stage_01", "ok", "fine")
    trace.stage_log(conn, newer, "stage_01", "ok", "fine")
    trace.stage_log(conn, newer, "stage_09", "error", "broke", error_detail="boom")

    recent = trace.list_recent_traces(conn)
    assert [r["trace_id"] for r in recent] == [newer, older]
    assert recent[0]["entries"] == 2
    assert recent[0]["errors"] == 1
    assert recent[1]["errors"] == 0


def test_list_recent_traces_respects_the_limit(conn):
    for _ in range(5):
        trace.stage_log(conn, trace.generate_trace_id(), "stage_01", "ok", "fine")

    assert len(trace.list_recent_traces(conn, limit=3)) == 3


def test_get_trace_of_an_unknown_id_is_empty(conn):
    assert trace.get_trace(conn, "not-a-real-trace") == []


# --- retention (trace.hard_delete_after_days) -------------------------------
# The file this replaces had no retention at all: 90 was configured from the
# start and enforced by nothing, so the log only ever grew.


def _stamp(days_ago: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _insert_at(conn, trace_id: str, days_ago: int) -> None:
    conn.execute(
        "INSERT INTO trace_log (trace_id, timestamp, stage, status, message, error_detail) "
        "VALUES (?, ?, 'stage_01', 'ok', 'm', '')",
        (trace_id, _stamp(days_ago)),
    )
    conn.commit()


def test_purge_removes_only_entries_past_the_retention_window(conn):
    _insert_at(conn, "old", days_ago=120)
    _insert_at(conn, "recent", days_ago=30)

    assert trace.purge_old_entries(conn) == 1
    assert [r["trace_id"] for r in conn.execute("SELECT trace_id FROM trace_log")] == ["recent"]


def test_purge_is_idempotent(conn):
    _insert_at(conn, "old", days_ago=120)

    assert trace.purge_old_entries(conn) == 1
    assert trace.purge_old_entries(conn) == 0


def test_purge_never_raises_on_a_broken_connection(conn):
    conn.close()
    assert trace.purge_old_entries(conn) == 0
