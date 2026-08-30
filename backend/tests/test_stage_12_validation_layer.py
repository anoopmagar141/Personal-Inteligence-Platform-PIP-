import pytest
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from backend.core.types import MemoryCandidate
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.stages.stage_12_validation_layer import run, reinforce_evidence
from backend.memory import profile_store
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
    # Setup explicit preference memory with behavioral override conditions.
    # behavioral_signal_count is derived from COUNT(*) over
    # preference_contradiction_log now (that column is no longer read at
    # all - see stage_12_validation_layer._fetch_existing_state), so the
    # "3+ sessions" condition is represented by 3 real log rows, not a
    # hand-set column value.
    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label)
        VALUES ('vim_keybindings', 'false', 'explicit')
    """)
    row_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'vim_keybindings'").fetchone()["id"]

    # Three contradiction rows, oldest > 14 days ago (trigger_days is 14).
    dates = [
        (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    for d in dates:
        db_conn.execute("""
            INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at)
            VALUES (?, 'User typed hjkl', ?)
        """, (row_id, d))
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


def test_prompt_reconciliation_does_not_fire_below_trigger_sessions(db_conn, enforcer):
    # Same shape as test_prompt_reconciliation but only 2 contradiction rows
    # (trigger_sessions is 3) - must not trigger yet.
    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label)
        VALUES ('vim_keybindings', 'false', 'explicit')
    """)
    row_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'vim_keybindings'").fetchone()["id"]

    for days_ago in (15, 8):
        d = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        db_conn.execute("""
            INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at)
            VALUES (?, 'User typed hjkl', ?)
        """, (row_id, d))
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
    assert result.status != "PROMPT_RECONCILIATION"


def test_fetch_existing_state_derives_behavioral_signal_count_from_log(db_conn):
    from backend.stages.stage_12_validation_layer import _fetch_existing_state

    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label)
        VALUES ('vim_keybindings', 'false', 'explicit')
    """)
    row_id = db_conn.execute("SELECT id FROM preference_memory WHERE name = 'vim_keybindings'").fetchone()["id"]
    # A stale/legacy value in the column itself must be ignored entirely -
    # the log is the only source of truth now.
    db_conn.execute("UPDATE preference_memory SET behavioral_signal_count = 99 WHERE id = ?", (row_id,))

    for _ in range(2):
        db_conn.execute(
            "INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at) VALUES (?, 'x', ?)",
            (row_id, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
    db_conn.commit()

    candidate = {"target_table": "preference_memory", "field_name": "vim_keybindings"}
    existing = _fetch_existing_state(db_conn, candidate)
    assert existing["behavioral_signal_count"] == 2


def test_fetch_existing_state_reports_zero_signal_count_with_no_log_rows(db_conn):
    from backend.stages.stage_12_validation_layer import _fetch_existing_state

    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label)
        VALUES ('vim_keybindings', 'false', 'explicit')
    """)
    db_conn.commit()

    candidate = {"target_table": "preference_memory", "field_name": "vim_keybindings"}
    existing = _fetch_existing_state(db_conn, candidate)
    assert existing["behavioral_signal_count"] == 0
    assert existing["first_contradiction_date"] is None

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


def test_reinforce_evidence_first_observation_of_an_unstored_field_stays_at_one(db_conn):
    # One session of evidence IS evidence_count 1 - reinforcement only has
    # something to add from the second session onward. See
    # test_reinforcement_accumulates_for_a_field_never_stored below.
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


# --- trigger_sessions means sessions, not rows ------------------------------


