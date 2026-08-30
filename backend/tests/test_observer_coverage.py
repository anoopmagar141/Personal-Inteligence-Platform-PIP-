"""
What a conversation can teach PIP, and what the constitution says needs
confirming first.

Three separate faults met here:

  - skill_memory candidates were named "python_level" while the store keys on
    the skill's own name ("Python"), so a candidate never matched the row it
    meant and INSERTed a duplicate beside it.
  - gated_fields' "skill_memory.*.level" pattern could never match anything, so
    a constitutional prompt_confirm gate silently never fired.
  - active_projects and interaction_style were supported end to end downstream
    and never offered to the model, so a conversation could not teach PIP that
    a project had started or that the user wants shorter answers.
"""

import os

import pytest

from backend.core.constitution_enforcer import ConstitutionEnforcer, OBSERVER_WRITABLE_TABLES
from backend.memory import profile_store
from backend.stages import stage_11_observer as stage_11
from backend.stages import stage_12_validation_layer as stage_12
from backend.stages import stage_13_profile_update as stage_13


@pytest.fixture
def conn(tmp_path, db_key):
    connection = profile_store.get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    profile_store.initialize_schema(connection)
    profile_store.complete_onboarding(
        connection,
        name="BatMan",
        language_preference="English",
        skills=["Python"],
        interaction_style="detailed",
        current_project={"name": "PIP", "description": "Final year project"},
    )
    yield connection
    connection.close()


@pytest.fixture
def enforcer():
    return ConstitutionEnforcer(os.path.join("backend", "core", "constitutional.json"))


def _candidate(table, field, value, label="explicit", evidence_count=3):
    return {
        "target_table": table,
        "field_name": field,
        "proposed_value": value,
        "label": label,
        "evidence_count": evidence_count,
        "evidence_text": "the user said so",
    }


# --- column-qualified gate patterns -----------------------------------------


def test_column_qualified_gate_pattern_now_matches(enforcer):
    """
    "skill_memory.*.level" is three segments; a candidate only ever produced
    two, so the pattern matched nothing and skill levels were written with no
    confirmation at all.
    """
    assert enforcer._matches_gated_field(_candidate("skill_memory", "Python", "0.9")) is True


def test_ungated_tables_stay_ungated(enforcer):
    """
    The fix must widen the gate to what the constitution says, not to
    everything - preference_memory and topic_interests are deliberately not in
    gated_fields.
    """
    assert enforcer._matches_gated_field(_candidate("preference_memory", "answer_style", "terse")) is False
    assert enforcer._matches_gated_field(_candidate("topic_interests", "rust", "rust")) is False


@pytest.mark.parametrize("table, field", [
    ("goal_memory", "active_goals"),
    ("interaction_style", "value"),
    ("active_projects", "Thesis"),
    ("skill_memory", "Python"),
])
def test_every_constitutionally_gated_table_is_gated(enforcer, table, field):
    assert enforcer._matches_gated_field(_candidate(table, field, "x")) is True


def test_a_skill_candidate_is_no_longer_written_without_confirmation(conn, enforcer):
    result = stage_12.run(conn, _candidate("skill_memory", "Python", "0.9"), enforcer)
    assert result.status == "REQUIRES_CONFIRMATION"


# --- skill naming -----------------------------------------------------------


def test_a_skill_candidate_matches_the_row_onboarding_wrote(conn):
    """
    Onboarding stores "Python". The Observer used to be told to emit
    "python_level", which matched nothing.
    """
    existing = stage_12._fetch_existing_state(conn, _candidate("skill_memory", "Python", "0.9"))
    assert existing is not None
    assert existing["current_value"] == 0.5


def test_confirming_a_skill_updates_it_rather_than_duplicating(conn, enforcer):
    """
    The measured symptom of the naming mismatch: a profile holding both
    ("Python", 0.5) and ("python_level", 0.9) after a single session.
    """
    candidate = _candidate("skill_memory", "Python", "0.9")
    result = stage_12.run(conn, dict(candidate), enforcer)
    stage_13.run(conn, dict(candidate), result)
    stage_13.resolve_pending(conn, stage_13.list_pending(conn)[0]["id"])

    rows = conn.execute("SELECT name, level, source_label FROM skill_memory").fetchall()
    assert len(rows) == 1
    assert rows[0]["name"] == "Python"
    assert rows[0]["level"] == 0.9
    assert rows[0]["source_label"] == "user_verified"


