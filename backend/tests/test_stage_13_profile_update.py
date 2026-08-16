import pytest
from backend.core.types import MemoryCandidate, ValidationResult
from backend.memory.profile_store import get_connection, initialize_schema
from backend.memory import candidate_store
from backend.stages import stage_13_profile_update as stage_13


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def test_approved_writes_preference_immediately(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "explicit",
        "evidence_count": 3,
        "evidence_text": "Used hjkl",
    }
    outcome = stage_13.run(db_conn, candidate, ValidationResult.APPROVED())
    assert outcome == "written"

    row = db_conn.execute("SELECT value, evidence_count, source_label FROM preference_memory WHERE name = 'editor'").fetchone()
    assert row["value"] == "vim"
    assert row["evidence_count"] == 3
    assert row["source_label"] == "explicit"


def test_approved_writes_goal_with_computed_confidence(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "goal_memory",
        "field_name": "goal:new",
        "proposed_value": "Finish thesis",
        "label": "explicit",
        "evidence_count": 3,
        "evidence_text": "Said so directly",
    }
    outcome = stage_13.run(db_conn, candidate, ValidationResult.APPROVED())
    assert outcome == "written"

    row = db_conn.execute("SELECT goal_text, confidence FROM goal_memory WHERE goal_text = 'Finish thesis'").fetchone()
    assert row is not None
    # explicit base 0.9 * min(3,5)/5 = 0.54
    assert row["confidence"] == pytest.approx(0.54)


@pytest.mark.parametrize("status_factory", [
    lambda: ValidationResult.REQUIRES_CONFIRMATION("gated field"),
    lambda: ValidationResult.TIER_2_REQUIRED("conflict"),
    lambda: ValidationResult.PROMPT_RECONCILIATION("behavioral override"),
])
def test_pending_statuses_persist_to_memory_candidates_pending(db_conn, status_factory):
    candidate: MemoryCandidate = {
        "target_table": "interaction_style",
        "field_name": "value",
        "proposed_value": "concise",
        "label": "explicit",
        "evidence_count": 5,
        "evidence_text": "User said be concise",
    }
    result = status_factory()
    outcome = stage_13.run(db_conn, candidate, result)
    assert outcome == "pending"

    pending = candidate_store.list_memory_candidates(db_conn)
    assert len(pending) == 1
    assert pending[0]["target_table"] == "interaction_style"
    assert pending[0]["validation_status"] == result.status
    assert pending[0]["state"] == "pending"


@pytest.mark.parametrize("status_factory", [
    lambda: ValidationResult.HARD_REJECT("immutable_field"),
    lambda: ValidationResult.DISCARD("below_threshold"),
])
def test_rejected_statuses_write_nothing(db_conn, status_factory):
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "guess",
    }
    outcome = stage_13.run(db_conn, candidate, status_factory())
    assert outcome == "rejected"
    assert db_conn.execute("SELECT COUNT(*) FROM preference_memory").fetchone()[0] == 0
    assert db_conn.execute("SELECT COUNT(*) FROM memory_candidates_pending").fetchone()[0] == 0


def test_approved_write_failure_retries_once_then_fails(db_conn, monkeypatch):
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "explicit",
        "evidence_count": 3,
        "evidence_text": "Used hjkl",
    }
    calls = {"count": 0}

    def _boom(conn, cand):
        calls["count"] += 1
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr("backend.stages.stage_13_profile_update.profile_store.write_approved_candidate", _boom)
    outcome = stage_13.run(db_conn, candidate, ValidationResult.APPROVED())
    assert outcome == "failed"
    assert calls["count"] == 2
