import datetime
import logging
import os
import re
import sqlite3
import uuid
from pathlib import Path, PurePath
from typing import Any, Iterable

from backend.config.settings import get_settings
from backend.core.types import TIMESTAMP_FORMAT, now_utc

logger = logging.getLogger(__name__)

try:
    import sqlcipher3
except ImportError:  # pragma: no cover - exercised when SQLCipher is installed.
    sqlcipher3 = None


SCHEMA_PATH = Path(__file__).parent.parent / "core" / "schema.sql"
CONSENT_SEED_PATH = Path(__file__).parent.parent.parent / "config" / "provider_consent.json"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_INTERACTION_STYLE = "adaptive"

# The identity table's own columns, as opposed to everything else get_profile()
# surfaces. They are singular, NOT NULL, and typed by the user at onboarding
# rather than inferred from anything - which is why they are the only fields
# with a rule about WHO may write them. See _write_profile_value.
IDENTITY_FIELDS = frozenset({"name", "language_preference", "timezone"})


def get_connection(db_path: str, db_key: str | None = None):
    # Was `assert re.fullmatch(...)` - assert statements are compiled out
    # entirely under `python -O`/`-OO` (security review finding), which would
    # silently drop this validation and let db_key reach the f-string PRAGMA
    # below unchecked. An explicit raise survives every optimization level.
    if db_key is not None and not re.fullmatch(r"[0-9a-fA-F]+", db_key):
        raise ValueError("db_key must be hex-encoded")

    if db_key is not None:
        if sqlcipher3 is None:
            raise RuntimeError(
                "db_key was provided but the sqlcipher3 package is not installed. "
                "Refusing to silently fall back to an unencrypted SQLite database."
            )
        conn = sqlcipher3.connect(db_path)
        conn.execute(f"PRAGMA key = \"x'{db_key}'\"")
        conn.row_factory = sqlcipher3.dbapi2.Row
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# Columns added to schema.sql after databases already existed in the wild.
#
# Every CREATE TABLE in schema.sql is IF NOT EXISTS, which means it shapes new
# databases only - an existing one silently keeps whatever columns it was
# created with, and the first query naming a new column fails at runtime with
# "no such column" rather than at init. SQLite has no ADD COLUMN IF NOT EXISTS,
# so each entry is guarded by a PRAGMA table_info check instead.
#
# Deliberately run from initialize_schema() rather than as another script in
# scripts/: open_app_connection() calls initialize_schema() on every connection,
# so an existing database repairs itself on the next start with nothing for the
# user to remember to run. The check is a local PRAGMA read - cheap enough to
# pay per connection, and paid only once per column thereafter.
#
# Only ever ADD nullable columns here. Renames, drops and type changes need a
# real table rebuild, which does not belong in a startup path.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # See schema.sql: update_decision_state() required a reason and had nowhere
    # to store it.
    ("decision_log", "state_reason", "TEXT"),
    # See schema.sql: NULL marks a conversation the Observer never processed.
    ("conversations", "observed_at", "TEXT"),
    # See schema.sql: which session a contradiction was observed in, so the
    # behavioral override can count sessions rather than rows. Deliberately no
    # backfill - there is no record of which session an existing row belonged
    # to, and inventing one would either merge unrelated contradictions into a
    # single session or split one session into several. The enforcer counts a
    # NULL row as its own session, which is what it did before this column, so
    # an upgraded database keeps the behaviour it already had.
    ("preference_contradiction_log", "session_no", "INTEGER"),
    # See schema.sql: which kind of question a pending candidate is asking.
    ("memory_candidates_pending", "origin", "TEXT"),
    # See schema.sql: skill contradictions are counted by session too, now that
    # anything writes them at all.
    ("skill_contradiction_log", "session_no", "INTEGER"),
    # See schema.sql: what Stage 0 measures the warm-start gap from.
    ("profile_meta", "previous_session_date", "TEXT"),
)

# Run once, immediately after the named column is first added, to give existing
# rows a sensible value. Keyed by "table.column" so a backfill can never fire
# twice: apply_column_migrations only calls it on the pass that actually adds
# the column.
_BACKFILLS: dict[str, str] = {
    # Every conversation predating this column has already had whatever
    # Observer treatment it was going to get, and is stamped as observed rather
    # than left NULL. Without this, the first start after the upgrade would see
    # the entire conversation history as unprocessed and queue an LLM pass for
    # each one - minutes of blocking startup, re-extracting from transcripts
    # that were handled long ago. Recovery is meant for sessions genuinely lost
    # to a kill, which only accumulate one at a time.
    # An upgraded database has no record of when the previous session ended, so
    # this seeds from the value that was standing in for it: session_snapshot's
    # date, the source Stage 0 read until now. One start on the old, slightly
    # wrong number beats one start treated as a first-ever run, which would
    # load no warm-start context at all.
    "profile_meta.previous_session_date": (
        "UPDATE profile_meta SET previous_session_date = "
        "(SELECT snapshot_date FROM session_snapshot WHERE id = 1) "
        "WHERE previous_session_date IS NULL"
    ),
    # Every pending candidate predating this column came from the Observer -
    # the verification loop that writes the other value did not exist yet.
    "memory_candidates_pending.origin": (
        "UPDATE memory_candidates_pending SET origin = 'observer' WHERE origin IS NULL"
    ),
    "conversations.observed_at": (
        "UPDATE conversations SET observed_at = datetime('now') WHERE observed_at IS NULL"
    ),
}


def apply_column_migrations(conn) -> list[str]:
    """
    Adds any columns in _ADDED_COLUMNS missing from an existing database.
    Idempotent. Returns the "table.column" strings actually added, so a caller
    can log a real migration and stay quiet on the usual no-op.
    """
    added = []
    for table, column, decl in _ADDED_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # table absent entirely - schema.sql owns creating it, not this
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            key = f"{table}.{column}"
            # Only on the pass that actually adds the column, so a backfill
            # cannot re-run later and overwrite real values with defaults.
            backfill = _BACKFILLS.get(key)
            if backfill:
                conn.execute(backfill)
            added.append(key)
    if added:
        conn.commit()
    return added


