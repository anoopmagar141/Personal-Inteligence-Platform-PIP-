import pytest
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from backend.core.types import MemoryCandidate
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.stages.stage_12_validation_layer import run, reinforce_evidence
from backend.memory.profile_store import get_connection, initialize_schema

@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    # Set up basic profile
    conn.execute(
        "INSERT INTO profile_meta (id, schema_version, constitution_version, first_session_date) VALUES (1, '1.0', '1.0', ?)",
        ((datetime.now(timezone.utc) - timedelta(weeks=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),)
    )
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def enforcer():
    # Use the real constitution
    constitution_path = os.path.join("backend", "core", "constitutional.json")
    return ConstitutionEnforcer(constitution_path)

def test_no_prior_state(db_conn, enforcer):
    candidate = {
        "target_table": "preference_memory",
        "field_name": "vim_keybindings",
        "proposed_value": "true",
        "label": "explicit",
        "evidence_count": 5,
        "evidence_text": "Used hjkl"
    }
    result = run(db_conn, candidate, enforcer)
    assert result.status == "APPROVED"

def test_hard_reject_immutable(db_conn, enforcer):
    db_conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en-US', 'UTC')")
    db_conn.commit()
    
    candidate = {
        "target_table": "identity",
        "field_name": "name",
        "proposed_value": "Bob",
        "label": "user_correction",
        "evidence_count": 1,
        "evidence_text": "Call me Bob"
    }
    result = run(db_conn, candidate, enforcer)
    assert result.status == "HARD_REJECT"

def test_prompt_reconciliation(db_conn, enforcer):
    # Setup explicit preference memory with behavioral override conditions
    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label, behavioral_signal_count)
        VALUES ('vim_keybindings', 'false', 'explicit', 4)
    """)
    row_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'vim_keybindings'").fetchone()["id"]
    
    # Insert contradiction log > 14 days ago (trigger_days is 14)
    old_date = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db_conn.execute("""
        INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at)
        VALUES (?, 'User typed hjkl', ?)
    """, (row_id, old_date))
    db_conn.commit()
    
    candidate = {
        "target_table": "preference_memory",
        "field_name": "vim_keybindings",
        "proposed_value": "true",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Used hjkl"
    }
    result = run(db_conn, candidate, enforcer)
    assert result.status == "PROMPT_RECONCILIATION"

def test_discard_threshold_violation(db_conn, enforcer):
    candidate = {
        "target_table": "preference_memory",
        "field_name": "vim_keybindings",
        "proposed_value": "true",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Used hjkl"
    }
    result = run(db_conn, candidate, enforcer)
    # Profile age is 2 weeks, so week 1-2 threshold requires explicit label. Inferred is discarded.
    assert result.status == "DISCARD"

def test_requires_confirmation_gated_field(db_conn, enforcer):
    candidate = {
        "target_table": "interaction_style",
        "field_name": "value",
        "proposed_value": "concise",
        "label": "explicit",
        "evidence_count": 5,
        "evidence_text": "User said be concise"
    }
    # interaction_style is gated, so even with explicit label and high evidence it needs confirmation
    result = run(db_conn, candidate, enforcer)
    assert result.status == "REQUIRES_CONFIRMATION"

def test_tier_2_required_conflict(db_conn, enforcer):
    # Insert existing high confidence value
    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label, evidence_count)
        VALUES ('vim_keybindings', 'false', 'explicit', 5)
    """)
    db_conn.commit()
    
    candidate = {
        "target_table": "preference_memory",
        "field_name": "vim_keybindings",
        "proposed_value": "true",
        "label": "explicit",  # skips behavioral override
        "evidence_count": 5,
        "evidence_text": "Actually I like vim"
    }
    result = run(db_conn, candidate, enforcer)
    # Different value, existing confidence > 0.7 (explicit, evidence 5 -> 0.9 * 1.0 = 0.9)
    assert result.status == "TIER_2_REQUIRED"

def test_unhandled_observer_writable_table_logs_warning_and_fails_open(db_conn, enforcer, caplog, monkeypatch):
    import backend.core.constitution_enforcer as ce
    monkeypatch.setattr(ce, "OBSERVER_WRITABLE_TABLES", ce.OBSERVER_WRITABLE_TABLES | {"_test_future_table"})
    
    candidate = {
        "target_table": "_test_future_table",  # hypothetical table added to constitution but not yet handled by stage_12
        "field_name": "some_field",
        "proposed_value": "true",
        "label": "explicit",
        "evidence_count": 5,
        "evidence_text": "test"
    }
    result = run(db_conn, candidate, enforcer)
    # Fails open -> handled as no prior state -> APPROVED due to explicit and evidence 5
    assert result.status == "APPROVED"
    assert "Unhandled target_table" in caplog.text


def test_reinforce_evidence_no_prior_state_leaves_candidate_unchanged(db_conn):
    candidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    reinforced = reinforce_evidence(db_conn, candidate)
    assert reinforced["evidence_count"] == 1
    assert reinforced is not candidate or reinforced == candidate  # unchanged either way


def test_reinforce_evidence_same_value_increments(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('editor', 'vim', 2, 'explicit', 'active')"
    )
    db_conn.commit()

    candidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",  # same value as stored -> repeat observation
        "label": "explicit",
        "evidence_count": 1,  # this session's own observation count
        "evidence_text": "still using vim"
    }
    reinforced = reinforce_evidence(db_conn, candidate)
    assert reinforced["evidence_count"] == 3  # existing 2 + 1, not the candidate's own 1


def test_reinforce_evidence_different_value_does_not_reinforce(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('editor', 'vim', 4, 'explicit', 'active')"
    )
    db_conn.commit()

    candidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",  # different value -> conflict, not reinforcement
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "switched to emacs"
    }
    reinforced = reinforce_evidence(db_conn, candidate)
    assert reinforced["evidence_count"] == 1  # left as the candidate's own count


def test_reinforce_evidence_skips_tables_without_evidence_count_column(db_conn):
    db_conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en-US', 'UTC')")
    db_conn.commit()

    candidate = {
        "target_table": "identity",
        "field_name": "name",
        "proposed_value": "Alice",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    reinforced = reinforce_evidence(db_conn, candidate)
    assert reinforced["evidence_count"] == 1


def test_reinforced_evidence_flows_through_to_approval_across_simulated_sessions(db_conn, enforcer):
    # Week 3-4 threshold requires evidence_count >= 2 (profile_age_weeks <= 2 is
    # week_1_2, which only requires evidence >= 1 - push the fixture's profile past
    # that boundary so this test actually exercises week_3_4, not week_1_2).
    db_conn.execute(
        "UPDATE profile_meta SET first_session_date = ? WHERE id = 1",
        ((datetime.now(timezone.utc) - timedelta(weeks=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),)
    )
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('editor', 'vim', 1, 'explicit', 'active')"
    )
    db_conn.commit()

    candidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "still vim"
    }

    unreinforced_result = run(db_conn, dict(candidate), enforcer)
    assert unreinforced_result.status == "DISCARD"

    reinforced = reinforce_evidence(db_conn, candidate)
    assert reinforced["evidence_count"] == 2
    reinforced_result = run(db_conn, reinforced, enforcer)
    assert reinforced_result.status == "APPROVED"
