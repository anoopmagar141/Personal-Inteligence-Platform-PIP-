"""
Retract the ungrounded candidates still sitting in the two pending queues.

What is in there
----------------
Eleven rows, none of which the user ever said, in three distinct groups. The
groups matter because only the first is historical - the other two were
produced by code that is still running.

  A. CONFABULATION (5 rows, 2026-08-24/25, before the grounding fixes)
     A whole fictional project: "Smith Project", "Johnson Report", and a
     smart-home security product with an ML threat-detection approach and
     smart-device integrations. The same failure cleanup_fabricated_memory.py
     mopped up on the decision_log side; these are the rows it did not cover,
     because they never left the pending queues to become profile state. The
     evidence_text on the first two is the ASSISTANT's own reply ("Based on
     our previous interactions, I can tell you that you're currently working
     on the **Smith Project**") harvested as if the user had said it.

  B. THE ASSISTANT'S OWN WORDS (2 rows)
     "You decided to start a project or task." is drawn from the assistant
     OFFERING to start one. "chose to work on the project's pipeline or
     architecture" is drawn from the assistant SPECULATING about a document
     it had not read ("it's likely related to..."). A question and a guess,
     both recorded as settled decisions.

  C. A QUESTION READ AS A COMMITMENT (2 rows, 2026-08-28, AFTER the fixes)
     The user typed "tell me about pip project ?". That became the goal
     "PIP project" and the decision "decided to work on the PIP project".
     Asking about a thing is not deciding to do it.

Group C is the one worth being precise about, because it means the intake
path is not fully closed. _looks_like_assistant_echo() rejects a
decision_text ending in "?" but never examines raw_quote, and
_quote_is_grounded() checks the quote appears somewhere in the transcript
without checking it came from a User: line. A user's question, quoted
faithfully and restated as a statement, clears both. That gap is not fixed
here - this script is the mop, not the leak repair, exactly as
cleanup_fabricated_memory.py said of its own scope.

Retraction, not deletion
------------------------
Both tables model this as state='dismissed' with a timestamp, and both have
a sanctioned helper (candidate_store.dismiss_memory_candidate /
dismiss_decision_candidate), so those are used rather than raw UPDATEs. The
rows stay readable and reversible, per ADR-022's posture on the decision log:
"the user doesn't remember saying it" is strong evidence, not proof.

Known limitation, inherited not introduced: neither table has a column for a
dismissal reason, so the reasons below live in this file and its commit
message, not in the database. cleanup_fabricated_memory.py recorded the same
gap for update_decision_state().

Safety
------
Every target is matched on its exact text, never on id alone - ids are
AUTOINCREMENT and would silently retract the wrong row if the queues had
moved on. A target whose text is not found is reported and skipped rather
than guessed at. Idempotent: an already-dismissed row is reported as such and
left alone.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\retract_fabricated_candidates.py --dry-run
    .venv\\Scripts\\python.exe scripts\\retract_fabricated_candidates.py
"""

from __future__ import annotations

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

import _db

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.memory import candidate_store  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "pip.db"
LOCK_PATH = ROOT / "data" / "pip.lock"

# (proposed_value, reason). Matched on proposed_value.
MEMORY_TARGETS: tuple[tuple[str, str], ...] = (
    ("Smith Project",
     "A. Confabulated. Evidence is the assistant's own reply, not the user's words."),
    ("Johnson Report",
     "A. Confabulated. Evidence is the assistant's own reply, not the user's words."),
    ("develop an innovative solution that combines AI and IoT technologies to enhance smart home security",
     "A. Confabulated. No such project exists; invented against an empty profile."),
    ("use a machine learning approach for threat detection",
     "A. Confabulated. Part of the same invented smart-home project."),
    ("integrate the system with popular smart home devices",
     "A. Confabulated. Part of the same invented smart-home project."),
    ("PIP project",
     "C. Drawn from the user's question 'tell me about pip project ?'. Asking about a "
     "project is not committing to a goal, and the real objectives are now recorded in "
     "goal_memory from the project's own spec."),
)

# (decision_text, reason). Matched on decision_text.
DECISION_TARGETS: tuple[tuple[str, str], ...] = (
    ("decided to work on the Smith Project",
     "A. Confabulated. Already dismissed on 2026-08-25; listed so the set is complete."),
    ("decided to complete the Johnson Report",
     "A. Confabulated. Already dismissed on 2026-08-25; listed so the set is complete."),
    ("You decided to start a project or task.",
     "B. Drawn from the assistant offering to start one, not from the user deciding to."),
    ("decided to work on the PIP project",
     "C. Drawn from the user's question 'tell me about pip project ?'."),
    ("chose to work on the project's pipeline or architecture",
     "B. Drawn from the assistant speculating about a document it had not read."),
)


def _connect():
    """
    Delegated to scripts/_db.py so every script resolves the key one way.

    This used to fall back to `key or None`, and None means "plain SQLite" to
    get_connection() rather than "no key" - so after the password migration
    removed data/db_key.txt it opened the encrypted database as an
    unencrypted one and failed later with "file is not a database".
    """
    return _db.connect(DB_PATH)


def _warn_if_running() -> None:
    if not LOCK_PATH.exists():
        return
    pid = LOCK_PATH.read_text(encoding="utf-8").strip()
    print(
        f"NOTE: data/pip.lock exists (pid {pid}) - PIP may be running. "
        "Closing it first makes the result easier to read back.\n"
    )


def _retract(conn, *, table: str, column: str, targets, dismiss, dry_run: bool) -> tuple[int, int, int]:
    print(f"\n{table} ({len(targets)} targets):")
    done = already = missing = 0

    for text, reason in targets:
        row = conn.execute(
            f"SELECT id, state FROM {table} WHERE {column} = ?", (text,)
        ).fetchone()

        if row is None:
            missing += 1
            print(f"  NOT FOUND, skipped: {text[:66]}")
            continue

        if row["state"] == "dismissed":
            already += 1
            print(f"  already dismissed (id {row['id']}): {text[:60]}")
            continue

        done += 1
        if dry_run:
            print(f"  WOULD RETRACT (id {row['id']}): {text[:60]}")
        else:
            dismiss(conn, row["id"])
            print(f"  retracted (id {row['id']}): {text[:60]}")
        print(f"      reason: {reason}")

    return done, already, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Retract ungrounded pending candidates.")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"no database at {DB_PATH}", file=sys.stderr)
        return 1

    _warn_if_running()
    if args.dry_run:
        print("DRY RUN - nothing will be written.\n")

    conn = _connect()
    try:
        m = _retract(
            conn,
            table="memory_candidates_pending",
            column="proposed_value",
            targets=MEMORY_TARGETS,
            dismiss=candidate_store.dismiss_memory_candidate,
            dry_run=args.dry_run,
        )
        d = _retract(
            conn,
            table="decision_candidates_pending",
            column="decision_text",
            targets=DECISION_TARGETS,
            dismiss=candidate_store.dismiss_decision_candidate,
            dry_run=args.dry_run,
        )

        verb = "would retract" if args.dry_run else "retracted"
        print(f"\n{verb}: {m[0] + d[0]}   already dismissed: {m[1] + d[1]}   not found: {m[2] + d[2]}")
        for table in ("memory_candidates_pending", "decision_candidates_pending"):
            left = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE state = 'pending'"
            ).fetchone()[0]
            print(f"still pending in {table}: {left}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
