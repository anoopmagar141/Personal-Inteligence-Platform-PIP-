from datetime import datetime, timedelta, timezone

import pytest
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.core.types import MemoryCandidate, ValidationResult
from backend.memory.profile_store import get_connection, initialize_schema
from backend.memory import candidate_store, profile_store
from backend.stages import stage_12_validation_layer as stage_12
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


# --- Behavioral contradiction logging (DISCARD path) ---
#
# Security review finding: nothing in this codebase ever wrote to
# preference_contradiction_log outside test fixtures, so
# ConstitutionEnforcer's behavioral override trigger could never see real
# data and could never fire. These tests cover the fix: Stage 13 logs a
# contradiction on the DISCARD path instead of throwing the observation away.


def test_discard_of_contradicting_inferred_candidate_logs_contradiction(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, source_label, evidence_count) VALUES ('editor', 'vim', 'explicit', 5)"
    )
    db_conn.commit()
    pref_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'editor'").fetchone()["id"]

    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Observed using emacs",
    }
    outcome = stage_13.run(db_conn, candidate, ValidationResult.DISCARD("threshold_violation"))
    assert outcome == "rejected"

    rows = db_conn.execute(
        "SELECT contradiction_text FROM preference_contradiction_log WHERE preference_id = ?", (pref_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["contradiction_text"] == "Observed using emacs"


def test_discard_does_not_log_when_value_matches_existing(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, source_label, evidence_count) VALUES ('editor', 'vim', 'explicit', 5)"
    )
    db_conn.commit()

    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",  # same as stored - not a contradiction
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Still using vim",
    }
    stage_13.run(db_conn, candidate, ValidationResult.DISCARD("threshold_violation"))
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0]
    assert count == 0


def test_discard_does_not_log_when_label_is_not_inferred(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, source_label, evidence_count) VALUES ('editor', 'vim', 'explicit', 5)"
    )
    db_conn.commit()

    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "explicit",  # an explicit contradiction is a real conflict (TIER_2), not a behavioral one
        "evidence_count": 1,
        "evidence_text": "Said switched to emacs",
    }
    stage_13.run(db_conn, candidate, ValidationResult.DISCARD("threshold_violation"))
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0]
    assert count == 0


def test_discard_does_not_log_when_existing_source_is_itself_inferred(db_conn):
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, source_label, evidence_count) VALUES ('editor', 'vim', 'inferred', 2)"
    )
    db_conn.commit()

    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Observed using emacs",
    }
    stage_13.run(db_conn, candidate, ValidationResult.DISCARD("threshold_violation"))
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0]
    assert count == 0


def test_discard_does_not_log_when_no_existing_preference(db_conn):
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Observed using emacs",
    }
    stage_13.run(db_conn, candidate, ValidationResult.DISCARD("threshold_violation"))
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0]
    assert count == 0


def test_discard_does_not_log_for_non_preference_table(db_conn):
    db_conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en-US', 'UTC')")
    db_conn.commit()

    candidate: MemoryCandidate = {
        "target_table": "identity",
        "field_name": "name",
        "proposed_value": "Bob",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "test",
    }
    stage_13.run(db_conn, candidate, ValidationResult.HARD_REJECT("immutable_field"))
    count = db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0]
    assert count == 0


