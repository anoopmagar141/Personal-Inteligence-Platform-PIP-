import pytest

from backend.core import trace
from backend.memory.profile_store import get_connection, initialize_schema
from backend.stages import stage_10_response_delivery as stage_10


@pytest.fixture
def conn(tmp_path, db_key):
    connection = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(connection)
    yield connection
    connection.close()


def test_success_logs_ok_and_returns_summary(conn):
    trace_id = trace.generate_trace_id()

    collected = {
        "response_text": "Here is your answer.",
        "status": "success",
        "error": None,
        "stage_hints": {"decision_log_hit": True, "web_search_used": False, "cache_hit": False, "model_loading": False},
    }
    result = stage_10.run(trace_id, collected, conn)

    assert result["status"] == "success"
    assert result["response_text"] == "Here is your answer."
    assert result["stage_hints"]["decision_log_hit"] is True

    entries = trace.get_trace(conn, trace_id)
    assert len(entries) == 1
    assert entries[0]["stage"] == "stage_10_response_delivery"
    assert entries[0]["status"] == "ok"


def test_failure_logs_error_with_detail(conn):
    trace_id = trace.generate_trace_id()

    collected = {
        "response_text": "",
        "status": "error",
        "error": "All providers failed: connection refused",
        "stage_hints": {},
    }
    result = stage_10.run(trace_id, collected, conn)

    assert result["status"] == "error"
    entries = trace.get_trace(conn, trace_id)
    assert entries[0]["status"] == "error"
    assert entries[0]["error_detail"] == "All providers failed: connection refused"


def test_stopped_is_recorded_as_ok_with_what_was_delivered(conn):
    trace_id = trace.generate_trace_id()

    result = stage_10.run(
        trace_id,
        {"response_text": "Half an ans", "status": "stopped", "error": None, "stage_hints": {}},
        conn,
    )

    assert result["status"] == "stopped"
    assert trace.get_trace(conn, trace_id)[0]["status"] == "ok"


def test_delivery_still_succeeds_when_the_trace_cannot_be_written(conn):
    """
    Stage 10's job is delivering the response. A trace write that fails must not
    take the response with it.
    """
    conn.close()
    result = stage_10.run(
        trace_id := trace.generate_trace_id(),
        {"response_text": "Answer", "status": "success", "error": None, "stage_hints": {}},
        conn,
    )

    assert result["response_text"] == "Answer"
    assert result["trace_id"] == trace_id


def test_full_pipeline_stage_9_into_stage_10(conn):
    from backend.providers.base_provider import BaseLLMProvider
    from backend.stages import stage_09_llm_streaming as stage_09

    class SimpleProvider(BaseLLMProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            yield "PIP "
            yield "works."

        def is_available(self):
            return True

        def get_model_info(self):
            return {"provider_id": "simple", "is_local": True, "model_name": "simple"}

    trace_id = trace.generate_trace_id()
    events = stage_09.run("context", [{"role": "user", "content": "hi"}], [SimpleProvider()], decision_log_hit=True)
    collected = stage_09.collect(events)
    result = stage_10.run(trace_id, collected, conn)

    assert result["response_text"] == "PIP works."
    assert result["status"] == "success"
    assert result["stage_hints"]["decision_log_hit"] is True
