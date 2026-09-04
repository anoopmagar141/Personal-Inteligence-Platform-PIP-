from typing import Iterator

import pytest

from backend.core import pipeline, response_cache, trace
from backend.memory import vector_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider


@pytest.fixture(autouse=True)
def isolated_response_cache():
    # response_cache._cache is a module-level dict shared across the whole
    # pytest process. Several tests here reuse plain messages like "hello" -
    # without this, a cached response from one test can silently serve a
    # LATER test (skipping Stage 3-9 entirely), which is exactly what
    # happened here live: it masked test_mid_stream_provider_failure's
    # DyingProvider never actually being called, and made
    # test_trace_log_records_every_stage fail because Stage 3 never ran.
    response_cache.clear()
    yield
    response_cache.clear()


class FakeProvider(BaseLLMProvider):
    def __init__(self, provider_id="ollama", tokens=None, is_local=True):
        self.provider_id = provider_id
        self.tokens = tokens if tokens is not None else ["Hello", " world"]
        self._is_local = is_local

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None) -> Iterator[str]:
        yield from self.tokens

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": self.provider_id, "is_local": self._is_local, "model_name": "fake"}


@pytest.fixture
def db_conn(tmp_path, db_key):
    # A fresh DB has no session_snapshot row yet, which is exactly the
    # "first-ever run" state Stage 0 should fail open to - no separate
    # empty-snapshot fixture needed now that the snapshot lives in this same
    # conn instead of a standalone file (security review fix).
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


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


def test_happy_path_yields_tokens_then_pipeline_complete(db_conn):
    events = list(pipeline.run(
        db_conn, "What is a hash table?",
        providers=[FakeProvider(tokens=["A ", "hash ", "table."])],
    ))

    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["data"] for e in token_events) == "A hash table."

    final = events[-1]
    assert final["type"] == "pipeline_complete"
    assert final["data"]["status"] == "success"
    assert final["data"]["response_text"] == "A hash table."
    assert "trace_id" in final["data"]


def test_should_stop_ends_pipeline_early_with_stopped_status(db_conn):
    events = list(pipeline.run(
        db_conn, "What is a hash table?",
        providers=[FakeProvider(tokens=["A ", "hash ", "table."])],
        should_stop=lambda: True,
    ))
    token_events = [e for e in events if e["type"] == "token"]
    assert token_events == []  # stopped before the provider's own generator was ever consumed

    final = events[-1]
    assert final["type"] == "pipeline_complete"
    assert final["data"]["status"] == "stopped"


def test_stopped_response_is_never_cached(db_conn):
    pipeline.run_sync(
        db_conn, "Explain how caching works",
        providers=[FakeProvider(tokens=["partial"])],
        should_stop=lambda: True,
    )
    second = pipeline.run_sync(
        db_conn, "Explain how caching works",
        providers=[FakeProvider(tokens=["fresh", " answer"])],
    )
    # If the stopped call had been cached, this would come back as "" (the
    # stopped call's empty response_text) instead of the fresh provider's text.
    assert second["response_text"] == "fresh answer"


def test_run_sync_returns_final_result_only(db_conn):
    result = pipeline.run_sync(
        db_conn, "Explain how a hash table works",
        providers=[FakeProvider(tokens=["ok"])],
    )
    assert result["status"] == "success"
    assert result["response_text"] == "ok"


def test_no_consented_providers_short_circuits_before_stage_9(db_conn):
    unconsented = FakeProvider(provider_id="some_unseeded_cloud_provider", is_local=False)
    events = list(pipeline.run(
        db_conn, "hello",
        providers=[unconsented],
    ))
    # No token/stage_hint events at all - short-circuited before Stage 9 ever ran.
    assert all(e["type"] != "token" for e in events)
    assert events[-1]["type"] == "pipeline_complete"
    assert events[-1]["data"]["status"] == "error"
    assert "No consented provider" in events[-1]["data"].get("response_text", "") or events[-1]["data"]["status"] == "error"


def test_web_search_blocked_without_consent_even_on_trigger_keywords(db_conn, monkeypatch):
    # Security regression test: config/provider_consent.json seeds web_search
    # with user_consented=0 by default - a trigger-keyword match alone must
    # NOT be enough to fire a real search before consent is granted.
    calls = []
    monkeypatch.setattr(pipeline.stage_06, "run", lambda *a, **kw: calls.append(a) or [{"title": "t", "url": "u", "snippet": "s"}])

    pipeline.run_sync(db_conn, "What's the latest news today?", providers=[FakeProvider()])
    assert len(calls) == 0