def rebuild_trace_log_if_stale(conn) -> bool:
    """
    Rebuilds trace_log if it still has its original (trace_id, stage) primary
    key. Returns True only on the pass that actually rebuilt it.

    _ADDED_COLUMNS above states the rule this deliberately steps outside:
    "Renames, drops and type changes need a real table rebuild, which does not
    belong in a startup path." That rule is about not risking user data during
    boot, and it is the right default. This one case is different, and the
    difference is checkable rather than asserted:

      - Nothing has ever written to trace_log. core/trace.py wrote to a JSON
        file for the whole life of the project, so the table is empty in every
        existing database - there is no user data to risk.
      - The rebuild copies rows across anyway. If that reasoning is somehow
        wrong on some database, the rows survive rather than the argument
        having to be right.
      - It runs inside a transaction, so a failure mid-way leaves the original
        table intact rather than a half-migrated one.
      - It is guarded by a shape check, so it runs once per database and is a
        cheap PRAGMA read on every connection after that.

    Leaving the old shape in place was the alternative, and it is worse: new
    databases would get the id-keyed table from schema.sql while existing ones
    kept the composite key, so the same write would succeed on one and raise
    IntegrityError on the other. This codebase already has a test insisting a
    repaired database and a fresh one are indistinguishable, and that is the
    reason why.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(trace_log)")}
    if not columns or "id" in columns:
        return False  # absent (schema.sql owns creating it) or already rebuilt

    logger.info("Rebuilding trace_log with an id primary key (was keyed by trace_id+stage).")
    conn.execute("BEGIN")
    try:
        conn.execute("""
            CREATE TABLE trace_log_rebuilt (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                error_detail TEXT
            )
        """)
        conn.execute("""
            INSERT INTO trace_log_rebuilt (trace_id, timestamp, stage, status, message, error_detail)
            SELECT trace_id, timestamp, stage, status, message, error_detail FROM trace_log
        """)
        conn.execute("DROP TABLE trace_log")
        conn.execute("ALTER TABLE trace_log_rebuilt RENAME TO trace_log")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_log_trace_id ON trace_log(trace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trace_log_timestamp ON trace_log(timestamp)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def rebuild_active_projects_if_stale(conn) -> bool:
    """
    Widens active_projects.status to allow 'deleted' on a database created
    before that was a legal value.

    SQLite cannot alter a CHECK constraint, so this is the same rebuild
    rebuild_trace_log_if_stale() does, with one difference that matters much
    more here: conversations.project_id REFERENCES active_projects ON DELETE
    SET NULL, and foreign keys are ON (schema.sql line 5, and get_connection).
    Dropping the table with enforcement live would fire that rule and quietly
    unlink every conversation from its project - destroying exactly the data
    this table exists to relate. So enforcement goes off for the rebuild and
    back on afterwards, which is SQLite's own documented procedure, and the
    pragma is set OUTSIDE the transaction because it is a no-op inside one.

    Guarded by reading the stored DDL, so it runs once per database and is a
    cheap sqlite_master read on every connection after that.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'active_projects'"
    ).fetchone()
    if row is None:
        return False  # absent; schema.sql owns creating it
    if "'deleted'" in (row["sql"] or ""):
        return False  # already widened

    logger.info("Rebuilding active_projects so a project can be retracted (status='deleted').")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        conn.execute("""
            CREATE TABLE active_projects_rebuilt (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                status TEXT DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'completed', 'deleted')),
                last_active TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO active_projects_rebuilt (project_id, name, description, status, last_active)
            SELECT project_id, name, description, status, last_active FROM active_projects
        """)
        conn.execute("DROP TABLE active_projects")
        conn.execute("ALTER TABLE active_projects_rebuilt RENAME TO active_projects")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return True


_DEFAULT_DOCUMENTS_ROOT = Path(__file__).parent.parent.parent / "data" / "documents"


def documents_root() -> Path:
    """
    Where ingested files live on THIS machine.

    A function reading an override, not a constant, for the reason conftest
    keeps a table of exactly these: a real path baked into a module is a path
    the test suite writes to. This one already did - the first run of the
    rebuild test put a notes.txt into the developer's actual data/documents/,
    which is the same shape as the unisolated PIP_SALT_PATH that could have
    destroyed the real database.

    Deliberately not imported from vector_store, which owns the matching
    constant for its ingestion sandbox: importing it here would pull chromadb
    and sentence-transformers into every database open, and initialize_schema()
    runs on every connection.
    """
    override = os.environ.get("PIP_DOCUMENTS_ROOT")
    return Path(override) if override else _DEFAULT_DOCUMENTS_ROOT


def initialize_schema(conn) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    apply_column_migrations(conn)
    rebuild_trace_log_if_stale(conn)
    rebuild_active_projects_if_stale(conn)
    backfill_document_blobs(conn)
    seed_provider_consent(conn)


def store_document_content(conn, document_id: int, content: bytes) -> None:
    """
    Keep the bytes of an ingested document inside the database.

    Lives here rather than in vector_store because initialize_schema() calls
    the backfill below on every connection, and vector_store cannot be
    imported that early: it pulls in chromadb and sentence-transformers, which
    is seconds of import time and a hard dependency on a machine that may be
    doing nothing but opening a database. This is plain SQLite and a file
    read; it needs neither.
    """
    conn.execute(
        "INSERT INTO document_blobs (document_id, content, byte_size, stored_at) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(document_id) DO UPDATE SET "
        "content = excluded.content, byte_size = excluded.byte_size, stored_at = excluded.stored_at",
        (document_id, content, len(content), now_utc()),
    )
    conn.commit()


def document_content(conn, document_id: int) -> bytes | None:
    """The stored bytes, or None if this document predates them and has no file."""
    row = conn.execute(
        "SELECT content FROM document_blobs WHERE document_id = ?", (document_id,)
    ).fetchone()
    return bytes(row[0]) if row else None


def documents_missing_content(conn) -> list[dict[str, Any]]:
    """
    Active documents whose bytes are not in the database.

    One indexed anti-join, and on a healthy installation it returns nothing -
    which is what makes calling it per connection affordable. Exposed rather
    than kept private because the export needs it too: a backup that silently
    omits a document is exactly the class of failure this whole feature
    exists to prevent, so /export says so rather than discovering it on the
    machine you are restoring onto.
    """
    return [
        dict(row)
        for row in conn.execute(
            "SELECT d.id, d.file_path FROM documents d "
            "LEFT JOIN document_blobs b ON b.document_id = d.id "
            "WHERE d.status = 'active' AND b.document_id IS NULL"
        )
    ]


def backfill_document_blobs(conn) -> int:
    """
    Store the bytes of any already-ingested document that predates this table.

    Run from initialize_schema() for the reason every migration here is: a
    database repairs itself on the next start, with nothing for the user to
    remember to run. Somebody who ingested four documents last month and
    upgrades today gets a complete backup without knowing anything changed.

    A file that is no longer on disk is skipped, not an error. Its registry
    row is still true - the document WAS ingested, and its chunks may still be
    in the index - and failing a database open because a source file was moved
    would be a spectacular overreaction. The gap stays visible through
    documents_missing_content().

    Returns how many were stored, so a caller that cares can say so.
    """
    stored = 0
    for row in documents_missing_content(conn):
        try:
            content = Path(row["file_path"]).read_bytes()
        except OSError:
            continue
        store_document_content(conn, row["id"], content)
        stored += 1
    return stored


