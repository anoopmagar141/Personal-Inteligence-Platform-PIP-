# PIP Memory layer - the governance audit log (BLUEPRINT G-7, A-3; issue #20)
#
# The one writer of governance_audit_log (see schema.sql for the table, its
# append-only triggers, and the limits of that). Stages call record(); none
# touches the table, and a test holds every INSERT to this module.
#
# Why it exists: the thesis contribution is "an auditable enforcement
# mechanism" (owner decision DEC-5, 2026-10-18), and before this a candidate
# the guard rejected left a logger line and nothing else - trace_log is
# diagnostic and purged after 90 days. Now every terminal outcome of a memory
# or decision candidate the Observer proposed, and every user resolution of a
# pending one, leaves exactly one row: who decided (system or user), at which
# stage, what (accepted, rejected, deferred, dismissed), and why (reason_code).
#
# What a row does not hold is the candidate's text: only an HMAC of table,
# field and value under this profile's random salt, so the same candidate can
# be followed across rows (and across a later user answer) without the log
# becoming a second copy of everything the user said, including what the
# guard refused to believe. It is a correlation key, not secrecy: anyone who
# can read this table already holds the key to the rest of the profile, and
# could guess short values by trying them.

import hashlib
import hmac
import secrets
import uuid
from typing import Any, Optional

from backend.core.evidence_gate import REJECTION_STATES
from backend.core.types import now_utc

ACTORS = frozenset({"system", "user"})
OUTCOMES = frozenset({"accepted", "rejected", "deferred", "dismissed"})
STAGES = frozenset({11, 12, 13})

# Every reason a row may give, from the sources that produce them. Checked here
# rather than by a SQL CHECK so the set can grow without a migration; a test
# asserts every stored code is in it.
CONSTITUTION_REASONS = frozenset({
    "immutable_field",
    "schema_violation",
    "behavioral_override",
    "threshold_violation_week_1_2",
    "threshold_violation_week_3_4",
    # One code used to cover both month-2 failures; A-3 splits them so the log
    # can say which rule refused a candidate.
    "threshold_violation_month_2_plus_evidence",
    "threshold_violation_month_2_plus_confidence",
    "gated_field",
    "high_confidence_conflict",
})
STAGE_11_REASONS = frozenset({
    "malformed_candidate",            # not an object, or missing table / field / value
    "label_not_allowed",              # Rule 1: a label other than explicit or inferred
    "skill_level_not_a_number",       # a skill level outside 0.0-1.0
    "evidence_not_in_transcript",     # grounding: the quote was never said
    "evidence_only_in_earlier_turns", # a resumed chat: re-read, not restated
    "candidate_error",                # the per-candidate isolation caught an exception
})
STAGE_13_REASONS = frozenset({
    "written",
    "write_failed",
    "queued",
    "already_queued",
})
DECISION_REASONS = frozenset({
    "decision_malformed",
    "decision_assistant_echo",
    "decision_quote_not_in_transcript",
    "decision_quote_only_in_earlier_turns",
    "decision_logged",
    "decision_queued",
    "decision_duplicate",
    "decision_failed",
})
USER_REASONS = frozenset({
    "user_confirmed",
    "user_dismissed",
    "user_retired_field",
    "user_promoted_decision",
    "user_dismissed_decision",
})
KNOWN_REASON_CODES = (
    frozenset(REJECTION_STATES) | CONSTITUTION_REASONS | STAGE_11_REASONS | STAGE_13_REASONS
    | DECISION_REASONS | USER_REASONS
)


def new_candidate_id() -> str:
    """The id a candidate carries from Stage 11 to the end of its life."""
    return uuid.uuid4().hex


def legacy_candidate_id(table: str, rowid: int) -> str:
    """
    For a pending row queued before candidate ids existed. Distinct per row: a
    shared placeholder would join unrelated candidates under one key.
    """
    return f"legacy:{table}:{rowid}"


def salt(conn) -> str:
    """This profile's audit salt, made once (random, 32 bytes) on first use."""
    row = conn.execute("SELECT salt FROM governance_audit_salt WHERE id = 1").fetchone()
    if row is not None:
        return row["salt"]
    conn.execute(
        "INSERT OR IGNORE INTO governance_audit_salt (id, salt, created_at) VALUES (1, ?, ?)",
        (secrets.token_hex(32), now_utc()),
    )
    conn.commit()
    return conn.execute("SELECT salt FROM governance_audit_salt WHERE id = 1").fetchone()["salt"]


def fingerprint(conn, target_table: Optional[str], field_name: Optional[str], value: Any) -> str:
    """HMAC-SHA256 of table, field and value under this profile's salt."""
    message = "\x1f".join([
        str(target_table or ""), str(field_name or ""), "" if value is None else str(value),
    ]).encode("utf-8")
    return hmac.new(bytes.fromhex(salt(conn)), message, hashlib.sha256).hexdigest()


