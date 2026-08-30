# PIP Core - Proactive Triggers (constitutional.json proactive_triggers,
# settings.json proactive.*)
#
# Neither settings key was read by anything, and no module by this name existed.
#
# The constitution is unusually specific about this feature, and the specificity
# is the point: proactive_triggers.allowed names exactly three conditions, and
# proactive_triggers.forbidden rules out "model_judgment_of_relevance" and
# "model_judgment_of_urgency". So this module is deliberately dull - date
# arithmetic over stored state, no LLM call, no scoring, no ranking. A trigger
# either fires because a recorded timestamp crossed a configured threshold, or
# it does not fire. Everything here is inspectable and reproducible, which is
# what makes it safe to surface unprompted.
#
# evaluate() is a pure read plus one cheap UPDATE (the goal decay pass). It does
# not notify, queue, or send anything - it answers "what is true right now" and
# leaves the decision of whether and how to raise it to the caller. That keeps
# the forbidden judgments out of the backend entirely rather than relying on
# this module to resist making them.

import datetime
import logging
from typing import Any

from backend.config.settings import get_settings
from backend.core.types import TIMESTAMP_FORMAT
from backend.memory import profile_store

logger = logging.getLogger(__name__)

SESSION_GAP = "session_gap_exceeds_48h"
GOAL_INACTIVE = "goal_inactive_14_days"

# constitutional.json lists a third allowed trigger,
# document_decision_conflict_detected, which is NOT evaluated here - see the
# module note in evaluate().
DOCUMENT_DECISION_CONFLICT = "document_decision_conflict_detected"


def _parse(value: Any) -> datetime.datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _session_gap(conn, now: datetime.datetime) -> dict[str, Any] | None:
    """
    Fires when the gap since the last session exceeds
    proactive.session_gap_trigger_hours (48).

    Measured from profile_meta.last_session_date, which since session counting
    exists is updated on the first message of every session. Stage 0's gap
    detector still measures from session_snapshot.snapshot_date, which is a
    proxy for the same thing and a slightly worse one - the Observer withholds a
    snapshot for a session with no substantive turn, so a run of thin sessions
    reads as a gap that never happened. They are deliberately left disagreeing
    for now: changing Stage 0's input changes which warm_start_level real
    sessions get, which is a behaviour change to the context pipeline and does
    not belong in the same breath as wiring up a config key.
    """
    row = conn.execute("SELECT last_session_date FROM profile_meta WHERE id = 1").fetchone()
    last = _parse(row["last_session_date"]) if row else None
    if last is None:
        return None

    hours = get_settings()["proactive"]["session_gap_trigger_hours"]
    gap = now - last
    if gap < datetime.timedelta(hours=hours):
        return None
    return {
        "trigger": SESSION_GAP,
        "threshold_hours": hours,
        "hours_elapsed": int(gap.total_seconds() // 3600),
        "last_session_date": row["last_session_date"],
    }


def _inactive_goals(conn, now: datetime.datetime) -> list[dict[str, Any]]:
    """
    One entry per active goal untouched for longer than
    proactive.goal_inactive_trigger_days (14).

    Evaluated against goal_memory.updated_at directly rather than reading
    decay_flag, even though profile_store.decay_stale_goals sets that flag off
    the same number today. They are separate settings
    (memory.goal_decay_inactive_days and proactive.goal_inactive_trigger_days)
    describing separate concerns - how a goal is RENDERED in context versus when
    the user is ASKED about it - and reading the flag would silently make one of
    the two keys unreachable the moment someone set them to different values.
    """
    days = get_settings()["proactive"]["goal_inactive_trigger_days"]
    cutoff = (now - datetime.timedelta(days=days)).strftime(TIMESTAMP_FORMAT)
    return [
        {
            "trigger": GOAL_INACTIVE,
            "threshold_days": days,
            "goal_id": row["id"],
            "goal_text": row["goal_text"],
            "updated_at": row["updated_at"],
        }
        for row in conn.execute(
            "SELECT id, goal_text, updated_at FROM goal_memory "
            "WHERE status = 'active' AND updated_at < ? ORDER BY updated_at ASC",
            (cutoff,),
        )
    ]


def evaluate(conn, now: datetime.datetime | None = None) -> list[dict[str, Any]]:
    """
    Every allowed proactive trigger currently firing, as plain data. Empty list
    when nothing is due, which is the normal case.

    `now` is injectable for deterministic tests, the same convention
    stage_00_gap_detector.run already uses for exactly this reason.

    document_decision_conflict_detected is the one allowed trigger not evaluated
    here, and not by oversight. Stage 5 already detects it, per query, against
    the chunks that query retrieved (see _check_conflict) - it is a property of
    a retrieval, not a standing fact about the database. Answering it here would
    mean pulling every active document's chunks out of ChromaDB and comparing
    them against every active decision on each call, which is a real design
    decision about cost and caching rather than a config key to wire up. The
    detection that exists today already reaches the user through the pipeline's
    conflict_flag.

    Fails open, per trigger: one broken evaluation returns no trigger rather
    than taking down the others or the endpoint.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    triggers: list[dict[str, Any]] = []

    try:
        # Keeps the rendered-context view of staleness in step with what is
        # being reported here. A long-running process runs the startup decay
        # pass once and would otherwise never notice a goal going quiet
        # afterwards.
        profile_store.decay_stale_goals(conn)
    except Exception as e:
        logger.error(f"Proactive: goal decay pass failed, continuing: {e}")

    for evaluator in (_session_gap,):
        try:
            result = evaluator(conn, now)
            if result:
                triggers.append(result)
        except Exception as e:
            logger.error(f"Proactive: {evaluator.__name__} failed, skipping: {e}")

    try:
        triggers.extend(_inactive_goals(conn, now))
    except Exception as e:
        logger.error(f"Proactive: inactive-goal check failed, skipping: {e}")

    return triggers