def materialise_documents(conn, *, into: Path | None = None) -> dict[str, list[str]]:
    """
    Write stored document bytes back to disk.

    The other half of the round trip, and the step that makes a restore
    complete: on a second machine the recorded paths point at files that have
    never existed there, so the bytes have to land somewhere before anything
    can re-embed them.

    Written to `into` (the documents directory on THIS machine) under each
    document's original file name, not to the absolute path recorded on the
    old machine - that path may name a drive that does not exist here, and
    writing to an arbitrary absolute path out of a restored database would be
    a fine way to turn a backup file into an arbitrary-write primitive.

    A document whose recorded file is already on disk is left completely alone -
    not rewritten, and its registry row not repointed. That restraint is the
    whole correctness condition here: this runs inside every index rebuild,
    including rebuilds on the machine that ingested the files in the first
    place, where every path is already valid and there is nothing to restore.
    Acting on those would rewrite working paths to point somewhere else.
    """
    target = Path(into) if into else documents_root()

    written: list[str] = []
    skipped: list[str] = []
    for row in conn.execute(
        "SELECT d.id, d.file_path, b.content FROM documents d "
        "JOIN document_blobs b ON b.document_id = d.id "
        "WHERE d.status = 'active'"
    ):
        if Path(row["file_path"]).exists():
            continue  # nothing to put back

        # Under its own name in this machine's documents directory, never the
        # absolute path recorded on the other machine: that path may name a
        # drive this one does not have, and writing to an arbitrary absolute
        # path out of a restored database would turn a backup file into an
        # arbitrary-write primitive.
        name = PurePath(row["file_path"].replace(chr(92), '/')).name
        destination = target / name

        if destination.exists():
            # The file is here under its own name, but the registry points at
            # where it used to live. Repoint rather than overwrite: the copy on
            # disk is the user's, and may be newer than the backup's.
            skipped.append(str(destination))
        else:
            target.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(bytes(row["content"]))
            written.append(str(destination))

        conn.execute(
            "UPDATE documents SET file_path = ? WHERE id = ?", (str(destination), row["id"])
        )
    conn.commit()
    return {"written": written, "skipped": skipped}


