import json
from typing import Iterator

import pytest

from backend.memory import session_snapshot
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import (
    BaseLLMProvider,
    ProviderExecutionError,
    ProviderUnavailableError,
)
from backend.stages import stage_11_observer as observer



class FakeProvider(BaseLLMProvider):
    def __init__(self, response_text: str = "", is_local: bool = True, raise_error: Exception = None):
        self.response_text = response_text
        self._is_local = is_local
        self.raise_error = raise_error
        self.last_messages = None
        self.last_response_format = None

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None) -> Iterator[str]:
        self.last_messages = messages
        self.last_response_format = response_format
        if self.raise_error:
            raise self.raise_error
        yield self.response_text

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": "fake", "is_local": self._is_local, "model_name": "fake-model"}


VALID_RESPONSE = {
    "memory_candidates": [
        {
            "target_table": "preference_memory",
            "field_name": "preferred_tools",
            "proposed_value": "Neovim",
            "label": "explicit",
            "evidence_text": "switched to Neovim last month",
        },
        {
            "target_table": "preference_memory",
            "field_name": "bogus",
            "proposed_value": "x",
            "label": "user_verified",  # invalid for Observer - must be dropped
        },
    ],
    "decision_candidates": [
        {
            "decision_text": "Chose FastAPI over Flask for async support",
            "signals_found": ["alternative_considered", "commitment_language"],
            "raw_quote": "I'm going with FastAPI",
        }
    ],
    "session_snapshot": {
        "topic": "Choosing a web framework",
        "open_problems": ["write the SQL query"],
        "last_decisions": ["FastAPI over Flask"],
        "suggested_next_step": "Write the inventory sync endpoint",
    },
}

# A realistic User:/Assistant: transcript (format_transcript()'s shape) that
# actually contains VALID_RESPONSE's raw_quote and a substantive user turn -
# the bare "transcript" placeholder string used elsewhere in this file can't
# satisfy the raw_quote-grounding / substantive-user-turn checks added after
# the live confabulation finding (see _quote_is_grounded's docstring).
#
# Now also carries the memory candidate's evidence_text verbatim. That line was
# missing for the same reason the raw_quote line was missing before it: nothing
# checked memory candidates, so nothing forced the fixture to be realistic
# about them. Grounding them exposed it immediately.
VALID_TRANSCRIPT = (
    "User: I'm going with FastAPI for the backend, what do you think?\n"
    "Assistant: FastAPI is a solid choice for async workloads.\n"
    "User: Also I switched to Neovim last month and I'm not going back.\n"
    "Assistant: Noted.\n"
)


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    # Rule 4's check now cross-verifies against provider_consent, not just
    # get_model_info()["is_local"] - FakeProvider's provider_id="fake" has no
    # seed row in config/provider_consent.json (only ollama/web_search do),
    # so every test using it needs one here, marked local (is_cloud=0).
    conn.execute(
        "INSERT INTO provider_consent (provider_id, is_cloud, user_consented, consent_scope, revoked) "
        "VALUES ('fake', 0, 1, 'full_inference', 0)"
    )
    conn.commit()
    yield conn
    conn.close()


def test_run_requires_local_provider(db_conn):
    provider = FakeProvider(is_local=False)
    with pytest.raises(observer.ObserverLocalProviderError):
        observer.run("transcript", provider, db_conn)


def test_run_requires_a_provider_consent_row_even_if_self_reported_local(db_conn):
    # Security regression test: a provider claiming is_local=True is not
    # enough on its own - if provider_consent has no row for its provider_id
    # (or marks it as cloud), Observer must still refuse, fail-closed, the
    # same posture Stage 8 already uses for unknown providers.
    db_conn.execute("DELETE FROM provider_consent WHERE provider_id = 'fake'")
    db_conn.commit()
    provider = FakeProvider(is_local=True)
    with pytest.raises(observer.ObserverLocalProviderError):
        observer.run("transcript", provider, db_conn)


def test_run_extracts_and_sanitizes_candidates(db_conn):
    provider = FakeProvider(response_text=json.dumps(VALID_RESPONSE))
    result = observer.run(VALID_TRANSCRIPT, provider, db_conn)

    assert len(result["memory_candidates"]) == 1
    candidate = result["memory_candidates"][0]
    assert candidate["target_table"] == "preference_memory"
    assert candidate["label"] == "explicit"
    assert candidate["evidence_count"] == 1

    assert len(result["decision_candidates"]) == 1
    assert result["decision_candidates"][0]["signals_found"] == ["alternative_considered", "commitment_language"]

    assert result["session_snapshot"]["topic"] == "Choosing a web framework"
    assert result["session_snapshot"]["last_decisions"] == ["FastAPI over Flask"]
    assert "snapshot_date" in result["session_snapshot"]


