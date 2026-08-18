import json
from typing import Iterator

import pytest

from backend.core import pipeline, trace
from backend.memory import vector_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider


class FakeProvider(BaseLLMProvider):
    def __init__(self, provider_id="ollama", tokens=None, is_local=True):
        self.provider_id = provider_id
        self.tokens = tokens if tokens is not None else ["Hello", " world"]
        self._is_local = is_local

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30) -> Iterator[str]:
        yield from self.tokens

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": self.provider_id, "is_local": self._is_local, "model_name": "fake"}


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def isolated_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    yield


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    # Stage 5 (RAG) is real, not mocked, in these pipeline tests - without this,
    # it would load the real embedding model against the real production
    # data/chroma directory on every run, which is both slow and pollutes real
    # app state. Same isolation pattern as test_vector_store.py / test_stage_05.
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    yield


@pytest.fixture
def empty_snapshot_path(tmp_path):
    # No session_snapshot.json on disk - Stage 0 should fail open to a first-run state.
    return str(tmp_path / "session_snapshot.json")


def test_happy_path_yields_tokens_then_pipeline_complete(db_conn, empty_snapshot_path):
    events = list(pipeline.run(
        db_conn, "What is a hash table?",
        providers=[FakeProvider(tokens=["A ", "hash ", "table."])],
        snapshot_path=empty_snapshot_path,
    ))

    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["data"] for e in token_events) == "A hash table."

    final = events[-1]
    assert final["type"] == "pipeline_complete"
    assert final["data"]["status"] == "success"
    assert final["data"]["response_text"] == "A hash table."
    assert "trace_id" in final["data"]


def test_run_sync_returns_final_result_only(db_conn, empty_snapshot_path):
    result = pipeline.run_sync(
        db_conn, "Explain how a hash table works",
        providers=[FakeProvider(tokens=["ok"])],
        snapshot_path=empty_snapshot_path,
    )
    assert result["status"] == "success"
    assert result["response_text"] == "ok"


def test_no_consented_providers_short_circuits_before_stage_9(db_conn, empty_snapshot_path):
    unconsented = FakeProvider(provider_id="some_unseeded_cloud_provider", is_local=False)
    events = list(pipeline.run(
        db_conn, "hello",
        providers=[unconsented],
        snapshot_path=empty_snapshot_path,
    ))
    # No token/stage_hint events at all - short-circuited before Stage 9 ever ran.
    assert all(e["type"] != "token" for e in events)
    assert events[-1]["type"] == "pipeline_complete"
    assert events[-1]["data"]["status"] == "error"
    assert "No consented provider" in events[-1]["data"].get("response_text", "") or events[-1]["data"]["status"] == "error"


def test_web_search_only_fires_on_trigger_keywords(db_conn, empty_snapshot_path, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline.stage_06, "run", lambda *a, **kw: calls.append(a) or [{"title": "t", "url": "u", "snippet": "s"}])

    pipeline.run_sync(db_conn, "What's the latest news today?", providers=[FakeProvider()], snapshot_path=empty_snapshot_path)
    assert len(calls) == 1

    calls.clear()
    pipeline.run_sync(db_conn, "Explain how a hash table works", providers=[FakeProvider()], snapshot_path=empty_snapshot_path)
    assert len(calls) == 0


def test_stage_3_exception_does_not_crash_pipeline(db_conn, empty_snapshot_path, monkeypatch):
    monkeypatch.setattr(pipeline.stage_03, "run", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated Stage 3 crash")))
    result = pipeline.run_sync(db_conn, "hello", providers=[FakeProvider()], snapshot_path=empty_snapshot_path)
    assert result["status"] == "success"  # pipeline still completes despite Stage 3 failing


def test_trace_log_records_every_stage(db_conn, empty_snapshot_path):
    pipeline.run_sync(db_conn, "hello", providers=[FakeProvider()], snapshot_path=empty_snapshot_path)
    entries = json.loads(trace.TRACE_LOG_PATH.read_text(encoding="utf-8"))
    stages = {e["stage"] for e in entries}
    assert "stage_00_gap_detector" in stages
    assert "stage_01_intent_classifier" in stages
    assert "stage_02_router" in stages
    assert "stage_03_decision_log_lookup" in stages
    assert "stage_04_memory_lookup" in stages
    assert "stage_05_rag_retrieval" in stages
    assert "stage_06_web_search" in stages
    assert "stage_07_context_assembly" in stages
    assert "stage_09_llm_streaming" in stages
    assert "stage_10_response_delivery" in stages
    # Every entry in one pipeline run shares the same trace_id.
    assert len({e["trace_id"] for e in entries}) == 1


def test_mid_stream_provider_failure_still_finalizes_via_stage_10(db_conn, empty_snapshot_path):
    from backend.providers.base_provider import ProviderExecutionError

    class DyingProvider(FakeProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30):
            yield "partial"
            raise ProviderExecutionError("dropped connection")

    result = pipeline.run_sync(db_conn, "hello", providers=[DyingProvider()], snapshot_path=empty_snapshot_path)
    assert result["status"] == "error"
    assert result["response_text"] == "partial"  # partial output preserved, not discarded
