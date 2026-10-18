"""
D-33 (BLUEPRINT card D-33; FREEZE_LIST §7.55): a statement about someone else is not the user's topic.

What was wrong: in V-2's longest chat, "My friend wants to pass the Azure Fundamentals exam by March" passed the
evidence gate as the user's topic_interests (field "exam") and was queued as a question to the user. Every other
table's support contract needs first-person language ("I prefer", "I'm learning"), and that is what stops "My
sister is learning Rust"; topic_interests needs none, because a question is as good as an assertion for "this came
up". So a sentence about another person passed as the user's own interest.

The rule: a topic is the user's when they ASK about it or SAY it in the first person. The third-person wordings
below are in no list in the gate (the owner's rule: test with wording no list was written for), and neither are
the first-person ones that must still pass.
"""

import json

import pytest

from backend.core.evidence_gate import EvidenceLedger, EvidenceState, adjudicate
from backend.memory import profile_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_11_observer as observer


def _topic(field, value, quote):
    return {"target_table": "topic_interests", "field_name": field, "proposed_value": value, "label": "explicit",
            "evidence_count": 1, "evidence_text": quote}


def _verdict(user_turn, candidate):
    return adjudicate(candidate, EvidenceLedger.from_transcript(f"User: {user_turn}\nAssistant: I see.\n"))


# The recorded candidate (V-2, long_L_r0_d7), then third-person statements no list was written for.
SOMEONE_ELSE = [
    ("My friend wants to pass the Azure Fundamentals exam by March.",
     _topic("exam", "Azure Fundamentals", "My friend wants to pass the Azure Fundamentals exam by March.")),
    ("My cousin is studying for the CKA exam.",
     _topic("CKA exam", "CKA exam", "My cousin is studying for the CKA exam.")),
    ("Priya wants to learn Haskell before summer.",
     _topic("Haskell", "Haskell", "Priya wants to learn Haskell before summer.")),
    ("Our neighbour runs a Kubernetes cluster at home.",
     _topic("Kubernetes", "Kubernetes", "Our neighbour runs a Kubernetes cluster at home.")),
]


@pytest.mark.parametrize("user_turn, candidate", SOMEONE_ELSE, ids=[c["field_name"] for _, c in SOMEONE_ELSE])
def test_a_statement_about_someone_else_is_not_the_users_topic(user_turn, candidate):
    verdict = _verdict(user_turn, candidate)

    assert verdict.state == EvidenceState.EVIDENCE_NOT_ENTAILING, verdict


# What the user asked about, or said in the first person, in wordings no list holds.
THE_USERS_OWN = [
    ("how do I speed up postgres indexing on a wide table?",
     _topic("postgres indexing", "postgres indexing", "how do I speed up postgres indexing on a wide table?")),
    ("what is the right way to think about vector clocks in a small cluster?",
     _topic("vector clocks", "vector clocks", "what is the right way to think about vector clocks in a small cluster?")),
    # A quote that stops short of its sentence's question mark is still that question.
    ("what is the right way to think about vector clocks in a small cluster?",
     _topic("vector clocks", "vector clocks", "what is the right way to think about vector clocks")),
    ("I'm curious about CRDTs lately.", _topic("CRDTs", "CRDTs", "I'm curious about CRDTs lately.")),
    ("I've been reading about vector clocks all week.",
     _topic("vector clocks", "vector clocks", "I've been reading about vector clocks all week.")),
    # The user's own question about someone else's plans still raises its topic: they asked it (the card's scope).
    ("My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level cloud exam?",
     _topic("exam", "exam", "My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an "
                           "entry-level cloud exam?")),
]


@pytest.mark.parametrize("user_turn, candidate", THE_USERS_OWN,
                         ids=["question", "question 2", "cut short of its question mark", "first person",
                              "first person 2", "asked about a friend's plan"])
def test_a_topic_the_user_asks_about_or_speaks_of_is_still_theirs(user_turn, candidate):
    verdict = _verdict(user_turn, candidate)

    assert verdict.sufficient, verdict


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


def test_a_friends_exam_is_neither_learned_nor_asked_about(tmp_path, db_key):
    # The recorded candidate through the real session-end path: the turn and the assistant's reply are copied from
    # V-2's long-chat set (docs/eval/v2_2026-10-17/long_chats).
    conn = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Zarqa Venn", language_preference="English")
    transcript = (
        "User: My friend wants to pass the Azure Fundamentals exam by March. Is two months enough for an entry-level "
        "cloud exam?\n"
        "Assistant: For an entry-level exam, two months of steady study is usually plenty, especially with the free "
        "practice questions.\n"
    )
    candidate = _topic("exam", "Azure Fundamentals", "My friend wants to pass the Azure Fundamentals exam by March.")

    try:
        observer.run_session_end(conn, transcript, _Model([candidate]))

        assert conn.execute("SELECT COUNT(*) FROM topic_interests").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM memory_candidates_pending").fetchone()[0] == 0
        assert [(r["stage"], r["reason_code"]) for r in conn.execute(
            "SELECT stage, reason_code FROM governance_audit_log")] == [(11, EvidenceState.EVIDENCE_NOT_ENTAILING)]
    finally:
        conn.close()