def test_run_handles_markdown_fenced_json(db_conn):
    fenced = "```json\n" + json.dumps(VALID_RESPONSE) + "\n```"
    provider = FakeProvider(response_text=fenced)
    # VALID_TRANSCRIPT rather than the bare "transcript" placeholder: the
    # candidate's evidence_text must appear in the transcript to survive
    # grounding, same as raw_quote already had to.
    result = observer.run(VALID_TRANSCRIPT, provider, db_conn)
    assert len(result["memory_candidates"]) == 1


def test_run_fails_open_on_invalid_json(db_conn):
    provider = FakeProvider(response_text="not json at all")
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []
    assert result["decision_candidates"] == []
    assert result["session_snapshot"]["topic"] == ""


def test_run_raises_rather_than_failing_open_when_the_provider_is_unreachable(db_conn):
    # This used to assert an empty result, and that assertion was the bug.
    # An empty output is indistinguishable from "this session held nothing
    # worth remembering", and every caller read it that way: drain() called
    # mark_completed() on a transcript the model never saw, and
    # _extract_and_mark() went on to stamp the conversation observed. Confirmed
    # live against a real database with Ollama down - the recovered session was
    # retired with nothing extracted.
    provider = FakeProvider(raise_error=ProviderUnavailableError("ollama down"))
    with pytest.raises(observer.ObserverUnavailableError):
        observer.run("transcript", provider, db_conn)


def test_run_raises_when_the_provider_errors_out(db_conn):
    provider = FakeProvider(raise_error=ProviderExecutionError("bad response"))
    with pytest.raises(observer.ObserverUnavailableError):
        observer.run("transcript", provider, db_conn)


def test_run_still_fails_open_when_the_model_answers_with_junk(db_conn):
    # The counterpart to the two above, and deliberately NOT symmetrical with
    # them. The model was reached and answered - it just answered badly. Making
    # that retryable would put an un-parseable transcript back on the queue to
    # fail again on every future start, blocking the drain permanently.
    provider = FakeProvider(response_text="still not json")
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []
    assert result["session_snapshot"]["topic"] == ""


def test_run_coerces_non_string_snapshot_list_items(db_conn):
    # Found live against real llama3.1:8b: last_decisions sometimes comes back as a
    # list of full decision objects instead of plain strings.
    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "test",
            "open_problems": ["a plain string problem"],
            "last_decisions": [
                {"decision_text": "Chose FastAPI", "signals_found": ["x"], "raw_quote": "y"},
                "a plain string decision",
            ],
            "suggested_next_step": "next",
        },
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run("User: we discussed the web framework and the RAG pipeline design.\n", provider, db_conn)
    assert result["session_snapshot"]["last_decisions"] == ["Chose FastAPI", "a plain string decision"]
    assert result["session_snapshot"]["open_problems"] == ["a plain string problem"]


