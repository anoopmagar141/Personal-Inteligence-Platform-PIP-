"""
A-2: RECORD_TABLES coverage test.

Promise: every table in a freshly initialised profile database is either in
RECORD_TABLES (with INSERT, UPDATE, DELETE triggers present) or in an explicit
exclusion list in this test, with a one-line reason per table.

Why this matters: a write to any listed table bumps record_version, which is
part of the response cache key. If a table that feeds the model's context is
missing from RECORD_TABLES, the cache serves stale answers silently - the
user sees the same reply even after their profile data changed. No test
compared the schema's tables to RECORD_TABLES before this one.

What this test CANNOT catch: tables created lazily at application level or
only by a migration, not present in a freshly initialised profile. The
exclusion list must be reviewed whenever schema.sql gains a new table.
"""

import pytest

from backend.memory.profile_store import (
    RECORD_TABLES,
    get_connection,
    initialize_schema,
)


# Tables that feed the model's context but are intentionally excluded from
# RECORD_TABLES. Each entry must have a reason. If you add a new table to
# schema.sql, place it in RECORD_TABLES or add it here with a reason -
# an omission in either direction causes this test to fail.
_EXCLUDED = {
    # ── system / plumbing ──────────────────────────────────────────────────
    "record_version": (
        "The counter itself; bumping it from a trigger on it would recurse infinitely."
    ),
    "sqlite_sequence": (
        "SQLite internal AUTOINCREMENT bookkeeping - not a user table."
    ),
    # ── FTS virtual table and its shadow tables ────────────────────────────
    # decision_fts is a VIRTUAL TABLE (FTS5). SQLite creates up to six
    # shadow tables automatically (_data, _idx, _content, _config,
    # _docsize, _segdir / _segments depending on version). None of these are
    # real tables that hold profile context; they are search-index artefacts
    # rebuilt from decision_log, which IS in RECORD_TABLES.
    "decision_fts": "FTS5 virtual table - index over decision_log, not a real content table.",
    "decision_fts_data": "FTS5 shadow table (auto-created by SQLite).",
    "decision_fts_idx": "FTS5 shadow table (auto-created by SQLite).",
    "decision_fts_content": "FTS5 shadow table (auto-created by SQLite).",
    "decision_fts_docsize": "FTS5 shadow table (auto-created by SQLite).",
    "decision_fts_config": "FTS5 shadow table (auto-created by SQLite).",
    "decision_fts_segdir": "FTS5 shadow table (auto-created by SQLite, older SQLite).",
    "decision_fts_segments": "FTS5 shadow table (auto-created by SQLite, older SQLite).",
    # ── operational queues (not model context) ─────────────────────────────
    "memory_candidates_pending": (
        "Staging queue; resolved candidates write to belief tables (which ARE listed). "
        "Including it would fire record_version on every Observer pass."
    ),
    "decision_candidates_pending": (
        "Staging queue for decision candidates; same reasoning as memory_candidates_pending."
    ),
    "pending_observer": (
        "Queue of unprocessed conversations awaiting Observer; not model context."
    ),
    # ── audit / history tables (model reads belief tables, not their history) ─
    "interaction_style_history": (
        "Audit trail of past interaction_style values; the current value "
        "is in interaction_style, which IS in RECORD_TABLES."
    ),
    "skill_contradiction_log": (
        "Records contradictions detected, not the resolved skill beliefs. "
        "skill_memory (the belief table) IS in RECORD_TABLES."
    ),
    "preference_contradiction_log": (
        "Same pattern as skill_contradiction_log; preference_memory IS listed."
    ),
    "memory_observation_log": (
        "Records which conversations have been observed; not fed to the model."
    ),
    "document_decision_conflicts": (
        "Records document-vs-decision conflicts for user review; not model context."
    ),
    # ── conversation store ─────────────────────────────────────────────────
    "conversations": (
        "Conversation metadata; the cache key already incorporates the message "
        "itself, and Stage 7 reads recent turns directly - not through a cached "
        "lookup keyed on record_version."
    ),
    "messages": (
        "Individual message rows; same reasoning as conversations."
    ),
    # ── binary / blob storage ──────────────────────────────────────────────
    "document_blobs": (
        "Raw bytes of ingested documents. The searchable text is indexed in "
        "ChromaDB (not SQLCipher); document metadata is in documents, which IS listed."
    ),
    # ── profile and consent metadata ───────────────────────────────────────
    "profile_meta": (
        "Profile-level metadata (name, language, timezone). Changes here "
        "affect system prompt assembly, but that path is not cached through "
        "record_version - it is rebuilt on every turn."
    ),
    "provider_consent": (
        "Consent flags; changing consent invalidates the provider gate, not "
        "the response cache - that is handled separately in api_revoke_consent."
    ),
    # ── avatar ─────────────────────────────────────────────────────────────
    "identity_avatar": (
        "Profile picture bytes; not fed to the model as context."
    ),
    # ── provider and model config ──────────────────────────────────────────
    "llm_settings": (
        "Stores the user's chosen Ollama model name. Changing the model "
        "changes the cache identity through the selected-model component of "
        "the response-cache key; record_version covers profile context tables."
    ),
    "llm_endpoints": (
        "Provider endpoint configuration; affects routing, not profile context."
    ),
    # ── diagnostics ────────────────────────────────────────────────────────
    "trace_log": (
        "Pipeline timing and diagnostic data; not model context."
    ),
}