def seed_provider_consent(conn, seed_path: Path | None = None) -> None:
    """Load default provider rows from config/provider_consent.json into the
    provider_consent table, but ONLY if the table is currently empty.

    Idempotent: calling this on every app startup is safe — it is a no-op
    when the table already has rows, so it cannot overwrite user-granted
    consent or duplicate existing rows after an app restart.

    Called from initialize_schema() so the seed runs immediately after the
    DB schema is created, as part of the single DB-init sequence. This is
    the correct call site because:
      - initialize_schema() is the only function that brings the DB from
        zero to a usable state.
      - Provider consent rows must exist before Stage 8 can gate any request.
      - Placing the call here ensures no code path can reach Stage 8 with
        an empty provider_consent table after a fresh DB creation.
    """
    import json  # local import — keep stdlib json out of module-level scope

    path = seed_path if seed_path is not None else CONSENT_SEED_PATH
    with open(path, "r", encoding="utf-8") as f:
        seed = json.load(f)

    row_count = conn.execute("SELECT COUNT(*) FROM provider_consent").fetchone()[0]
    if row_count > 0:
        return  # already seeded — no-op

    for provider in seed["providers"]:
        conn.execute(
            """
            INSERT INTO provider_consent
                (provider_id, is_cloud, user_consented, consent_scope, revoked)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                provider["provider_id"],
                1 if provider["is_cloud"] else 0,
                provider["user_consented"],
                provider["consent_scope"],
                provider["revoked"],
            ),
        )
    conn.commit()


def complete_onboarding(
    conn,
    *,
    name: str,
    language_preference: str,
    timezone: str | None = None,
    current_project: dict[str, str] | None = None,
    skills: Iterable[str] | None = None,
    interaction_style: str | None = None,
    preferred_tools: Iterable[str] | None = None,
) -> str:
    if not name.strip():
        raise ValueError("name is required")
    if not language_preference.strip():
        raise ValueError("language_preference is required")

    timestamp = now_utc()
    conn.execute(
        """
        INSERT INTO identity (id, name, language_preference, timezone)
        VALUES (1, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            language_preference = excluded.language_preference,
            timezone = excluded.timezone
        """,
        (name.strip(), language_preference.strip(), (timezone or DEFAULT_TIMEZONE).strip()),
    )
    conn.execute(
        """
        INSERT INTO profile_meta (
            id, session_count, schema_version, constitution_version,
            first_session_date, last_session_date, onboarding_complete
        )
        VALUES (1, 1, '1.0', '1.0', ?, ?, 1)
        ON CONFLICT(id) DO UPDATE SET
            first_session_date = COALESCE(profile_meta.first_session_date, excluded.first_session_date),
            last_session_date = excluded.last_session_date,
            onboarding_complete = 1
        """,
        (timestamp, timestamp),
    )

    if current_project and current_project.get("name"):
        create_project(
            conn,
            current_project["name"],
            current_project.get("description", ""),
            timestamp=timestamp,
        )

    for skill in _limited_clean_values(skills, limit=3):
        upsert_skill(conn, skill, level=0.5, source_label="explicit")

    style = (interaction_style or DEFAULT_INTERACTION_STYLE).strip()
    set_interaction_style(conn, style, source_label="explicit", timestamp=timestamp)

    for tool_name in _limited_clean_values(preferred_tools, limit=5):
        conn.execute(
            """
            INSERT INTO preferred_tools (tool_name, evidence_count, last_observed, status)
            VALUES (?, 1, ?, 'active')
            ON CONFLICT(tool_name) DO UPDATE SET
                evidence_count = preferred_tools.evidence_count + 1,
                last_observed = excluded.last_observed,
                status = 'active'
            """,
            (tool_name, timestamp),
        )

    conn.commit()
    return "Setup complete. PIP is ready."


def get_profile(conn) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    identity = conn.execute("SELECT * FROM identity WHERE id = 1").fetchone()
    if identity:
        rows.extend(
            [
                _profile_row("identity", "name", identity["name"], 1.0, "explicit", "active"),
                _profile_row(
                    "identity",
                    "language_preference",
                    identity["language_preference"],
                    1.0,
                    "explicit",
                    "active",
                ),
                _profile_row("identity", "timezone", identity["timezone"], 1.0, "explicit", "active"),
            ]
        )

    rows.extend(
        _profile_row("skill_memory", row["name"], row["level"], row["confidence"], row["source_label"], row["status"])
        for row in conn.execute("SELECT * FROM skill_memory WHERE status = 'active' ORDER BY name")
    )
    rows.extend(
        _profile_row(
            "preference_memory",
            row["name"],
            row["value"],
            row["confidence"],
            row["source_label"],
            row["status"],
        )
        for row in conn.execute("SELECT * FROM preference_memory WHERE status = 'active' ORDER BY name")
    )
    rows.extend(
        _profile_row(
            "goal_memory",
            f"goal:{row['id']}",
            row["goal_text"],
            row["confidence"],
            "explicit",
            row["status"],
            stale=bool(row["decay_flag"]),
        )
        for row in conn.execute("SELECT * FROM goal_memory WHERE status = 'active' ORDER BY updated_at DESC")
    )
    # topic_interests and document_access_patterns are set-membership tables in
    # the same family as preferred_tools above - a name, an evidence counter,
    # a status - so they render the same way (field == value, no separate value
    # to show). Both were declared in the schema, named in the constitution's
    # observer_may_write list, and selected from by nothing at all: Stage 11's
    # own comment gave "nothing in the codebase reads them" as the reason not to
    # write to them either, which is a stable, self-justifying kind of dead.
    # This is the read half that reason asked for.
    rows.extend(
        _profile_row("topic_interests", row["topic"], row["topic"], 1.0, "inferred", row["status"])
        for row in conn.execute(
            "SELECT * FROM topic_interests WHERE status = 'active' "
            "ORDER BY evidence_count DESC, topic"
        )
    )
    rows.extend(
        _profile_row(
            "document_access_patterns",
            row["document_path"],
            row["document_path"],
            1.0,
            "inferred",
            row["status"],
        )
        for row in conn.execute(
            "SELECT * FROM document_access_patterns WHERE status = 'active' "
            "ORDER BY access_count DESC, last_accessed DESC LIMIT 10"
        )
    )
    style = conn.execute("SELECT * FROM interaction_style WHERE id = 1").fetchone()
    if style:
        rows.append(
            _profile_row(
                "interaction_style",
                "interaction_style",
                style["value"],
                style["confidence"],
                style["source_label"],
                "active",
            )
        )
    rows.extend(
        _profile_row("active_projects", row["name"], row["description"], 1.0, "explicit", row["status"])
        for row in conn.execute("SELECT * FROM active_projects WHERE status = 'active' ORDER BY last_active DESC")
    )
    rows.extend(
        _profile_row("preferred_tools", row["tool_name"], row["tool_name"], 1.0, "explicit", row["status"])
        for row in conn.execute("SELECT * FROM preferred_tools WHERE status = 'active' ORDER BY tool_name")
    )
    return rows


def get_profile_field(conn, field: str) -> dict[str, Any] | None:
    for row in get_profile(conn):
        if row["field"] == field:
            return row
    return None


def correct_profile_field(conn, field: str, value: str) -> None:
    """
    Applies a correction the user made directly, to whichever table already
    holds the field.

    The table is looked up rather than passed in. A caller that named the
    target table could name the wrong one, and there is no second source of
    truth to check it against - get_profile() already knows where every field
    lives, because it is what put the field on screen in the first place.

    A field nobody has seen before becomes a preference. That is this
    function's oldest behaviour and several callers depend on it: it is how a
    preference gets created at all outside the Observer, and "correcting"
    something PIP has never recorded is really just stating it.
    """
    existing = get_profile_field(conn, field)
    target_table = existing["table"] if existing else "preference_memory"

    if target_table == "skill_memory":
        # skill_memory.level is a REAL, and SQLite would happily store the
        # string "expert" in it - then every comparison against that row
        # silently stops meaning anything. Rejected here, where the sentence
        # can still reach the person who typed it.
        try:
            level = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"A skill level is a number between 0 and 1, not {value!r}."
            ) from None
        if not 0.0 <= level <= 1.0:
            raise ValueError(f"A skill level must be between 0 and 1, not {level}.")
        value = level

    _write_profile_value(
        conn,
        target_table=target_table,
        field=field,
        value=value,
        source_label="user_correction",
        # The only caller that passes this. A direct correction is the user
        # stating a fact about themselves; every other path into this function
        # is PIP inferring one.
        allow_identity=True,
    )


GOAL_FIELD_PREFIX = "goal:"


def goal_id_from_field(field: str) -> str | None:
    """
    The goal id a field name addresses, or None when the name does not address
    one at all.

    goal_memory is the only profile table with no natural name column - a goal
    IS its text - so get_profile() hands out a synthetic "goal:<id>" handle to
    give the UI something stable to send back when editing an existing goal.
    That convention only ever worked for editing. The Observer proposes NEW
    goals and cannot know an id that does not exist yet, so it emits the
    category names from its own APPROVED_MEMORY_FIELDS ("active_goals",
    "project_objectives") instead - and every goal write path rejected those
    outright with "Invalid goal field name".

    The result was a goal candidate that could pass validation, be queued for
    the user, be shown to them, and then fail on confirmation with no way to
    ever apply it. Nothing was mis-stored; the two halves of the system simply
    never agreed on what a goal is called, and no single call site could see
    both halves.

    Resolved by making the id OPTIONAL rather than by forcing one convention on
    both sides, because the two callers are genuinely asking different
    questions. "goal:7" means THIS row. "active_goals" means a goal whose
    identity is its text, which is the only identity a new goal can have - the
    same way active_projects is matched by name and preference_memory by key.
    The category itself is discarded on purpose: goal_memory has no column for
    one, and inventing schema to make a name look meaningful would be storing a
    distinction nothing reads.
    """
    if not field or not field.startswith(GOAL_FIELD_PREFIX):
        return None
    return field.split(":", 1)[1]


def soft_delete_profile_field(conn, field: str) -> bool:
    if field in {"name", "language_preference", "timezone"}:
        raise ValueError("immutable identity fields cannot be deleted")

    updated = 0
    for table, column in (
        ("skill_memory", "name"),
        ("preference_memory", "name"),
        ("preferred_tools", "tool_name"),
        ("topic_interests", "topic"),
        ("document_access_patterns", "document_path"),
    ):
        cur = conn.execute(f"UPDATE {table} SET status = 'deleted' WHERE {column} = ?", (field,))
        updated += cur.rowcount

    goal_id = goal_id_from_field(field)
    if goal_id is not None:
        cur = conn.execute("UPDATE goal_memory SET status = 'deleted' WHERE id = ?", (goal_id,))
        updated += cur.rowcount

    conn.commit()
    return updated > 0


def create_project(conn, name: str, description: str = "", *, timestamp: str | None = None) -> str:
    project_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO active_projects (project_id, name, description, status, last_active)
        VALUES (?, ?, ?, 'active', ?)
        """,
        (project_id, name.strip(), description.strip(), timestamp or now_utc()),
    )
    conn.commit()
    return project_id


def list_projects(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            # Retracted projects are excluded here rather than deleted from the
            # table: a decision or conversation still pointing at one keeps a
            # real row to point at, and nothing dangles.
            "SELECT * FROM active_projects WHERE status != 'deleted' "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, last_active DESC"
        )
    ]


def update_project_status(conn, project_id: str, status: str) -> None:
    # 'deleted' is here with the rest rather than behind its own endpoint: it
    # is a status like any other, and routing it separately would imply the row
    # goes away, which it does not.
    if status not in {"active", "archived", "completed", "deleted"}:
        raise ValueError("invalid project status")
    conn.execute(
        "UPDATE active_projects SET status = ?, last_active = ? WHERE project_id = ?",
        (status, now_utc(), project_id),
    )
    conn.commit()


