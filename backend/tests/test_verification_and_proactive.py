import datetime

import pytest

from backend.core import proactive
from backend.memory import candidate_store, profile_store, verification
from backend.stages import stage_13_profile_update as stage_13

# Every setting exercised here existed in config/settings.json and was read by
# no code at all before this: memory.verification_loop_frequency_sessions,
# memory.verification_loop_sample_size, memory.goal_decay_inactive_days,
# proactive.session_gap_trigger_hours and proactive.goal_inactive_trigger_days.


@pytest.fixture
def conn(tmp_path, db_key):
    connection = profile_store.get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    profile_store.initialize_schema(connection)
    profile_store.complete_onboarding(connection, name="BatMan", language_preference="English")
    yield connection
    connection.close()


def _days_ago(days: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _add_goal(conn, text: str, *, updated_days_ago: int) -> int:
    cur = conn.execute(
        "INSERT INTO goal_memory (goal_text, evidence_count, confidence, created_at, updated_at) "
        "VALUES (?, 1, 0.9, ?, ?)",
        (text, _days_ago(updated_days_ago), _days_ago(updated_days_ago)),
    )
    conn.commit()
    return int(cur.lastrowid)


# --- goal decay -------------------------------------------------------------


def test_decay_flags_only_goals_past_the_threshold(conn):
    fresh = _add_goal(conn, "Ship the viva demo", updated_days_ago=2)
    stale = _add_goal(conn, "Learn Rust", updated_days_ago=30)

    assert profile_store.decay_stale_goals(conn) == 1

    flags = dict(conn.execute("SELECT id, decay_flag FROM goal_memory"))
    assert flags[fresh] == 0
    assert flags[stale] == 1


def test_decay_is_idempotent(conn):
    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    assert profile_store.decay_stale_goals(conn) == 1
    assert profile_store.decay_stale_goals(conn) == 0


def test_decay_does_not_touch_completed_goals(conn):
    goal_id = _add_goal(conn, "Learn Rust", updated_days_ago=30)
    conn.execute("UPDATE goal_memory SET status = 'completed' WHERE id = ?", (goal_id,))
    conn.commit()

    assert profile_store.decay_stale_goals(conn) == 0


def test_stale_goals_are_marked_in_the_profile_not_hidden(conn):
    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    profile_store.decay_stale_goals(conn)

    goals = [r for r in profile_store.get_profile(conn) if r["table"] == "goal_memory"]
    assert len(goals) == 1, "a stale goal must still be listed - the context header promises a complete list"
    assert goals[0]["stale"] is True


def test_stale_marker_reaches_the_assembled_context(conn):
    from backend.stages import stage_07_context_assembly as stage_07

    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    profile_store.decay_stale_goals(conn)

    block = stage_07._format_profile(profile_store.get_profile(conn), max_tokens=400)
    assert "Learn Rust" in block
    assert "may no longer be current" in block


# --- verification loop ------------------------------------------------------


def test_verification_is_due_only_on_multiples_of_the_frequency(conn):
    assert verification.is_due(None) is False
    assert verification.is_due(0) is False
    assert verification.is_due(1) is False
    assert verification.is_due(29) is False
    assert verification.is_due(30) is True
    assert verification.is_due(60) is True


def test_verification_queues_the_sample_size(conn):
    for name in ("editor", "answer_style", "tone", "format"):
        profile_store.correct_profile_field(conn, name, "something")
    conn.execute("UPDATE preference_memory SET source_label = 'inferred'")
    conn.commit()

    created = verification.run_if_due(conn, 30)
    assert len(created) == 3  # memory.verification_loop_sample_size

    pending = stage_13.list_pending(conn)
    assert len(pending) == 3
    assert {p["origin"] for p in pending} == {"verification"}
    assert {p["validation_status"] for p in pending} == {"REQUIRES_CONFIRMATION"}


def test_verification_does_nothing_when_not_due(conn):
    profile_store.correct_profile_field(conn, "editor", "vim")
    conn.execute("UPDATE preference_memory SET source_label = 'inferred'")
    conn.commit()

    assert verification.run_if_due(conn, 29) == []
    assert stage_13.list_pending(conn) == []


def test_verification_skips_values_the_user_already_attested(conn):
    profile_store.correct_profile_field(conn, "editor", "vim")  # writes user_correction
    assert verification.select_fields(conn) == []


def test_verification_does_not_re_ask_something_already_queued(conn):
    profile_store.correct_profile_field(conn, "editor", "vim")
    conn.execute("UPDATE preference_memory SET source_label = 'inferred'")
    conn.commit()

    first = verification.run_if_due(conn, 30)
    assert len(first) == 1
    second = verification.run_if_due(conn, 60)
    assert second == []
    assert len(stage_13.list_pending(conn)) == 1


def test_verification_asks_about_the_least_confident_memory_first(conn):
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('confident', 'yes', 5, 'explicit', 'active')"
    )
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('doubtful', 'maybe', 1, 'inferred', 'active')"
    )
    conn.commit()

    assert verification.select_fields(conn, limit=1)[0]["field_name"] == "doubtful"


