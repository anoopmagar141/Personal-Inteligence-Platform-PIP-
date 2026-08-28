import sqlite3

import pytest

from backend.memory import profile_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_get_connection_rejects_non_hex_db_key(tmp_path):
    # Security regression test: this used to be `assert re.fullmatch(...)`,
    # which python -O/-OO strip out entirely, silently letting a non-hex
    # db_key reach the f-string-built PRAGMA key statement unchecked.
    with pytest.raises(ValueError, match="hex-encoded"):
        profile_store.get_connection(str(tmp_path / "pip.db"), db_key="not-hex!!")


def test_onboarding_writes_identity_profile_and_completion_flag(conn):
    message = profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        timezone=None,
        current_project={"name": "PIP", "description": "Personal Intelligence Platform"},
        skills=["Python", "AI", "Databases", "Ignored"],
        interaction_style=None,
        preferred_tools=["VS Code", "Git", "Ollama", "SQLite", "pytest", "Ignored"],
    )

    assert message == "Setup complete. PIP is ready."
    identity = conn.execute("SELECT * FROM identity WHERE id = 1").fetchone()
    assert identity["name"] == "BatMan"
    assert identity["language_preference"] == "English"
    assert identity["timezone"] == profile_store.DEFAULT_TIMEZONE

    meta = conn.execute("SELECT * FROM profile_meta WHERE id = 1").fetchone()
    assert meta["onboarding_complete"] == 1
    assert meta["first_session_date"] is not None

    assert conn.execute("SELECT COUNT(*) FROM skill_memory").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM preferred_tools").fetchone()[0] == 5
    style = conn.execute("SELECT * FROM interaction_style WHERE id = 1").fetchone()
    assert style["value"] == profile_store.DEFAULT_INTERACTION_STYLE


def test_profile_view_includes_confidence_and_source_label(conn):
    profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        skills=["Python"],
        interaction_style="Brief summary first",
        preferred_tools=["Git"],
    )

    profile = profile_store.get_profile(conn)
    fields = {row["field"]: row for row in profile}

    assert fields["name"]["confidence"] == 1.0
    assert fields["name"]["source_label"] == "explicit"
    assert fields["Python"]["table"] == "skill_memory"
    assert fields["Python"]["source_label"] == "explicit"
    assert fields["interaction_style"]["value"] == "Brief summary first"


def test_profile_correction_and_soft_delete(conn):
    profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        skills=["Python"],
    )

    profile_store.correct_profile_field(conn, "answer_depth", "brief")
    corrected = profile_store.get_profile_field(conn, "answer_depth")
    assert corrected["value"] == "brief"
    assert corrected["source_label"] == "user_correction"

    assert profile_store.soft_delete_profile_field(conn, "Python") is True
    assert profile_store.get_profile_field(conn, "Python") is None


def test_identity_fields_are_immutable_after_onboarding(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")

    with pytest.raises(ValueError):
        profile_store.correct_profile_field(conn, "name", "Bruce")
    with pytest.raises(ValueError):
        profile_store.soft_delete_profile_field(conn, "timezone")


def test_profile_write_interrupted_before_commit_reopens_with_prewrite_state(tmp_path, db_key):
    db_path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(db_path), db_key=db_key)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    profile_store.correct_profile_field(conn, "answer_depth", "brief")
    conn.close()

    raw_conn = profile_store.get_connection(str(db_path), db_key=db_key)

    class CrashBeforeCommitConnection:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def execute(self, *args, **kwargs):
            return self.wrapped.execute(*args, **kwargs)

        def commit(self):
            raise RuntimeError("simulated crash before final commit")

    with pytest.raises(RuntimeError, match="simulated crash"):
        profile_store.correct_profile_field(
            CrashBeforeCommitConnection(raw_conn),
            "answer_depth",
            "full detail",
        )
    raw_conn.close()

    reopened = profile_store.get_connection(str(db_path), db_key=db_key)
    try:
        field = profile_store.get_profile_field(reopened, "answer_depth")
        assert field["value"] == "brief"
        assert field["source_label"] == "user_correction"
        assert reopened.execute(
            "SELECT COUNT(*) FROM preference_memory WHERE name = ?",
            ("answer_depth",),
        ).fetchone()[0] == 1
    finally:
        reopened.close()


# --- Column migrations for databases created before a column existed ---


def _decision_log_columns(conn):
    return {row["name"] for row in conn.execute("PRAGMA table_info(decision_log)")}