def activate_project(conn, project_id: str) -> None:
    conn.execute("UPDATE active_projects SET status = 'active', last_active = ? WHERE project_id = ?", (now_utc(), project_id))
    conn.commit()


def upsert_skill(conn, name: str, *, level: float, source_label: str) -> None:
    conn.execute(
        """
        INSERT INTO skill_memory (name, level, evidence_count, source_label, status)
        VALUES (?, ?, 1, ?, 'active')
        ON CONFLICT(name) DO UPDATE SET
            level = excluded.level,
            evidence_count = skill_memory.evidence_count + 1,
            source_label = excluded.source_label,
            status = 'active'
        """,
        (name, level, source_label),
    )


def set_interaction_style(conn, value: str, *, source_label: str, timestamp: str) -> None:
    conn.execute(
        """
        INSERT INTO interaction_style (id, value, evidence_count, source_label)
        VALUES (1, ?, 1, ?)
        ON CONFLICT(id) DO UPDATE SET
            value = excluded.value,
            evidence_count = interaction_style.evidence_count + 1,
            source_label = excluded.source_label
        """,
        (value, source_label),
    )
    conn.execute(
        "INSERT INTO interaction_style_history (value, changed_at) VALUES (?, ?)",
        (value, timestamp),
    )


def _limited_clean_values(values: Iterable[str] | None, *, limit: int) -> list[str]:
    if values is None:
        return []
    clean = [value.strip() for value in values if value and value.strip()]
    return clean[:limit]


def _profile_row(
    table: str,
    field: str,
    value: Any,
    confidence: float,
    source_label: str,
    status: str,
    stale: bool = False,
) -> dict[str, Any]:
    return {
        "table": table,
        "field": field,
        "value": value,
        "confidence": confidence,
        "source_label": source_label,
        "status": status,
        # Only goal_memory can be stale - it is the one memory type the
        # constitution marks decay: true. Every other table passes the default.
        "stale": stale,
    }


def decay_stale_goals(conn: sqlite3.Connection) -> int:
    """
    Flags active goals untouched for longer than memory.goal_decay_inactive_days
    (settings.json, 14) and returns how many were newly flagged.

    goal_memory.decay_flag existed, and constitutional.json marks goal_memory as
    the one memory type with decay: true, but nothing ever set the flag - only
    cleared it. So a goal reached from a conversation six months ago kept being
    presented to the model as a current objective, indistinguishable from one
    the user mentioned yesterday.

    Marks rather than deletes or hides. A goal going quiet for two weeks is
    evidence it may be finished or abandoned, not proof - the user is the only
    one who knows which, and dropping it silently would be the system quietly
    forgetting something it was asked to remember. The flag makes the staleness
    visible in context (see stage_07) and gives the goal_inactive proactive
    trigger something to ask about.

    Idempotent: a goal already flagged is not re-counted, so a caller can run
    this on every startup and log a real number rather than a running total.
    Any write that touches a goal clears the flag again, because every one of
    them sets decay_flag = 0 and refreshes updated_at.
    """
    days = get_settings()["memory"]["goal_decay_inactive_days"]
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).strftime(TIMESTAMP_FORMAT)
    cur = conn.execute(
        "UPDATE goal_memory SET decay_flag = 1 "
        "WHERE status = 'active' AND decay_flag = 0 AND updated_at < ?",
        (cutoff,),
    )
    conn.commit()
    if cur.rowcount:
        logger.info(f"Flagged {cur.rowcount} goal(s) as stale after {days} days of inactivity.")
    return cur.rowcount

from backend.core.types import MemoryCandidate, ValidationResult

def apply_verified_correction(
    conn: sqlite3.Connection,
    candidate: MemoryCandidate,
    validation_result: ValidationResult
) -> None:
    """
    Applies a verified correction (either a user_verified gated field or a user_correction override).
    Forces confidence to maximum limits (1.0 for goals, 0.9 via evidence_count=5 for GENERATED columns)
    and clears stale behavioral history.

    The status determines the source_label written, because the three statuses
    that can reach here mean different things about what the user just did:

      REQUIRES_CONFIRMATION -> user_verified. A gated field the constitution
          says must be confirmed before it is written at all. The user is
          affirming a value, not overturning one.
      PROMPT_RECONCILIATION -> user_correction. The behavioral override fired:
          repeated inferred observations contradicted a value the user had
          stated. Confirming replaces the stated value, so it is a correction.
      TIER_2_REQUIRED       -> user_correction. Same shape as the above - the
          candidate conflicts with a stored value whose confidence is > 0.7, and
          confirming overwrites that value. The constitution names the status
          but never says which label a confirmed one carries; resolved as
          user_correction because "the stored value is being replaced on the
          user's say-so" is exactly what distinguishes it from user_verified,
          and it is the same act the behavioral-override path already labels
          that way. Previously this raised ValueError, which meant a
          TIER_2_REQUIRED row could be written to memory_candidates_pending by
          Stage 13 and then never resolved by anything - a third of the pending
          queue had no write path at all.
    """
    status = validation_result.status
    if status == "REQUIRES_CONFIRMATION":
        source_label = "user_verified"
    elif status in ("PROMPT_RECONCILIATION", "TIER_2_REQUIRED"):
        source_label = "user_correction"
    else:
        raise ValueError(f"Invalid validation status for verified correction: {status}")

    _write_profile_value(
        conn,
        target_table=candidate.get("target_table"),
        field=candidate.get("field_name"),
        value=candidate.get("proposed_value"),
        source_label=source_label,
    )