def record_user_resolution(
    conn,
    *,
    pending_table: str,
    row: dict[str, Any],
    outcome: str,
    reason_code: str,
    target_table: Optional[str],
    field_name: Optional[str],
    value: Any,
) -> Optional[int]:
    """
    The user's answer to a queued question (G-7 part 3): actor "user", no
    pipeline stage, the session it was answered in. Recorded under the queued
    row's candidate_id, so it joins the system's own row for the same
    candidate (same id, same fingerprint), or under "legacy:<table>:<rowid>"
    for a row queued before ids existed. The chat is the system row's, or the
    queued row's own if it has one.

    Called after the answer has taken effect, and logs rather than raises if
    the row cannot be written: the user's action stands either way, and an
    error here must not tell them it failed when it did not.
    """
    import logging

    try:
        candidate_id = row.get("candidate_id") or legacy_candidate_id(pending_table, row["id"])
        prior = conn.execute(
            "SELECT conversation_id FROM governance_audit_log WHERE candidate_id = ? ORDER BY id LIMIT 1",
            (candidate_id,),
        ).fetchone()
        conversation_id = row.get("conversation_id") or (prior["conversation_id"] if prior else None)
        return record(
            conn, candidate_id=candidate_id, actor="user", stage=None, outcome=outcome, reason_code=reason_code,
            target_table=target_table, field_name=field_name, value=value,
            evidence_count=row.get("evidence_count"), confidence=row.get("confidence"),
            conversation_id=conversation_id,
        )
    except Exception as e:
        logging.getLogger(__name__).error(f"Governance audit: could not record a user answer ({reason_code}): {e}")
        return None


def summary(conn) -> dict[str, Any]:
    """
    The log read back (G-7 part 4): how many rows, and how many per outcome,
    per reason and per actor. What an examiner asks first - what did the guard
    refuse, and why - answered from the table rather than from a log file.
    """
    def counts(column: str) -> dict[str, int]:
        return {r[0]: r[1] for r in conn.execute(
            f"SELECT {column}, COUNT(*) FROM governance_audit_log GROUP BY {column} ORDER BY {column}")}

    return {
        "rows": conn.execute("SELECT COUNT(*) FROM governance_audit_log").fetchone()[0],
        "by_outcome": counts("outcome"),
        "by_reason": counts("reason_code"),
        "by_actor": counts("actor"),
    }


def history(conn, candidate_id: str) -> list[dict[str, Any]]:
    """Every row for one candidate, oldest first: the system's decision, then the user's answer."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM governance_audit_log WHERE candidate_id = ? ORDER BY id", (candidate_id,))]


def has_row(conn, candidate_id: str) -> bool:
    """Whether a candidate already has a row; Stage 11's error path asks, so it adds none twice."""
    return conn.execute(
        "SELECT 1 FROM governance_audit_log WHERE candidate_id = ? LIMIT 1", (candidate_id,)
    ).fetchone() is not None


def _session_no(conn) -> int:
    # The session in which this decision was taken; 0 before onboarding has
    # created profile_meta (a pass can run before that).
    row = conn.execute("SELECT session_count FROM profile_meta WHERE id = 1").fetchone()
    return int(row["session_count"]) if row and row["session_count"] is not None else 0


def record(
    conn,
    *,
    candidate_id: str,
    actor: str,
    outcome: str,
    reason_code: str,
    stage: Optional[int] = None,
    target_table: Optional[str] = None,
    field_name: Optional[str] = None,
    value: Any = None,
    evidence_count: Optional[int] = None,
    confidence: Optional[float] = None,
    conversation_id: Optional[str] = None,
) -> int:
    """
    Appends one row. Refuses (ValueError) a row the log does not define: an
    unknown reason, outcome or actor, a stage outside 11-13, or a user action
    given a pipeline stage. `value` is fingerprinted and never stored.
    """
    if reason_code not in KNOWN_REASON_CODES:
        raise ValueError(f"unknown audit reason_code {reason_code!r}")
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown audit outcome {outcome!r}")
    if actor not in ACTORS:
        raise ValueError(f"unknown audit actor {actor!r}")
    if stage is not None and stage not in STAGES:
        raise ValueError(f"audit stage must be 11, 12, 13 or None, not {stage!r}")
    if actor == "user" and stage is not None:
        raise ValueError("a user action has no pipeline stage")
    if not candidate_id:
        raise ValueError("an audit row needs a candidate_id")

    cur = conn.execute(
        """
        INSERT INTO governance_audit_log (
            candidate_id, candidate_hmac, session_no, stage, actor, outcome, reason_code,
            target_table, field_name, evidence_count, confidence, conversation_id, decided_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, fingerprint(conn, target_table, field_name, value), _session_no(conn), stage,
            actor, outcome, reason_code, target_table, field_name, evidence_count, confidence,
            conversation_id, now_utc(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)
