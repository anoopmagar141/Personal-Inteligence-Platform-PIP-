"""
One-time remediation: retract memory entries fabricated by the pre-fix Observer.

What happened
-------------
Before 1221a42 ("Stop Observer from logging the assistant's own replies as
decisions") and e814a9e ("Ground Observer's decision/snapshot extraction
against the real transcript"), the Observer could not distinguish content the
USER stated from content the ASSISTANT had just invented. When early sessions
asked about projects against an empty profile, the model confabulated - and
the Observer then harvested those confabulations from the transcript and
persisted them as established fact.

Those two commits fixed the intake path. They did not - and could not -
retract what had already been written. The result is a feedback loop that
survives the fix: Stage 7 assembles the stored fiction into every subsequent
prompt, the model reports it faithfully (correctly, given its context), and
the user sees confident false answers about projects that never existed.

This script closes that loop from the data side. It is the mop, not the leak
repair; the leak was already repaired.

Retraction, not deletion
------------------------
ADR-022 is explicit that decision-log entries are never hard-deleted, so
fabricated decisions are moved to state='abandoned' via decision_log's own
update_decision_state(). They remain readable, and remain reversible if one
turns out to have been genuine after all - which matters, because "the user
doesn't remember saying it" is good evidence but not proof.

Known limitation, surfaced rather than hidden: update_decision_state()
requires a `reason`, validates that it is non-empty, and then does not store
it - decision_log has no column for it. The reason passed below is therefore
recorded in this script and in the commit that adds it, but NOT in the
database. Worth fixing separately; noting it here so the gap isn't mistaken
for one this script created.

Safety
------
Every target is matched on its text, not just its id, and anything whose text
does not match the recorded fabrication is skipped and reported. If the
database has moved on since this was written, the script declines to act
rather than guessing. Idempotent: re-running reports "already retracted".

Usage
-----
    .venv\\Scripts\\python.exe scripts\\cleanup_fabricated_memory.py --dry-run
    .venv\\Scripts\\python.exe scripts\\cleanup_fabricated_memory.py
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

from backend.memory import decision_log, session_snapshot  # noqa: E402

DB_PATH = pathlib.Path(__file__).parent.parent / "data" / "pip.db"

RETRACTION_REASON = (
    "Fabricated by the pre-fix Observer (before 1221a42/e814a9e): extracted from "
    "the assistant's own invented output, not from anything the user stated. "
    "Retracted, not deleted, per ADR-022."
)

# Matched on text as well as id - see the Safety note above. These are the
# exact fabrications found in the live database: a fictional smart-home threat
# detection product bearing no relation to the user's actual project (PIP).
FABRICATED_DECISIONS = {
    1: "We've decided to use a machine learning approach for threat detection.",
    2: "We'll integrate the system with popular smart home devices.",
    3: "We'll prioritize user-friendly interface and ease of use.",
    4: "We've decided to use a machine learning approach for threat detection.",
    5: "We'll integrate the system with popular smart home devices.",
    6: "You decided to focus on data collection for the next 2 weeks.",
}

FABRICATED_PENDING = {
    1: "decided to work on the Smith Project",
    2: "decided to complete the Johnson Report",
}

# The snapshot names a project ("Project Genesis") that does not exist in
# active_projects and never has. Cleared wholesale rather than field-by-field:
# a snapshot built from a confabulated transcript has no trustworthy parts.
FABRICATED_SNAPSHOT_TOPIC = "Project Genesis"


def _connect():
    """
    Delegated to scripts/_db.py so every script resolves the key one way.

    This used to fall back to `key or None`, and None means "plain SQLite" to
    get_connection() rather than "no key" - so after the password migration
    removed data/db_key.txt it opened the encrypted database as an
    unencrypted one and failed later with "file is not a database".
    """
    return _db.connect(DB_PATH)


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _has_state_reason(conn) -> bool:
    """
    Whether this database has the state_reason column yet. Normally it will -
    profile_store.apply_column_migrations() adds it on any app start - but this
    script connects directly and may run against a database the app has not
    opened since the column was introduced. Checked rather than assumed so the
    backfill degrades to a no-op instead of raising "no such column".
    """
    return any(r["name"] == "state_reason" for r in conn.execute("PRAGMA table_info(decision_log)"))


def retract_decisions(conn, dry_run: bool) -> tuple[int, int, int]:
    done = skipped = already = 0
    for decision_id, expected_text in sorted(FABRICATED_DECISIONS.items()):
        # SELECT * rather than naming state_reason: this script may run against
        # a database predating that column, where naming it raises outright.
        row = conn.execute("SELECT * FROM decision_log WHERE id = ?", (decision_id,)).fetchone()

        if row is None:
            print(f"  [{decision_id}] SKIP - no such decision (database has moved on)")
            skipped += 1
            continue
        if _norm(row["decision_text"]) != _norm(expected_text):
            print(f"  [{decision_id}] SKIP - text does not match the recorded fabrication:")
            print(f"           stored:   {row['decision_text']!r}")
            print(f"           expected: {expected_text!r}")
            skipped += 1
            continue
        if row["state"] != "active":
            # Backfill: the first run of this script predated
            # decision_log.state_reason existing, so those retractions recorded
            # the state change and lost the reason - exactly the gap the column
            # was added to close. Repair them rather than skipping, otherwise
            # the rows this script itself retracted stay permanently
            # unexplained while every later one is documented.
            has_column = _has_state_reason(conn)
            if has_column and not (row["state_reason"] or "").strip():
                if dry_run:
                    print(f"  [{decision_id}] already retracted - would backfill missing reason")
                else:
                    conn.execute(
                        "UPDATE decision_log SET state_reason = ? WHERE id = ?",
                        (RETRACTION_REASON, decision_id),
                    )
                    conn.commit()
                    print(f"  [{decision_id}] already retracted - reason backfilled")
            else:
                print(f"  [{decision_id}] already retracted (state={row['state']})")
            already += 1
            continue

        if dry_run:
            print(f"  [{decision_id}] would retract: {row['decision_text']}")
        else:
            decision_log.update_decision_state(
                conn, decision_id, state="abandoned", reason=RETRACTION_REASON
            )
            print(f"  [{decision_id}] retracted: {row['decision_text']}")
        done += 1
    return done, skipped, already


def dismiss_pending(conn, dry_run: bool) -> tuple[int, int, int]:
    done = skipped = already = 0
    for candidate_id, expected_text in sorted(FABRICATED_PENDING.items()):
        row = conn.execute(
            "SELECT id, decision_text, state FROM decision_candidates_pending WHERE id = ?",
            (candidate_id,),
        ).fetchone()

        if row is None:
            print(f"  [{candidate_id}] SKIP - no such candidate")
            skipped += 1
            continue
        if _norm(row["decision_text"]) != _norm(expected_text):
            print(f"  [{candidate_id}] SKIP - text does not match: {row['decision_text']!r}")
            skipped += 1
            continue
        if row["state"] != "pending":
            print(f"  [{candidate_id}] already handled (state={row['state']})")
            already += 1
            continue

        if dry_run:
            print(f"  [{candidate_id}] would dismiss: {row['decision_text']}")
        else:
            decision_log.dismiss_pending(conn, candidate_id)
            print(f"  [{candidate_id}] dismissed: {row['decision_text']}")
        done += 1
    return done, skipped, already


def clear_snapshot(conn, dry_run: bool) -> bool:
    snapshot = session_snapshot.load_snapshot(conn)
    if snapshot is None:
        print("  no snapshot stored - nothing to clear")
        return False

    topic = snapshot.get("topic", "")
    if FABRICATED_SNAPSHOT_TOPIC.lower() not in topic.lower():
        print(f"  SKIP - snapshot topic is not the recorded fabrication: {topic!r}")
        print("         (a real session has written a new snapshot since; leaving it alone)")
        return False

    if dry_run:
        print(f"  would clear snapshot: {topic!r}")
    else:
        session_snapshot.clear_snapshot(conn)
        print(f"  cleared snapshot: {topic!r}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}.")
        return 1

    conn = _connect()
    mode = "DRY RUN - no changes will be written" if args.dry_run else "APPLYING CHANGES"
    print(f"{mode}\n")

    print("Decisions (retracted to state='abandoned', recoverable):")
    d_done, d_skip, d_already = retract_decisions(conn, args.dry_run)

    print("\nPending decision candidates (dismissed):")
    p_done, p_skip, p_already = dismiss_pending(conn, args.dry_run)

    print("\nSession snapshot:")
    s_done = clear_snapshot(conn, args.dry_run)

    print(
        f"\nSummary: {d_done} decisions, {p_done} candidates, {1 if s_done else 0} snapshot"
        f"{' would be' if args.dry_run else ''} retracted."
    )
    if d_skip or p_skip:
        print(f"         {d_skip + p_skip} skipped (text mismatch or missing) - reported above, not guessed at.")
    if d_already or p_already:
        print(f"         {d_already + p_already} already retracted on an earlier run.")

    remaining = conn.execute("SELECT COUNT(*) FROM decision_log WHERE state = 'active'").fetchone()[0]
    print(f"\nActive decisions remaining: {remaining}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
