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
DEFAULT_TIMEZONE = "UTC"
DEFAULT_INTERACTION_STYLE = "adaptive"


def get_connection(db_path: str, db_key: str | None = None):
    if db_key is not None:
        assert re.fullmatch(r"[0-9a-fA-F]+", db_key), "db_key must be hex-encoded"

    if sqlcipher3 is not None:
        assert db_key is not None, "db_key is required when SQLCipher is available"
        conn = sqlcipher3.connect(db_path)
        conn.execute(f"PRAGMA key = \"x'{db_key}'\"")
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
