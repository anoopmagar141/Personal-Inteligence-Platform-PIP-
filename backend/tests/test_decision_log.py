import sqlite3

import pytest

from backend.memory import candidate_store, decision_log, profile_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_manual_decide_logs_with_any_one_signal(conn):
    result = decision_log.create_decision(
        conn,
        text="We decided to use SQLite for the profile store.",
    )

    assert result["status"] == "logged"
    assert result["confidence"] == 0.4
    rows = decision_log.list_decisions(conn)
    assert len(rows) == 1
    assert rows[0]["decision_text"] == "We decided to use SQLite for the profile store."


def test_decision_confidence_uses_or_logic(conn):
    one = decision_log.create_decision(conn, text="We will use FastAPI.")
    two = decision_log.create_decision(
        conn,
        text="We will use FastAPI.",
        reasoning="It keeps the REST surface simple.",
    )
    three = decision_log.create_decision(
        conn,
        text="We will use FastAPI.",
        reasoning="It keeps the REST surface simple.",
        alternatives="Flask and stdlib http.server.",
    )

    assert one["confidence"] == 0.4
    assert two["confidence"] == 0.7
    assert three["confidence"] == 1.0


def test_no_signal_decision_goes_to_pending(conn):
    result = decision_log.create_decision(conn, text="SQLite profile store")

    assert result["status"] == "pending"
    pending = decision_log.list_pending(conn)
    assert len(pending) == 1
    assert pending[0]["confidence"] == 0.0


def test_pending_order_is_confidence_then_created(conn):
    high = candidate_store.create_decision_candidate(
        conn,
        decision_text="High confidence",
        signals_found=["commitment_language"],
        raw_quote="High confidence",
        confidence=0.7,
    )
    low = candidate_store.create_decision_candidate(
        conn,
        decision_text="Low confidence",
        signals_found=[],
        raw_quote="Low confidence",
        confidence=0.0,
    )

    pending_ids = [row["id"] for row in decision_log.list_pending(conn)]
    assert pending_ids == [low, high]


def test_search_state_update_promote_and_dismiss(conn):
    logged = decision_log.create_decision(
        conn,
        text="We decided ChromaDB stays rebuildable.",
        reasoning="SQLite remains authoritative.",
    )
    matches = decision_log.search_decisions(conn, query="ChromaDB")
    assert [row["id"] for row in matches] == [logged["decision_id"]]

    decision_log.update_decision_state(
        conn,
        logged["decision_id"],
        state="abandoned",
        reason="Architecture changed.",
    )
    assert decision_log.list_decisions(conn, state="active") == []
    assert len(decision_log.list_decisions(conn, state="abandoned")) == 1


def test_search_decisions_matches_despite_query_punctuation(conn):
    logged = decision_log.create_decision(
        conn,
        text="We decided ChromaDB stays rebuildable.",
        reasoning="SQLite remains authoritative.",
    )
    # Bareword FTS5 syntax treats "?", "-", "(", ")", '"' as query operators, not
    # literal characters - a raw natural-language question must still match.
    matches = decision_log.search_decisions(conn, query="What did we decide about ChromaDB?")
    assert [row["id"] for row in matches] == [logged["decision_id"]]


def test_search_decisions_query_with_no_word_tokens_returns_empty(conn):
    decision_log.create_decision(conn, text="We decided ChromaDB stays rebuildable.")
    assert decision_log.search_decisions(conn, query="???") == []

    promote_id = candidate_store.create_decision_candidate(
        conn,
        decision_text="Promote this candidate",
        signals_found=["commitment_language"],
        raw_quote="Promote this candidate",
        confidence=0.4,
    )
    promoted = decision_log.promote_pending(conn, promote_id)
    assert promoted["status"] == "promoted"

    dismiss_id = candidate_store.create_decision_candidate(
        conn,
        decision_text="Dismiss this candidate",
        signals_found=[],
        raw_quote="Dismiss this candidate",
        confidence=0.0,
    )
    dismissed = decision_log.dismiss_pending(conn, dismiss_id)
    assert dismissed == {"status": "dismissed", "candidate_id": dismiss_id}
    assert dismiss_id not in [row["id"] for row in decision_log.list_pending(conn)]


def test_decision_text_is_write_once(conn):
    result = decision_log.create_decision(conn, text="We will keep decision text immutable.")

    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(
            "UPDATE decision_log SET decision_text = 'mutated' WHERE id = ?",
            (result["decision_id"],),
        )


def test_route_observer_decision_two_signals_auto_logs(conn):
    result = decision_log.route_observer_decision(
        conn,
        text="Chose FastAPI over Flask",
        signals_found=["alternative_considered", "commitment_language"],
        raw_quote="I'm going with FastAPI",
    )
    assert result["status"] == "logged"
    assert result["confidence"] == 0.7
    assert decision_log.list_decisions(conn)[0]["decision_text"] == "Chose FastAPI over Flask"


def test_route_observer_decision_one_signal_goes_to_pending_not_manual_threshold(conn):
    # log_threshold_observer (0.7) is stricter than log_threshold_manual (0.4) -
    # a single signal (confidence 0.4) must NOT auto-log via the Observer path,
    # even though create_decision() would auto-log it via the manual path.
    result = decision_log.route_observer_decision(
        conn,
        text="Maybe use Redis for caching",
        signals_found=["commitment_language"],
        raw_quote="I'll probably use Redis",
    )
    assert result["status"] == "pending"
    assert result["confidence"] == 0.4
    assert decision_log.list_decisions(conn) == []
    assert len(decision_log.list_pending(conn)) == 1


