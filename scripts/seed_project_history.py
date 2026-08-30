"""
Seed PIP's own development history into its memory tables.

Why this exists
---------------
PIP's decision log was, in practice, empty. The seven rows in it were all
Observer confabulations from before the grounding fixes (1221a42, e814a9e)
and were retracted wholesale by cleanup_fabricated_memory.py, leaving
state='abandoned' on every one. So when the user asks PIP what it is, when a
thing was built, or why a choice was made, Stage 3 searches an empty log and
Stage 7 assembles nothing - and the model answers from the prompt alone.

The project's actual history is in the repository: 71 commits between
2026-07-03 and 2026-08-28, most with a substantial body explaining the
reasoning. That is exactly the shape decision_log stores, and it is
first-hand rather than inferred, so it can be written directly instead of
being routed through the Observer's extraction path.

What it writes
--------------
Two tiers, both into decision_log, both attached to the 'PIP' project:

  MILESTONES  Hand-written phase-level entries (Phase 0 through the current
              hardening pass), each with reasoning and, where one genuinely
              existed, the alternative that was rejected. These are the
              entries a question like "what did we build in Phase 6?" should
              match.

  COMMITS     One entry per commit, read from `git log` at run time rather
              than frozen into this file - re-running after more commits
              land catches the log up instead of needing an edit here. The
              subject becomes decision_text; the body (minus trailer lines)
              becomes reasoning.

Also fills in active_projects.description for the PIP row, which said only
"a personalised system" - a placeholder the Observer wrote.

Dates
-----
created_at is set to the real historical date, not now(). insert_decision()
stamps now_utc() because every other caller is recording something as it
happens; this one is backfilling, so the row is updated immediately after
insert. decision_log's immutability trigger covers decision_text only, so
this is allowed by design rather than by omission.

Confidence
----------
score_confidence() over classify_decision_signals(), floored at 0.7
(log_threshold_observer). The floor is deliberate and is not a model
estimate - ADR-005's rule is that the *model* never assigns confidence.
These entries are attested by the repository itself, so the keyword-derived
score is a lower bound on how certain they are, not the measure of it.

insert_decision() is called directly rather than create_decision(), so the
manual log threshold does not apply: a curated backfill has already been
reviewed, and routing half of it into decision_candidates_pending would just
create review work for facts that are not in question.

Safety
------
Idempotent. Every insert goes through insert_decision(), which returns the
existing id for an active duplicate rather than writing a second row, so
re-running reports "already present" instead of doubling the log. Nothing is
deleted or overwritten except the project description, and that only while it
still holds the placeholder value.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\seed_project_history.py --dry-run
    .venv\\Scripts\\python.exe scripts\\seed_project_history.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.memory import decision_log, profile_store  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "pip.db"
KEY_PATH = ROOT / "data" / "db_key.txt"
LOCK_PATH = ROOT / "data" / "pip.lock"

PROJECT_NAME = "PIP"
PLACEHOLDER_DESCRIPTIONS = {"", "a personalised system"}
PROJECT_DESCRIPTION = (
    "Personal Intelligence Platform - a local-first personal AI that remembers. "
    "Python/FastAPI backend, a 14-stage message pipeline, a SQLCipher-encrypted "
    "profile and decision log, ChromaDB RAG over local documents, Ollama for "
    "inference, and a native Windows Flutter client. Final year project, started "
    "2026-07-03."
)

# Trailer lines dropped from a commit body: they are provenance for the
# commit, not reasoning for the decision, and would otherwise be indexed by
# FTS5 and match searches for the wrong reason.
_TRAILER_PREFIXES = ("Co-Authored-By:", "Co-authored-by:", "Signed-off-by:")

# How much of a commit body to keep as reasoning. Long enough for the
# argument, short enough that 71 of them don't turn the log into a mirror of
# the repository. reasoning is never printed into the prompt - Stage 7's
# _format_decisions uses decision_text only - so this bounds storage and the
# FTS index, not context.
_MAX_REASONING_CHARS = 1200


# (date, decision_text, reasoning, alternatives_considered)
#
# Dates are the day the work landed, per git. Where a milestone spans several
# days the date is the day it completed. alternatives is None wherever no
# alternative was genuinely weighed - inventing one would make the log say
# something the project never did.
MILESTONES: tuple[tuple[str, str, str | None, str | None], ...] = (
    (
        "2026-07-03",
        "PIP is a local-first personal intelligence platform: a Python/FastAPI backend, "
        "a SQLCipher-encrypted profile, and a staged message pipeline that runs against "
        "a local model.",
        "Phase 0. The founding shape of the project: configuration, database schema and "
        "core components. Local-first is the premise the rest of the design follows from - "
        "the profile, decision log and conversation history are the most personal data a "
        "user has, so they stay on the user's machine and the default inference provider "
        "is local.",
        "A cloud-hosted assistant with a remote profile store, which would have been "
        "simpler to build and impossible to make the same privacy claim about.",
    ),
    (
        "2026-07-04",
        "Every write to the profile passes through a Constitutional Core that can refuse it.",
        "Phase 1. ConstitutionEnforcer validates candidate writes against constitutional.json: "
        "which tables the Observer may write at all, which fields are gated behind explicit "
        "user confirmation, and the tiered evidence thresholds a candidate must clear before it "
        "becomes profile state. The point is that an inference the system makes about the user "
        "is not the same as something the user said, and the schema knows the difference.",
        "Letting the Observer write directly to the profile and relying on prompt discipline "
        "to keep it honest.",
    ),
    (
        "2026-07-05",
        "Architecture decisions are recorded as numbered ADRs rather than left in commit messages.",
        "Phase 2. The master reference document collected the ADRs behind the design so later "
        "work could cite a decision by number instead of re-arguing it. The document itself was "
        "later moved out of the repository (7db2f17), but the ADR numbering it established is "
        "still what the code comments reference.",
        None,
    ),
    (
        "2026-07-09",
        "Cloud providers are gated behind explicit per-provider consent, stored and revocable.",
        "Phase 3, tagged v0.3 at 6f1efa5 with 81 tests passing. The provider layer abstracts "
        "inference behind BaseLLMProvider, and the consent gate stands in front of it: a provider "
        "marked is_cloud cannot be used until the user has consented, with a recorded scope and "
        "date, and consent can be revoked. Local providers need no gate, which is why local "
        "stayed the default.",
        None,
    ),
    (
        "2026-07-11",
        "PIP detects what it does not know about the user and carries a session summary forward.",
        "Phase 4, tagged v0.4 at 2583c4f with 97 tests passing. The Gap Detector (Stage 0) finds "
        "missing profile fields worth asking about; the session snapshot gives the next session a "
        "warm start - topic, open problems, last decisions, suggested next step - instead of "
        "beginning cold every time.",
        None,
    ),
    (
        "2026-08-16",
        "get_connection() raises instead of silently falling back to plaintext SQLite when a key "
        "is supplied without SQLCipher installed.",
        "Found while rebuilding the dev environment (c558893): sqlcipher3-binary had disappeared "
        "from PyPI and no wheel existed for the Python version in use, so the SQLCipher import "
        "failed and every test run to date had exercised unencrypted SQLite while believing it "
        "was testing the encrypted path. The environment was rebuilt on Python 3.12 with a real "
        "requirements.txt, and the silent degradation was turned into a loud failure.",
        "Keeping the fallback and warning instead - rejected, because the failure it hides is "
        "exactly the one nobody notices.",
    ),
    (
        "2026-08-16",
        "A validation layer sits between the Observer's proposals and the profile, and Stage 13 "
        "owns every write.",
        "Phase 5, tagged v0.5 at b2fc6df with 121 tests passing. Stage 12 checks a candidate "
        "against real database state - existing value, evidence count, profile age - and returns "
        "one of six outcomes; Stage 13 routes that outcome to a write path, a pending-candidate "
        "row, or nothing at all. memory_candidates_pending gained target_table and state tracking "
        "so a candidate needing the user's decision survives to the next session.",
        None,
    ),
    (
        "2026-08-16",
        "The Observer runs on llama3.1:8b, the same model as generation, instead of a separate "
        "small model (ADR-033).",
        "The two-model design (phi3:mini for observation, llama3.1:8b for generation) required "
        "strict sequential VRAM swapping on an 8GB card, and the swap benchmark that justified it "
        "had never been run. Running the A/B test instead of deciding from documentation: "
        "phi3:mini took 58s and produced structurally broken output - it echoed the schema back "
        "rather than populating candidates, and missed a decision with two extractable signals. "
        "llama3.1:8b took 131s and produced valid, correctly labelled candidates. The gap was not "
        "marginal, so the two-model design was dropped and observer_max_seconds raised from 30 "
        "(never validated for either model) to 180.",
        "Keeping phi3:mini as a dedicated Observer model, which the A/B test ruled out.",
    ),
    (
        "2026-08-17",
        "SQLite is the source of truth for what has been ingested; ChromaDB is never authoritative "
        "and is rebuildable from it.",
        "Phase 6. The documents registry (file_path, content_hash, chunk_count) is what makes "
        "'rebuild the vector index from SQLite' implementable - before it there was nothing to "
        "rebuild from. Embeddings are all-MiniLM-L6-v2 on CPU, keeping the GPU free for "
        "inference. Two real bugs surfaced by running against the actual dependencies rather than "
        "mocks: the unchanged-hash shortcut skipped re-ingestion even when Chroma had drifted out "
        "of sync, and the decision-conflict heuristic used Jaccard similarity, which under-flags "
        "a short decision against a long chunk.",
        "Jaccard similarity for the conflict check, replaced by the overlap coefficient "
        "(intersection over the smaller set) once it failed a realistic case.",
    ),
    (
        "2026-08-17",
        "A session's learning is queued to the database before the process exits, so a crash "
        "during the Observer pass does not lose it.",
        "ADR-033's second locked condition, and a pre-existing gap in ADR-003. An Observer pass "
        "takes around 130 seconds cold, which cannot block SIGINT or SIGTERM; the pending_observer "
        "table holds the transcript (SQLCipher-encrypted, never a plain file) and it is drained "
        "before Stage 0 on the next launch. Rows left in 'processing' are retried, not skipped - a "
        "stuck 'processing' row means a previous drain crashed mid-run, which is the exact failure "
        "this table exists to survive.",
        None,
    ),
    (
        "2026-08-17",
        "The Observer extracts memory and decisions from a whole session at its end, never per "
        "message, and its confidence is computed rather than self-reported.",
        "Phase 7. Stage 11 runs a single extraction pass over the transcript and routes what it "
        "finds through Stages 12 and 13. Signals come from the model's reading of the "
        "conversation, but the score is always computed by score_confidence(), and unknown signal "
        "names are dropped before scoring so a hallucinated signal cannot inflate it. "
        "Cross-session evidence reinforcement followed immediately: a single pass can only ever "
        "produce evidence_count=1, so without it every candidate would stop clearing the tiered "
        "thresholds after a few weeks of real use.",
        None,
    ),
    (
        "2026-08-18",
        "The message pipeline is fourteen ordered stages with a fixed per-source context budget "
        "and a documented drop order when it overflows.",
        "Phase 8. Intent classification, routing, decision/memory/RAG lookup, web search, context "
        "assembly, the provider gate, streaming and delivery, wired together by core/pipeline.py "
        "and exposed over /ws/chat, with process-lifecycle handling (idle timeout, disconnect, "
        "shutdown) and a response cache. Assembly resolved a real inconsistency in the spec: the "
        "itemised token budget summed to 6400 against a stated 6000 total, resolved as per-source "
        "ceilings reconciled by overflow trimming rather than guaranteed reservations. Retrieval "
        "stages fail open by contract - an error returns empty and the pipeline continues.",
        "Treating the per-source budgets as fixed reservations, which cannot be made to sum "
        "correctly and would have starved whichever source was listed last.",
    ),
    (
        "2026-08-19",
        "The API authenticates with a Bearer token from a local file, and the whole surface was "
        "put through a security review pass.",
        "Auth moved to Authorization: Bearer with the token in data/api_token.txt; the consent "
        "gate, the document path sandbox and trust verification were fixed in the same pass. The "
        "session snapshot was moved off plaintext disk into the SQLCipher database, where the rest "
        "of the structured profile already lived - it had been sitting outside the encryption "
        "boundary holding topics, decisions and open problems.",
        None,
    ),
    (
        "2026-08-22",
        "The client is a Flutter app with a conversation sidebar, mid-stream stop, model selection "
        "and document upload.",
        "A throwaway Dart spike proved async WebSocket stream handling first, then was discarded "
        "rather than grown into the real client. The redesign added a genuine mid-stream interrupt "
        "(threaded through Stage 9 and the pipeline, after two concurrent-receiver designs "
        "deadlocked Starlette's WebSocket under TestClient), model selection backed by a new "
        "llm_settings table that the Observer also reads, document upload through a sandboxed copy "
        "step, and conversations/messages tables so chat history survives a disconnect.",
        None,
    ),
    (
        "2026-08-24",
        "PIP ships as a native Windows app started by a hidden one-click launcher; the browser "
        "workflow is retired.",
        "A compiled executable cannot have a build-time constant match a token that does not exist "
        "until the backend's first run, so configuration moved from --dart-define to runtime reads "
        "of the environment and data/api_token.txt. The launcher starts Ollama and the backend "
        "with no console windows and exits; waiting for readiness is the app's own splash screen's "
        "job. ChromaDB chunk text and file paths were Fernet-encrypted in the same period, and a "
        "PID-file lock now stops a second backend writing the same database.",
        "Keeping the web/-d edge debug workflow, which cannot read the environment through "
        "dart:io at all.",
    ),
    (
        "2026-08-25",
        "The Observer may not write anything it cannot quote from the transcript.",
        "The confabulation arc, all of it found in the live database rather than in tests. A "
        "session of nothing but 'hi'/'yes'/'sure' produced seven auto-logged fake decisions and a "
        "session snapshot describing a product launch meeting that never happened. Fixes, in "
        "order: reject candidates phrased as questions or echoing the assistant's own lines; "
        "require the model's own raw_quote to actually appear in the transcript; withhold the "
        "snapshot when a session has no real user turn; constrain output with a JSON schema "
        "instead of parsing hopefully; ground memory candidates the same way; reject a "
        "target_table that does not exist; suppress duplicates on write; and retract the "
        "fabrications already in the database, without deleting them, per ADR-022.",
        "Tightening the extraction prompt alone, which was kept as a secondary defence but is not "
        "the fix - the deterministic checks against the real transcript are.",
    ),
    (
        "2026-08-27",
        "The database key is derived from a password the user types, and is never written to disk.",
        "Encryption at rest was found to be dead code in the shipped product (8414e44): PIP_DB_KEY "
        "was never set on either launch path, so every real run took the plain sqlite3 branch. The "
        "first fix generated a random key and persisted it to data/db_key.txt - beside the "
        "database it decrypts, so anything that copies data/ gets both. Replacing it with PBKDF2 "
        "from a password means a stolen disk or a backup of data/ is useless without it, at the "
        "cost of no recovery if the password is forgotten, which is the intended trade. The salt "
        "is created on first run so a fresh install is never plaintext, and one derivation "
        "implementation is called from everywhere - a PowerShell reimplementation differing in any "
        "parameter would fail as 'wrong password' against a correct one.",
        "Keeping the random key in data/db_key.txt, which encrypts against a stolen disk only if "
        "the thief does not take the whole folder.",
    ),
    (
        "2026-08-28",
        "Nothing a session produced is dropped silently: unobserved turns, unreachable models and "
        "interrupted rekeys all leave a recoverable trace.",
        "The current durability pass. Conversations track how far the Observer got as a message-id "
        "high-water mark, so turns added after a pass are not silently treated as observed; an "
        "unreachable Ollama no longer retires a queued transcript as if it had been processed; the "
        "trace log appends rather than rewriting itself on every entry; ChromaDB is cleared before "
        "a rebuild so a rekey leaves nothing behind, in the migration script as well as the main "
        "path; and the retired web client, which could only authenticate by putting the token in "
        "the URL, is no longer served.",
        None,
    ),
    (
        "2026-08-28",
        "PIP's own development history lives in the decision log it searches, and the dates and "
        "reasoning behind each entry are put in front of the model.",
        "A system whose premise is that it remembers was answering every question about itself "
        "from the prompt alone: the seven rows in the decision log were all pre-grounding Observer "
        "confabulations, retracted wholesale, which left Stage 3 searching an empty table. The "
        "history was never missing - it was in the repository, one commit body at a time - so it "
        "was written in directly rather than inferred, as hand-written phase milestones plus one "
        "entry per commit read from git at run time, each carrying the date the work actually "
        "landed rather than the date it was backfilled. Seeding it then exposed three things an "
        "empty log had hidden: created_at never reached the model, so the log could say what was "
        "decided and never when; reasoning never reached it either, leaving the model to guess at "
        "justifications that were sitting unread in the database, which is the exact gap that "
        "invites invention; and Stage 3 returned every bareword match, so a general-knowledge "
        "question pulled in 77 unrelated decisions. Dates now render on every entry, reasoning on "
        "the top three by bm25 rank, and the block is capped at 12 and built up to the token "
        "budget rather than built whole and truncated mid-sentence.",
        "Routing the history through the Observer's extraction path, which would have inferred "
        "reasoning from commit bodies that already state it first-hand.",
    ),
)


def _connect():
    key = os.environ.get("PIP_DB_KEY")
    if not key and KEY_PATH.exists():
        key = KEY_PATH.read_text(encoding="utf-8").strip()
    return profile_store.get_connection(str(DB_PATH), key or None)


def _warn_if_running() -> None:
    """
    A running backend holds data/pip.lock. WAL serialises the writes either
    way, so this is a warning rather than a refusal - but a seed run landing
    mid-session is confusing to read back, so say so.
    """
    if not LOCK_PATH.exists():
        return
    pid = LOCK_PATH.read_text(encoding="utf-8").strip()
    print(
        f"NOTE: data/pip.lock exists (pid {pid}) - PIP may be running. "
        "Closing it first makes the result easier to read back.\n"
    )


def _project_id(conn, dry_run: bool) -> str | None:
    row = conn.execute("SELECT * FROM active_projects WHERE name = ?", (PROJECT_NAME,)).fetchone()
    if row is None:
        print(f"NOTE: no '{PROJECT_NAME}' project row - entries will be logged with no project.")
        return None

    description = (row["description"] or "").strip()
    if description in PLACEHOLDER_DESCRIPTIONS:
        print(f"  project description: {description!r} -> real description")
        if not dry_run:
            conn.execute(
                "UPDATE active_projects SET description = ? WHERE project_id = ?",
                (PROJECT_DESCRIPTION, row["project_id"]),
            )
            conn.commit()
    else:
        print(f"  project description already set, left alone: {description[:60]!r}")
    return str(row["project_id"])


def _commit_entries() -> list[tuple[str, str, str | None, str | None]]:
    """
    Every commit, oldest first, as (created_at, text, reasoning, alternatives).

    Read from git at run time rather than frozen here: a later re-run picks up
    whatever has landed since, which is the whole reason this is a script and
    not a one-off INSERT.
    """
    unit, record = "\x1f", "\x1e"
    out = subprocess.run(
        ["git", "log", "--reverse", f"--format=%h{unit}%aI{unit}%s{unit}%b{record}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout

    entries: list[tuple[str, str, str | None, str | None]] = []
    for raw in out.split(record):
        if not raw.strip():
            continue
        short_hash, iso_date, subject, body = raw.strip("\n").split(unit, 3)
        # Two dates, deliberately. created_at is UTC because every other
        # timestamp in this schema is (now_utc()), and a log that mixed the two
        # could not be ordered against conversations or trace entries. The
        # header keeps the AUTHOR'S LOCAL date, which is the one the user
        # remembers and searches for - the two differ by a day for anything
        # committed late at night (f433541 is 2026-08-27 locally, 2026-08-26
        # in UTC), and reasoning is FTS-indexed, so the local date is findable.
        authored = dt.datetime.fromisoformat(iso_date)
        when = authored.astimezone(dt.timezone.utc)

        lines = [
            line for line in body.strip().splitlines()
            if not line.startswith(_TRAILER_PREFIXES)
        ]
        detail = "\n".join(lines).strip()
        if len(detail) > _MAX_REASONING_CHARS:
            detail = detail[:_MAX_REASONING_CHARS].rstrip() + " [...]"

        header = f"Commit {short_hash}, {authored.strftime('%Y-%m-%d')}."
        reasoning = f"{header}\n\n{detail}" if detail else header
        entries.append((when.strftime("%Y-%m-%dT%H:%M:%SZ"), subject.strip(), reasoning, None))
    return entries


def _confidence(text: str, reasoning: str | None, alternatives: str | None) -> float:
    signals = decision_log.classify_decision_signals(text, reasoning, alternatives)
    # See the module docstring: the floor is a statement about provenance
    # (the repository), not an estimate made by a model.
    return max(decision_log.score_confidence(signals), 0.7)


def _seed(conn, entries, project_id: str | None, label: str, dry_run: bool) -> tuple[int, int]:
    written = existing = 0
    print(f"\n{label} ({len(entries)}):")
    for created_at, text, reasoning, alternatives in entries:
        duplicate_id = decision_log.find_active_duplicate(conn, text, project_id)
        if duplicate_id is not None:
            existing += 1
            print(f"  [{created_at[:10]}] already present (id {duplicate_id}): {text[:70]}")
            continue

        written += 1
        if dry_run:
            print(f"  [{created_at[:10]}] WOULD WRITE: {text[:70]}")
            continue

        decision_id = decision_log.insert_decision(
            conn,
            text=text,
            reasoning=reasoning,
            alternatives=alternatives,
            project_id=project_id,
            confidence=_confidence(text, reasoning, alternatives),
        )
        # insert_decision() stamps now_utc(); this is a backfill, so the row
        # carries the date the thing actually happened. Only decision_text is
        # covered by the immutability trigger.
        conn.execute("UPDATE decision_log SET created_at = ? WHERE id = ?", (created_at, decision_id))
        conn.commit()
        print(f"  [{created_at[:10]}] written (id {decision_id}): {text[:70]}")
    return written, existing


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed PIP's own development history.")
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    parser.add_argument("--milestones-only", action="store_true", help="skip the per-commit entries")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"no database at {DB_PATH}", file=sys.stderr)
        return 1

    _warn_if_running()
    if args.dry_run:
        print("DRY RUN - nothing will be written.\n")

    conn = _connect()
    try:
        project_id = _project_id(conn, args.dry_run)

        milestones = [(f"{d}T12:00:00Z", t, r, a) for d, t, r, a in MILESTONES]
        written, existing = _seed(conn, milestones, project_id, "Milestones", args.dry_run)

        if not args.milestones_only:
            w, e = _seed(conn, _commit_entries(), project_id, "Commits", args.dry_run)
            written += w
            existing += e

        verb = "would write" if args.dry_run else "written"
        print(f"\n{verb}: {written}   already present: {existing}")
        total = conn.execute("SELECT COUNT(*) FROM decision_log WHERE state = 'active'").fetchone()[0]
        print(f"active decisions in the log: {total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