def test_behavioral_override_fires_end_to_end_after_repeated_discards(db_conn):
    # The defense artifact: proof the governance mechanism actually executes
    # end-to-end now, driven entirely by what Stage 12/13 themselves write -
    # not a hand-set column or hand-seeded log row. Before this fix, this
    # sequence could never reach PROMPT_RECONCILIATION no matter how many
    # times a user's behavior contradicted a stated preference.
    db_conn.execute(
        "INSERT INTO profile_meta (id, schema_version, constitution_version, first_session_date) VALUES (1, '1.0', '1.0', ?)",
        ((datetime.now(timezone.utc) - timedelta(weeks=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),)
    )
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, source_label, evidence_count) VALUES ('editor', 'vim', 'explicit', 5)"
    )
    db_conn.commit()

    import os
    enforcer = ConstitutionEnforcer(os.path.join("backend", "core", "constitutional.json"))

    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "emacs",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Observed using emacs this session",
    }

    # Month-2+ profile: a lone inferred candidate (confidence caps at 0.4)
    # can never clear the 0.7 threshold, so every one of these is DISCARDed
    # today - and each DISCARD should now log a contradiction instead of
    # throwing the observation away.
    #
    # One session per iteration, because that is what the real system does:
    # Rule 3 pins the Observer to session end, so a field can produce at most
    # one contradiction per session. The override counts DISTINCT sessions
    # (see stage_12._fetch_existing_state) - looping without advancing the
    # session would be asserting that three contradictions in one conversation
    # satisfy a rule that asks for three separate ones, which is the bug that
    # counting made possible.
    for _ in range(3):
        profile_store.begin_session(db_conn)
        result = stage_12.run(db_conn, dict(candidate), enforcer)
        assert result.status == "DISCARD"
        outcome = stage_13.run(db_conn, dict(candidate), result)
        assert outcome == "rejected"

    pref_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'editor'").fetchone()["id"]
    logged = db_conn.execute(
        "SELECT COUNT(*) FROM preference_contradiction_log WHERE preference_id = ?", (pref_id,)
    ).fetchone()[0]
    assert logged == 3

    # Not enough elapsed time yet - all 3 rows were just inserted "now".
    result = stage_12.run(db_conn, dict(candidate), enforcer)
    assert result.status != "PROMPT_RECONCILIATION"

    # Backdate the earliest row past trigger_days (14), simulating the first
    # contradiction having actually happened two weeks ago.
    old_date = (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db_conn.execute(
        "UPDATE preference_contradiction_log SET created_at = ? WHERE id = ("
        "  SELECT id FROM preference_contradiction_log WHERE preference_id = ? ORDER BY created_at ASC LIMIT 1"
        ")",
        (old_date, pref_id),
    )
    db_conn.commit()

    # Both trigger_sessions (3) and trigger_days (14) are now real,
    # derived entirely from what Stage 13 itself wrote.
    final_result = stage_12.run(db_conn, dict(candidate), enforcer)
    assert final_result.status == "PROMPT_RECONCILIATION"

    final_outcome = stage_13.run(db_conn, dict(candidate), final_result)
    assert final_outcome == "pending"
    pending = candidate_store.list_memory_candidates(db_conn)
    assert len(pending) == 1
    assert pending[0]["validation_status"] == "PROMPT_RECONCILIATION"


# --- Resolving what run() parked -------------------------------------------
# Before these, every pending candidate was written and then unreachable: the
# whole review queue had no read or resolve path outside candidate_store's own
# unit tests.


def _park(db_conn, status, **overrides) -> int:
    candidate: MemoryCandidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "inferred",
        "evidence_count": 2,
        "evidence_text": "Used hjkl repeatedly",
    }
    candidate.update(overrides)
    assert stage_13.run(db_conn, candidate, status) == "pending"
    return candidate_store.list_memory_candidates(db_conn)[0]["id"]


@pytest.mark.parametrize("status_factory, expected_label", [
    (lambda: ValidationResult.REQUIRES_CONFIRMATION("gated_field"), "user_verified"),
    (lambda: ValidationResult.PROMPT_RECONCILIATION("behavioral_override"), "user_correction"),
    (lambda: ValidationResult.TIER_2_REQUIRED("high_confidence_conflict"), "user_correction"),
])
def test_resolve_pending_applies_as_verified_correction(db_conn, status_factory, expected_label):
    """
    All three pending statuses must be resolvable. TIER_2_REQUIRED is the one
    that could not be: apply_verified_correction raised on it, so a third of
    the queue was write-path-less.
    """
    candidate_id = _park(db_conn, status_factory())

    result = stage_13.resolve_pending(db_conn, candidate_id)
    assert result["status"] == "resolved"
    assert result["target_table"] == "preference_memory"

    row = db_conn.execute(
        "SELECT value, evidence_count, source_label FROM preference_memory WHERE name = 'editor'"
    ).fetchone()
    assert row["value"] == "vim"
    assert row["source_label"] == expected_label
    # Forced to maximum confidence - a user decision outranks the candidate's
    # own evidence_count of 2.
    assert row["evidence_count"] == 5

    assert stage_13.list_pending(db_conn) == []