def test_existing_database_missing_a_column_is_repaired(tmp_path, db_key):
    # The case CREATE TABLE IF NOT EXISTS silently misses: a database created
    # before the column existed keeps its original shape forever, and the
    # failure surfaces at query time as "no such column", not at init.
    db_path = str(tmp_path / "old.db")
    conn = profile_store.get_connection(db_path, db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE decision_log DROP COLUMN state_reason")
    conn.commit()
    assert "state_reason" not in _decision_log_columns(conn)

    added = profile_store.apply_column_migrations(conn)

    assert added == ["decision_log.state_reason"]
    assert "state_reason" in _decision_log_columns(conn)


def test_column_migration_is_idempotent(tmp_path, db_key):
    # Runs on every connection via initialize_schema(), so a second pass must
    # be a silent no-op rather than an error or a duplicate column.
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), db_key)
    profile_store.initialize_schema(conn)
    assert profile_store.apply_column_migrations(conn) == []
    assert profile_store.apply_column_migrations(conn) == []


def test_migrated_database_matches_a_freshly_created_one(tmp_path, db_key):
    # A repaired database and a new one must be indistinguishable, or the two
    # populations drift and later code has to handle both shapes.
    fresh = profile_store.get_connection(str(tmp_path / "fresh.db"), db_key)
    profile_store.initialize_schema(fresh)

    migrated = profile_store.get_connection(str(tmp_path / "migrated.db"), db_key)
    profile_store.initialize_schema(migrated)
    migrated.execute("ALTER TABLE decision_log DROP COLUMN state_reason")
    migrated.commit()
    profile_store.apply_column_migrations(migrated)

    assert _decision_log_columns(migrated) == _decision_log_columns(fresh)


def test_retraction_reason_survives_the_migration(tmp_path, db_key):
    # End to end: an old database can be repaired and then record a reason,
    # which is the whole point of the column.
    from backend.memory import decision_log

    conn = profile_store.get_connection(str(tmp_path / "pip.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE decision_log DROP COLUMN state_reason")
    conn.commit()

    decision_id = decision_log.insert_decision(conn, text="A decision made before the column existed")
    profile_store.apply_column_migrations(conn)
    decision_log.update_decision_state(conn, decision_id, state="abandoned", reason="No longer relevant")

    row = conn.execute("SELECT state_reason FROM decision_log WHERE id = ?", (decision_id,)).fetchone()
    assert row["state_reason"] == "No longer relevant"


def test_observed_at_backfill_marks_existing_conversations_as_handled(tmp_path, db_key):
    # Without the backfill, the first start after this upgrade would see every
    # conversation ever held as unprocessed and queue an LLM pass for each -
    # minutes of blocking startup, re-extracting transcripts handled long ago.
    from backend.memory import conversation_store

    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE conversations DROP COLUMN observed_at")
    conn.commit()

    cid = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, cid, "user", "an old conversation")

    added = profile_store.apply_column_migrations(conn)

    assert "conversations.observed_at" in added
    row = conn.execute("SELECT observed_at FROM conversations WHERE id = ?", (cid,)).fetchone()
    assert row["observed_at"] is not None, "pre-existing conversations must not look unprocessed"
    assert conversation_store.list_unobserved(conn) == []


def test_backfill_does_not_rerun_and_overwrite_real_values(tmp_path, db_key):
    # apply_column_migrations runs on every connection; a backfill firing again
    # would stamp genuinely-unobserved conversations as handled and silently
    # discard their learning.
    from backend.memory import conversation_store

    conn = profile_store.get_connection(str(tmp_path / "pip.db"), db_key)
    profile_store.initialize_schema(conn)

    cid = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, cid, "user", "a conversation killed before extraction")

    profile_store.apply_column_migrations(conn)
    profile_store.apply_column_migrations(conn)

    assert [c["id"] for c in conversation_store.list_unobserved(conn)] == [cid]


def test_observed_upto_backfill_gives_existing_observed_conversations_a_mark(tmp_path, db_key):
    # Upgrading a database that already has observed conversations. Without the
    # backfill every one of them would have a NULL high-water mark, and
    # list_unobserved would offer their entire history up for re-extraction on
    # the first start after the upgrade.
    from backend.memory import conversation_store

    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE conversations DROP COLUMN observed_upto_message_id")
    conn.commit()

    observed = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, observed, "user", "already handled")
    conn.execute("UPDATE conversations SET observed_at = datetime('now') WHERE id = ?", (observed,))
    unobserved = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, unobserved, "user", "killed before extraction")
    conn.commit()

    added = profile_store.apply_column_migrations(conn)

    assert "conversations.observed_upto_message_id" in added
    assert conversation_store.observed_upto(conn, observed) is not None
    # The one that was never observed must stay fully recoverable.
    assert conversation_store.observed_upto(conn, unobserved) is None
    assert [c["id"] for c in conversation_store.list_unobserved(conn)] == [unobserved]
    conn.close()