def _write_profile_value(
    conn: sqlite3.Connection,
    *,
    target_table: str | None,
    field: str | None,
    value: Any,
    source_label: str,
    allow_identity: bool = False,
) -> None:
    """
    Writes one value into whichever profile table owns it, at maximum
    confidence, clearing whatever behavioural history contradicted it.

    Split out of apply_verified_correction() so that a direct user correction
    can reach it too. That function resolves a source_label from a Stage 12
    validation status and is the only way this dispatch could be reached, so
    correct_profile_field() - which has no validation result and never will -
    carried its own hardcoded preference_memory INSERT instead. The result was
    that correcting a skill wrote a preference of the same name and left the
    skill untouched: not an error, just a silently wrong place.

    The alternative was to hand this function a fabricated validation status
    purely to get "user_correction" back out of it, which would have put a lie
    in the audit trail to avoid a refactor.

    Raises ValueError for a table with no in-place correction (the
    set-membership tables - preferred_tools, topic_interests,
    document_access_patterns - where a "correction" is a delete plus an add,
    not an update).
    """
    if target_table == "identity":
        # WHO may write these, rather than whether they can be written at all.
        #
        # This refused every caller, so somebody who mistyped their own name at
        # onboarding lived with it permanently. The reason for the refusal is
        # real, though, and it is not about the user: apply_verified_correction
        # reaches this same function from stage_13, so lifting the rule
        # outright would let the Observer rename the person it is observing,
        # from a value it inferred out of their own conversation.
        #
        # So the gate moves from the field to the caller. Nothing automated
        # passes allow_identity, because nothing automated should decide who
        # somebody is. correct_profile_field passes it, because a direct
        # correction is a person stating a fact about themselves - the one
        # source that outranks anything PIP could infer.
        if field in IDENTITY_FIELDS and not allow_identity:
            raise ValueError(
                f"'{field}' can only be set by you, not inferred - "
                "correct it from your profile."
            )
        
        # In case other identity fields exist in the future, whitelist against actual schema columns
        allowed_columns = {row["name"] for row in conn.execute("PRAGMA table_info(identity)")}
        if field not in allowed_columns:
            raise ValueError(f"Unknown identity field: {field}")
            
        # Refused here, where the sentence can still reach whoever typed it,
        # rather than surfacing as an IntegrityError from the driver.
        if not str(value).strip():
            raise ValueError(f"Your {field.replace('_', ' ')} cannot be empty.")
        value = str(value).strip()

        conn.execute(f"UPDATE identity SET {field} = ? WHERE id = 1", (value,))

    elif target_table == "preference_memory":
        conn.execute(
            """
            INSERT INTO preference_memory (name, value, evidence_count, source_label, status, behavioral_signal_count)
            VALUES (?, ?, 5, ?, 'active', 0)
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value,
                evidence_count = 5,
                source_label = excluded.source_label,
                status = 'active',
                behavioral_signal_count = 0
            """,
            (field, value, source_label),
        )
        conn.execute(
            "DELETE FROM preference_contradiction_log WHERE preference_id = (SELECT id FROM preference_memory WHERE name = ?)",
            (field,)
        )

    elif target_table == "skill_memory":
        conn.execute(
            """
            INSERT INTO skill_memory (name, level, evidence_count, source_label, status)
            VALUES (?, ?, 5, ?, 'active')
            ON CONFLICT(name) DO UPDATE SET
                level = excluded.level,
                evidence_count = 5,
                source_label = excluded.source_label,
                status = 'active'
            """,
            (field, value, source_label),
        )
        conn.execute(
            "DELETE FROM skill_contradiction_log WHERE skill_id = (SELECT id FROM skill_memory WHERE name = ?)",
            (field,)
        )

    elif target_table == "interaction_style":
        timestamp = now_utc()
        conn.execute(
            """
            INSERT INTO interaction_style (id, value, evidence_count, source_label)
            VALUES (1, ?, 5, ?)
            ON CONFLICT(id) DO UPDATE SET
                value = excluded.value,
                evidence_count = 5,
                source_label = excluded.source_label
            """,
            (value, source_label),
        )
        conn.execute(
            "INSERT INTO interaction_style_history (value, changed_at) VALUES (?, ?)",
            (value, timestamp),
        )

    elif target_table == "goal_memory":
        # updated_at is refreshed on every branch below. Without it a goal the
        # user just confirmed keeps whatever timestamp it already had, and
        # decay_stale_goals - which reads exactly this column - would flag it
        # stale again on its next pass despite having been affirmed moments
        # earlier. Clearing decay_flag alone is not enough; the clock has to
        # move too, or the next pass just sets it straight back.
        goal_id = goal_id_from_field(field)
        if goal_id is not None:
            cur = conn.execute(
                """
                UPDATE goal_memory
                SET goal_text = ?, confidence = 1.0, evidence_count = 5, decay_flag = 0,
                    status = 'active', updated_at = ?
                WHERE id = ?
                """,
                (value, now_utc(), goal_id),
            )
            if cur.rowcount == 0:
                try:
                    conn.execute(
                        "INSERT INTO goal_memory (id, goal_text, evidence_count, confidence, created_at, updated_at) VALUES (?, ?, 5, 1.0, ?, ?)",
                        (int(goal_id), value, now_utc(), now_utc())
                    )
                except ValueError:
                    conn.execute(
                        "INSERT INTO goal_memory (goal_text, evidence_count, confidence, created_at, updated_at) VALUES (?, 5, 1.0, ?, ?)",
                        (value, now_utc(), now_utc())
                    )
        else:
            # No id: the goal is identified by its own text - see
            # goal_id_from_field(). Match-then-insert rather than an upsert,
            # because goal_text has no UNIQUE constraint to conflict on.
            cur = conn.execute(
                """
                UPDATE goal_memory
                SET confidence = 1.0, evidence_count = 5, decay_flag = 0,
                    status = 'active', updated_at = ?
                WHERE goal_text = ?
                """,
                (now_utc(), value),
            )
            if cur.rowcount == 0:
                conn.execute(
                    "INSERT INTO goal_memory (goal_text, evidence_count, confidence, created_at, updated_at) VALUES (?, 5, 1.0, ?, ?)",
                    (value, now_utc(), now_utc()),
                )

    elif target_table == "active_projects":
        cur = conn.execute(
            """
            UPDATE active_projects 
            SET description = ?, status = 'active', last_active = ?
            WHERE name = ?
            """,
            (value, now_utc(), field),
        )
        if cur.rowcount == 0:
            import uuid
            conn.execute(
                "INSERT INTO active_projects (project_id, name, description, status, last_active) VALUES (?, ?, ?, 'active', ?)",
                (str(uuid.uuid4()), field, value, now_utc())
            )
    else:
        raise ValueError(f"Unsupported target_table for correction: {target_table}")

    conn.commit()