def test_web_search_fires_on_trigger_keywords_once_consented(db_conn, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline.stage_06, "run", lambda *a, **kw: calls.append(a) or [{"title": "t", "url": "u", "snippet": "s"}])
    db_conn.execute(
        "UPDATE provider_consent SET user_consented = 1 WHERE provider_id = 'web_search'"
    )
    db_conn.commit()

    pipeline.run_sync(db_conn, "What's the latest news today?", providers=[FakeProvider()])
    assert len(calls) == 1

    calls.clear()
    pipeline.run_sync(db_conn, "Explain how a hash table works", providers=[FakeProvider()])
    assert len(calls) == 0


def test_web_search_blocked_after_consent_revoked(db_conn, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline.stage_06, "run", lambda *a, **kw: calls.append(a) or [{"title": "t", "url": "u", "snippet": "s"}])
    db_conn.execute(
        "UPDATE provider_consent SET user_consented = 1, revoked = 0 WHERE provider_id = 'web_search'"
    )
    db_conn.commit()
    pipeline.run_sync(db_conn, "What's the latest news today?", providers=[FakeProvider()])
    assert len(calls) == 1

    calls.clear()
    db_conn.execute("UPDATE provider_consent SET revoked = 1 WHERE provider_id = 'web_search'")
    db_conn.commit()
    pipeline.run_sync(db_conn, "What's the latest news today?", providers=[FakeProvider()])
    assert len(calls) == 0


def test_stage_3_exception_does_not_crash_pipeline(db_conn, monkeypatch):
    monkeypatch.setattr(pipeline.stage_03, "run", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("simulated Stage 3 crash")))
    result = pipeline.run_sync(db_conn, "hello", providers=[FakeProvider()])
    assert result["status"] == "success"  # pipeline still completes despite Stage 3 failing


def test_trace_log_records_every_stage(db_conn):
    pipeline.run_sync(db_conn, "hello", providers=[FakeProvider()])
    recent = trace.list_recent_traces(db_conn)
    assert len(recent) == 1, "one pipeline run is one trace"
    entries = trace.get_trace(db_conn, recent[0]["trace_id"])
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
    # And they come back in the order the stages actually ran, which is the
    # only thing that makes a trace readable.
    assert [e["stage"] for e in entries][:3] == [
        "pipeline",
        "stage_00_gap_detector",
        "stage_01_intent_classifier",
    ]


def test_mid_stream_provider_failure_still_finalizes_via_stage_10(db_conn):
    from backend.providers.base_provider import ProviderExecutionError

    class DyingProvider(FakeProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            yield "partial"
            raise ProviderExecutionError("dropped connection")

    result = pipeline.run_sync(db_conn, "hello", providers=[DyingProvider()])
    assert result["status"] == "error"
    assert result["response_text"] == "partial"  # partial output preserved, not discarded


def test_cache_hit_skips_stages_3_through_9(db_conn, monkeypatch):
    calls = {"stage_03": 0}
    real_stage_03_run = pipeline.stage_03.run

    def counting_stage_03(*args, **kwargs):
        calls["stage_03"] += 1
        return real_stage_03_run(*args, **kwargs)

    monkeypatch.setattr(pipeline.stage_03, "run", counting_stage_03)

    first = pipeline.run_sync(
        db_conn, "Explain how caching works", providers=[FakeProvider(tokens=["cached", " answer"])],
    )
    assert first["status"] == "success"
    assert calls["stage_03"] == 1

    # Second call, same message, same project_id (None) - should be served
    # from cache without Stage 3 (or the LLM) running again. A different
    # provider that would produce different tokens proves the cached text
    # was served, not freshly generated.
    second = pipeline.run_sync(
        db_conn, "Explain how caching works", providers=[FakeProvider(tokens=["should", " not", " appear"])],
    )
    assert calls["stage_03"] == 1  # not called again
    assert second["response_text"] == "cached answer"
    assert second["stage_hints"]["cache_hit"] is True


def test_stage_0_context_depth_modifier_is_passed_to_stage_7(db_conn, monkeypatch):
    # Stage 0's context_depth_modifier used to be computed and discarded - this
    # confirms the orchestrator actually forwards it to Stage 7, not just that
    # Stage 7 knows how to use it in isolation (already covered by
    # test_stage_07_context_assembly.py).
    captured = {}
    real_stage_07_run = pipeline.stage_07.run

    def capturing_stage_07(*args, **kwargs):
        captured.update(kwargs)
        return real_stage_07_run(*args, **kwargs)

    monkeypatch.setattr(pipeline.stage_07, "run", capturing_stage_07)

    pipeline.run_sync(db_conn, "hello", providers=[FakeProvider()])

    # A fresh db_conn has no session_snapshot row -> Stage 0 fails open to a
    # first-run gap -> modifier 0.
    assert captured["context_depth_modifier"] == 0


def test_project_question_is_never_cached(db_conn):
    db_conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p1', 'InventorySync', 'sync service', 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    first = pipeline.run_sync(
        db_conn, "How is InventorySync going?", providers=[FakeProvider(tokens=["first answer"])],
    )
    assert first["status"] == "success"

    second = pipeline.run_sync(
        db_conn, "How is InventorySync going?", providers=[FakeProvider(tokens=["second answer"])],
    )
    # project_question has TTL 0 (never cache) - the second call must have
    # actually run again, not served a cached first answer.
    assert second["response_text"] == "second answer"
    assert second["stage_hints"]["cache_hit"] is False


