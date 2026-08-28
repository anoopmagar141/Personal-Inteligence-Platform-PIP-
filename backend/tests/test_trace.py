import json
import uuid

from backend.core import trace


def test_generate_trace_id_returns_uuid4():
    trace_id = trace.generate_trace_id()

    parsed = uuid.UUID(trace_id, version=4)
    assert str(parsed) == trace_id


def test_stage_log_appends_valid_json(tmp_path):
    trace.TRACE_LOG_PATH = tmp_path / "trace_log.json"
    trace_id = trace.generate_trace_id()

    trace.stage_log(trace_id, "stage_01_intent_classifier", "ok", "Intent classified")
    trace.stage_log(trace_id, "stage_02_context_router", "ok", "Context routed")

    entries = trace.read_entries()
    assert len(entries) == 2
    assert entries[0]["trace_id"] == trace_id
    assert entries[0]["stage"] == "stage_01_intent_classifier"
    assert entries[0]["status"] == "ok"
    assert entries[1]["stage"] == "stage_02_context_router"


def test_mock_pipeline_run_produces_readable_full_trace(tmp_path):
    trace.TRACE_LOG_PATH = tmp_path / "trace_log.json"
    trace_id = trace.generate_trace_id()

    mock_pipeline = [
        ("stage_00_input", "ok", "User message accepted"),
        ("stage_01_intent_classifier", "ok", "Intent classified"),
        ("stage_07_response", "ok", "Response generated"),
    ]
    for stage, status, message in mock_pipeline:
        trace.stage_log(trace_id, stage, status, message)

    entries = trace.read_entries()
    readable_trace = "\n".join(
        f"{entry['stage']} [{entry['status']}]: {entry['message']}"
        for entry in entries
    )

    assert "stage_00_input [ok]: User message accepted" in readable_trace
    assert "stage_01_intent_classifier [ok]: Intent classified" in readable_trace
    assert "stage_07_response [ok]: Response generated" in readable_trace


# --- The log is appended to, bounded, concurrent-safe, and torn-line tolerant


def test_appending_never_rewrites_what_is_already_there(tmp_path, monkeypatch):
    # The old implementation read the whole file, re-serialized it and wrote it
    # all back on every entry - O(n) per call, O(n^2) per session, on the
    # response path. Byte-identical prefixes are what "appended" means, and the
    # cheapest thing to assert it with.
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.jsonl")
    trace_id = trace.generate_trace_id()

    trace.stage_log(trace_id, "stage_00", "ok", "first")
    prefix = trace.TRACE_LOG_PATH.read_bytes()

    for i in range(20):
        trace.stage_log(trace_id, f"stage_{i}", "ok", "later")

    assert trace.TRACE_LOG_PATH.read_bytes().startswith(prefix)
    assert len(trace.read_entries()) == 21


def test_a_torn_line_costs_one_entry_not_the_whole_log(tmp_path, monkeypatch):
    # The old `except JSONDecodeError: data = []` discarded every entry in the
    # log when one write went wrong - the entire debugging history, silently
    # thrown away by the code whose job was keeping it.
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.jsonl")
    trace_id = trace.generate_trace_id()

    trace.stage_log(trace_id, "stage_00", "ok", "before the tear")
    with open(trace.TRACE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write('{"trace_id": "half a line, no clos\n')
    trace.stage_log(trace_id, "stage_01", "ok", "after the tear")

    entries = trace.read_entries()
    assert [e["message"] for e in entries] == ["before the tear", "after the tear"]


def test_concurrent_writers_do_not_lose_or_corrupt_entries(tmp_path, monkeypatch):
    # Each WS connection runs its stages on its own executor thread, so two
    # connections log at the same time as a matter of course. The old
    # read/seek/dump/truncate cycle interleaved into a corrupt file.
    import threading

    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.jsonl")

    def writer(n: int) -> None:
        for i in range(25):
            trace.stage_log(f"trace-{n}", f"stage_{i}", "ok", f"worker {n} entry {i}")

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    entries = trace.read_entries()
    assert len(entries) == 8 * 25, "entries were lost to interleaved writes"
    # Every worker's entries all present and individually parseable.
    for n in range(8):
        assert sum(1 for e in entries if e["trace_id"] == f"trace-{n}") == 25


def test_the_log_is_rotated_once_it_passes_the_size_cap(tmp_path, monkeypatch):
    # Previously unbounded - nothing anywhere trimmed it, on a file written to
    # for every stage of every message forever.
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.jsonl")
    monkeypatch.setattr(trace, "MAX_TRACE_LOG_BYTES", 2000)
    trace_id = trace.generate_trace_id()

    for i in range(200):
        trace.stage_log(trace_id, f"stage_{i}", "ok", "x" * 100)

    rotated = tmp_path / "trace_log.jsonl.1"
    assert rotated.exists(), "the log grew past its cap without rotating"
    assert trace.TRACE_LOG_PATH.stat().st_size < 2000 + 500
    # Rotation must not stop the log working, and the live generation is what
    # read_entries reports.
    assert len(trace.read_entries()) > 0


def test_read_entries_is_empty_when_nothing_has_been_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "never_written.jsonl")
    assert trace.read_entries() == []
