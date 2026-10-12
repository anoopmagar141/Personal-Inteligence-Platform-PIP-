"""
B-2: Per-stage timing in the trace tests.

Promise: every trace_log row written by a pipeline run carries duration_ms
(the time that stage took), so slow stages are visible after the fact.
"""

import sqlite3
import time
import pytest
from backend.core import pipeline, trace, response_cache
from backend.api import server
from backend.memory import profile_store, vector_store
from backend.providers.ollama_provider import OllamaProvider


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    response_cache.clear()
    yield
    response_cache.clear()


@pytest.fixture
def local_ollama(monkeypatch):
    """Local Ollama provider stub."""
    def answer(self, messages, *args, **kwargs):
        yield "STUB_RESPONSE"

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "chat", answer)


def test_pipeline_trace_rows_carry_duration_ms(conn, local_ollama):
    """
    Assert that every trace_log row emitted by a pipeline run carries a non-null
    duration_ms integer >= 0.
    """
    res = pipeline.run_sync(conn, "What is quantum computing?")
    trace_id = res["trace_id"]

    rows = trace.get_trace(conn, trace_id)
    assert len(rows) > 0

    for row in rows:
        assert "duration_ms" in row, f"Missing duration_ms in row: {row}"
        assert row["duration_ms"] is not None, f"duration_ms is None in row: {row}"
        assert isinstance(row["duration_ms"], int)
        assert row["duration_ms"] >= 0


def test_slow_stage_duration_break_it(conn, local_ollama, monkeypatch):
    """
    Break-it / accuracy test: Monkeypatch a stage to sleep for 50 ms and assert
    its trace_log row duration_ms >= 50.
    """
    from backend.stages import stage_04_memory_lookup as stage_04

    original_run = stage_04.run

    def slow_run(*args, **kwargs):
        time.sleep(0.05)  # 50 ms
        return original_run(*args, **kwargs)

    monkeypatch.setattr(stage_04, "run", slow_run)

    res = pipeline.run_sync(conn, "Hello memory test")
    trace_id = res["trace_id"]

    rows = trace.get_trace(conn, trace_id)
    mem_rows = [r for r in rows if r["stage"] == "stage_04_memory_lookup"]

    assert len(mem_rows) == 1
    assert mem_rows[0]["duration_ms"] >= 50, f"Expected duration_ms >= 50 for 50ms sleep, got: {mem_rows[0]['duration_ms']}"


def test_list_recent_traces_returns_total_duration(conn, local_ollama):
    """
    list_recent_traces returns total_duration_ms for each trace summary.
    """
    res = pipeline.run_sync(conn, "Summary test")
    summaries = trace.list_recent_traces(conn, limit=1)

    assert len(summaries) == 1
    assert "total_duration_ms" in summaries[0]
    assert summaries[0]["total_duration_ms"] is not None
    assert summaries[0]["total_duration_ms"] >= 0


def test_legacy_trace_table_migration_keeps_duration_column():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE trace_log (
            trace_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            error_detail TEXT,
            PRIMARY KEY (trace_id, stage)
        )
        """
    )
    connection.execute(
        "INSERT INTO trace_log VALUES (?, ?, ?, ?, ?, ?)",
        ("old-trace", "2026-10-01", "stage_00", "ok", "old row", ""),
    )

    profile_store.initialize_schema(connection)

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(trace_log)")}
    assert "duration_ms" in columns
    assert connection.execute(
        "SELECT COUNT(*) FROM trace_log WHERE trace_id = 'old-trace'"
    ).fetchone()[0] == 1
    trace.stage_log(connection, "new-trace", "stage_00", "ok", "timed", duration_ms=12)
    assert connection.execute(
        "SELECT duration_ms FROM trace_log WHERE trace_id = 'new-trace'"
    ).fetchone()[0] == 12
    connection.close()


def test_denied_provider_trace_records_gate_duration(conn, local_ollama, monkeypatch):
    from backend.stages import stage_08_provider_gate as stage_08

    def slow_denial(*args, **kwargs):
        time.sleep(0.05)
        raise stage_08.ProviderConsentError("test denial")

    monkeypatch.setattr(stage_08, "run", slow_denial)
    result = pipeline.run_sync(conn, "Measure denied provider", providers=[OllamaProvider()])
    rows = trace.get_trace(conn, result["trace_id"])
    denied = [row for row in rows if row["stage"] == "stage_08_provider_gate" and "blocked" in (row["message"] or "")]

    assert len(denied) == 1
    assert denied[0]["duration_ms"] >= 50
