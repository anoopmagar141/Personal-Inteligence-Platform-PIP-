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


# --- Session counting -------------------------------------------------------
# profile_meta.session_count was written once by onboarding and never touched
# again, so everything the constitution measures in sessions had nothing to
# measure against.


def test_begin_session_returns_none_before_onboarding(conn):
    """
    No profile_meta row exists until onboarding. A session that predates the
    profile must not be counted, and must not raise either.
    """
    assert profile_store.current_session_no(conn) is None
    assert profile_store.begin_session(conn) is None


def test_onboarding_is_session_one(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    assert profile_store.current_session_no(conn) == 1


def test_begin_session_increments_and_stamps_last_session_date(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    before = conn.execute("SELECT last_session_date FROM profile_meta WHERE id = 1").fetchone()[0]

    assert profile_store.begin_session(conn) == 2
    assert profile_store.begin_session(conn) == 3
    assert profile_store.current_session_no(conn) == 3

    after = conn.execute("SELECT last_session_date FROM profile_meta WHERE id = 1").fetchone()[0]
    assert after >= before


def test_begin_session_does_not_reset_on_repeat_onboarding(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    profile_store.begin_session(conn)
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    assert profile_store.current_session_no(conn) == 2


def test_contradictions_are_stamped_with_the_current_session(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    profile_store.correct_profile_field(conn, "editor", "vscode")
    pref_id = conn.execute("SELECT id FROM preference_memory WHERE name = 'editor'").fetchone()["id"]

    profile_store.log_preference_contradiction(conn, pref_id, "used vim")
    profile_store.begin_session(conn)
    profile_store.log_preference_contradiction(conn, pref_id, "used vim again")

    stamps = [
        r["session_no"]
        for r in conn.execute(
            "SELECT session_no FROM preference_contradiction_log ORDER BY id"
        )
    ]
    assert stamps == [1, 2]


def test_session_no_column_is_added_to_an_existing_database(tmp_path, db_key):
    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE preference_contradiction_log DROP COLUMN session_no")
    conn.commit()

    assert profile_store.apply_column_migrations(conn) == ["preference_contradiction_log.session_no"]
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(preference_contradiction_log)")}
    assert "session_no" in columns


def test_session_no_is_deliberately_not_backfilled(tmp_path, db_key):
    """
    There is no record of which session an existing contradiction belonged to.
    Inventing one would either merge unrelated contradictions into a single
    session (disarming an override that was already armed) or split one session
    into several (arming one that should not be). NULL is the honest value, and
    the enforcer counts NULL rows one-each, which is what they were written
    under.
    """
    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("INSERT INTO preference_memory (name, value, source_label) VALUES ('editor', 'vscode', 'explicit')")
    pref_id = conn.execute("SELECT id FROM preference_memory WHERE name = 'editor'").fetchone()["id"]
    conn.execute("ALTER TABLE preference_contradiction_log DROP COLUMN session_no")
    conn.execute(
        "INSERT INTO preference_contradiction_log (preference_id, contradiction_text, created_at) "
        "VALUES (?, 'used vim', '2026-01-01T00:00:00Z')",
        (pref_id,),
    )
    conn.commit()

    profile_store.apply_column_migrations(conn)

    assert conn.execute("SELECT session_no FROM preference_contradiction_log").fetchone()["session_no"] is None


def test_observation_log_appears_on_an_existing_database(tmp_path, db_key):
    """
    memory_observation_log is a new TABLE rather than a new column, so
    schema.sql's CREATE TABLE IF NOT EXISTS repairs an existing database on the
    next connection with no migration entry needed. Asserted rather than assumed
    - reinforcement silently stops accumulating if the table is missing, and the
    symptom (nothing new is ever learned) is the same one it was built to fix.
    """
    db_path = str(tmp_path / "old.db")
    conn = profile_store.get_connection(db_path, db_key)
    profile_store.initialize_schema(conn)
    conn.execute("DROP TABLE memory_observation_log")
    conn.commit()
    conn.close()

    reopened = profile_store.get_connection(db_path, db_key)
    profile_store.initialize_schema(reopened)
    tables = {
        r["name"]
        for r in reopened.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    reopened.close()
    assert "memory_observation_log" in tables


def test_origin_backfills_existing_pending_candidates_as_observer(tmp_path, db_key):
    """
    Every pending candidate predating the column came from the Observer - the
    verification loop that writes the other value did not exist yet. Left NULL,
    a client would have no way to word the question and would have to guess.
    """
    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    conn.execute("ALTER TABLE memory_candidates_pending DROP COLUMN origin")
    conn.execute(
        "INSERT INTO memory_candidates_pending "
        "(target_table, field_name, proposed_value, label, evidence_count, "
        " evidence_text, validation_status, created_at) "
        "VALUES ('preference_memory', 'editor', 'vim', 'inferred', 1, 'x', "
        "        'TIER_2_REQUIRED', '2026-01-01T00:00:00Z')"
    )
    conn.commit()

    assert "memory_candidates_pending.origin" in profile_store.apply_column_migrations(conn)
    assert conn.execute("SELECT origin FROM memory_candidates_pending").fetchone()["origin"] == "observer"


def _make_legacy_trace_log(conn):
    """The original shape: composite primary key, no id column."""
    conn.execute("DROP TABLE IF EXISTS trace_log")
    conn.execute("""
        CREATE TABLE trace_log (
            trace_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            error_detail TEXT,
            PRIMARY KEY (trace_id, stage)
        )
    """)
    conn.commit()


def test_stale_trace_log_is_rebuilt_with_an_id_key(tmp_path, db_key):
    """
    CREATE TABLE IF NOT EXISTS cannot change a primary key, so without this an
    upgraded database would keep the composite key while a fresh one got the id
    key - and the same INSERT would succeed on one and raise IntegrityError on
    the other.
    """
    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    _make_legacy_trace_log(conn)

    assert profile_store.rebuild_trace_log_if_stale(conn) is True

    columns = {r["name"] for r in conn.execute("PRAGMA table_info(trace_log)")}
    assert "id" in columns


def test_trace_log_rebuild_is_idempotent(tmp_path, db_key):
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), db_key)
    profile_store.initialize_schema(conn)
    assert profile_store.rebuild_trace_log_if_stale(conn) is False
    assert profile_store.rebuild_trace_log_if_stale(conn) is False


def test_trace_log_rebuild_preserves_any_rows_it_finds(tmp_path, db_key):
    """
    The table should be empty in every existing database, since nothing ever
    wrote to it - but the rebuild copies rows rather than relying on that
    argument being right.
    """
    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    _make_legacy_trace_log(conn)
    conn.execute(
        "INSERT INTO trace_log (trace_id, timestamp, stage, status, message, error_detail) "
        "VALUES ('t1', '2026-01-01T00:00:00Z', 'stage_01', 'ok', 'kept', '')"
    )
    conn.commit()

    profile_store.rebuild_trace_log_if_stale(conn)

    rows = conn.execute("SELECT trace_id, message FROM trace_log").fetchall()
    assert [(r["trace_id"], r["message"]) for r in rows] == [("t1", "kept")]


def test_a_rebuilt_trace_log_accepts_repeated_stages(tmp_path, db_key):
    """
    The point of the rebuild: the old key silently dropped the second entry for
    a stage, and the stages that log twice are the error paths.
    """
    from backend.core import trace

    conn = profile_store.get_connection(str(tmp_path / "old.db"), db_key)
    profile_store.initialize_schema(conn)
    _make_legacy_trace_log(conn)
    profile_store.rebuild_trace_log_if_stale(conn)

    trace.stage_log(conn, "t1", "stage_08_provider_gate", "error", "first")
    trace.stage_log(conn, "t1", "stage_08_provider_gate", "error", "second")

    assert len(trace.get_trace(conn, "t1")) == 2


def test_initialize_schema_rebuilds_a_stale_trace_log(tmp_path, db_key):
    """A database repairs itself on the next connection, with nothing to run."""
    db_path = str(tmp_path / "old.db")
    conn = profile_store.get_connection(db_path, db_key)
    profile_store.initialize_schema(conn)
    _make_legacy_trace_log(conn)
    conn.close()

    reopened = profile_store.get_connection(db_path, db_key)
    profile_store.initialize_schema(reopened)
    columns = {r["name"] for r in reopened.execute("PRAGMA table_info(trace_log)")}
    reopened.close()
    assert "id" in columns