def test_the_observer_is_no_longer_limited_to_three_skills():
    """
    The old fixed list was [python_level, docker_level, sql_level], so a Rust
    developer's Rust was unlearnable by construction.
    """
    assert isinstance(stage_11.APPROVED_MEMORY_FIELDS["skill_memory"], str)
    assert "python_level" not in stage_11._EXTRACTION_PROMPT_PREFIX


@pytest.mark.parametrize("value", ["advanced", "", None, "1.5", "-0.2", "very good"])
def test_an_unstorable_skill_level_is_dropped_cleanly(value):
    """
    skill_memory.level is REAL with CHECK (0.0 <= level <= 1.0). A word survives
    every check between extraction and the write, then fails that CHECK - which
    Stage 13 turns into a retry and an outcome of "failed", losing the signal
    with only a log line. Dropped here instead, as any other malformed
    candidate is.
    """
    raw = {
        "target_table": "skill_memory",
        "field_name": "Rust",
        "proposed_value": value,
        "label": "explicit",
        "evidence_text": "quoted",
    }
    assert stage_11._sanitize_memory_candidate(raw) is None


@pytest.mark.parametrize("value", ["0.0", "0.85", "1.0", 0.5])
def test_a_storable_skill_level_survives(value):
    raw = {
        "target_table": "skill_memory",
        "field_name": "Rust",
        "proposed_value": value,
        "label": "explicit",
        "evidence_text": "quoted",
    }
    assert stage_11._sanitize_memory_candidate(raw) is not None


# --- newly learnable tables -------------------------------------------------


def test_a_new_project_can_be_learned_from_a_conversation(conn, enforcer):
    candidate = _candidate("active_projects", "Thesis", "Writing the dissertation")
    result = stage_12.run(conn, dict(candidate), enforcer)
    assert result.status == "REQUIRES_CONFIRMATION", "projects are gated, never written silently"
    stage_13.run(conn, dict(candidate), result)
    stage_13.resolve_pending(conn, stage_13.list_pending(conn)[0]["id"])

    projects = {r["name"]: r["description"] for r in conn.execute("SELECT name, description FROM active_projects")}
    assert projects["Thesis"] == "Writing the dissertation"
    assert projects["PIP"] == "Final year project", "an existing project must not be disturbed"


def test_a_style_change_can_be_learned_from_a_conversation(conn, enforcer):
    candidate = _candidate("interaction_style", "value", "concise")
    result = stage_12.run(conn, dict(candidate), enforcer)
    assert result.status == "REQUIRES_CONFIRMATION"
    stage_13.run(conn, dict(candidate), result)
    stage_13.resolve_pending(conn, stage_13.list_pending(conn)[0]["id"])

    row = conn.execute("SELECT value, source_label FROM interaction_style WHERE id = 1").fetchone()
    assert row["value"] == "concise"
    assert row["source_label"] == "user_verified"


def test_a_learned_style_change_is_recorded_in_its_history(conn, enforcer):
    candidate = _candidate("interaction_style", "value", "concise")
    result = stage_12.run(conn, dict(candidate), enforcer)
    stage_13.run(conn, dict(candidate), result)
    stage_13.resolve_pending(conn, stage_13.list_pending(conn)[0]["id"])

    values = [h["value"] for h in profile_store.get_interaction_style_history(conn)]
    assert "concise" in values and "detailed" in values


# --- coverage ---------------------------------------------------------------


def test_the_only_tables_left_unoffered_are_the_two_with_reasons():
    """
    preferred_tools reaches memory through preference_memory.preferred_tools, a
    path that works end to end. document_access_patterns cannot come from a
    transcript at all - Stage 5 writes it, because retrieval is the only thing
    that knows which documents were consulted.
    """
    unoffered = OBSERVER_WRITABLE_TABLES - set(stage_11.APPROVED_MEMORY_FIELDS)
    assert unoffered == {"preferred_tools", "document_access_patterns"}


def test_every_offered_table_has_a_validation_handler(conn):
    """
    Stage 11's own note: naming a permitted-but-unimplemented table is worse
    than not naming it, because the candidate throws on write instead of being
    cleanly rejected. _fetch_existing_state returning None is fine (no row yet);
    an "Unhandled target_table" warning is not.
    """
    import logging

    for table in stage_11.APPROVED_MEMORY_FIELDS:
        field = "goal:1" if table == "goal_memory" else "something"
        logger = logging.getLogger("backend.stages.stage_12_validation_layer")
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logger.addHandler(handler)
        try:
            stage_12._fetch_existing_state(conn, _candidate(table, field, "0.5"))
        finally:
            logger.removeHandler(handler)

        assert not any("Unhandled target_table" in r.getMessage() for r in records), table
