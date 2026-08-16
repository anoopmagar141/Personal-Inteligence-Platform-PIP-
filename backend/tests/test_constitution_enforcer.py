import pytest
import os
from datetime import datetime, timedelta, timezone
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.core.types import MemoryCandidate

@pytest.fixture
def enforcer():
    # Load enforcer using the constitutional.json file relative to tests
    path = os.path.join(os.path.dirname(__file__), "..", "core", "constitutional.json")
    return ConstitutionEnforcer(path)

def test_immutable_fields_hard_reject(enforcer):
    immutable_cases = [
        ("name", "Alice", "Bob"),
        ("language_preference", "en", "ne"),
        ("timezone", "UTC", "Asia/Kathmandu"),
    ]

    for field, existing_value, proposed_value in immutable_cases:
        existing = {"current_value": existing_value}
        candidate: MemoryCandidate = {
            "target_table": "identity",
            "field_name": field,
            "proposed_value": proposed_value,
            "label": "explicit",
            "evidence_count": 1,
            "evidence_text": "User stated a new immutable value."
        }
        res = enforcer.validate(candidate, existing, profile_age_weeks=1)
        assert res.status == "HARD_REJECT"
        assert res.reason == "immutable_field"

    # Onboarding never calls validate(); observer attempts to write identity are rejected.
    candidate: MemoryCandidate = {
        "target_table": "identity",
        "field_name": "name",
        "proposed_value": "Bob",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "I am Bob."
    }
    res_empty = enforcer.validate(candidate, None, profile_age_weeks=1)
    assert res_empty.status == "HARD_REJECT"
    assert res_empty.reason == "schema_violation"

def test_forbidden_schema_violation(enforcer):
    # Non-approved field name -> HARD_REJECT
    candidate: MemoryCandidate = {
        "target_table": "unapproved_table",
        "field_name": "invalid_field_name",
        "proposed_value": "Some Value",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate, {}, profile_age_weeks=1)
    assert res.status == "HARD_REJECT"
    assert res.reason == "schema_violation"

def test_gated_fields_require_confirmation(enforcer):
    gated_fields = [
        ("interaction_style", "value"),
        ("goal_memory", "goal_text"),
        ("active_projects", "name"),
        ("skill_memory", "python.level"),
    ]
    for target_table, field in gated_fields:
        candidate: MemoryCandidate = {
            "target_table": target_table,
            "field_name": field,
            "proposed_value": "value_here",
            "label": "explicit",
            "evidence_count": 1,
            "evidence_text": "evidence text"
        }
        res = enforcer.validate(candidate, {}, profile_age_weeks=1)
        assert res.status == "REQUIRES_CONFIRMATION"

def test_tiered_thresholds(enforcer):
    # Week 1-2: evidence >= 1, requires explicit label
    candidate_week1_explicit: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week1_explicit, None, profile_age_weeks=1)
    assert res.status == "APPROVED"

    candidate_week1_inferred: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week1_inferred, None, profile_age_weeks=1)
    assert res.status == "DISCARD"

    # Week 3-4: evidence >= 2 (regardless of label)
    candidate_week3_low_ev: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week3_low_ev, None, profile_age_weeks=3)
    assert res.status == "DISCARD"

    candidate_week3_pass: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 2,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week3_pass, None, profile_age_weeks=3)
    assert res.status == "APPROVED"

    # Month 2+: evidence >= 3, confidence >= 0.7
    # For explicit, evidence_count = 3 -> base 0.9 * 3/5 = 0.54 (fails confidence threshold of 0.7)
    # For explicit, evidence_count = 4 -> base 0.9 * 4/5 = 0.72 (passes confidence threshold)
    candidate_month2_low_ev: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 2,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_month2_low_ev, None, profile_age_weeks=8)
    assert res.status == "DISCARD"

    candidate_month2_low_conf: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 3,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_month2_low_conf, None, profile_age_weeks=8)
    assert res.status == "DISCARD"

    candidate_month2_pass: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 4,
        "evidence_text": "",
    }
    res = enforcer.validate(candidate_month2_pass, None, profile_age_weeks=8)
    assert res.status == "APPROVED"

    goal_month2: MemoryCandidate = {
        "target_table": "goal_memory",
        "field_name": "goal_text",
        "proposed_value": "Finish PIP",
        "label": "inferred",
        "evidence_count": 3,
        "evidence_text": ""
    }
    res = enforcer.validate(goal_month2, None, profile_age_weeks=8)
    assert res.status == "REQUIRES_CONFIRMATION"

def test_behavioral_override(enforcer):
    # Stated preference contradicts behavioral inference for 3+ sessions across 14+ days.
    existing = {
        "current_value": "explicit_val",
        "source_label": "explicit",
        "confidence": 0.9,
        "behavioral_signal_count": 3,
        "first_contradiction_date": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
    }
    
    # Under 3 sessions: does not trigger reconciliation yet.
    candidate_low_sessions: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "behavioral_val",
        "label": "inferred",
        "evidence_count": 2,
        "evidence_text": "",
    }
    low_sessions_existing = {**existing, "behavioral_signal_count": 2}
    res = enforcer.validate(candidate_low_sessions, low_sessions_existing, profile_age_weeks=1)
    assert res.status != "PROMPT_RECONCILIATION"

    # Under 14 days: does not trigger reconciliation yet.
    candidate_low_days: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "behavioral_val",
        "label": "inferred",
        "evidence_count": 3,
        "evidence_text": "",
    }
    low_days_existing = {
        **existing,
        "first_contradiction_date": (datetime.now(timezone.utc) - timedelta(days=13)).isoformat(),
    }
    res = enforcer.validate(candidate_low_days, low_days_existing, profile_age_weeks=1)
    assert res.status != "PROMPT_RECONCILIATION"

    unstated_existing = {**existing, "source_label": "inferred"}
    res = enforcer.validate(candidate_low_days, unstated_existing, profile_age_weeks=1)
    assert res.status != "PROMPT_RECONCILIATION"

    # 3+ sessions and 14+ days: triggers PROMPT_RECONCILIATION.
    candidate_override: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "preference_name",
        "proposed_value": "behavioral_val",
        "label": "inferred",
        "evidence_count": 3,
        "evidence_text": "",
    }
    res = enforcer.validate(candidate_override, existing, profile_age_weeks=1)
    assert res.status == "PROMPT_RECONCILIATION"
