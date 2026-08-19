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

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30) -> Iterator[str]:
        self.last_messages = messages
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
    result = observer.run("transcript", provider, db_conn)

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
    result = observer.run("transcript", provider, db_conn)
    assert len(result["memory_candidates"]) == 1


def test_run_fails_open_on_invalid_json(db_conn):
    provider = FakeProvider(response_text="not json at all")
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []
    assert result["decision_candidates"] == []
    assert result["session_snapshot"]["topic"] == ""


def test_run_fails_open_on_provider_unavailable(db_conn):
    provider = FakeProvider(raise_error=ProviderUnavailableError("ollama down"))
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []
    assert result["decision_candidates"] == []
    assert result["session_snapshot"]["topic"] == ""


def test_run_fails_open_on_provider_execution_error(db_conn):
    provider = FakeProvider(raise_error=ProviderExecutionError("bad response"))
    result = observer.run("transcript", provider, db_conn)
    assert result["memory_candidates"] == []


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
    result = observer.run("transcript", provider, db_conn)
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

    result = observer.run_session_end(db_conn, "transcript", provider)

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
    result = observer.run_session_end(db_conn, "transcript", provider)

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
    result = observer.run_session_end(db_conn, "transcript", provider)

    assert result["memory_results"][0]["validation_status"] == "APPROVED"
    assert result["memory_results"][0]["candidate"]["evidence_count"] == 2

    row = db_conn.execute("SELECT evidence_count FROM preference_memory WHERE name = 'preferred_tools'").fetchone()
    assert row["evidence_count"] == 2  # written value reflects reinforcement, not just the check