def test_run_drops_candidate_with_missing_keys(db_conn):
    response = {
        "memory_candidates": [{"target_table": "preference_memory", "label": "explicit"}],  # missing field_name/proposed_value
        "decision_candidates": [],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []


def test_run_session_end_writes_snapshot_and_routes_candidates(db_conn):
    provider = FakeProvider(response_text=json.dumps(VALID_RESPONSE))

    result = observer.run_session_end(db_conn, VALID_TRANSCRIPT, provider)

    # snapshot written to the DB (session_snapshot table, security review fix
    # - it used to be a plain data/session_snapshot.json file)
    written = session_snapshot.load_snapshot(db_conn)
    assert written["topic"] == "Choosing a web framework"

    # memory candidate routed through Stage 12 + 13
    assert len(result["memory_results"]) == 1
    assert result["memory_results"][0]["validation_status"] in (
        "APPROVED", "DISCARD", "REQUIRES_CONFIRMATION", "TIER_2_REQUIRED", "PROMPT_RECONCILIATION", "HARD_REJECT",
    )

    # decision candidate routed through decision_log (2 signals -> logged)
    assert len(result["decision_results"]) == 1
    assert result["decision_results"][0]["status"] == "logged"
    logged = db_conn.execute("SELECT decision_text FROM decision_log").fetchone()
    assert logged["decision_text"] == "Chose FastAPI over Flask for async support"


def test_run_session_end_single_signal_decision_goes_to_pending(db_conn):
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                "decision_text": "Maybe use Redis for caching",
                "signals_found": ["commitment_language"],
                "raw_quote": "I'll probably use Redis",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    transcript = "User: I'll probably use Redis for caching, does that sound right?\n"
    result = observer.run_session_end(db_conn, transcript, provider)

    assert result["decision_results"][0]["status"] == "pending"
    assert db_conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 0
    assert db_conn.execute("SELECT COUNT(*) FROM decision_candidates_pending").fetchone()[0] == 1


def test_run_session_end_reinforces_evidence_across_simulated_sessions(db_conn):
    # Push the profile past week_1_2 (profile_age_weeks <= 2, evidence >= 1) into
    # week_3_4 (evidence >= 2), where a single session's evidence_count=1 candidate
    # discards on its own but should pass once reinforced against a prior session's
    # stored observation of the same value.
    from datetime import datetime, timedelta, timezone
    db_conn.execute(
        "INSERT INTO profile_meta (id, schema_version, constitution_version, first_session_date) VALUES (1, '1.0', '1.0', ?)",
        ((datetime.now(timezone.utc) - timedelta(weeks=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),)
    )
    db_conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('preferred_tools', 'Neovim', 1, 'explicit', 'active')"
    )
    db_conn.commit()

    response = {
        "memory_candidates": [
            {
                "target_table": "preference_memory",
                "field_name": "preferred_tools",
                "proposed_value": "Neovim",  # same value as the "prior session" row above
                "label": "explicit",
                "evidence_text": "still using Neovim",
            }
        ],
        "decision_candidates": [],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    # Transcript must contain the candidate's evidence_text verbatim, or
    # grounding drops it before reinforcement is ever reached.
    transcript = "User: still using Neovim, it's working well for me.\nAssistant: Good to hear.\n"
    result = observer.run_session_end(db_conn, transcript, provider)

    assert result["memory_results"][0]["validation_status"] == "APPROVED"
    assert result["memory_results"][0]["candidate"]["evidence_count"] == 2

    row = db_conn.execute("SELECT evidence_count FROM preference_memory WHERE name = 'preferred_tools'").fetchone()
    assert row["evidence_count"] == 2  # written value reflects reinforcement, not just the check


# --- Re-reading a resumed conversation is not corroboration ---------------
#
# A resumed conversation arrives carrying its whole history, and that history
# is handed to the Observer on purpose - the closing turns of a resumed chat
# rarely stand alone. But an already-extracted turn coming past a second time
# is the user being QUOTED, not the user repeating themselves, and Stage 12
# could not tell: it stamps every extraction with the current session_no, so a
# re-read looked like independent corroboration from a new session. Two
# sessions is the week_3_4 auto-write threshold.

_RESUMED_HISTORY = (
    "User: I switched to Neovim last month and I am not going back\n"
    "Assistant: Noted.\n"
)
_NEW_TURNS = (
    "User: anyway, what is a hash table?\n"
    "Assistant: A structure mapping keys to values.\n"
)


def _neovim_response(evidence: str) -> str:
    return json.dumps({
        "memory_candidates": [{
            "target_table": "preference_memory",
            "field_name": "preferred_tools",
            "proposed_value": "Neovim",
            "label": "explicit",
            "evidence_text": evidence,
        }],
        "decision_candidates": [],
        "session_snapshot": {},
    })


def test_a_signal_only_in_the_resumed_history_is_not_counted_again(db_conn):
    provider = FakeProvider(response_text=_neovim_response("switched to Neovim last month"))

    result = observer.run_session_end(
        db_conn,
        _RESUMED_HISTORY + _NEW_TURNS,
        provider,
        unobserved_transcript=_NEW_TURNS,
    )

    assert result["memory_results"] == []
    logged = db_conn.execute(
        "SELECT COUNT(*) AS n FROM memory_observation_log WHERE proposed_value = 'Neovim'"
    ).fetchone()
    assert logged["n"] == 0, "a re-read was recorded as an observation"


def test_the_same_signal_restated_in_the_new_turns_still_counts(db_conn):
    # The other direction, and the reason this is a grounding check rather than
    # a blanket "drop anything seen before": saying it again IS corroboration.
    restated = _NEW_TURNS + "User: and Neovim is still my editor of choice\nAssistant: Noted.\n"
    provider = FakeProvider(response_text=_neovim_response("Neovim is still my editor of choice"))

    result = observer.run_session_end(
        db_conn,
        _RESUMED_HISTORY + restated,
        provider,
        unobserved_transcript=restated,
    )

    assert len(result["memory_results"]) == 1
    logged = db_conn.execute(
        "SELECT COUNT(*) AS n FROM memory_observation_log WHERE proposed_value = 'Neovim'"
    ).fetchone()
    assert logged["n"] == 1


def test_a_decision_only_in_the_resumed_history_is_not_logged_again(db_conn):
    # Decisions route to their own store, so they need their own guard - the
    # same re-read would otherwise re-file a settled decision under today.
    history = "User: we are going with FastAPI for the backend\nAssistant: Good choice.\n"
    provider = FakeProvider(response_text=json.dumps({
        "memory_candidates": [],
        "decision_candidates": [{
            "decision_text": "Chose FastAPI for the backend",
            "signals_found": ["commitment_language"],
            "raw_quote": "we are going with FastAPI for the backend",
        }],
        "session_snapshot": {},
    }))

    result = observer.run_session_end(
        db_conn, history + _NEW_TURNS, provider, unobserved_transcript=_NEW_TURNS
    )

    assert result["decision_results"] == []


def test_without_an_unobserved_transcript_everything_still_counts(db_conn):
    # The default, and what a fresh conversation and the startup drain both
    # pass. Nothing about those paths changed.
    provider = FakeProvider(response_text=_neovim_response("switched to Neovim last month"))

    result = observer.run_session_end(db_conn, _RESUMED_HISTORY + _NEW_TURNS, provider)

    assert len(result["memory_results"]) == 1


def test_a_throwaway_reply_to_an_old_chat_cannot_overwrite_the_snapshot(db_conn):
    # The snapshot gate counts substantive turns, and a resumed conversation
    # carries any number of them from sessions it was already summarised from.
    # Measured on the new turns, one idle reply is not a session with an arc.
    _standing_snapshot(db_conn)
    long_history = "".join(
        f"User: this is substantive turn number {i} of the earlier session\nAssistant: ok\n"
        for i in range(5)
    )
    new_turn = "User: thanks for that, appreciated\nAssistant: Any time.\n"
    provider = FakeProvider(response_text=json.dumps({
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "saying thanks",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "",
        },
    }))

    observer.run_session_end(
        db_conn, long_history + new_turn, provider, unobserved_transcript=new_turn
    )

    assert session_snapshot.load_snapshot(db_conn)["topic"] == "Wiring the RAG retrieval stage"


# --- Decision candidates that are really the assistant's own text (found live) ---


def test_run_drops_decision_candidate_matching_an_assistant_line(db_conn):
    transcript = (
        "User: what's my status?\n"
        "Assistant: Would you like me to help you prioritize the tasks or provide any updates on the project timeline?\n"
    )
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                # Not phrased as a question by itself, but is a verbatim echo of
                # the assistant's own line above - the case the question-mark
                # heuristic alone wouldn't catch.
                "decision_text": "Would you like me to help you prioritize the tasks or provide any updates on the project timeline",
                "signals_found": ["commitment_language", "alternative_considered"],
                "raw_quote": "",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert result["decision_candidates"] == []


def test_run_drops_decision_candidate_phrased_as_a_question(db_conn):
    # Caught even with no matching assistant line at all - genuine decisions
    # are statements, not questions.
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                "decision_text": "Should we use Redis for caching?",
                "signals_found": ["commitment_language", "alternative_considered"],
                "raw_quote": "",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run("User: no assistant lines here", provider, db_conn)
    assert result["decision_candidates"] == []


def test_run_keeps_genuine_decision_alongside_assistant_lines(db_conn):
    # A real decision must still survive even when the transcript has
    # Assistant: lines present - the filter targets the specific echoed text,
    # not "any decision in a transcript with assistant replies."
    transcript = (
        "User: let's go with FastAPI for async support\n"
        "Assistant: Great choice, FastAPI has excellent async support.\n"
    )
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                "decision_text": "Chose FastAPI over Flask for async support",
                "signals_found": ["alternative_considered", "commitment_language"],
                "raw_quote": "let's go with FastAPI",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert len(result["decision_candidates"]) == 1
    assert result["decision_candidates"][0]["decision_text"] == "Chose FastAPI over Flask for async support"


# --- Confabulated decisions/snapshot from a thin transcript (found live) ---
#
# A real session consisting only of "hi" / "yes" / "sure" replies produced 7
# auto-logged fake decisions and a fabricated session_snapshot describing an
# entire "product launch meeting with Figma" scenario that was never
# discussed - none phrased as questions, none verbatim assistant echoes, so
# neither guard above caught them. The model invented plausible-sounding
# content with no basis in the transcript at all.


def test_run_drops_decision_candidate_with_unverifiable_raw_quote(db_conn):
    # decision_text reads as a plausible, declarative (non-question) claim,
    # and doesn't echo any assistant line - but the raw_quote it cites as its
    # evidence was never actually said by anyone in this transcript.
    transcript = "User: hi\nAssistant: Hi! How can I help?\nUser: yes\nAssistant: Great, let's proceed.\n"
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                "decision_text": "we'll proceed with integrating Figma as your design tool",
                "signals_found": ["commitment_language", "alternative_considered"],
                "raw_quote": "let's integrate Figma into the workflow",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert result["decision_candidates"] == []


def test_run_keeps_decision_with_a_raw_quote_actually_in_the_transcript(db_conn):
    transcript = "User: let's integrate Figma into the workflow, I've decided.\nAssistant: Sounds good.\n"
    response = {
        "memory_candidates": [],
        "decision_candidates": [
            {
                "decision_text": "Decided to integrate Figma into the workflow",
                "signals_found": ["commitment_language", "alternative_considered"],
                "raw_quote": "let's integrate Figma into the workflow",
            }
        ],
        "session_snapshot": {},
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert len(result["decision_candidates"]) == 1


def test_run_withholds_snapshot_from_a_session_with_no_substantive_user_turn(db_conn):
    # Reproduces the live finding exactly: a session of one-word
    # acknowledgments still got a fabricated "product launch" topic/next-step
    # with no basis in what was actually said.
    transcript = (
        "User: hi\n"
        "Assistant: Hi! How can I help?\n"
        "User: yes\n"
        "Assistant: Great, let's proceed.\n"
        "User: sure\n"
        "Assistant: I'll take notes during the meeting.\n"
    )
    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "Product launch preparations",
            "open_problems": ["User Experience"],
            "last_decisions": ["User committed to meeting with marketing team"],
            "suggested_next_step": "Attend meeting with marketing team at 2 PM",
        },
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert result["session_snapshot"]["topic"] == ""
    assert result["session_snapshot"]["last_decisions"] == []


def test_run_keeps_snapshot_from_a_session_with_a_real_substantive_turn(db_conn):
    transcript = "User: let's go with FastAPI for the backend\nAssistant: Good choice.\n"
    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "Choosing a web framework",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "",
        },
    }
    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run(transcript, provider, db_conn)
    assert result["session_snapshot"]["topic"] == "Choosing a web framework"