@pytest.fixture
def fresh_conn(tmp_path, db_key):
    """Isolated, freshly initialised profile connection."""
    db_path = str(tmp_path / "pip.db")
    conn = get_connection(db_path, db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def _real_tables(conn) -> set[str]:
    """All table names in sqlite_master for this database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'shadow')"
    ).fetchall()
    return {row[0] for row in rows}


def _triggers_for_table(conn, table: str) -> set[str]:
    """Trigger names that exist for the given table."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?",
        (table,),
    ).fetchall()
    return {row[0] for row in rows}


def _assert_schema_tables_accounted(conn, record_tables=None):
    """
    Every table in a freshly initialised profile database is either in
    RECORD_TABLES (with the three required triggers) or in _EXCLUDED with a
    stated reason. A table missing from both is a test failure - it must be
    consciously assigned to one side.
    """
    real = _real_tables(conn)
    listed = set(RECORD_TABLES if record_tables is None else record_tables)

    # Tables that are in RECORD_TABLES but do not actually exist in this
    # fresh schema. That would be a bug in RECORD_TABLES (phantom entries).
    phantom = listed - real
    assert not phantom, (
        f"RECORD_TABLES contains tables not in the schema: {phantom}. "
        "Remove phantom entries from RECORD_TABLES."
    )

    # Tables present in the schema but accounted for in neither list.
    unlisted = real - listed - set(_EXCLUDED)
    assert not unlisted, (
        f"Tables present in the schema but not in RECORD_TABLES or _EXCLUDED: {unlisted}. "
        "Add each table to RECORD_TABLES if it feeds the model's context, "
        "or to _EXCLUDED with a one-line reason."
    )


def test_every_table_is_listed_or_excluded(fresh_conn):
    _assert_schema_tables_accounted(fresh_conn)


def _assert_record_tables_have_all_three_triggers(conn):
    """
    Every table in RECORD_TABLES must have INSERT, UPDATE, and DELETE triggers
    after initialize_schema(). A missing trigger is a silent cache-staleness bug.
    """
    missing = {}
    for table in RECORD_TABLES:
        triggers = _triggers_for_table(conn, table)
        required = {
            f"record_version_{table}_insert",
            f"record_version_{table}_update",
            f"record_version_{table}_delete",
        }
        absent = required - triggers
        if absent:
            missing[table] = absent

    assert not missing, (
        f"Missing triggers for RECORD_TABLES entries: {missing}. "
        "Check install_record_version_triggers() in profile_store.py."
    )


def test_record_tables_have_all_three_triggers(fresh_conn):
    _assert_record_tables_have_all_three_triggers(fresh_conn)


def test_exclusion_list_has_reasons():
    """
    Sanity-check: every entry in _EXCLUDED has a non-empty reason string.
    Prevents silently adding a table with an empty placeholder.
    """
    empty = [name for name, reason in _EXCLUDED.items() if not reason.strip()]
    assert not empty, f"_EXCLUDED entries with no reason: {empty}"


def test_break_it_missing_table_caught(fresh_conn):
    """
    Break-it: remove 'documents' from RECORD_TABLES and add a new schema table.
    The actual coverage assertion must fail and name both omissions.
    """
    # Create a dummy table that feeds context but is not in either list.
    fresh_conn.execute(
        "CREATE TABLE IF NOT EXISTS _test_unlisted (id INTEGER PRIMARY KEY)"
    )
    fresh_conn.commit()

    with pytest.raises(AssertionError) as error:
        _assert_schema_tables_accounted(
            fresh_conn,
            record_tables=tuple(table for table in RECORD_TABLES if table != "documents"),
        )
    assert "documents" in str(error.value)
    assert "_test_unlisted" in str(error.value)


def test_break_it_missing_trigger_caught(fresh_conn):
    """
    Break-it: manually drop one trigger for 'documents' and confirm the
    trigger-presence test catches it.
    """
    fresh_conn.execute("DROP TRIGGER IF EXISTS record_version_documents_delete")
    fresh_conn.commit()

    with pytest.raises(AssertionError) as error:
        _assert_record_tables_have_all_three_triggers(fresh_conn)
    assert "documents" in str(error.value)
    assert "record_version_documents_delete" in str(error.value)
