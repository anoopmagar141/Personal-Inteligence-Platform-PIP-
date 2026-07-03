import pytest
import os
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.core.types import MemoryCandidate

@pytest.fixture
def enforcer():
    # Load enforcer using the constitutional.json file relative to tests
    path = os.path.join(os.path.dirname(__file__), "..", "core", "constitutional.json")
    return ConstitutionEnforcer(path)

def test_immutable_field_hard_reject(enforcer):
    # Field: name (immutable)
    # Existing value present -> HARD_REJECT
    existing = {"name": "Alice"}
    candidate: MemoryCandidate = {
        "field_name": "name",
        "proposed_value": "Bob",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "I am Bob now."
    }
    res = enforcer.validate(candidate, existing, profile_age_weeks=1)
    assert res.status == "HARD_REJECT"
    assert res.reason == "immutable_field"

    # No existing value -> APPROVED (during bootstrapping/first write)
    res_empty = enforcer.validate(candidate, {}, profile_age_weeks=1)
    assert res_empty.status == "APPROVED"

def test_forbidden_schema_violation(enforcer):
    # Non-approved field name -> HARD_REJECT
    candidate: MemoryCandidate = {
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
    # interaction_style, goals, active_projects, skill_level are gated
    gated_fields = ["interaction_style", "goals", "active_projects", "skill_level"]
    for field in gated_fields:
        candidate: MemoryCandidate = {
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
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week1_explicit, {}, profile_age_weeks=1)
    assert res.status == "APPROVED"

    candidate_week1_inferred: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week1_inferred, {}, profile_age_weeks=1)
    assert res.status == "DISCARD"

    # Week 3-4: evidence >= 2 (regardless of label)
    candidate_week3_low_ev: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week3_low_ev, {}, profile_age_weeks=3)
    assert res.status == "DISCARD"

    candidate_week3_pass: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 2,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_week3_pass, {}, profile_age_weeks=3)
    assert res.status == "APPROVED"

    # Month 2+: evidence >= 3, confidence >= 0.7
    # For explicit, evidence_count = 3 -> base 0.9 * 3/5 = 0.54 (fails confidence threshold of 0.7)
    # For explicit, evidence_count = 4 -> base 0.9 * 4/5 = 0.72 (passes confidence threshold)
    candidate_month2_low_ev: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 2,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_month2_low_ev, {}, profile_age_weeks=8)
    assert res.status == "DISCARD"

    candidate_month2_low_conf: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 3,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_month2_low_conf, {}, profile_age_weeks=8)
    assert res.status == "DISCARD"

    candidate_month2_pass: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "val",
        "label": "explicit",
        "evidence_count": 4,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_month2_pass, {}, profile_age_weeks=8)
    assert res.status == "APPROVED"

def test_behavioral_override(enforcer):
    # Stated preference contradicts behavioral inference for 3+ sessions
    existing = {"session_continuity": "explicit_val"}
    
    # Under 3 sessions: does not trigger reconciliation yet (gets approved or goes to conflict checks)
    candidate_low_sessions: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "behavioral_val",
        "label": "inferred",
        "evidence_count": 2,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_low_sessions, existing, profile_age_weeks=1)
    assert res.status != "PROMPT_RECONCILIATION"

    # 3+ sessions: triggers PROMPT_RECONCILIATION
    candidate_override: MemoryCandidate = {
        "field_name": "session_continuity",
        "proposed_value": "behavioral_val",
        "label": "inferred",
        "evidence_count": 3,
        "evidence_text": ""
    }
    res = enforcer.validate(candidate_override, existing, profile_age_weeks=1)
    assert res.status == "PROMPT_RECONCILIATION"
