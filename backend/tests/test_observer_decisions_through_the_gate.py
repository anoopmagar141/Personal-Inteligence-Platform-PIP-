"""
G-4 (BLUEPRINT; issue #3; owner decision DEC-7 = A, fix the code): the
Observer's decisions go through the evidence gate, and an immutable field name
cannot be stored as a preference.

What was wrong, with the evidence:

1. Decisions skipped the evidence gate (FREEZE_LIST §7.13 finding 1). A
   decision candidate was checked only for being grounded (its quote appears
   somewhere in the transcript, the assistant's turns included) and then
   logged on the signals the model itself claimed. §7.14 found four tentative
   remarks logged as decisions ("I'm not convinced" about Java twice, "probably
   not worth it" as "decided against rewriting in Elixir", "to stay with Go").
   W-1's long chats (§7.56) logged a friend's exam goal and a line the
   assistant said as the user's decisions.
2. An immutable field name could be stored as a preference (§7.13 finding 2).
   The Constitution refused name, language_preference and timezone only when
   the same table already held a value, so "I prefer French, please answer me
   in French" wrote preference_memory.language_preference = French and the
   prompt then showed two language preferences.

Driven through the real session-end path with a stand-in model playing the
Observer's LLM (the untrusted part); the quotes and decision texts below are
the model's own, from the recordings the card names. Everything after the
model is real: grounding, the evidence gate, the Constitution, Stage 13, the
decision log, and the audit log.
"""

import json

import pytest

from backend.core import evidence_gate
from backend.memory import governance_audit, profile_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_04_memory_lookup
from backend.stages import stage_11_observer as observer
from backend.tests.observer_cases import CASES

TRANSCRIPTS = {c["id"]: c["transcript"] for c in CASES}


