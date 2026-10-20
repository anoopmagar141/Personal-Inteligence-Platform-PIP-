"""
#19 (BLUEPRINT card #19; MEMORY_BRAIN M-2): a fact that falls short of the Constitution's count is asked about,
not silently dropped, and a correction reads as an update.

What was wrong: after week 2 the Constitution needs the same fact in 2 chats (weeks 3-4), then 3 chats and
confidence 0.7 (month 2+), counted only when the exact wording comes back; in weeks 1-2 a fact the model labels
"inferred" is dropped. A candidate the evidence gate had accepted - the user's own words, supporting the claim - was
then thrown away with a log line, before any "ask the user" step. A correction a month in ("I switched to Helix") is
one sighting, so it was dropped the same way.

Now such a candidate becomes ONE question to the user (origin "shortfall"), never a write, at most two per chat, and
only for the tables that hold beliefs about the user. Driven through the real session-end path with a stand-in model
playing the Observer; everything after it is real.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.memory import candidate_store, profile_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_11_observer as observer
from backend.stages import stage_13_profile_update as stage_13


class _Model(BaseLLMProvider):
    def __init__(self, memory):
        self.answer = json.dumps({
            "memory_candidates": memory, "decision_candidates": [],
            "session_snapshot": {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
        })

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield self.answer

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


def _profile(tmp_path, db_key, *, weeks):
    conn = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Zarqa Venn", language_preference="English")
    first = (datetime.now(timezone.utc) - timedelta(weeks=weeks, days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("UPDATE profile_meta SET first_session_date = ? WHERE id = 1", (first,))
    conn.commit()
    return conn


@pytest.fixture
def week3(tmp_path, db_key):
    conn = _profile(tmp_path, db_key, weeks=3)
    yield conn
    conn.close()


@pytest.fixture
def month2(tmp_path, db_key):
    conn = _profile(tmp_path, db_key, weeks=9)
    yield conn
    conn.close()


@pytest.fixture
def week1(tmp_path, db_key):
    conn = _profile(tmp_path, db_key, weeks=0)
    yield conn
    conn.close()


def _c(table, field, value, quote, label="explicit"):
    return {"target_table": table, "field_name": field, "proposed_value": value, "label": label,
            "evidence_count": 1, "evidence_text": quote}


def _say(conn, *candidates, chat=None):
    transcript = "".join(f"User: {c['evidence_text']}\nAssistant: Noted.\n" for c in candidates)
    return observer.run_session_end(conn, transcript, _Model(list(candidates)), conversation_id=chat)


def _questions(conn):
    return [dict(r) for r in conn.execute(
        "SELECT target_table, field_name, proposed_value, origin, validation_status, state "
        "FROM memory_candidates_pending ORDER BY id")]


def _audit(conn):
    return [tuple(r) for r in conn.execute("SELECT stage, outcome, reason_code FROM governance_audit_log ORDER BY id")]


NEOVIM = _c("preference_memory", "preferred_tools", "Neovim", "I use Neovim for all my coding.")


# --- part 1: asked, not dropped --------------------------------------------------------------------------------


def test_a_supported_fact_seen_once_in_week_3_is_asked_about_not_dropped(week3):
    _say(week3, NEOVIM)

    assert _questions(week3) == [{"target_table": "preference_memory", "field_name": "preferred_tools",
                                  "proposed_value": "Neovim", "origin": "shortfall",
                                  "validation_status": "REQUIRES_CONFIRMATION", "state": "pending"}]
    assert week3.execute("SELECT COUNT(*) FROM preference_memory").fetchone()[0] == 0, "asked, never written"
    assert _audit(week3) == [(12, "deferred", "threshold_violation_week_3_4")]


def test_a_fact_the_model_labels_inferred_in_week_1_is_asked_about(week1):
    _say(week1, _c("preference_memory", "preferred_tools", "Neovim", "I use Neovim for all my coding.",
                   label="inferred"))

    assert [(q["proposed_value"], q["origin"]) for q in _questions(week1)] == [("Neovim", "shortfall")]
    assert _audit(week1) == [(12, "deferred", "threshold_violation_week_1_2")]


def test_a_fact_seen_once_in_month_2_is_asked_about(month2):
    _say(month2, NEOVIM)

    assert [(q["proposed_value"], q["origin"]) for q in _questions(month2)] == [("Neovim", "shortfall")]
    assert _audit(month2) == [(12, "deferred", "threshold_violation_month_2_plus_evidence")]


def test_confirming_the_question_writes_the_fact_as_the_users(week3):
    _say(week3, NEOVIM)
    question = candidate_store.list_memory_candidates(week3)[0]

    stage_13.resolve_pending(week3, question["id"])

    row = week3.execute("SELECT value, source_label FROM preference_memory WHERE name = 'preferred_tools'").fetchone()
    assert tuple(row) == ("Neovim", "user_verified")


def test_at_most_two_shortfall_questions_per_chat(week3):
    third = _c("preference_memory", "editor_theme", "dark", "I prefer dark themes in every editor.")
    _say(week3, NEOVIM, _c("preference_memory", "testing_framework", "pytest", "I always write my tests with pytest."),
         third)

    assert [q["proposed_value"] for q in _questions(week3)] == ["Neovim", "pytest"]
    assert _audit(week3)[-1] == (12, "rejected", "threshold_violation_week_3_4"), "past the cap: dropped, as before"


def test_the_cap_is_per_chat(week3):
    _say(week3, NEOVIM, _c("preference_memory", "testing_framework", "pytest", "I always write my tests with pytest."))
    _say(week3, _c("preference_memory", "editor_theme", "dark", "I prefer dark themes in every editor."))

    assert [q["proposed_value"] for q in _questions(week3)] == ["Neovim", "pytest", "dark"]


def test_the_same_fact_in_a_second_chat_is_not_asked_twice(week3):
    _say(week3, NEOVIM)
    _say(week3, NEOVIM)

    assert len(_questions(week3)) == 1


def test_a_topic_that_falls_short_is_still_dropped_not_asked(week1):
    # Topics, like the tool and document sets, record what came up, not a belief about the user; asking about each
    # would be nagging, and a topic raised in someone else's sentence (D-41) would become a question.
    _say(week1, _c("topic_interests", "vector clocks", "vector clocks",
                   "what is the right way to think about vector clocks in a small cluster?", label="inferred"))

    assert _questions(week1) == []
    assert _audit(week1) == [(12, "rejected", "threshold_violation_week_1_2")]


def test_a_candidate_the_gate_refused_is_not_asked_about(week3):
    _say(week3, _c("preference_memory", "preferred_tools", "Flask", "I've been comparing FastAPI and Flask."))

    assert _questions(week3) == []
    assert [a[:2] for a in _audit(week3)] == [(11, "rejected")]


def test_stage_13_on_its_own_still_drops_a_shortfall(week3):
    # Only the Observer's session-end pass asks (it knows the chat and the cap); any other caller is unchanged.
    from backend.core.types import ValidationResult

    outcome = stage_13.run(week3, dict(NEOVIM), ValidationResult.DISCARD("threshold_violation_week_3_4"))

    assert outcome == "rejected" and _questions(week3) == []


# --- part 2: a correction reads as an update -------------------------------------------------------------------


def _store_neovim(conn):
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('preferred_tools', 'Neovim', 5, 'explicit', 'active')"
    )
    conn.commit()


def test_a_correction_a_month_in_is_asked_about_with_the_stored_value(month2):
    _store_neovim(month2)

    _say(month2, _c("preference_memory", "preferred_tools", "Helix", "I switched to Helix last month."))

    pending = stage_13.list_pending(month2)
    assert [(q["proposed_value"], q["current_value"], q["origin"]) for q in pending] == [("Helix", "Neovim", "shortfall")]


def test_confirming_a_correction_replaces_the_stored_value(month2):
    _store_neovim(month2)
    _say(month2, _c("preference_memory", "preferred_tools", "Helix", "I switched to Helix last month."))

    stage_13.resolve_pending(month2, stage_13.list_pending(month2)[0]["id"])

    assert month2.execute("SELECT value FROM preference_memory WHERE name = 'preferred_tools'").fetchone()[0] == "Helix"


def test_a_question_with_nothing_stored_has_no_current_value(week3):
    _say(week3, NEOVIM)

    assert [q["current_value"] for q in stage_13.list_pending(week3)] == [None]