def _seed_contradicted_preference(db_conn, session_numbers):
    """
    A stated preference plus one contradiction row per entry in session_numbers,
    dated 15/8/1 days ago so the trigger_days condition (14) is always met and
    only the session count is under test.
    """
    db_conn.execute("""
        INSERT INTO preference_memory (name, value, source_label)
        VALUES ('vim_keybindings', 'false', 'explicit')
    """)
    row_id = db_conn.execute(
        "SELECT id FROM preference_memory WHERE name = 'vim_keybindings'"
    ).fetchone()["id"]

    ages = [15, 8, 1, 1, 1]
    for i, session_no in enumerate(session_numbers):
        created = (datetime.now(timezone.utc) - timedelta(days=ages[i])).strftime("%Y-%m-%dT%H:%M:%SZ")
        db_conn.execute("""
            INSERT INTO preference_contradiction_log (preference_id, contradiction_text, session_no, created_at)
            VALUES (?, 'User typed hjkl', ?, ?)
        """, (row_id, session_no, created))
    db_conn.commit()

    return {
        "target_table": "preference_memory",
        "field_name": "vim_keybindings",
        "proposed_value": "true",
        "label": "inferred",
        "evidence_count": 1,
        "evidence_text": "Used hjkl",
    }


def test_three_contradictions_in_one_session_do_not_trigger_the_override(db_conn, enforcer):
    """
    The constitution asks for trigger_sessions (3) - three separate sessions.
    Counting rows meant one unusual conversation could satisfy it on its own.
    """
    candidate = _seed_contradicted_preference(db_conn, [7, 7, 7])
    assert run(db_conn, candidate, enforcer).status != "PROMPT_RECONCILIATION"


def test_three_contradictions_across_three_sessions_trigger_the_override(db_conn, enforcer):
    candidate = _seed_contradicted_preference(db_conn, [5, 6, 7])
    assert run(db_conn, candidate, enforcer).status == "PROMPT_RECONCILIATION"


def test_repeats_within_sessions_still_count_once_each(db_conn, enforcer):
    """Five rows, two sessions - fewer distinct sessions than the trigger."""
    candidate = _seed_contradicted_preference(db_conn, [5, 5, 6, 6, 6])
    assert run(db_conn, candidate, enforcer).status != "PROMPT_RECONCILIATION"


def test_unstamped_legacy_rows_keep_counting_one_each(db_conn, enforcer):
    """
    Rows predating the session_no column are NULL and were written under
    count-the-rows semantics. They must keep behaving that way rather than
    collapsing into a single "unknown session" and silently disarming an
    override that was already armed on an upgraded database.
    """
    candidate = _seed_contradicted_preference(db_conn, [None, None, None])
    assert run(db_conn, candidate, enforcer).status == "PROMPT_RECONCILIATION"


# --- Reinforcement accumulates across sessions ------------------------------
# Before this, reinforce_evidence() could only raise evidence_count by reading
# an already-stored row, and storing the row is what the thresholds blocked.
# From week 3 onward that was a deadlock: nothing new could ever be learned.


def _signal(**overrides):
    candidate = {
        "target_table": "preference_memory",
        "field_name": "answer_style",
        "proposed_value": "terse",
        "label": "explicit",
        "evidence_count": 1,
        "evidence_text": "User asked for short answers",
    }
    candidate.update(overrides)
    return candidate


def _observe_across_sessions(db_conn, count, **overrides):
    """One reinforce_evidence() call per session, as Stage 11 does."""
    last = None
    for _ in range(count):
        profile_store.begin_session(db_conn)
        last = reinforce_evidence(db_conn, _signal(**overrides))
    return last


def test_reinforcement_accumulates_for_a_field_never_stored(db_conn):
    assert _observe_across_sessions(db_conn, 1)["evidence_count"] == 1
    assert _observe_across_sessions(db_conn, 1)["evidence_count"] == 2
    assert _observe_across_sessions(db_conn, 1)["evidence_count"] == 3


def test_reinforcement_does_not_move_within_a_single_session(db_conn):
    """
    Rule 3 gives one Observer pass per session, but a retry or a drained
    pending_observer row must not inflate the count. Sessions are counted, not
    rows, so repeats inside one session collapse.
    """
    profile_store.begin_session(db_conn)
    first = reinforce_evidence(db_conn, _signal())
    second = reinforce_evidence(db_conn, _signal())
    third = reinforce_evidence(db_conn, _signal())
    assert first["evidence_count"] == second["evidence_count"] == third["evidence_count"] == 1


