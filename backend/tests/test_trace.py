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

    entries = json.loads(trace.TRACE_LOG_PATH.read_text(encoding="utf-8"))
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

    entries = json.loads(trace.TRACE_LOG_PATH.read_text(encoding="utf-8"))
    readable_trace = "\n".join(
        f"{entry['stage']} [{entry['status']}]: {entry['message']}"
        for entry in entries
    )

    assert "stage_00_input [ok]: User message accepted" in readable_trace
    assert "stage_01_intent_classifier [ok]: Intent classified" in readable_trace
    assert "stage_07_response [ok]: Response generated" in readable_trace
