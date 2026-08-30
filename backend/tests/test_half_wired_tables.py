"""
Four tables that were declared and then only half-connected.

  skill_contradiction_log      read and cleared by three call sites, written by none
  interaction_style_history    written from three places, read by none
  topic_interests              declared, permitted by the constitution, untouched
  document_access_patterns     the same, with no event source to write it

Each was stable in that state: a table nothing reads is a table nothing writes
to, which is a self-justifying kind of dead.
"""

import pytest

from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.memory import profile_store
from backend.stages import stage_04_memory_lookup as stage_04
from backend.stages import stage_07_context_assembly as stage_07
from backend.stages import stage_11_observer as stage_11
from backend.stages import stage_12_validation_layer as stage_12
from backend.stages import stage_13_profile_update as stage_13


@pytest.fixture
def conn(tmp_path, db_key):
    connection = profile_store.get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    profile_store.initialize_schema(connection)
    profile_store.complete_onboarding(connection, name="BatMan", language_preference="English")
    yield connection
    connection.close()


@pytest.fixture
def enforcer():
    import os
    return ConstitutionEnforcer(os.path.join("backend", "core", "constitutional.json"))


# --- skill_contradiction_log ------------------------------------------------


def _stated_skill(conn, name="python", level="0.4"):
    conn.execute(
        "INSERT INTO skill_memory (name, level, evidence_count, source_label, status) "
        "VALUES (?, ?, 5, 'explicit', 'active')",
        (name, level),
    )
    conn.commit()
    return conn.execute("SELECT id FROM skill_memory WHERE name = ?", (name,)).fetchone()["id"]


def _contradicting_skill_candidate():
    return {
        "target_table": "skill_memory",
        "field_name": "python",
        "proposed_value": "0.9",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Wrote a metaclass without looking it up",
    }


def test_discarded_skill_contradiction_is_recorded(conn):
    """
    The table was read by stage_12 and cleared by apply_verified_correction, and
    written by nothing - so a stated skill level that had gone stale could never
    be revisited, because every contradicting observation was discarded silently.
    """
    _stated_skill(conn)
    from backend.core.types import ValidationResult

    outcome = stage_13.run(
        conn, _contradicting_skill_candidate(), ValidationResult.DISCARD("threshold_violation")
    )

    assert outcome == "rejected"
    assert conn.execute("SELECT COUNT(*) FROM skill_contradiction_log").fetchone()[0] == 1


def test_skill_contradictions_are_stamped_with_the_session(conn):
    skill_id = _stated_skill(conn)
    profile_store.log_skill_contradiction(conn, skill_id, "observed otherwise")
    profile_store.begin_session(conn)
    profile_store.log_skill_contradiction(conn, skill_id, "observed otherwise again")

    stamps = [
        r["session_no"]
        for r in conn.execute("SELECT session_no FROM skill_contradiction_log ORDER BY id")
    ]
    assert stamps == [1, 2]


def test_skill_behavioral_signal_count_is_real_not_hardcoded_zero(conn):
    skill_id = _stated_skill(conn)
    for _ in range(2):
        profile_store.begin_session(conn)
        profile_store.log_skill_contradiction(conn, skill_id, "observed otherwise")

    existing = stage_12._fetch_existing_state(conn, _contradicting_skill_candidate())
    assert existing["behavioral_signal_count"] == 2
    assert existing["first_contradiction_date"] is not None


def test_skill_contradictions_count_sessions_not_rows(conn):
    skill_id = _stated_skill(conn)
    profile_store.begin_session(conn)
    for _ in range(4):
        profile_store.log_skill_contradiction(conn, skill_id, "same session")

    existing = stage_12._fetch_existing_state(conn, _contradicting_skill_candidate())
    assert existing["behavioral_signal_count"] == 1


def test_correcting_a_skill_clears_its_contradiction_history(conn):
    """
    apply_verified_correction already deleted from this table - one of the three
    call sites built around data nothing produced. Now there is something to
    clear.
    """
    from backend.core.types import ValidationResult

    skill_id = _stated_skill(conn)
    profile_store.log_skill_contradiction(conn, skill_id, "observed otherwise")

    profile_store.apply_verified_correction(
        conn,
        {"target_table": "skill_memory", "field_name": "python", "proposed_value": "0.9",
         "label": "user_verified", "evidence_count": 1, "evidence_text": ""},
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
    )

    assert conn.execute("SELECT COUNT(*) FROM skill_contradiction_log").fetchone()[0] == 0


# --- interaction_style_history ----------------------------------------------


def test_interaction_style_history_is_readable(conn):
    profile_store.set_interaction_style(conn, "concise", source_label="user_correction", timestamp="2026-01-01T00:00:00Z")
    profile_store.set_interaction_style(conn, "detailed", source_label="user_correction", timestamp="2026-01-02T00:00:00Z")

    history = profile_store.get_interaction_style_history(conn)
    values = [h["value"] for h in history]
    assert "concise" in values and "detailed" in values
    assert all("changed_at" in h for h in history)


def test_interaction_style_history_respects_its_limit(conn):
    for i in range(5):
        profile_store.set_interaction_style(conn, f"style-{i}", source_label="user_correction", timestamp=f"2026-01-0{i + 1}T00:00:00Z")

    assert len(profile_store.get_interaction_style_history(conn, limit=2)) == 2


# --- topic_interests --------------------------------------------------------


def _topic_candidate(topic="distributed systems", evidence_count=1):
    return {
        "target_table": "topic_interests",
        "field_name": topic,
        "proposed_value": topic,
        "label": "inferred",
        "evidence_count": evidence_count,
        "evidence_text": "Asked about consensus protocols again",
    }