def test_run_session_end_does_not_overwrite_a_real_snapshot_with_a_withheld_one(db_conn):
    # A later thin session ("thanks, bye") must not clobber a real prior
    # snapshot with an empty one - the last good snapshot should survive.
    session_snapshot.write_snapshot(db_conn, {
        "topic": "Choosing a web framework",
        "open_problems": [],
        "last_decisions": [],
        "suggested_next_step": "Write the inventory sync endpoint",
        "snapshot_date": "2026-08-01T00:00:00Z",
    })

    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "Product launch preparations",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "Attend meeting with marketing team",
        },
    }
    provider = FakeProvider(response_text=json.dumps(response))
    observer.run_session_end(db_conn, "User: thanks\nAssistant: You're welcome!\nUser: bye\n", provider)

    written = session_snapshot.load_snapshot(db_conn)
    assert written["topic"] == "Choosing a web framework"


def _standing_snapshot(conn):
    session_snapshot.write_snapshot(conn, {
        "topic": "Wiring the RAG retrieval stage",
        "open_problems": ["chunk overlap still guessy"],
        "last_decisions": ["Chose Chroma over FAISS"],
        "suggested_next_step": "Tune the similarity threshold",
        "snapshot_date": "2026-08-01T00:00:00Z",
    })


def test_a_failed_recall_does_not_overwrite_the_session_it_failed_to_recall(db_conn):
    # The live case, reproduced exactly. The user opens a new chat, asks what
    # they were doing last time, PIP cannot answer - and the Observer then
    # summarises that two-message failure over the very snapshot that was
    # supposed to answer it. Left unguarded, each retry destroys more of the
    # record than the one before, and a user whose recall just failed retries.
    _standing_snapshot(db_conn)

    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "retrieving information about the pip project",
            "open_problems": ["User wants to recall previous conversation about pip project"],
            "last_decisions": [],
            "suggested_next_step": "Try searching previous conversations or ask for clarification",
        },
    }
    transcript = (
        "User: what we were doing last time in pip project\n"
        "Assistant: I don't have that recorded.\n"
    )
    observer.run_session_end(db_conn, transcript, FakeProvider(response_text=json.dumps(response)))

    assert session_snapshot.load_snapshot(db_conn)["topic"] == "Wiring the RAG retrieval stage"


