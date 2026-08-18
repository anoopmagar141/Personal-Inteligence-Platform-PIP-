import pytest

from backend.memory import decision_log
from backend.memory.profile_store import get_connection, initialize_schema
from backend.stages import stage_03_decision_log_lookup as stage_03


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def test_empty_retrieval_hint_returns_empty(db_conn):
    assert stage_03.run(db_conn, "") == []


def test_returns_matching_active_decisions(db_conn):
    # Must go through decision_log.insert_decision() - it's the only place that
    # syncs the decision_fts index (ADR-025 one-writer rule). A raw INSERT into
    # decision_log would leave the FTS index out of sync and the search would
    # silently return nothing, which is a test-realism bug, not a Stage 3 bug.
    decision_log.insert_decision(
        db_conn, text="We chose FastAPI for the inventory service", confidence=0.7
    )

    results = stage_03.run(db_conn, "FastAPI")
    assert len(results) == 1
    assert results[0]["decision_text"] == "We chose FastAPI for the inventory service"


def test_excludes_superseded_decisions(db_conn):
    decision_id = decision_log.insert_decision(
        db_conn, text="We chose Flask originally", confidence=0.7
    )
    decision_log.update_decision_state(db_conn, decision_id, state="superseded", reason="switched to FastAPI")

    assert stage_03.run(db_conn, "Flask") == []


def test_fails_open_on_search_error(db_conn, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated search failure")

    monkeypatch.setattr(stage_03.decision_log, "search_decisions", _boom)
    assert stage_03.run(db_conn, "anything") == []


def test_handles_special_characters_that_could_break_fts5_syntax(db_conn):
    # FTS5 MATCH treats characters like quotes/hyphens/parens specially - a raw user
    # query containing them must not crash the stage, only ever fail open.
    result = stage_03.run(db_conn, 'weird "query" with -- special (chars)')
    assert result == []


def test_finds_matches_despite_punctuation_in_the_query(db_conn):
    # Regression test: punctuation must not just fail to crash (the test above)
    # but must not silently prevent matching either - "What did I just ask you
    # about FastAPI?" needs to find the FastAPI decision, not fail open to [].
    decision_log.insert_decision(
        db_conn, text="We chose FastAPI for the inventory service", confidence=0.7
    )

    results = stage_03.run(db_conn, "What did I decide about FastAPI?")
    assert len(results) == 1
    assert results[0]["decision_text"] == "We chose FastAPI for the inventory service"