def test_topic_interests_survives_the_write_path(conn):
    profile_store.write_approved_candidate(conn, _topic_candidate())

    row = conn.execute("SELECT topic, evidence_count, status FROM topic_interests").fetchone()
    assert row["topic"] == "distributed systems"
    assert row["status"] == "active"


def test_repeating_a_topic_reinforces_rather_than_duplicating(conn):
    profile_store.write_approved_candidate(conn, _topic_candidate())
    profile_store.write_approved_candidate(conn, _topic_candidate())

    rows = conn.execute("SELECT topic, evidence_count FROM topic_interests").fetchall()
    assert len(rows) == 1
    assert rows[0]["evidence_count"] == 2


def test_topic_interests_reaches_the_profile(conn):
    """
    Stage 11's comment gave "nothing reads them" as the reason not to write to
    them. This is that reason answered.
    """
    profile_store.write_approved_candidate(conn, _topic_candidate())

    topics = [r for r in profile_store.get_profile(conn) if r["table"] == "topic_interests"]
    assert [t["field"] for t in topics] == ["distributed systems"]


def test_topic_interests_reaches_the_assembled_context(conn):
    profile_store.write_approved_candidate(conn, _topic_candidate())

    block = stage_07._format_profile(profile_store.get_profile(conn), max_tokens=400)
    assert "Topics they keep returning to" in block
    assert "distributed systems" in block


def test_stage_12_can_look_up_a_topic(conn):
    """
    A handler here was the first of the three things Stage 11 said enabling
    these tables required - without it every candidate produced an "Unhandled
    target_table" warning.
    """
    assert stage_12._fetch_existing_state(conn, _topic_candidate()) is None

    profile_store.write_approved_candidate(conn, _topic_candidate())
    existing = stage_12._fetch_existing_state(conn, _topic_candidate())
    assert existing["current_value"] == "distributed systems"
    assert existing["evidence_count"] == 1


def test_a_repeat_topic_is_never_treated_as_a_conflict(conn, enforcer):
    """
    current_value equals the proposed value by construction for a set-membership
    table, so a topic can never contradict itself into TIER_2_REQUIRED.
    """
    profile_store.write_approved_candidate(conn, _topic_candidate())
    result = stage_12.run(conn, _topic_candidate(evidence_count=3), enforcer)
    assert result.status != "TIER_2_REQUIRED"


def test_topic_interests_is_offered_to_the_observer(conn):
    assert "topic_interests" in stage_11.APPROVED_MEMORY_FIELDS
    enum = stage_11._EXTRACTION_SCHEMA["properties"]["memory_candidates"]["items"]["properties"]["target_table"]["enum"]
    assert "topic_interests" in enum
    assert "topic_interests" in stage_11._EXTRACTION_PROMPT_PREFIX


def test_the_prompt_field_list_is_generated_not_restated():
    """
    The schema enum was derived from APPROVED_MEMORY_FIELDS under a comment
    claiming schema, prompt and write path could not drift - but the prompt text
    was a hand-written literal, so adding a table updated two of the three.
    """
    for table in stage_11.APPROVED_MEMORY_FIELDS:
        assert table in stage_11._EXTRACTION_PROMPT_PREFIX
    assert "__APPROVED_FIELDS__" not in stage_11._EXTRACTION_PROMPT_PREFIX


def test_topics_are_looked_up_for_topic_shaped_questions():
    assert "topic_interests" in stage_04.tables_for_category("technical_explanation")


# --- document_access_patterns -----------------------------------------------


def test_recording_document_access_counts_each_path_once_per_call(conn):
    assert profile_store.record_document_access(conn, ["/docs/a.md", "/docs/a.md", "/docs/b.md"]) == 2

    rows = {r["document_path"]: r["access_count"] for r in
            conn.execute("SELECT document_path, access_count FROM document_access_patterns")}
    assert rows == {"/docs/a.md": 1, "/docs/b.md": 1}


def test_repeated_access_increments_rather_than_duplicating(conn):
    profile_store.record_document_access(conn, ["/docs/a.md"])
    profile_store.record_document_access(conn, ["/docs/a.md"])

    rows = conn.execute("SELECT document_path, access_count FROM document_access_patterns").fetchall()
    assert len(rows) == 1
    assert rows[0]["access_count"] == 2


def test_recording_ignores_empty_paths(conn):
    assert profile_store.record_document_access(conn, [None, ""]) == 0


def test_recording_never_raises(conn):
    conn.close()
    assert profile_store.record_document_access(conn, ["/docs/a.md"]) == 0


def test_most_consulted_documents_reach_the_profile(conn):
    profile_store.record_document_access(conn, ["/docs/a.md"])

    docs = [r for r in profile_store.get_profile(conn) if r["table"] == "document_access_patterns"]
    assert [d["field"] for d in docs] == ["/docs/a.md"]


def test_stage_05_records_what_it_retrieved(conn, monkeypatch):
    """
    Stage 5 is the only thing that knows which documents were consulted - the
    Observer reads a transcript, and a transcript cannot say.
    """
    from backend.memory import vector_store
    from backend.stages import stage_05_rag_retrieval as stage_05

    monkeypatch.setattr(
        vector_store, "query",
        lambda *a, **kw: [{"chunk_text": "some text", "file_path": "/docs/spec.md"}],
    )

    stage_05.run(conn, "anything")

    row = conn.execute("SELECT document_path, access_count FROM document_access_patterns").fetchone()
    assert row["document_path"] == "/docs/spec.md"
    assert row["access_count"] == 1


def test_soft_delete_reaches_the_set_membership_tables(conn):
    profile_store.write_approved_candidate(conn, _topic_candidate())
    assert profile_store.soft_delete_profile_field(conn, "distributed systems") is True
    assert [r for r in profile_store.get_profile(conn) if r["table"] == "topic_interests"] == []
