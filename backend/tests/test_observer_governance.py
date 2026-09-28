"""
Promises 1-3 (docs/FREEZE_LIST.md §4): the Observer's memory candidates reach
the profile only through governance, never touch the immutable fields, and
wait for the user on the gated ones.

Driven through the real session-end path, stage_11_observer.run_session_end,
with a stand-in model whose output the test controls - the Observer's LLM is
the untrusted part, so the test plays it. Everything after the model is real:
grounding, the evidence gate, Stage 12 and the Constitution, Stage 13. Every
assertion is on what the database holds afterwards, not on a status value.

Promise 2's "grounded, gate-passing candidate" is forced where the real gate
would have refused first: the gate is told to say yes, so what is under test
is what governance does with a candidate that got that far - the worst case
the promise has to survive.
"""

import json
from pathlib import Path

import pytest

from backend.core import evidence_gate
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.memory import candidate_store, profile_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_11_observer as observer
from backend.stages import stage_13_profile_update as stage_13

NAME, LANGUAGE, TIMEZONE = "Zarqa Venn", "English", "Asia/Kathmandu"

# Every table a memory candidate can end up in, and the queue that holds the
# ones waiting for the user.
PROFILE_TABLES = (
    "identity", "skill_memory", "preference_memory", "goal_memory", "interaction_style",
    "active_projects", "topic_interests", "preferred_tools", "document_access_patterns",
)


class ScriptedObserverModel(BaseLLMProvider):
    """Plays the Observer's LLM: returns exactly the extraction it is given.
    provider_id is "ollama", which the seeded consent table records as local,
    so the Stage 11 locality gate lets it through."""

    def __init__(self, memory_candidates=(), decision_candidates=()):
        self.output = json.dumps({
            "memory_candidates": list(memory_candidates),
            "decision_candidates": list(decision_candidates),
            "session_snapshot": {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
        })

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield self.output

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "scripted"}


def candidate(target_table, field_name, proposed_value, evidence_text, label="explicit"):
    return {
        "target_table": target_table,
        "field_name": field_name,
        "proposed_value": proposed_value,
        "label": label,
        "evidence_count": 1,
        "evidence_text": evidence_text,
    }


@pytest.fixture
def conn(tmp_path, db_key):
    connection = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(connection)
    profile_store.complete_onboarding(
        connection, name=NAME, language_preference=LANGUAGE, timezone=TIMEZONE
    )
    yield connection
    connection.close()


def _profile(conn) -> dict[str, list[tuple]]:
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")] for t in PROFILE_TABLES}