def test_a_single_turn_session_that_learned_something_may_still_snapshot(db_conn):
    # One turn is not disqualifying on its own - a candidate is proof the
    # session arrived somewhere, which is what the gate actually asks.
    _standing_snapshot(db_conn)

    response = {
        "memory_candidates": [{
            "target_table": "preference_memory",
            "field_name": "preferred_tools",
            "proposed_value": "Neovim",
            "label": "explicit",
            "evidence_text": "switched to Neovim last month",
        }],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "Editor setup",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "port the keybindings",
        },
    }
    transcript = "User: I switched to Neovim last month for everything\nAssistant: Noted.\n"
    observer.run_session_end(db_conn, transcript, FakeProvider(response_text=json.dumps(response)))

    assert session_snapshot.load_snapshot(db_conn)["topic"] == "Editor setup"


def test_a_session_with_a_real_arc_may_snapshot_without_producing_candidates(db_conn):
    # Two substantive turns and nothing extracted is a real working session
    # whose recap is worth keeping - the gate must not require a candidate.
    _standing_snapshot(db_conn)

    response = {
        "memory_candidates": [],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "Debugging the WebSocket disconnect path",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "check the executor queue",
        },
    }
    transcript = (
        "User: the disconnect handler seems to hang sometimes\n"
        "Assistant: Let's look at the executor.\n"
        "User: it only happens after a database write\n"
        "Assistant: That narrows it down.\n"
    )
    observer.run_session_end(db_conn, transcript, FakeProvider(response_text=json.dumps(response)))

    assert session_snapshot.load_snapshot(db_conn)["topic"] == "Debugging the WebSocket disconnect path"


