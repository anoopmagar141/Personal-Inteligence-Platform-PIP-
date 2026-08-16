import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from backend.core.types import now_utc

try:
    import sqlcipher3
except ImportError:  # pragma: no cover - exercised when SQLCipher is installed.
    sqlcipher3 = None


SCHEMA_PATH = Path(__file__).parent.parent / "core" / "schema.sql"
CONSENT_SEED_PATH = Path(__file__).parent.parent.parent / "config" / "provider_consent.json"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_INTERACTION_STYLE = "adaptive"


def get_connection(db_path: str, db_key: str | None = None):
    if db_key is not None:
        assert re.fullmatch(r"[0-9a-fA-F]+", db_key), "db_key must be hex-encoded"

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


def initialize_schema(conn) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    seed_provider_consent(conn)


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
        )
        for row in conn.execute("SELECT * FROM goal_memory WHERE status = 'active' ORDER BY updated_at DESC")
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
    if field in {"name", "language_preference", "timezone"}:
        raise ValueError("immutable identity fields cannot be edited after onboarding")

    if field == "interaction_style":
        set_interaction_style(conn, value, source_label="user_correction", timestamp=now_utc())
    else:
        conn.execute(
            """
            INSERT INTO preference_memory (name, value, evidence_count, source_label, status)
            VALUES (?, ?, 1, 'user_correction', 'active')
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value,
                evidence_count = preference_memory.evidence_count + 1,
                source_label = 'user_correction',
                status = 'active'
            """,
            (field, value),
        )
    conn.commit()


def soft_delete_profile_field(conn, field: str) -> bool:
    if field in {"name", "language_preference", "timezone"}:
        raise ValueError("immutable identity fields cannot be deleted")

    updated = 0
    for table, column in (
        ("skill_memory", "name"),
        ("preference_memory", "name"),
        ("preferred_tools", "tool_name"),
    ):
        cur = conn.execute(f"UPDATE {table} SET status = 'deleted' WHERE {column} = ?", (field,))
        updated += cur.rowcount

    if field.startswith("goal:"):
        goal_id = field.split(":", 1)[1]
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
            "SELECT * FROM active_projects ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, last_active DESC"
        )
    ]


def update_project_status(conn, project_id: str, status: str) -> None:
    if status not in {"active", "archived", "completed"}:
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
) -> dict[str, Any]:
    return {
        "table": table,
        "field": field,
        "value": value,
        "confidence": confidence,
        "source_label": source_label,
        "status": status,
    }

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
    """
    status = validation_result.status
    if status == "REQUIRES_CONFIRMATION":
        source_label = "user_verified"
    elif status == "PROMPT_RECONCILIATION":
        source_label = "user_correction"
    else:
        raise ValueError(f"Invalid validation status for verified correction: {status}")

    target_table = candidate.get("target_table")
    field = candidate.get("field_name")
    value = candidate.get("proposed_value")

    if target_table == "identity":
        if field in {"name", "language_preference", "timezone"}:
            raise ValueError("immutable identity fields cannot be edited after onboarding")
        
        # In case other identity fields exist in the future, whitelist against actual schema columns
        allowed_columns = {row["name"] for row in conn.execute("PRAGMA table_info(identity)")}
        if field not in allowed_columns:
            raise ValueError(f"Unknown identity field: {field}")
            
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
        if field.startswith("goal:"):
            goal_id = field.split(":", 1)[1]
            cur = conn.execute(
                """
                UPDATE goal_memory 
                SET goal_text = ?, confidence = 1.0, evidence_count = 5, decay_flag = 0, status = 'active'
                WHERE id = ?
                """,
                (value, goal_id),
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
            raise ValueError(f"Invalid goal field name: {field}")

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