def test_reinforcement_is_scoped_to_the_exact_value(db_conn):
    _observe_across_sessions(db_conn, 3, proposed_value="terse")
    other = _observe_across_sessions(db_conn, 1, proposed_value="verbose")
    assert other["evidence_count"] == 1


def test_reinforcement_is_scoped_to_the_field(db_conn):
    _observe_across_sessions(db_conn, 3, field_name="answer_style")
    other = _observe_across_sessions(db_conn, 1, field_name="editor")
    assert other["evidence_count"] == 1


def test_reinforcement_never_lowers_a_stored_count(db_conn):
    """
    A stored row that already claims more evidence than the log has seen keeps
    its count - apply_verified_correction pins a user-confirmed value to 5, and
    a couple of observations must not talk that back down.
    """
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('answer_style', 'terse', 5, 'user_verified', 'active')"
    )
    db_conn.commit()

    reinforced = _observe_across_sessions(db_conn, 2)
    assert reinforced["evidence_count"] == 6


def test_reinforcement_still_ignores_a_contradicting_value(db_conn):
    """
    Repeat observations of a value that disagrees with what is stored must not
    accumulate into confidence. That path escalates to the user through the
    behavioral override instead, which is the whole point of having one.
    """
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('answer_style', 'verbose', 4, 'explicit', 'active')"
    )
    db_conn.commit()

    reinforced = _observe_across_sessions(db_conn, 5, proposed_value="terse")
    assert reinforced["evidence_count"] == 1


def test_explicit_signal_clears_week_3_4_on_its_second_session(db_conn, enforcer):
    """
    The deadlock, end to end. Six sessions of the same explicit statement used
    to produce six DISCARDs with evidence_count stuck at 1.
    """
    db_conn.execute(
        "UPDATE profile_meta SET first_session_date = ? WHERE id = 1",
        ((datetime.now(timezone.utc) - timedelta(weeks=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),),
    )
    db_conn.commit()

    statuses = []
    for _ in range(3):
        profile_store.begin_session(db_conn)
        candidate = reinforce_evidence(db_conn, _signal())
        statuses.append(run(db_conn, candidate, enforcer).status)

    assert statuses == ["DISCARD", "APPROVED", "APPROVED"]


def test_explicit_signal_clears_month_2_on_its_fourth_session(db_conn, enforcer):
    """
    Month 2+ needs evidence >= 3 AND confidence >= 0.7. An explicit label
    computes 0.9 * min(ec, 5) / 5, so it takes four sessions (0.72), not three
    (0.54) - the evidence and confidence rules bind at different points.
    """
    db_conn.execute(
        "UPDATE profile_meta SET first_session_date = ? WHERE id = 1",
        ((datetime.now(timezone.utc) - timedelta(weeks=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),),
    )
    db_conn.commit()

    statuses = []
    for _ in range(5):
        profile_store.begin_session(db_conn)
        candidate = reinforce_evidence(db_conn, _signal())
        statuses.append(run(db_conn, candidate, enforcer).status)

    assert statuses == ["DISCARD", "DISCARD", "DISCARD", "APPROVED", "APPROVED"]


def test_inferred_signal_still_cannot_auto_write_after_month_2(db_conn, enforcer):
    """
    Deliberately NOT fixed by reinforcement. An inferred label caps confidence
    at 0.4 however many sessions accumulate, and month_2_plus requires 0.7. That
    is the constitution's confidence model: something PIP merely inferred should
    reach the profile through the user, not through repetition.
    """
    db_conn.execute(
        "UPDATE profile_meta SET first_session_date = ? WHERE id = 1",
        ((datetime.now(timezone.utc) - timedelta(weeks=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),),
    )
    db_conn.commit()

    for _ in range(8):
        profile_store.begin_session(db_conn)
        candidate = reinforce_evidence(db_conn, _signal(label="inferred"))
        assert run(db_conn, candidate, enforcer).status == "DISCARD"

    assert candidate["evidence_count"] == 8