# --- Constrained output (response_format) ---
#
# The prompt asked for "valid JSON only" and _extract_json() cleaned up
# afterwards; anything it could not parse cost the whole session's extraction -
# every candidate and the snapshot - silently, with the transcript already
# consumed. response_format moves that from a request to a constraint.


def test_observer_asks_the_provider_for_schema_constrained_output(db_conn):
    provider = FakeProvider(response_text=json.dumps(VALID_RESPONSE))
    observer.run_session_end(db_conn, VALID_TRANSCRIPT, provider)

    schema = provider.last_response_format
    assert schema is not None, "Observer must request constrained output when the provider supports it"
    assert set(schema["required"]) == {"memory_candidates", "decision_candidates", "session_snapshot"}


def test_requested_schema_matches_what_the_sanitizers_expect(db_conn):
    # The schema and the OUTPUT FORMAT block in the prompt describe one
    # contract; a field required by the parser but absent from the schema is
    # how they drift apart unnoticed.
    provider = FakeProvider(response_text=json.dumps(VALID_RESPONSE))
    observer.run_session_end(db_conn, VALID_TRANSCRIPT, provider)
    schema = provider.last_response_format

    decision_props = schema["properties"]["decision_candidates"]["items"]
    assert "raw_quote" in decision_props["required"], (
        "raw_quote is what _quote_is_grounded() checks against the transcript - "
        "a candidate without one cannot be verified at all"
    )
    memory_props = schema["properties"]["memory_candidates"]["items"]
    assert memory_props["properties"]["label"]["enum"] == ["explicit", "inferred"]
    # ADR-005: the model labels, it never scores. No confidence field anywhere.
    assert "confidence" not in memory_props["properties"]
    # snapshot_date is stamped by the code via now_utc(), never asked of the model.
    assert "snapshot_date" not in schema["properties"]["session_snapshot"]["properties"]


def test_provider_without_response_format_support_still_works(db_conn):
    # base_provider documents response_format as optional for implementers.
    # A provider that never adopted it must extract unconstrained rather than
    # raise TypeError and lose the session.
    class LegacyProvider(BaseLLMProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30) -> Iterator[str]:
            yield json.dumps(VALID_RESPONSE)

        def is_available(self) -> bool:
            return True

        def get_model_info(self):
            return {"provider_id": "fake", "is_local": True, "model_name": "legacy"}

    observer.run_session_end(db_conn, VALID_TRANSCRIPT, LegacyProvider())
    # Asserted through the DB, as the other end-to-end tests here do: the
    # snapshot is a write, not part of the return value.
    written = session_snapshot.load_snapshot(db_conn)
    assert written["topic"] == VALID_RESPONSE["session_snapshot"]["topic"]


def test_accepts_response_format_detects_support_correctly():
    class Takes(BaseLLMProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            yield ""

        def is_available(self): return True
        def get_model_info(self): return {}

    class DoesNot(BaseLLMProvider):
        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30):
            yield ""

        def is_available(self): return True
        def get_model_info(self): return {}

    class TakesKwargs(BaseLLMProvider):
        def chat(self, messages, context=None, **kwargs):
            yield ""

        def is_available(self): return True
        def get_model_info(self): return {}

    assert observer._accepts_response_format(Takes()) is True
    assert observer._accepts_response_format(DoesNot()) is False
    # **kwargs binds the keyword fine, so it counts as support.
    assert observer._accepts_response_format(TakesKwargs()) is True


# --- Memory candidates must be grounded in the transcript ---
#
# Decisions had two grounding checks; memory candidates had none, so an
# invented preference reached Stage 12 on its own say-so and the evidence_text
# shown to the user at review time was never verified to exist.


def _memory_response(evidence_text: str) -> dict:
    return {
        "memory_candidates": [
            {
                "target_table": "preference_memory",
                "field_name": "preferred_tools",
                "proposed_value": "Neovim",
                "label": "explicit",
                "evidence_text": evidence_text,
            }
        ],
        "decision_candidates": [],
        "session_snapshot": {},
    }


def test_memory_candidate_with_evidence_in_the_transcript_survives(db_conn):
    transcript = "User: I switched to Neovim last month and I'm not going back.\nAssistant: Noted.\n"
    provider = FakeProvider(response_text=json.dumps(_memory_response("switched to Neovim last month")))
    result = observer.run(transcript, provider, db_conn)
    assert len(result["memory_candidates"]) == 1


def test_memory_candidate_with_invented_evidence_is_dropped(db_conn):
    transcript = "User: I switched to Neovim last month.\nAssistant: Noted.\n"
    provider = FakeProvider(
        response_text=json.dumps(_memory_response("the user said they love Neovim above all else"))
    )
    result = observer.run(transcript, provider, db_conn)
    # Same standard decisions are already held to: evidence that isn't in the
    # transcript cannot be checked, so the candidate has no verifiable basis.
    assert result["memory_candidates"] == []