def write_approved_candidate(conn: sqlite3.Connection, candidate: MemoryCandidate) -> None:
    """
    Writes a Stage 12 APPROVED candidate at its own label/evidence_count
    (not forced to maximum confidence - that's apply_verified_correction's job).
    Never called for identity: immutable fields are HARD_REJECTed before
    a candidate can reach APPROVED, so this path is unreachable for identity
    and intentionally not implemented here.
    """
    target_table = candidate.get("target_table")
    field = candidate.get("field_name")
    value = candidate.get("proposed_value")
    label = candidate.get("label")
    evidence_count = candidate.get("evidence_count")

    if target_table == "preference_memory":
        conn.execute(
            """
            INSERT INTO preference_memory (name, value, evidence_count, source_label, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value,
                evidence_count = excluded.evidence_count,
                source_label = excluded.source_label,
                status = 'active'
            """,
            (field, value, evidence_count, label),
        )

    elif target_table == "skill_memory":
        conn.execute(
            """
            INSERT INTO skill_memory (name, level, evidence_count, source_label, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT(name) DO UPDATE SET
                level = excluded.level,
                evidence_count = excluded.evidence_count,
                source_label = excluded.source_label,
                status = 'active'
            """,
            (field, value, evidence_count, label),
        )

    elif target_table == "goal_memory":
        # Same optional-id rule as apply_verified_correction - see
        # goal_id_from_field(). Kept in step deliberately even though this
        # branch is currently unreachable for goals: constitutional.json gates
        # goal_memory.*, so a goal candidate becomes REQUIRES_CONFIRMATION
        # before it can ever be APPROVED. Leaving the two write paths
        # disagreeing about what a goal is called is how this bug survived in
        # the first place - one half reachable and wrong, the other unreachable
        # and equally wrong, and neither under a test.
        goal_id = goal_id_from_field(field)
        base = 0.9 if label in ("explicit", "user_verified", "user_correction") else 0.4
        confidence = base * min(evidence_count, 5) / 5.0
        if goal_id is not None:
            cur = conn.execute(
                """
                UPDATE goal_memory
                SET goal_text = ?, confidence = ?, evidence_count = ?, decay_flag = 0,
                    status = 'active', updated_at = ?
                WHERE id = ?
                """,
                (value, confidence, evidence_count, now_utc(), goal_id),
            )
        else:
            cur = conn.execute(
                """
                UPDATE goal_memory
                SET confidence = ?, evidence_count = ?, decay_flag = 0,
                    status = 'active', updated_at = ?
                WHERE goal_text = ?
                """,
                (confidence, evidence_count, now_utc(), value),
            )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO goal_memory (goal_text, evidence_count, confidence, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (value, evidence_count, confidence, now_utc(), now_utc()),
            )

    elif target_table == "active_projects":
        cur = conn.execute(
            "UPDATE active_projects SET description = ?, status = 'active', last_active = ? WHERE name = ?",
            (value, now_utc(), field),
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO active_projects (project_id, name, description, status, last_active) VALUES (?, ?, ?, 'active', ?)",
                (str(uuid.uuid4()), field, value, now_utc()),
            )

    elif target_table == "interaction_style":
        conn.execute(
            """
            INSERT INTO interaction_style (id, value, evidence_count, source_label)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                value = excluded.value,
                evidence_count = excluded.evidence_count,
                source_label = excluded.source_label
            """,
            (value, evidence_count, label),
        )
        conn.execute(
            "INSERT INTO interaction_style_history (value, changed_at) VALUES (?, ?)",
            (value, now_utc()),
        )

    elif target_table == "topic_interests":
        # Set membership, not name/value: the topic IS the field, and there is
        # no separate value to store. evidence_count accumulates on re-observation
        # the same way preferred_tools does at onboarding.
        conn.execute(
            """
            INSERT INTO topic_interests (topic, evidence_count, last_observed, status)
            VALUES (?, ?, ?, 'active')
            ON CONFLICT(topic) DO UPDATE SET
                evidence_count = MAX(topic_interests.evidence_count + 1, excluded.evidence_count),
                last_observed = excluded.last_observed,
                status = 'active'
            """,
            (field, evidence_count, now_utc()),
        )

    else:
        raise ValueError(f"Unsupported target_table for approved write: {target_table}")

    conn.commit()


def current_session_no(conn: sqlite3.Connection) -> int | None:
    """
    The ordinal of the session in progress, or None before onboarding has
    created profile_meta. Never increments - see begin_session().
    """
    row = conn.execute("SELECT session_count FROM profile_meta WHERE id = 1").fetchone()
    return row["session_count"] if row else None


def begin_session(conn: sqlite3.Connection) -> int | None:
    """
    Counts one session and returns its ordinal, or None before onboarding has
    created profile_meta (a session that predates the profile is not a session
    OF that profile, and counting it would put session_count out of step with
    the first_session_date onboarding stamps).

    profile_meta.session_count was previously written exactly once, as the
    literal 1 in complete_onboarding()'s INSERT, and never incremented by
    anything - so it read "1" forever, and every feature the constitution
    measures in sessions had no counter to measure against
    (behavioral_override.trigger_sessions, memory_verification.
    frequency_sessions). last_session_date had the same problem: set at
    onboarding, never updated, so it meant "when onboarding happened".

    Counted at session START, not end, and specifically on the first real
    message of a connection:

      - Start, because a session killed outright (crash, taskkill, power cut)
        runs neither the disconnect path nor the shutdown path. Counting at end
        would silently skip exactly those sessions, and undercounting is the
        failure mode that matters here - a rule that fires "every 30 sessions"
        would quietly stretch to 40.
      - First message rather than connect, because a WebSocket that opens and
        closes without sending anything produces no conversation and no Observer
        pass. The rest of this codebase already treats that as a non-session:
        _resolve_connection_state defers creating the conversation row for the
        same reason, and enqueue_for_shutdown no-ops on an empty history.

    Idempotence is the caller's job - ws_chat holds one flag per connection.
    There is no way to make this function itself idempotent without a notion of
    session identity, which is the thing it exists to create.
    """
    # Captured before last_session_date is overwritten, and taken from the
    # messages table rather than from last_session_date itself, because the two
    # answer different questions: last_session_date is when the previous session
    # STARTED, while the last message is when it was last active. Measuring a
    # gap from the start of a two-hour session overstates it by two hours.
    #
    # No message rows at all (a database that predates chat history, or a first
    # ever session) falls back to last_session_date, which is the best available
    # answer rather than a wrong one.
    row = conn.execute("SELECT MAX(created_at) AS last_activity FROM messages").fetchone()
    last_activity = row["last_activity"] if row else None

    cur = conn.execute(
        "UPDATE profile_meta SET session_count = session_count + 1, "
        "previous_session_date = COALESCE(?, last_session_date), last_session_date = ? "
        "WHERE id = 1",
        (last_activity, now_utc()),
    )
    if cur.rowcount == 0:
        return None
    conn.commit()
    return current_session_no(conn)


def record_document_access(conn: sqlite3.Connection, document_paths) -> int:
    """
    Counts one access per distinct document path. Returns how many rows moved.

    NOT written by the Observer, unlike every other table in the constitution's
    observer_may_write list. The Observer reads a conversation transcript, and a
    transcript cannot say which documents were consulted - that is Stage 5's
    knowledge and nobody else's. Retrieval is the honest signal available:
    documents only ever enter a conversation by being retrieved, so how often a
    document is retrieved IS its access pattern here. Recording it anywhere else
    would mean inventing an event stream that does not exist.

    Fails open. This is a usage statistic; a message must never fail because a
    counter could not be incremented.
    """
    moved = 0
    try:
        for path in {p for p in document_paths if p}:
            # Match-then-insert, not an upsert: document_path carries no UNIQUE
            # constraint, so ON CONFLICT has nothing to target. Adding one would
            # mean a CREATE UNIQUE INDEX in the startup path that raises - and
            # takes the whole app down - if any database ever held a duplicate.
            # Not worth that for a usage counter.
            cur = conn.execute(
                "UPDATE document_access_patterns "
                "SET access_count = access_count + 1, last_accessed = ?, status = 'active' "
                "WHERE document_path = ?",
                (now_utc(), path),
            )
            if cur.rowcount == 0:
                conn.execute(
                    "INSERT INTO document_access_patterns (document_path, access_count, last_accessed, status) "
                    "VALUES (?, 1, ?, 'active')",
                    (path, now_utc()),
                )
            moved += 1
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record document access, continuing: {e}")
        return 0
    return moved


