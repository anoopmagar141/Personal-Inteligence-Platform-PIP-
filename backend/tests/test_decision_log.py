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