def test_prompt_placeholder_echoed_as_evidence_is_dropped(db_conn):
    # The exact string the live model returned once response_format made the
    # output legible - it copied the prompt's own description of the field
    # instead of filling it in. Caught by grounding rather than by matching
    # this specific text: a placeholder isn't in the transcript either.
    transcript = "User: I switched to Neovim last month.\nAssistant: Noted.\n"
    provider = FakeProvider(
        response_text=json.dumps(_memory_response("the exact quote or paraphrase this was drawn from"))
    )
    result = observer.run(transcript, provider, db_conn)
    assert result["memory_candidates"] == []


def test_memory_candidate_with_empty_evidence_is_dropped(db_conn):
    transcript = "User: I switched to Neovim last month.\nAssistant: Noted.\n"
    provider = FakeProvider(response_text=json.dumps(_memory_response("")))
    result = observer.run(transcript, provider, db_conn)
    assert result["memory_candidates"] == []


def test_evidence_grounding_ignores_case_and_whitespace(db_conn):
    # Same normalisation _quote_is_grounded already applies, so a candidate is
    # not rejected over capitalisation the model chose differently.
    transcript = "User: I switched to Neovim last month.\nAssistant: Noted.\n"
    provider = FakeProvider(response_text=json.dumps(_memory_response("SWITCHED   to   neovim")))
    result = observer.run(transcript, provider, db_conn)
    assert len(result["memory_candidates"]) == 1


def test_prompt_tells_the_model_not_to_copy_the_field_descriptions(db_conn):
    # The placeholders are angle-bracketed and the rules say not to copy them;
    # grounding is the enforcement, this is the instruction that should make it
    # unnecessary in the first place.
    assert "Never copy those descriptions" in observer._EXTRACTION_PROMPT_PREFIX
    assert "WORD FOR WORD" in observer._EXTRACTION_PROMPT_PREFIX
    assert "the exact quote or paraphrase this was drawn from" not in observer._EXTRACTION_PROMPT_PREFIX


# --- target_table must name a real, writable table ---


def test_approved_fields_name_only_real_writable_tables():
    # "observer_writable" was a key here: a CATEGORY name from
    # constitutional.json, not a table. The prompt taught it as a target_table,
    # the model emitted it, and every such candidate was HARD_REJECTed as a
    # schema violation - two rejections and four "Unhandled target_table"
    # warnings per session, guaranteed, from a conversation about nothing
    # unusual.
    from backend.core.constitution_enforcer import OBSERVER_WRITABLE_TABLES

    for table in observer.APPROVED_MEMORY_FIELDS:
        assert table in OBSERVER_WRITABLE_TABLES, f"{table} would be HARD_REJECTed by the constitution"


def test_approved_tables_can_actually_be_written(db_conn):
    # Naming a permitted-but-unimplemented table would be worse than the bug it
    # replaced: write_approved_candidate raises "Unsupported target_table",
    # so the candidate throws and lands as "failed" rather than being cleanly
    # rejected. Every table offered to the model must survive the write path.
    from backend.memory import profile_store

    for table, fields in observer.APPROVED_MEMORY_FIELDS.items():
        # fields is a sentence rather than a list for an open-ended table
        # (topic_interests, skill_memory, active_projects: the field name is the
        # record's own name, so there is no fixed list). Any name is valid
        # there, which is exactly what this asserts survives the write path.
        if table == "goal_memory":
            field_name = "goal:1"
        elif isinstance(fields, str):
            field_name = "distributed systems"
        else:
            field_name = fields[0]
        candidate = {
            "target_table": table,
            "field_name": field_name,
            "proposed_value": "0.5" if table == "skill_memory" else "something",
            # interaction_style writes a singleton row keyed on id = 1 and
            # ignores field_name, but the name still has to be the one the
            # prompt teaches, or the gated-field pattern would not match it.
            "label": "explicit",
            "evidence_count": 1,
            "evidence_text": "quoted",
        }
        # Must not raise "Unsupported target_table for approved write".
        profile_store.write_approved_candidate(db_conn, candidate)


def test_schema_constrains_target_table_to_the_approved_set():
    # Enforced at the sampler, not merely requested in the prompt.
    enum = observer._EXTRACTION_SCHEMA["properties"]["memory_candidates"]["items"]["properties"]["target_table"]["enum"]
    assert set(enum) == set(observer.APPROVED_MEMORY_FIELDS)
    assert "observer_writable" not in enum


def test_prompt_does_not_advertise_the_category_name_as_a_table():
    assert "observer_writable" not in observer._EXTRACTION_PROMPT_PREFIX


# --- observer.max_session_tokens ------------------------------------------
# The setting existed and was read by nothing, so a long session sent its whole
# transcript to a model with a finite context window - where over-length input
# is not an error but a silent truncation nobody downstream can detect.


def test_short_transcript_is_passed_through_untouched():
    transcript = "User: hello\nAssistant: hi"
    assert observer._cap_transcript(transcript) == transcript


