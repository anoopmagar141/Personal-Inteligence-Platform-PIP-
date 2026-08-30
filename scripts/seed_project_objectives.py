"""
Seed PIP's own objectives into goal_memory.

Why this exists
---------------
goal_memory was empty. Not "sparse" - zero active rows, while the project it
belongs to has 99 decisions and 4 ingested documents behind it. So PIP could
answer what was decided and when, and had nothing to say about what any of it
was FOR. Asked "what goals do I have?", it answered "I don't have any recorded
goals for you" (conversation 3093f89e, 2026-08-25), which was true and is
exactly the gap this closes.

The objectives are not invented here. They are transcribed from section 5 of
data/documents/PIP_OVERVIEW.md - the project's own overview, already ingested
into RAG - which states them as the spec's "locked priority order". That
document is first-hand, so the objectives can be written directly rather than
inferred by the Observer from conversation, the same argument
seed_project_history.py makes for the decision log.

What it writes
--------------
Eight rows into goal_memory, all status='active':

  1 thesis-level objective  The governance-layer claim the project is built to
                            demonstrate. PIP_OVERVIEW.md is explicit that this
                            is THE contribution, and that the UI and app shell
                            exist to demonstrate it rather than being it.

  7 product objectives      The locked priority order, 1 through 7. The
                            priority number is written into goal_text rather
                            than implied by row order, because get_profile()
                            reads goal_memory ORDER BY updated_at DESC - so
                            display order is a timestamp artifact, and encoding
                            priority in the text is the only way it survives
                            into the context the model actually sees. Staggering
                            updated_at to fake the ordering would put a false
                            edit history on eight rows to control a sort.

All eight are 'active'. Several are substantially built - the decision log and
RAG are working and populated - but "the objective is met" is a judgement about
the project, not a fact this script can read out of a document, and marking a
goal 'completed' removes it from the active_goals view and from context. What
was actually built is already recorded, per commit and per phase, in
decision_log; duplicating a completion claim here would state it in a second
place with less evidence behind it.

Confidence
----------
Computed by profile_store.write_approved_candidate()'s own formula, not chosen:

    base = 0.9 for an explicit label;  confidence = base * min(count, 5) / 5

evidence_count is 5, the point at which that formula saturates. That is a claim
about provenance, and it is worth being precise about what it rests on: these
objectives are stated in the project's own locked spec AND the user explicitly
directed them to be written here. Anything lower would understate a first-hand
source in the same way seed_project_history.py's confidence floor would have.

1.0 is deliberately not used. In this codebase 1.0 belongs to
apply_verified_correction() - the user correcting a specific field in the moment
- and borrowing it for a bulk seed would erase the distinction between "the
user's own document says so" and "the user just told us this is wrong".

The confirmation gate
---------------------
constitutional.json lists goal_memory.* under gated_fields with enforcement
'prompt_confirm', so the Observer cannot write a goal without the user
confirming it. That gate is not being bypassed here, it is being satisfied: it
exists to stop the SYSTEM inferring goals silently, and this is a write the user
asked for by name. The five fabricated goals sitting in
memory_candidates_pending ("Smith Project", "Johnson Report", a smart-home
security product) are what the gate looks like when it is doing its job - they
never reached this table.

Safety
------
Idempotent. Each goal is matched on exact goal_text against the active rows
before writing, so a second run reports them present and writes nothing.
Nothing is updated or deleted; the fabricated pending candidates are left
untouched for a separate retraction pass.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\seed_project_objectives.py --dry-run
    .venv\\Scripts\\python.exe scripts\\seed_project_objectives.py
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.memory import profile_store  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "pip.db"
KEY_PATH = ROOT / "data" / "db_key.txt"
LOCK_PATH = ROOT / "data" / "pip.lock"

SOURCE = "data/documents/PIP_OVERVIEW.md section 5"

# The date the objectives were set, not the date this script ran. The locked
# priority order predates implementation - it is the spec the first commit was
# written against - so it carries the project's start date, the same backfill
# convention seed_project_history.py uses for its milestones.
SET_AT = "2026-07-03T12:00:00Z"

# write_approved_candidate()'s formula for an explicit label, at the count
# where it saturates. See the module docstring for why 5 and not 1, and why
# not 1.0.
EVIDENCE_COUNT = 5
CONFIDENCE = 0.9 * min(EVIDENCE_COUNT, 5) / 5.0

GOALS: tuple[str, ...] = (
    "Thesis objective: demonstrate a working governance layer for personal AI memory - a "
    "system that decides, deterministically and auditably, what an LLM is and is not allowed "
    "to learn and retain about a user, including conflicting evidence, behavioural "
    "contradictions of stated preferences and low-confidence inferences, without ever "
    "silently corrupting or fabricating what it believes about the user.",

    "Priority 1 (locked spec order) - Decision Log: a searchable, permanent record of "
    "decisions made and the reasoning behind them. The highest-priority feature.",

    "Priority 2 (locked spec order) - Project Memory: what the user is actively working on.",

    "Priority 3 (locked spec order) - RAG document retrieval: grounding answers in the "
    "user's own documents.",

    "Priority 4 (locked spec order) - Session Continuity: picking up where the last session "
    "left off.",

    "Priority 5 (locked spec order) - Personal Profile: skills, preferences and interaction "
    "style.",

    "Priority 6 (locked spec order) - Observer auto-learning: inferring memory-worthy signals "
    "from conversation without the user having to log everything manually.",

    "Priority 7 (locked spec order) - Depth Detection: lowest priority, largely solved by "
    "letting the user ask for an answer 'briefly' or 'in detail'.",
)


def _connect():
    key = os.environ.get("PIP_DB_KEY")
    if not key and KEY_PATH.exists():
        key = KEY_PATH.read_text(encoding="utf-8").strip()
    return profile_store.get_connection(str(DB_PATH), key or None)


def _warn_if_running() -> None:
    """Same note as seed_project_history.py: WAL serialises the writes, but a
    seed landing mid-session is confusing to read back."""
    if not LOCK_PATH.exists():
        return
    pid = LOCK_PATH.read_text(encoding="utf-8").strip()
    print(
        f"NOTE: data/pip.lock exists (pid {pid}) - PIP may be running. "
        "Closing it first makes the result easier to read back.\n"
    )


def _existing_goals(conn) -> set[str]:
    return {
        row["goal_text"]
        for row in conn.execute("SELECT goal_text FROM goal_memory WHERE status = 'active'")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PIP's own objectives into goal_memory.")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"no database at {DB_PATH}", file=sys.stderr)
        return 1

    _warn_if_running()
    if args.dry_run:
        print("DRY RUN - nothing will be written.\n")

    print(f"source: {SOURCE}")
    print(f"evidence_count={EVIDENCE_COUNT}  confidence={CONFIDENCE:.2f}  set_at={SET_AT}\n")

    conn = _connect()
    try:
        present = _existing_goals(conn)
        written = existing = 0

        for goal_text in GOALS:
            if goal_text in present:
                existing += 1
                print(f"  already present: {goal_text[:78]}")
                continue

            written += 1
            if args.dry_run:
                print(f"  WOULD WRITE:     {goal_text[:78]}")
                continue

            cur = conn.execute(
                "INSERT INTO goal_memory (goal_text, evidence_count, confidence, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', ?, ?)",
                (goal_text, EVIDENCE_COUNT, CONFIDENCE, SET_AT, SET_AT),
            )
            conn.commit()
            print(f"  written (id {cur.lastrowid}): {goal_text[:70]}")

        verb = "would write" if args.dry_run else "written"
        print(f"\n{verb}: {written}   already present: {existing}")
        total = conn.execute("SELECT COUNT(*) FROM goal_memory WHERE status = 'active'").fetchone()[0]
        print(f"active goals: {total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