# Tables a verification can retire a field from, and the contradiction log that
# belongs to each. An allowlist rather than an f-string over whatever the
# candidate row happens to say: the table name reaches SQL, and "it came from
# our own code" is a weaker guarantee than not interpolating it at all.
_RETIRABLE_TABLES = {
    "preference_memory": ("preference_contradiction_log", "preference_id"),
    "skill_memory": ("skill_contradiction_log", "skill_id"),
}


def record_document_conflicts(conn: sqlite3.Connection, conflicts) -> int:
    """
    Records (document_path, decision_id) pairs Stage 5 found to overlap.
    Returns how many rows were written or refreshed.

    Fails open, like everything else on the per-message path: a proactive
    trigger is worth less than the response it would have cost.
    """
    written = 0
    try:
        for document_path, decision_id in conflicts:
            conn.execute(
                """
                INSERT INTO document_decision_conflicts (document_path, decision_id, detected_at)
                VALUES (?, ?, ?)
                ON CONFLICT(document_path, decision_id) DO UPDATE SET
                    detected_at = excluded.detected_at
                """,
                (document_path, int(decision_id), now_utc()),
            )
            written += 1
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to record a document/decision conflict, continuing: {e}")
        return 0
    return written


def retire_profile_field(conn: sqlite3.Connection, target_table: str, field_name: str) -> bool:
    """
    Marks one stored field deleted after the user has said it is wrong about
    them. Returns whether a row actually changed.

    Scoped to a single table, unlike soft_delete_profile_field, which takes a
    bare field name and applies it to every table that has one - fine for a user
    deleting "editor" from their profile, wrong here, where the candidate names
    exactly one table and a same-named field elsewhere must not be collateral.

    Soft, not hard: status = 'deleted' keeps the row, so this is recoverable and
    consistent with every other deletion in this module.

    The field's contradiction history goes with it, for the same reason
    apply_verified_correction clears it on a correction. Those rows are keyed by
    the profile row's id, and re-adding a field of the same name upserts onto
    that same id - so stale behavioural evidence about a value the user has
    disowned would attach itself to whatever replaces it.
    """
    handler = _RETIRABLE_TABLES.get(target_table)
    if handler is None:
        logger.warning(f"retire_profile_field: nothing to retire for target_table {target_table!r}")
        return False
    log_table, id_column = handler

    row = conn.execute(
        f"SELECT id FROM {target_table} WHERE name = ? AND status = 'active'", (field_name,)
    ).fetchone()
    if row is None:
        return False

    conn.execute(f"UPDATE {target_table} SET status = 'deleted' WHERE id = ?", (row["id"],))
    conn.execute(f"DELETE FROM {log_table} WHERE {id_column} = ?", (row["id"],))
    conn.commit()
    logger.info(f"Retired {target_table}.{field_name} - the user said it was no longer right.")
    return True


def get_interaction_style_history(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """
    How the user's interaction style has changed over time, newest first.

    interaction_style_history was written from three separate places in this
    module and read by nothing - an audit trail that recorded every change and
    could not answer a single question about them. It is the one profile field
    with a recorded history at all (every other table keeps only its current
    value), which makes it the only place PIP can say "you asked for this, and
    you asked for something different before" rather than just asserting the
    current setting.

    Newest first because the question worth asking of a change log is what
    changed most recently.
    """
    return [
        dict(row)
        for row in conn.execute(
            "SELECT value, changed_at FROM interaction_style_history "
            "ORDER BY changed_at DESC, id DESC LIMIT ?",
            (limit,),
        )
    ]


def log_skill_contradiction(conn: sqlite3.Connection, skill_id: int, contradiction_text: str) -> None:
    """
    Records one instance of an inferred observation contradicting a stated
    skill_memory level - the mirror of log_preference_contradiction below, and
    for a long time the missing half of a mechanism three other places already
    assumed existed.

    skill_contradiction_log was declared in the schema, READ by
    stage_12._fetch_existing_state, and cleared by apply_verified_correction on
    a skill correction ("clears stale behavioral history") - three call sites
    built around a table nothing ever inserted into. stage_12 then returned a
    hardcoded behavioral_signal_count of 0 for skills while deriving
    first_contradiction_date from that same empty table, which is incoherent
    whichever way the underlying question is answered.

    That question - should skills get a behavioral override at all? - was
    previously answered "no" in Stage 13, on the grounds that skill_memory uses
    the constitution's "demonstrated_performance" validation rather than
    "explicit_or_behavioral". Reversed here, deliberately:

      - constitutional.json scopes behavioral_override to no table at all; it is
        a top-level rule, and gated_fields already names skill_memory.*.level.
      - The three call sites above are the original design's own evidence about
        what was intended. One comment argued the other way; the schema, the
        read path and the cleanup path all argued for this.
      - Without it, the case is not merely unhandled but silently permanent: a
        user states "python: intermediate" at onboarding (explicit), then
        demonstrates otherwise for months. Every one of those inferred
        observations is DISCARDed - inferred confidence caps at 0.4 against a
        month_2_plus threshold of 0.7 - so a stated level that has gone stale
        can never be revisited by anything. "Demonstrated performance" is
        exactly what those discarded observations were.
    """
    conn.execute(
        "INSERT INTO skill_contradiction_log (skill_id, contradiction_text, session_no, created_at) "
        "VALUES (?, ?, ?, ?)",
        (skill_id, contradiction_text, current_session_no(conn), now_utc()),
    )
    conn.commit()


def log_preference_contradiction(conn: sqlite3.Connection, preference_id: int, contradiction_text: str) -> None:
    """
    Records one instance of an inferred observation contradicting a stated
    preference_memory value - the data ConstitutionEnforcer's behavioral
    override trigger counts and dates (MIN(created_at)), see
    stage_12_validation_layer._fetch_existing_state. Called from Stage 13 on
    the DISCARD path, never from Observer directly (Rule 2: Observer never
    writes) - same one-writer-per-resource discipline as every other
    preference_memory write in this module.

    The session number is read here rather than passed in, which is safe for
    one specific reason: Rule 3 pins the Observer to session end, so by the
    time anything on this path runs, profile_meta.session_count is still the
    ordinal of the session the contradiction came from - the next session has
    not begun. That holds for the deferred paths too. pending_observer rows and
    conversations recovered from an unclean shutdown are drained during startup,
    before the first connection of the new run can call begin_session(), so
    they are stamped with the session they actually belong to rather than the
    one that happens to be draining them.

    Threading a session_no parameter down from ws_chat through Stage 11 into
    Stage 13 would have been the alternative, and it would have been four
    signatures changed to carry a value that is already in the database and
    already correct at every call site.
    """
    conn.execute(
        "INSERT INTO preference_contradiction_log (preference_id, contradiction_text, session_no, created_at) "
        "VALUES (?, ?, ?, ?)",
        (preference_id, contradiction_text, current_session_no(conn), now_utc()),
    )
    conn.commit()