def test_route_observer_decision_drops_unknown_signal_names(conn):
    # A hallucinated signal name must not be able to inflate confidence past what
    # the two real, known signals would produce on their own.
    result = decision_log.route_observer_decision(
        conn,
        text="Chose FastAPI over Flask",
        signals_found=["alternative_considered", "commitment_language", "made_up_signal"],
        raw_quote="I'm going with FastAPI",
    )
    assert result["signals"] == ["alternative_considered", "commitment_language"]
    assert result["confidence"] == 0.7


# --- state_reason: retractions must record why (schema.sql / ADR-022) ---


def test_update_decision_state_persists_the_reason_it_demands(conn):
    decision_id = decision_log.insert_decision(conn, text="Use SQLCipher for storage")
    decision_log.update_decision_state(
        conn, decision_id, state="abandoned", reason="Superseded by a platform decision"
    )
    row = conn.execute("SELECT state, state_reason FROM decision_log WHERE id = ?", (decision_id,)).fetchone()
    assert row["state"] == "abandoned"
    # The reason was required and validated from the start, then discarded for
    # want of a column - leaving "abandoned" indistinguishable between a
    # cleaned-up fabrication and a genuine change of mind.
    assert row["state_reason"] == "Superseded by a platform decision"


def test_reactivating_replaces_the_retraction_reason_rather_than_keeping_it(conn):
    decision_id = decision_log.insert_decision(conn, text="Use Flask")
    decision_log.update_decision_state(conn, decision_id, state="abandoned", reason="Chose FastAPI instead")
    decision_log.update_decision_state(conn, decision_id, state="active", reason="Flask is back for the admin app")
    row = conn.execute("SELECT state, state_reason FROM decision_log WHERE id = ?", (decision_id,)).fetchone()
    assert row["state"] == "active"
    # Leaving "Chose FastAPI instead" attached to a row that is active again
    # would read as a live justification for the opposite of what happened.
    assert row["state_reason"] == "Flask is back for the admin app"


def test_active_decisions_have_no_state_reason(conn):
    decision_id = decision_log.insert_decision(conn, text="Never retracted")
    row = conn.execute("SELECT state_reason FROM decision_log WHERE id = ?", (decision_id,)).fetchone()
    assert row["state_reason"] is None


# --- Duplicate suppression on write ---
#
# The live log held "machine learning approach for threat detection" and
# "integrate with popular smart home devices" twice each (ids 1&4, 2&5): the
# Observer proposed the same decision in consecutive sessions and nothing
# compared it against what was already recorded.


def test_identical_decision_is_not_logged_twice(conn):
    first = decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    second = decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 1


def test_duplicate_matching_ignores_case_and_whitespace(conn):
    first = decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    second = decision_log.insert_decision(conn, text="  we   CHOSE   fastapi  ", confidence=0.7)
    assert first == second
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 1


def test_same_text_under_a_different_project_is_a_separate_decision(conn):
    conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p1', 'One', '', 'active', '2026-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p2', 'Two', '', 'active', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    first = decision_log.insert_decision(conn, text="Use Postgres", project_id="p1", confidence=0.7)
    second = decision_log.insert_decision(conn, text="Use Postgres", project_id="p2", confidence=0.7)
    # The same sentence about two projects describes two different commitments.
    assert first != second
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 2


def test_redeciding_something_previously_abandoned_is_not_a_duplicate(conn):
    first = decision_log.insert_decision(conn, text="Use Flask", confidence=0.7)
    decision_log.update_decision_state(conn, first, state="abandoned", reason="moved to FastAPI")
    second = decision_log.insert_decision(conn, text="Use Flask", confidence=0.7)
    # Re-adopting something once dropped is exactly what this log should record,
    # not collapse back into the retracted original.
    assert first != second
    assert conn.execute("SELECT COUNT(*) FROM decision_log WHERE state = 'active'").fetchone()[0] == 1


def test_create_decision_reports_duplicate_rather_than_logging_again(conn):
    first = decision_log.create_decision(
        conn, text="We decided to use SQLCipher", reasoning="privacy", alternatives="plain sqlite"
    )
    assert first["status"] == "logged"

    second = decision_log.create_decision(
        conn, text="We decided to use SQLCipher", reasoning="privacy", alternatives="plain sqlite"
    )
    assert second["status"] == "duplicate"
    assert second["decision_id"] == first["decision_id"]


def test_duplicate_does_not_queue_a_pending_candidate(conn):
    decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    # Low signal count would normally route to pending; an already-logged
    # decision must not queue review work for something already recorded.
    result = decision_log.create_decision(conn, text="We chose FastAPI")
    assert result["status"] == "duplicate"
    assert conn.execute("SELECT COUNT(*) FROM decision_candidates_pending").fetchone()[0] == 0


def test_observer_path_suppresses_a_decision_it_already_logged(conn):
    first = decision_log.route_observer_decision(
        conn, text="Ship the Flutter client first",
        signals_found=["commitment_language", "alternative_considered"], raw_quote="q",
    )
    assert first["status"] == "logged"

    second = decision_log.route_observer_decision(
        conn, text="Ship the Flutter client first",
        signals_found=["commitment_language", "alternative_considered"], raw_quote="q",
    )
    assert second["status"] == "duplicate"
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == 1


def test_duplicate_is_not_indexed_twice_in_fts(conn):
    decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    decision_log.insert_decision(conn, text="We chose FastAPI", confidence=0.7)
    # A skipped insert must skip its FTS sync too, or search returns the same
    # decision repeatedly from a stale index.
    assert len(decision_log.search_decisions(conn, query="FastAPI")) == 1
