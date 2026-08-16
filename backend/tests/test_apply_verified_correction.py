import pytest
from backend.core.types import MemoryCandidate, ValidationResult, now_utc
from backend.memory.profile_store import get_connection, initialize_schema, apply_verified_correction

@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en-US', 'UTC')")
    conn.commit()
    yield conn
    conn.close()

def test_apply_verified_correction_preference_memory(db_conn):
    # Setup initial state with some contradictions
    db_conn.execute("INSERT INTO preference_memory (name, value, evidence_count, source_label, status, behavioral_signal_count) VALUES ('editor', 'vim', 2, 'inferred', 'active', 3)")
    pref_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'editor'").fetchone()["id"]
    db_conn.execute("INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at) VALUES (?, 'Used emacs', '2020-01-01T00:00:00Z')", (pref_id,))
    
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "I like emacs"
    }
    validation_result = ValidationResult.PROMPT_RECONCILIATION("override")
    
    apply_verified_correction(db_conn, candidate, validation_result)
    
    row = db_conn.execute("SELECT value, evidence_count, source_label, behavioral_signal_count, confidence FROM preference_memory WHERE name = 'editor'").fetchone()
    assert row["value"] == "emacs"
    assert row["source_label"] == "user_correction"
    assert row["evidence_count"] == 5
    assert row["behavioral_signal_count"] == 0
    assert row["confidence"] == 0.9 # Maximum for GENERATED column based on user_correction + 5 evidence
    
    # Contradiction log should be cleared
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log WHERE preference_id = ?", (pref_id,)).fetchone()[0]
    assert count == 0

def test_apply_verified_correction_skill_memory(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "skill_memory",
        "field_name": "python",
        "proposed_value": "0.8",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "I am pro"
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")
    
    apply_verified_correction(db_conn, candidate, validation_result)
    
    row = db_conn.execute("SELECT level, evidence_count, source_label, confidence FROM skill_memory WHERE name = 'python'").fetchone()
    assert row["level"] == 0.8
    assert row["source_label"] == "user_verified"
    assert row["evidence_count"] == 5
    assert row["confidence"] == 0.9

def test_apply_verified_correction_interaction_style(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "interaction_style",
        "field_name": "value",
        "proposed_value": "terse",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "Be short"
    }
    validation_result = ValidationResult.PROMPT_RECONCILIATION("override")
    
    apply_verified_correction(db_conn, candidate, validation_result)
    
    row = db_conn.execute("SELECT value, evidence_count, source_label, confidence FROM interaction_style WHERE id = 1").fetchone()
    assert row["value"] == "terse"
    assert row["source_label"] == "user_correction"
    assert row["evidence_count"] == 5
    assert row["confidence"] == 0.9

def test_apply_verified_correction_goal_memory(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "goal_memory",
        "field_name": "goal:999",
        "proposed_value": "Finish tests",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "New goal"
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")
    
    apply_verified_correction(db_conn, candidate, validation_result)
    
    row = db_conn.execute("SELECT goal_text, confidence, evidence_count, decay_flag FROM goal_memory WHERE id = 999").fetchone()
    assert row["goal_text"] == "Finish tests"
    assert row["confidence"] == 1.0 # explicitly stored
    assert row["evidence_count"] == 5
    assert row["decay_flag"] == 0

def test_apply_verified_correction_active_projects(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "active_projects",
        "field_name": "Project X",
        "proposed_value": "Top secret",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "New project"
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")
    
    apply_verified_correction(db_conn, candidate, validation_result)
    
    row = db_conn.execute("SELECT description, status FROM active_projects WHERE name = 'Project X'").fetchone()
    assert row["description"] == "Top secret"
    assert row["status"] == "active"

def test_apply_verified_correction_immutable_identity(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "identity",
        "field_name": "name",
        "proposed_value": "Bob",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "My name is bob"
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")
    
    with pytest.raises(ValueError, match="immutable identity fields cannot be edited"):
        apply_verified_correction(db_conn, candidate, validation_result)
def test_apply_verified_correction_goal_memory_malformed_id(db_conn):
    # Use a non-numeric identifier to trigger the fallback autoincrement branch
    candidate: MemoryCandidate = {
        "target_table": "goal_memory",
        "field_name": "goal:abc",
        "proposed_value": "New ambiguous goal",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "Malformed ID test",
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")

    # Should insert with auto-generated id
    apply_verified_correction(db_conn, candidate, validation_result)

    row = db_conn.execute("SELECT goal_text, confidence, evidence_count, decay_flag FROM goal_memory WHERE goal_text = ?", ("New ambiguous goal",)).fetchone()
    assert row is not None
    assert row["confidence"] == 1.0
    assert row["evidence_count"] == 5
    assert row["decay_flag"] == 0

def test_apply_verified_correction_active_projects_update_path(db_conn):
    # Seed an existing project
    db_conn.execute("INSERT INTO active_projects (project_id, name, description, status, last_active) VALUES (?, ?, ?, 'active', ?)",
                    ("proj-123", "Project X", "Old description", now_utc()))
    db_conn.commit()

    candidate: MemoryCandidate = {
        "target_table": "active_projects",
        "field_name": "Project X",
        "proposed_value": "Updated description",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "Update description",
    }
    validation_result = ValidationResult.REQUIRES_CONFIRMATION("gated")

    apply_verified_correction(db_conn, candidate, validation_result)

    rows = db_conn.execute("SELECT description FROM active_projects WHERE name = 'Project X'").fetchall()
    assert len(rows) == 1
    assert rows[0]["description"] == "Updated description"