# --- where Stage 0 measures the warm-start gap from -------------------------


def _stamp(**kw):
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_snapshot(conn, when):
    conn.execute(
        "INSERT INTO session_snapshot (id, topic, snapshot_date) VALUES (1, 'topic', ?) "
        "ON CONFLICT(id) DO UPDATE SET snapshot_date = excluded.snapshot_date",
        (when,),
    )
    conn.commit()


def test_gap_is_measured_from_the_last_message_not_the_last_snapshot(db_conn):
    """
    The Observer withholds a snapshot for a session with no substantive turn, so
    snapshot_date froze while short check-ins kept happening and the gap grew as
    though the user had been away the whole time.
    """
    from backend.memory import conversation_store, profile_store

    conversation_id = conversation_store.create_conversation(db_conn)
    conversation_store.append_message(db_conn, conversation_id, "user", "hi")
    db_conn.execute("UPDATE messages SET created_at = ?", (_stamp(hours=2),))
    _seed_snapshot(db_conn, _stamp(days=9))
    profile_store.complete_onboarding(db_conn, name="A", language_preference="English")

    profile_store.begin_session(db_conn)

    measured = pipeline._load_last_session_timestamp(db_conn)
    assert measured is not None
    from datetime import datetime, timezone
    hours = (datetime.now(timezone.utc) - measured).total_seconds() / 3600
    assert 1 < hours < 4, f"expected the 2h message gap, got {hours:.1f}h"


def test_gap_does_not_collapse_to_zero_once_the_session_has_started(db_conn):
    """
    last_session_date is the obvious candidate and is wrong: ws_chat sets it on
    the first message, BEFORE the pipeline runs, so reading it here would report
    a gap of zero on every message and disable warm start entirely.
    """
    from backend.memory import conversation_store, profile_store

    conversation_id = conversation_store.create_conversation(db_conn)
    conversation_store.append_message(db_conn, conversation_id, "user", "earlier")
    db_conn.execute("UPDATE messages SET created_at = ?", (_stamp(days=3),))
    profile_store.complete_onboarding(db_conn, name="A", language_preference="English")

    profile_store.begin_session(db_conn)

    from datetime import datetime, timezone
    measured = pipeline._load_last_session_timestamp(db_conn)
    days = (datetime.now(timezone.utc) - measured).total_seconds() / 86400
    assert days > 2, f"gap collapsed to {days:.2f} days - Stage 0 is reading the current session"


def test_falls_back_to_the_snapshot_before_the_first_migrated_session(db_conn):
    """
    An upgraded database has previous_session_date NULL until its first session
    begins. Degrading to the old source beats treating it as a first-ever run,
    which would load no warm-start context at all.
    """
    _seed_snapshot(db_conn, _stamp(days=5))
    db_conn.execute("UPDATE profile_meta SET previous_session_date = NULL WHERE id = 1")
    db_conn.commit()

    from datetime import datetime, timezone
    measured = pipeline._load_last_session_timestamp(db_conn)
    assert measured is not None
    days = (datetime.now(timezone.utc) - measured).total_seconds() / 86400
    assert 4 < days < 6


def test_no_history_at_all_reads_as_a_first_run(db_conn):
    assert pipeline._load_last_session_timestamp(db_conn) is None