def test_long_transcript_is_capped_to_the_configured_budget(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "_settings", None)
    real = settings.get_settings()
    monkeypatch.setattr(
        settings, "_settings", {**real, "observer": {**real["observer"], "max_session_tokens": 20}}
    )

    lines = [f"User: message number {i} with some padding words here" for i in range(50)]
    capped = observer._cap_transcript("\n".join(lines))

    assert len(capped.split()) <= 20


def test_capping_keeps_the_end_of_the_session(monkeypatch):
    """
    A session-end pass summarises what the session arrived at, so the closing
    turns are the ones that must survive. Cutting on line boundaries also means
    the model never receives half a turn.
    """
    from backend.config import settings

    monkeypatch.setattr(settings, "_settings", None)
    real = settings.get_settings()
    monkeypatch.setattr(
        settings, "_settings", {**real, "observer": {**real["observer"], "max_session_tokens": 12}}
    )

    lines = [f"User: turn {i}" for i in range(40)]
    capped = observer._cap_transcript("\n".join(lines))

    assert "turn 39" in capped
    assert "turn 0" not in capped
    for line in capped.splitlines():
        assert line.startswith("User: turn ")


def test_run_session_end_survives_one_failing_candidate(db_conn, monkeypatch):
    """
    A candidate that blows up mid-route must cost that candidate and nothing
    else. Before per-candidate isolation, the raise escaped run_session_end
    and the caller logged "session transcript discarded" - every other memory
    candidate AND every decision candidate in the same session went with it.
    Found live: a None confidence reaching the enforcer's conflict check
    raised TypeError on every disconnect, so nothing was ever learned.
    """
    response = {
        "memory_candidates": [
            {
                "target_table": "preference_memory",
                "field_name": "answer_style",
                "proposed_value": "concise",
                "label": "explicit",
                "evidence_text": "keep it short when you answer",
            },
            {
                "target_table": "preference_memory",
                "field_name": "preferred_tools",
                "proposed_value": "Neovim",
                "label": "explicit",
                "evidence_text": "switched to Neovim last month",
            },
        ],
        "decision_candidates": VALID_RESPONSE["decision_candidates"],
        "session_snapshot": VALID_RESPONSE["session_snapshot"],
    }

    real_run = observer.stage_12.run

    def exploding_run(conn, candidate, enforcer):
        if candidate.get("field_name") == "answer_style":
            raise TypeError("'>' not supported between instances of 'NoneType' and 'float'")
        return real_run(conn, candidate, enforcer)

    monkeypatch.setattr(observer.stage_12, "run", exploding_run)

    # Both evidence_text quotes have to appear verbatim, or run()'s grounding
    # check drops the candidate before it ever reaches the loop under test.
    transcript = VALID_TRANSCRIPT + "User: and keep it short when you answer.\n"

    provider = FakeProvider(response_text=json.dumps(response))
    result = observer.run_session_end(db_conn, transcript, provider)

    # The failing candidate is recorded as failed, not silently dropped.
    assert len(result["memory_results"]) == 2
    poisoned = next(r for r in result["memory_results"] if r["candidate"]["field_name"] == "answer_style")
    assert poisoned["validation_status"] == "ERROR"
    assert poisoned["outcome"] == "failed"

    # Everything else in the same session still went through.
    survivor = next(r for r in result["memory_results"] if r["candidate"]["field_name"] == "preferred_tools")
    assert survivor["validation_status"] != "ERROR"

    assert len(result["decision_results"]) == 1
    assert result["decision_results"][0]["status"] == "logged"
    assert session_snapshot.load_snapshot(db_conn)["topic"] == "Choosing a web framework"


def test_prompt_teaches_active_projects_by_example_not_only_by_name():
    """
    active_projects was added to APPROVED_MEMORY_FIELDS and to the schema enum,
    but the OUTPUT FORMAT block still illustrated only preference_memory and
    skill_memory - and a model copies the example far more readily than it
    reads the list. Measured against llama3.1:8b on a transcript whose first
    line is "I started a new project called Halo, it's a note-taking app in
    Rust": active_projects was proposed in 1 of 6 runs. The model reliably
    emitted a skill, a goal, or a topic instead - all true, none of them the
    project - so a project the user named in plain words could not be learned.
    With the example and the two rules below, 5 of 6, and 0 fabricated projects
    across 8 runs of two project-free control transcripts.

    Asserted on the prompt text because that is the only deterministic handle;
    the behaviour it buys is measured live, not here.
    """
    prefix = observer._EXTRACTION_PROMPT_PREFIX

    output_format = prefix.split("OUTPUT FORMAT:", 1)[1]
    assert '"target_table": "active_projects"' in output_format, (
        "a table the example never demonstrates is one the model rarely emits"
    )

    # The example must not name a project a real transcript could not contain,
    # or the model has a ready-made answer to copy when it has no real one.
    assert "Halo" not in prefix

    assert "record it" in prefix and "active_projects" in prefix
    assert "not the menu of" in prefix, (
        "the example is a shape, not the set of tables worth emitting"
    )