def _pending(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM memory_candidates_pending WHERE state = 'pending'")]


def _observe(conn, transcript, *candidates, decisions=()):
    return observer.run_session_end(
        conn, transcript, ScriptedObserverModel(candidates, decisions)
    )


def _gate_says_yes(monkeypatch):
    def sufficient(candidate, ledger):
        return evidence_gate.EvidenceVerdict(evidence_gate.EvidenceState.EVIDENCE_SUFFICIENT, "forced by test")
    monkeypatch.setattr(evidence_gate, "adjudicate", sufficient)


# --- Promise 1: Observer writes only through governance --------------------


def test_a_supported_candidate_is_written(conn):
    """The property is "only through governance", not "never": a chain that
    rejected everything would pass every other test in this file."""
    transcript = "User: what is the right way to think about vector clocks in a small cluster?\nAssistant: Start with causality."

    result = _observe(conn, transcript, candidate(
        "topic_interests", "vector clocks", "vector clocks",
        "what is the right way to think about vector clocks in a small cluster?",
    ))

    assert [r["outcome"] for r in result["memory_results"]] == ["written"]
    assert conn.execute("SELECT 1 FROM topic_interests WHERE topic = 'vector clocks'").fetchone()


def test_nothing_reaches_the_profile_that_the_constitution_did_not_approve(conn, monkeypatch):
    """
    A mixed extraction - one supported fact, one genuine quote that does not
    support its claim, one quote the user never said, one attempt on an
    immutable field, one gated goal. Every profile write must be for a
    candidate the Constitution approved, and the profile must change by exactly
    those writes and nothing else.
    """
    approvals, writes = [], []
    real_validate = ConstitutionEnforcer.validate
    real_write = profile_store.write_approved_candidate

    def recording_validate(self, candidate, existing, age):
        result = real_validate(self, candidate, existing, age)
        approvals.append((candidate["target_table"], candidate["field_name"], result.status))
        return result

    def recording_write(conn_, candidate):
        writes.append((candidate["target_table"], candidate["field_name"]))
        return real_write(conn_, candidate)

    monkeypatch.setattr(ConstitutionEnforcer, "validate", recording_validate)
    monkeypatch.setattr(profile_store, "write_approved_candidate", recording_write)

    transcript = (
        "User: what is the right way to think about vector clocks in a small cluster?\n"
        "Assistant: Start with causality.\n"
        "User: I've been comparing FastAPI and Flask.\n"
        "User: I have decided to migrate the whole thing to Postgres before the quarter ends.\n"
        "User: call me Zed from now on.\n"
    )
    before = _profile(conn)

    _observe(
        conn, transcript,
        candidate("topic_interests", "vector clocks", "vector clocks",
                  "what is the right way to think about vector clocks in a small cluster?"),
        candidate("preference_memory", "preferred_tools", "Flask", "I've been comparing FastAPI and Flask."),
        candidate("preference_memory", "editor", "Emacs", "I have used Emacs every day for ten years."),
        candidate("identity", "name", "Zed", "call me Zed from now on."),
        candidate("goal_memory", "active_goals", "migrate the whole thing to Postgres",
                  "I have decided to migrate the whole thing to Postgres before the quarter ends."),
    )
    after = _profile(conn)

    approved = {(t, f) for t, f, status in approvals if status == "APPROVED"}
    assert writes, "nothing was written - the property would hold for a chain that rejects everything"
    assert set(writes) <= approved, f"written without approval: {set(writes) - approved}"
    changed = {t for t in PROFILE_TABLES if before[t] != after[t]}
    assert changed == {t for t, _ in writes}, f"profile tables changed outside an approved write: {changed}"


def test_the_only_code_that_writes_an_observer_candidate_is_stage_13():
    """
    A census, not a proof (§5: medium evidence): outside the tests, the two
    functions that put a memory candidate into the profile or its queue are
    called from Stage 13 - and the queue also from the verification loop,
    which asks the user rather than writing. A new caller elsewhere would be a
    route around governance, and this is what would notice it.
    """
    backend = Path(__file__).resolve().parents[1]
    callers = {}
    for path in backend.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for name in ("write_approved_candidate(", "create_memory_candidate("):
            if f".{name}" in text:
                callers.setdefault(name, set()).add(path.relative_to(backend).as_posix())

    assert callers["write_approved_candidate("] == {"stages/stage_13_profile_update.py"}
    assert callers["create_memory_candidate("] == {
        "stages/stage_13_profile_update.py", "memory/verification.py",
    }


# --- Promise 2: Observer cannot write immutable fields ---------------------


@pytest.mark.parametrize("field, new_value, said", [
    ("name", "Zed", "call me Zed from now on."),
    ("language_preference", "French", "please answer me in French from now on."),
    ("timezone", "America/Los_Angeles", "I moved to Los Angeles last month."),
])
def test_an_immutable_identity_field_is_never_written_even_past_the_gate(conn, monkeypatch, field, new_value, said):
    _gate_says_yes(monkeypatch)
    before_identity = _profile(conn)["identity"]

    result = _observe(conn, f"User: {said}\n", candidate("identity", field, new_value, said))

    assert result["memory_results"][0]["evidence_state"] == "EVIDENCE_SUFFICIENT", "the gate was not passed"
    assert _profile(conn)["identity"] == before_identity
    assert not [p for p in _pending(conn) if p["target_table"] == "identity"], "queued as a question instead"


# --- Promise 3: gated fields require confirmation --------------------------


# Shapes the real evidence gate accepts (backend/tests/evidence_cases.py, the
# held-out set), one per gated pattern in constitutional.json.
GATED = [
    pytest.param("I have decided to migrate the whole thing to Postgres before the quarter ends.",
                 candidate("goal_memory", "active_goals", "migrate the whole thing to Postgres",
                           "I have decided to migrate the whole thing to Postgres before the quarter ends."),
                 "SELECT 1 FROM goal_memory WHERE goal_text = 'migrate the whole thing to Postgres'",
                 id="goal_memory.*"),
    pytest.param("give me more detail next time, that was too compressed.",
                 candidate("interaction_style", "value", "full_detail",
                           "give me more detail next time, that was too compressed."),
                 "SELECT 1 FROM interaction_style WHERE value = 'full_detail'",
                 id="interaction_style.*"),
    pytest.param("I am working on Halyard, a scheduling tool for boat clubs.",
                 candidate("active_projects", "Halyard", "a scheduling tool for boat clubs",
                           "I am working on Halyard, a scheduling tool for boat clubs."),
                 "SELECT 1 FROM active_projects WHERE name = 'Halyard'",
                 id="active_projects.*"),
    pytest.param("I have written TypeScript professionally for about four years.",
                 candidate("skill_memory", "TypeScript", "0.8",
                           "I have written TypeScript professionally for about four years."),
                 "SELECT 1 FROM skill_memory WHERE name = 'TypeScript'",
                 id="skill_memory.*.level"),
]


@pytest.mark.parametrize("said, gated, stored", GATED)
def test_a_gated_field_is_written_only_once_the_user_confirms_it(conn, said, gated, stored):
    result = _observe(conn, f"User: {said}\n", gated)

    assert result["memory_results"][0]["evidence_state"] == "EVIDENCE_SUFFICIENT", "the real gate refused it"
    assert conn.execute(stored).fetchone() is None, "written without confirmation"
    queued = [p for p in _pending(conn) if p["target_table"] == gated["target_table"]]
    assert len(queued) == 1, "not queued for the user"

    stage_13.resolve_pending(conn, queued[0]["id"])  # what POST /memory/pending/{id}/confirm calls

    assert conn.execute(stored).fetchone() is not None, "confirmed, but still not written"
