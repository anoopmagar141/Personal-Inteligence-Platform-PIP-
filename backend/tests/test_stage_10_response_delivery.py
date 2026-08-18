import json

from backend.core import trace
from backend.stages import stage_10_response_delivery as stage_10


def test_success_logs_ok_and_returns_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    trace_id = trace.generate_trace_id()

    collected = {
        "response_text": "Here is your answer.",
        "status": "success",
        "error": None,
        "stage_hints": {"decision_log_hit": True, "web_search_used": False, "cache_hit": False, "model_loading": False},
    }
    result = stage_10.run(trace_id, collected)

    assert result["status"] == "success"
    assert result["response_text"] == "Here is your answer."
    assert result["stage_hints"]["decision_log_hit"] is True

    entries = json.loads(trace.TRACE_LOG_PATH.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["trace_id"] == trace_id
    assert entries[0]["stage"] == "stage_10_response_delivery"
    assert entries[0]["status"] == "ok"


def test_failure_logs_error_with_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    trace_id = trace.generate_trace_id()

    collected = {
        "response_text": "",
        "status": "error",
        "error": "All providers failed: connection refused",
        "stage_hints": {},
    }
    result = stage_10.run(trace_id, collected)

    assert result["status"] == "error"
    entries = json.loads(trace.TRACE_LOG_PATH.read_text(encoding="utf-8"))
    assert entries[0]["status"] == "error"
    assert entries[0]["error_detail"] == "All providers failed: connection refused"


def test_full_pipeline_stage_9_into_stage_10(tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / "trace_log.json")
    from backend.stages import stage_09_llm_streaming as stage_09
    from backend.providers.base_provider import BaseLLMProvider

    class SimpleProvider(BaseLLMProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30):
            yield "PIP "
            yield "works."

        def is_available(self):
            return True

        def get_model_info(self):
            return {"provider_id": "simple", "is_local": True, "model_name": "simple"}

    trace_id = trace.generate_trace_id()
    events = stage_09.run("context", [{"role": "user", "content": "hi"}], [SimpleProvider()], decision_log_hit=True)
    collected = stage_09.collect(events)
    result = stage_10.run(trace_id, collected)

    assert result["response_text"] == "PIP works."
    assert result["status"] == "success"
    assert result["stage_hints"]["decision_log_hit"] is True