def test_resolve_pending_is_not_repeatable(db_conn):
    candidate_id = _park(db_conn, ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    stage_13.resolve_pending(db_conn, candidate_id)

    with pytest.raises(LookupError):
        stage_13.resolve_pending(db_conn, candidate_id)


def test_dismiss_pending_writes_nothing(db_conn):
    candidate_id = _park(db_conn, ValidationResult.TIER_2_REQUIRED("high_confidence_conflict"))

    assert stage_13.dismiss_pending(db_conn, candidate_id)["status"] == "dismissed"
    assert stage_13.list_pending(db_conn) == []
    assert db_conn.execute("SELECT COUNT(*) FROM preference_memory WHERE name = 'editor'").fetchone()[0] == 0
    # A rejection must not count toward the behavioral override, whose entire
    # purpose is to decide when to ask the user again.
    assert db_conn.execute("SELECT COUNT(*) FROM preference_contradiction_log").fetchone()[0] == 0


def test_unknown_candidate_is_a_lookup_error(db_conn):
    with pytest.raises(LookupError):
        stage_13.resolve_pending(db_conn, 4242)
    with pytest.raises(LookupError):
        stage_13.dismiss_pending(db_conn, 4242)


def test_unapplicable_candidate_stays_pending(db_conn):
    """
    A candidate the write path cannot accept must not be consumed by the failed
    attempt - it is still in the queue, so the caller has to be told that
    rather than "no such candidate".

    Uses an immutable identity field, which apply_verified_correction refuses
    permanently and by design. This test used to use a goal named
    "active_goals", which was unapplicable for a much worse reason - the write
    path and the Observer disagreed about how a goal field is spelled, so every
    goal PIP ever proposed was unresolvable. That is now fixed (see
    test_goal_candidate_from_the_observer_can_be_confirmed below), which is why
    this test needed a genuinely unapplicable candidate instead.
    """
    candidate_id = _park(
        db_conn,
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
        target_table="identity",
        field_name="name",
        proposed_value="Bruce",
    )

    with pytest.raises(ValueError):
        stage_13.resolve_pending(db_conn, candidate_id)

    assert len(stage_13.list_pending(db_conn)) == 1
    assert stage_13.list_pending(db_conn)[0]["id"] == candidate_id


def test_goal_candidate_from_the_observer_can_be_confirmed(db_conn):
    """
    The regression this fix exists for. stage_11.APPROVED_MEMORY_FIELDS spells
    goal fields "active_goals" / "project_objectives" - the only spelling the
    Observer produces - and every goal write path rejected them outright. A goal
    could be extracted, validated, queued and shown to the user, and then fail
    on confirmation with no way to ever apply it.
    """
    candidate_id = _park(
        db_conn,
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
        target_table="goal_memory",
        field_name="active_goals",
        proposed_value="Finish the PIP write-up",
    )

    assert stage_13.resolve_pending(db_conn, candidate_id)["status"] == "resolved"
    assert stage_13.list_pending(db_conn) == []

    row = db_conn.execute(
        "SELECT goal_text, confidence, evidence_count, decay_flag, status FROM goal_memory"
    ).fetchone()
    assert row["goal_text"] == "Finish the PIP write-up"
    assert row["confidence"] == 1.0
    assert row["evidence_count"] == 5
    assert row["decay_flag"] == 0
    assert row["status"] == "active"


def test_confirming_the_same_goal_twice_does_not_duplicate_it(db_conn):
    """
    Without an id, a goal is identified by its text - so a second confirmation
    of the same goal has to find the first one rather than insert a twin.
    """
    for _ in range(2):
        candidate_id = _park(
            db_conn,
            ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
            target_table="goal_memory",
            field_name="project_objectives",
            proposed_value="Finish the PIP write-up",
        )
        stage_13.resolve_pending(db_conn, candidate_id)

    assert db_conn.execute("SELECT COUNT(*) FROM goal_memory").fetchone()[0] == 1


def test_confirming_a_goal_refreshes_its_decay_clock(db_conn):
    """
    decay_stale_goals reads updated_at. Clearing decay_flag without moving the
    clock would let the very next decay pass re-flag a goal the user had just
    confirmed - the two are only meaningful together.
    """
    from backend.memory import profile_store

    db_conn.execute(
        "INSERT INTO goal_memory (goal_text, evidence_count, confidence, decay_flag, created_at, updated_at) "
        "VALUES ('Finish the PIP write-up', 1, 0.4, 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    candidate_id = _park(
        db_conn,
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
        target_table="goal_memory",
        field_name="active_goals",
        proposed_value="Finish the PIP write-up",
    )
    stage_13.resolve_pending(db_conn, candidate_id)

    assert db_conn.execute("SELECT decay_flag FROM goal_memory").fetchone()["decay_flag"] == 0
    assert profile_store.decay_stale_goals(db_conn) == 0, "a just-confirmed goal must not decay again"


def test_editing_an_existing_goal_by_id_still_works(db_conn):
    """
    The "goal:<id>" handle get_profile hands out is the other half of the
    convention and must keep addressing that exact row - making the id optional
    must not make it ignored.
    """
    db_conn.execute(
        "INSERT INTO goal_memory (goal_text, evidence_count, confidence, created_at, updated_at) "
        "VALUES ('Old wording', 1, 0.4, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()
    goal_id = db_conn.execute("SELECT id FROM goal_memory").fetchone()["id"]

    candidate_id = _park(
        db_conn,
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
        target_table="goal_memory",
        field_name=f"goal:{goal_id}",
        proposed_value="Better wording",
    )
    stage_13.resolve_pending(db_conn, candidate_id)

    rows = db_conn.execute("SELECT id, goal_text FROM goal_memory").fetchall()
    assert len(rows) == 1, "editing by id must update the row, not add one"
    assert rows[0]["id"] == goal_id
    assert rows[0]["goal_text"] == "Better wording"


# --- the queue asks each question once --------------------------------------
# Gated fields re-queue on every session that mentions them. Measured before
# this: three identical rows after three sessions, so the user was asked the
# same thing three times and confirming one left two live twins behind it.


def _pending_candidate(**overrides):
    candidate: MemoryCandidate = {
        "target_table": "goal_memory",
        "field_name": "active_goals",
        "proposed_value": "Finish the PIP write-up",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "User said so",
    }
    candidate.update(overrides)
    return candidate


def test_the_same_question_is_only_queued_once(db_conn):
    for _ in range(3):
        assert stage_13.run(
            db_conn,
            _pending_candidate(),
            ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
        ) == "pending"

    assert len(stage_13.list_pending(db_conn)) == 1


def test_a_different_value_is_a_different_question(db_conn):
    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    stage_13.run(
        db_conn,
        _pending_candidate(proposed_value="Start the PIP write-up"),
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
    )

    assert len(stage_13.list_pending(db_conn)) == 2


def test_a_different_field_is_a_different_question(db_conn):
    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    stage_13.run(
        db_conn,
        _pending_candidate(field_name="project_objectives"),
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
    )

    assert len(stage_13.list_pending(db_conn)) == 2


def test_the_same_field_name_in_another_table_is_a_different_question(db_conn):
    """
    Field names are only unique within their own table, so the table has to be
    part of the key - otherwise one of two unrelated memories gets dropped.
    """
    stage_13.run(
        db_conn,
        _pending_candidate(target_table="preference_memory", field_name="focus", proposed_value="deep"),
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
    )
    stage_13.run(
        db_conn,
        _pending_candidate(target_table="skill_memory", field_name="focus", proposed_value="deep"),
        ValidationResult.REQUIRES_CONFIRMATION("gated_field"),
    )

    assert len(stage_13.list_pending(db_conn)) == 2


def test_an_answered_question_can_be_asked_again(db_conn):
    """
    Dedup is against UNANSWERED questions only. Once the user has resolved or
    dismissed one, a later observation is new information, and suppressing it
    against an answer from weeks ago would be the silent discard this queue
    exists to prevent.
    """
    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    stage_13.dismiss_pending(db_conn, stage_13.list_pending(db_conn)[0]["id"])

    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    assert len(stage_13.list_pending(db_conn)) == 1


def test_dedup_keeps_the_oldest_question_rather_than_restarting_it(db_conn):
    """
    The queue is ordered oldest-first, so a repeat must not push the original
    down it - the question the user has been waiting longest on stays at the
    front.
    """
    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    original = stage_13.list_pending(db_conn)[0]

    stage_13.run(db_conn, _pending_candidate(), ValidationResult.REQUIRES_CONFIRMATION("gated_field"))
    after = stage_13.list_pending(db_conn)[0]

    assert after["id"] == original["id"]
    assert after["created_at"] == original["created_at"]