class _Model(BaseLLMProvider):
    def __init__(self, memory=(), decisions=()):
        self.answer = json.dumps({
            "memory_candidates": list(memory), "decision_candidates": list(decisions),
            "session_snapshot": {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
        })

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield self.answer

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture
def conn(tmp_path, db_key):
    c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(c)
    profile_store.complete_onboarding(c, name="Zarqa Venn", language_preference="English", timezone="Asia/Kathmandu")
    yield c
    c.close()


def _decision(text, quote, *signals):
    return {"decision_text": text, "raw_quote": quote, "signals_found": list(signals)}


def _logged(conn):
    return [r["decision_text"] for r in conn.execute("SELECT decision_text FROM decision_log")]


def _queued(conn):
    return [r["decision_text"] for r in conn.execute("SELECT decision_text FROM decision_candidates_pending")]


# --- 1. decisions through the gate --------------------------------------------------

REASONING, COMMITMENT, ALTERNATIVE = "explicit_reasoning_in_conversation", "commitment_language", "alternative_considered"

# §7.14's four overstatements. The decision texts are the ones the 2026-09-28
# run logged (and, for the last, the 2026-10-12 recording's version of it);
# the quote is the user's turn the model cited.
NOT_CONVINCED = "My colleague wants us to move to Java but I'm not convinced."
OVERSTATED = [
    ("mixed_stack", _decision("I'm not convinced to move to Java.", NOT_CONVINCED, REASONING, COMMITMENT)),
    ("mixed_stack", _decision("I'm not convinced about moving to Java.", NOT_CONVINCED, REASONING, COMMITMENT)),
    ("mixed_stack", _decision("Decide whether to stay with Go or consider Java for the payments service.",
                              NOT_CONVINCED, REASONING, COMMITMENT)),
    ("trap_what_if", _decision("Decide against rewriting the backend in Elixir.", "Yeah, probably not worth it.",
                               REASONING, COMMITMENT)),
]


@pytest.mark.parametrize("case_id, decision", OVERSTATED, ids=[d["decision_text"][:40] for _, d in OVERSTATED])
def test_a_tentative_remark_is_not_logged_as_a_decision(conn, case_id, decision):
    observer.run_session_end(conn, TRANSCRIPTS[case_id], _Model(decisions=[decision]), conversation_id="chat-1")

    assert _logged(conn) == [] and _queued(conn) == []
    rows = [dict(r) for r in conn.execute("SELECT * FROM governance_audit_log")]
    assert [(r["stage"], r["outcome"], r["target_table"]) for r in rows] == [(11, "rejected", "decision_log")]
    assert rows[0]["reason_code"] in evidence_gate.REJECTION_STATES


# W-1's two long-chat near-misses (§7.56), the turns copied from the long-chat
# set (docs/eval/v2_2026-10-17/long_chats), the candidates from W-1's recording.
FRIENDS_GOAL = (
    "User: My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level "
    "cloud exam?\n"
    "Assistant: For an entry-level exam, two months of steady study is usually plenty, especially with the free "
    "practice questions.\n"
)
ASSISTANTS_ADVICE = (
    "User: Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. "
    "How should I name the tables for shared expenses?\n"
    "Assistant: Plain nouns that match what people say out loud work best: expense, share, member, settlement. "
    "Avoid abbreviations and keep one naming style for every table.\n"
)
NEAR_MISSES = [
    (FRIENDS_GOAL, _decision("pass the Azure Fundamentals exam by March",
                             "my friend wants to pass the Azure Fundamentals exam by March.",
                             REASONING, COMMITMENT, ALTERNATIVE)),
    (ASSISTANTS_ADVICE, _decision("Name tables for shared expenses in Lanternfish with plain nouns.",
                                  "Plain nouns that match what people say out loud work best: expense, share, "
                                  "member, settlement. Avoid abbreviations and keep one naming style for every table.",
                                  REASONING, COMMITMENT)),
]


@pytest.mark.parametrize("transcript, decision", NEAR_MISSES, ids=["a friend's goal", "the assistant's advice"])
def test_a_long_chat_near_miss_is_not_logged_as_the_users_decision(conn, transcript, decision):
    observer.run_session_end(conn, transcript, _Model(decisions=[decision]))

    assert _logged(conn) == [] and _queued(conn) == []


def test_a_decision_text_sharing_only_the_word_decided_with_the_quote_is_not_logged(conn):
    # The decision text is the model's paraphrase, not the user's words, so
    # "the quote mentions something in the decision" has to mean more than the
    # commitment phrase both of them contain.
    transcript = "User: I've decided to go to bed early tonight.\nAssistant: Sleep well.\n"
    decision = _decision("User decided to rewrite the backend in Elixir", "I've decided to go to bed early tonight.",
                         REASONING, COMMITMENT)

    observer.run_session_end(conn, transcript, _Model(decisions=[decision]))

    assert _logged(conn) == [] and _queued(conn) == []


# Decisions the user did state, which the gate must keep (each was logged
# before G-4 as well; this is the check that the gate did not shut the path).
STATED = [
    ("fact_postgres_decision", _decision("Move the database to Postgres before the next release.",
                                         "I've decided to move our database to Postgres before the next release.",
                                         REASONING, COMMITMENT)),
    ("mixed_goal_and_maybe", _decision("Decided to run a half marathon in April.",
                                       "I've decided to run a half marathon in April.", REASONING, COMMITMENT)),
    ("mixed_tools_and_question", _decision("I'll stay with Docker Compose on my VPS.", "Good, I'll stay put.",
                                           REASONING, COMMITMENT)),
]


@pytest.mark.parametrize("case_id, decision", STATED, ids=[c for c, _ in STATED])
def test_a_decision_the_user_stated_is_still_logged(conn, case_id, decision):
    observer.run_session_end(conn, TRANSCRIPTS[case_id], _Model(decisions=[decision]))

    assert _logged(conn) == [decision["decision_text"]]


# D-38 (FREEZE_LIST §7.60): the model often copies the turn together with its
# "User:" label, and the evidence ledger holds turns without it, so the quote
# was "not found". G-4's replays lost 7 of their 9 plain decisions that way,
# these three among them ("User: Good, I'll stay put.", "User: I've decided to
# move our database to Postgres before the next release.").
LABELLED = [(case_id, {**d, "raw_quote": "User: " + d["raw_quote"]}) for case_id, d in STATED]


@pytest.mark.parametrize("case_id, decision", LABELLED, ids=[c for c, _ in LABELLED])
def test_a_decision_quoted_with_its_user_label_is_still_logged(conn, case_id, decision):
    observer.run_session_end(conn, TRANSCRIPTS[case_id], _Model(decisions=[decision]))

    assert _logged(conn) == [decision["decision_text"]]


def test_a_decision_with_one_signal_is_still_queued_rather_than_logged(conn):
    decision = _decision("Decided to run a half marathon in April.", "I've decided to run a half marathon in April.",
                         COMMITMENT)

    observer.run_session_end(conn, TRANSCRIPTS["mixed_goal_and_maybe"], _Model(decisions=[decision]))

    assert _logged(conn) == [] and _queued(conn) == [decision["decision_text"]]


# --- 2. an immutable field name is not a preference -----------------------------------

SHADOWS = [
    ("language_preference", "French", "I prefer French, please answer me in French from now on."),
    ("timezone", "Central European Time", "I prefer Central European Time for all my times from now on."),
    ("name", "Zed", "I prefer to be called Zed from now on."),
    # The model writes field names itself; spelling one differently must not
    # make it a different field.
    ("Time Zone", "Central European Time", "I prefer Central European Time for all my times from now on."),
]


@pytest.mark.parametrize("field, value, quote", SHADOWS, ids=[s[0] for s in SHADOWS])
def test_an_immutable_field_name_is_not_stored_as_a_preference(conn, field, value, quote):
    transcript = f"User: {quote}\nAssistant: Noted.\n"
    candidate = {"target_table": "preference_memory", "field_name": field, "proposed_value": value,
                 "label": "explicit", "evidence_count": 1, "evidence_text": quote}

    result = observer.run_session_end(conn, transcript, _Model(memory=[candidate]))

    assert conn.execute("SELECT name, value FROM preference_memory").fetchall() == []
    assert conn.execute("SELECT COUNT(*) FROM memory_candidates_pending").fetchone()[0] == 0
    identity = conn.execute("SELECT name, language_preference, timezone FROM identity").fetchone()
    assert tuple(identity) == ("Zarqa Venn", "English", "Asia/Kathmandu")
    # The gate let it through; the Constitution is what refused it, and says so.
    assert [r["evidence_state"] for r in result["memory_results"]] == [evidence_gate.EvidenceState.EVIDENCE_SUFFICIENT]
    assert [(r["stage"], r["reason_code"]) for r in conn.execute(
        "SELECT stage, reason_code FROM governance_audit_log")] == [(12, "immutable_field")]


def test_a_preference_stored_under_an_immutable_name_before_g4_is_not_put_into_the_prompt(conn):
    # A profile from before this fix can already hold one.
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('language_preference', 'French', 1, 'explicit', 'active')"
    )
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('preferred_tools', 'Neovim', 1, 'explicit', 'active')"
    )
    conn.commit()

    shown = [(r["table"], r["field"], r["value"]) for r in stage_04_memory_lookup.run(conn, "personal_question")]

    assert ("identity", "language_preference", "English") in shown
    assert ("preference_memory", "preferred_tools", "Neovim") in shown
    assert ("preference_memory", "language_preference", "French") not in shown
    # Still listed where the user reviews their memory, so they can see it and delete it.
    assert ("preference_memory", "language_preference", "French") in [
        (r["table"], r["field"], r["value"]) for r in profile_store.get_profile(conn)]