def test_confirming_a_verification_writes_it_back_as_user_verified(conn):
    """
    The constitution gives verification authority "overrides_observer_derived".
    Confirming has to actually upgrade the record, or the loop is just noise.
    """
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('answer_style', 'terse', 1, 'inferred', 'active')"
    )
    conn.commit()

    candidate_id = verification.run_if_due(conn, 30)[0]
    assert stage_13.resolve_pending(conn, candidate_id)["status"] == "resolved"

    row = conn.execute(
        "SELECT value, source_label, evidence_count FROM preference_memory WHERE name = 'answer_style'"
    ).fetchone()
    assert row["value"] == "terse", "confirming must reaffirm the stored value, never replace it"
    assert row["source_label"] == "user_verified"
    assert row["evidence_count"] == 5


def test_verification_survives_an_empty_profile(conn):
    assert verification.run_if_due(conn, 30) == []


# --- proactive triggers -----------------------------------------------------


def _set_last_session(conn, hours_ago: int) -> None:
    stamp = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE profile_meta SET last_session_date = ? WHERE id = 1", (stamp,))
    conn.commit()


def test_no_triggers_fire_on_a_fresh_profile(conn):
    assert proactive.evaluate(conn) == []


def test_session_gap_fires_past_the_threshold(conn):
    _set_last_session(conn, hours_ago=49)
    triggers = proactive.evaluate(conn)
    assert [t["trigger"] for t in triggers] == [proactive.SESSION_GAP]
    assert triggers[0]["threshold_hours"] == 48


def test_session_gap_does_not_fire_just_below_the_threshold(conn):
    _set_last_session(conn, hours_ago=47)
    assert proactive.evaluate(conn) == []


def test_inactive_goal_fires_and_names_the_goal(conn):
    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    _add_goal(conn, "Ship the viva demo", updated_days_ago=1)

    triggers = [t for t in proactive.evaluate(conn) if t["trigger"] == proactive.GOAL_INACTIVE]
    assert len(triggers) == 1
    assert triggers[0]["goal_text"] == "Learn Rust"
    assert triggers[0]["threshold_days"] == 14


def test_evaluate_is_deterministic_for_a_given_now(conn):
    """
    proactive_triggers.forbidden rules out model judgment of relevance and
    urgency. Nothing here should vary between two calls at the same instant.
    """
    _set_last_session(conn, hours_ago=100)
    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    now = datetime.datetime.now(datetime.timezone.utc)

    assert proactive.evaluate(conn, now=now) == proactive.evaluate(conn, now=now)


def test_evaluate_refreshes_goal_decay(conn):
    """
    A long-running process runs the startup decay pass once. Without this, a
    goal going stale afterwards would be reported as inactive by the trigger
    while still rendering in context as current.
    """
    _add_goal(conn, "Learn Rust", updated_days_ago=30)
    assert conn.execute("SELECT decay_flag FROM goal_memory").fetchone()["decay_flag"] == 0

    proactive.evaluate(conn)

    assert conn.execute("SELECT decay_flag FROM goal_memory").fetchone()["decay_flag"] == 1


def test_observer_candidates_keep_their_origin(conn):
    """
    The origin column has to distinguish the two questions, not just exist.
    """
    candidate_store.create_memory_candidate(
        conn,
        target_table="preference_memory",
        field_name="editor",
        proposed_value="vim",
        label="inferred",
        evidence_count=1,
        evidence_text="observed",
        validation_status="TIER_2_REQUIRED",
    )
    assert stage_13.list_pending(conn)[0]["origin"] == "observer"
