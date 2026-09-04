"""
Write a five-part worked example into a profile: one conversation, and the
decisions it reaches.

    python scripts/seed_demo_conversation.py
    python scripts/seed_demo_conversation.py --project PIP
    python scripts/seed_demo_conversation.py --undo data/demo_seed_<stamp>.json

WHY THE CONTENT IS TRUE
-----------------------
The obvious way to build a demo is to invent one, and this project has already
paid for that once - cleanup_fabricated_memory.py and
retract_fabricated_candidates.py exist because invented rows got into a real
profile and could not afterwards be told apart from observed ones.

So nothing here is invented. The three decisions it logs were actually taken,
on 2026-09-02, while building cross-machine continuity: documents moved into the
database, profiles became separately encrypted databases, and the export stayed
off the HTTP API. The dialogue is a reconstruction of reasoning that genuinely
happened, not a script for reasoning that did not. That is the difference
between a demo and a fabrication, and it is the whole reason this script is safe
to point at a real profile when seed_test_profile.py is not.

The transcript is still synthesised - these words were not typed into PIP's chat
box in this order - and anybody reading this file should know that. What is
being claimed is that the decisions are real and the reasoning is accurate.

WHY IT IS REVERSIBLE WITHOUT BEING MARKED
-----------------------------------------
Marking every row as demo data would defeat the purpose: you cannot show
somebody what the Decisions screen looks like when every row announces itself as
an example. So the rows read normally, and reversibility lives outside them - a
manifest naming exactly the conversation and decision ids that were written,
which --undo removes and nothing else.

That is a deliberate exception to ADR-022's "hard deletion never permitted",
and the distinction is worth stating: ADR-022 governs DECISIONS, which are
retracted rather than erased because the fact that you once believed something
is itself part of the record. Undoing a seeding operation is not retracting a
decision - it is removing rows that a script put there, restoring the state that
existed before it ran. Retracting them instead would leave the log asserting
that these were decided and later abandoned, which is false in both halves.

WHAT IT REFUSES TO DO
---------------------
Run while PIP is open, because the session-end Observer writes against the
conversation it is holding. Write a second copy, because the title is checked
first. Guess a project, because a conversation filed against the wrong one is
worse than one filed against none.
"""

import _venv

_venv.require("sqlcipher3")

import _db

import argparse
import json
import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import profiles  # noqa: E402
from backend.memory import decision_log  # noqa: E402

TITLE = "Cross-machine continuity"

# Taken on 2026-09-02. Each one is a decision that was actually made, with the
# reasoning that actually decided it and the alternative that was actually
# weighed - which is why these can go into a real decision log.
DECISIONS = [
    (
        "Store ingested document content in the database, not only on disk",
        "A backup recorded that a document had been ingested - its path, hash and "
        "chunk count - and held none of the file, so restoring on a second machine "
        "brought back a registry pointing at paths that had never existed there. "
        "Everything else arrived and RAG arrived empty. It also closes the one "
        "place ADR-026's 'no plaintext' rule did not hold: ingested files sat "
        "readable in data/documents while every other byte was inside SQLCipher.",
        "Considered shipping a documents folder beside the .pipbak, which would "
        "have meant a package format and a folder that can be separated from the "
        "file it belongs to; and leaving it manual, which depends on remembering "
        "one step on the day you are already restoring from a backup.",
    ),
    (
        "Multiple profiles as separately encrypted databases, not a profile_id column",
        "One database means one SQLCipher key, so a profile_id column would have "
        "meant one password decrypting every profile in it - each user able to read "
        "the others' conversations and memory. For an application whose claim is "
        "governed private personal data, that is a display filter wearing the word "
        "privacy. Separate databases also left the five CHECK (id = 1) singletons "
        "and every existing query untouched.",
        "Considered a profile_id on all ~25 tables, which would have made switching "
        "instant with no restart, at the cost of the separation being real.",
    ),
    (
        "Keep the export off the HTTP API; the Backup screen launches a console",
        "ADR-027 upheld rather than revisited. The backend's live connection already "
        "holds the real key, so a route producing a re-encrypted copy would hand "
        "that capability to anything able to read data/api_token.txt - any process "
        "running as this user - without it ever knowing the live key. The button "
        "starts a console where the export asks for the live password from a person.",
        "Considered a real in-app flow posting the password to a new endpoint, which "
        "reads better and would have put the master password through an HTTP body "
        "and the app's memory.",
    ),
]

# Five sections, each demonstrating a different part of PIP. The decision indices
# say which decision (if any) that section reaches, so the transcript and the
# decision log agree with each other rather than being written twice.
SECTIONS = [
    (
        "Warm start",
        None,
        [
            ("user", "I'm back on PIP after a couple of days. Where did I leave the backup work?"),
            ("assistant",
             "Two days since the last recorded session. What is in the log: the export "
             "writes a single encrypted .pipbak and the restore rebuilds from one, and "
             "both are proven end to end by a test that destroys the database in "
             "between. What is not resolved is what a backup actually contains - the "
             "documents table records that a file was ingested and nothing holds the "
             "file. I am reporting that from the decision log and the test names, not "
             "from remembering the conversation."),
            ("user", "Right, that's the gap. If I restore on a new laptop, RAG comes back empty."),
            ("assistant",
             "Yes. The profile, projects, decisions and every message come back, "
             "because those are rows. The four ingested markdown files are not rows - "
             "they are files in data/documents, and the vector index is rebuilt from "
             "them. Neither is inside the .pipbak."),
        ],
    ),
    (
        "Reaching a decision",
        0,
        [
            ("user",
             "Then put the document bytes in the database. One file should be enough to "
             "carry - no sibling folder, no package format."),
            ("assistant",
             "Logged that as a decision against PIP, with the reasoning and the two "
             "alternatives you weighed. It does not contradict anything active in the "
             "log; it completes ADR-026 rather than amending it, since those four files "
             "were the only bytes you own sitting outside SQLCipher."),
            ("user", "Does it need a schema change?"),
            ("assistant",
             "One table. document_blobs, keyed on documents.id, holding the content and "
             "its size. Separate from documents because list_documents does SELECT * on "
             "every Documents screen load, and a BLOB in that row would drag the whole "
             "corpus through a query that wants five columns."),
        ],
    ),
    (
        "Declining to learn too fast",
        None,
        [
            ("user", "Keep your answers shorter from now on."),
            ("assistant",
             "I have not stored that. You have said it once, and a single statement is "
             "below the threshold for writing to your profile - storing it now would "
             "mean adapting to something you may have meant only for today. I will keep "
             "answers short for the rest of this session, and if you say it again in "
             "another one I will ask whether to make it permanent."),
            ("user", "That's the behaviour I designed, so good. What would change your mind?"),
            ("assistant",
             "A second session with the same statement, which takes evidence_count to "
             "the threshold, or you telling me directly to store it - a user correction "
             "outranks accumulated inference and applies immediately. The rule is in "
             "constitutional.json, and the enforcer applies it; I am not choosing to be "
             "cautious here, I am reporting what the gate did."),
        ],
    ),
    (
        "Answering from the documents",
        1,
        [
            ("user", "What did I decide about multi-user, back when I wrote the ADRs?"),
            ("assistant",
             "From PIP_ARCHITECTURE_PRD_ADR.md, which is ingested: ADR-010 rejected "
             "ephemeral consent tokens on the grounds that they solve a multi-user "
             "web-app problem and are the wrong scale here. The overview and the "
             "current-state doc both describe PIP as single-user. That is what the "
             "documents say - I am not inferring your intent beyond them."),
            ("user",
             "It still is single-user per profile. I want more than one profile, each "
             "its own encrypted database with its own password - not a user_id column."),
            ("assistant",
             "Logged. Recorded as separate databases rather than a shared one, with the "
             "reason being that a shared database has a single key, so one password "
             "would open everyone's data. It narrows ADR-010 rather than reversing it: "
             "still one user per database, now more than one database."),
        ],
    ),
    (
        "Correcting me",
        2,
        [
            ("user", "Should the Backup screen just do the export itself? The console is clumsy."),
            ("assistant",
             "It reads better, and it would put your live password through an HTTP body "
             "and the app's memory. ADR-027 keeps the export off the API because the "
             "backend already holds the real key, so a route re-encrypting under a "
             "caller's password hands that capability to anything that can read "
             "api_token.txt."),
            ("user",
             "Agreed, keep it off the API. But your earlier note said the WAL checkpoint "
             "is what saves recent writes - that's wrong, the export reads through the "
             "page layer and the checkpoint is defence in depth."),
            ("assistant",
             "Corrected, and recorded as a user correction, which outranks what I had "
             "inferred. Part 10.2 says the same and the round-trip test proves it: one "
             "case removes the checkpoint entirely and the uncheckpointed row still "
             "comes back. I have logged the decision to keep the export off the API "
             "with the in-app flow noted as the alternative you rejected."),
        ],
    ),
]


def find_project(conn, name: str) -> str:
    row = conn.execute(
        "SELECT project_id, name FROM active_projects WHERE name = ? AND status != 'deleted'",
        (name,),
    ).fetchone()
    if row is None:
        available = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM active_projects WHERE status != 'deleted' ORDER BY name"
            )
        ]
        sys.exit(
            f"ERROR: no project named {name!r} in this profile.\n"
            f"       Available: {', '.join(available) or '(none)'}\n"
            "       A conversation filed against the wrong project is worse than one "
            "filed against none, so this will not guess."
        )
    return row["project_id"]


def refuse_if_pip_is_running() -> None:
    """
    The session-end Observer writes against the conversation a live session is
    holding. Adding rows underneath it is a good way to find out what happens
    when two writers disagree about what a conversation contains.
    """
    from backend.core import instance_lock

    lock_path = instance_lock._lock_path()
    if not lock_path.exists():
        return
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return
    if instance_lock._pid_is_running(pid):
        sys.exit(f"ERROR: PIP appears to be running (pid {pid}). Close it and try again.")


def seed(conn, project_id: str, *, title: str) -> dict:
    existing = conn.execute(
        "SELECT id FROM conversations WHERE title = ?", (title,)
    ).fetchone()
    if existing:
        sys.exit(
            f"ERROR: a conversation titled {title!r} is already here.\n"
            "       Refusing to write a second copy. Use --undo with the manifest from "
            "the first run if you want to redo it."
        )

    conversation_id = str(uuid.uuid4())
    # Spread across a plausible working afternoon rather than all on one
    # timestamp, so the transcript reads as a session rather than as an import.
    start = datetime.now(timezone.utc) - timedelta(hours=3)
    started = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    # The conversation row first. messages.conversation_id is a foreign key to
    # it and foreign keys are ON (schema.sql line 5, and get_connection), so
    # writing the turns first fails outright - which it did, on the first run of
    # these tests rather than on somebody's real database.
    #
    # observed_at is set here deliberately. NULL means the Observer never ran,
    # and startup recovery would pick this up and spend an LLM pass extracting
    # memory from a transcript that was written rather than spoken.
    conn.execute(
        "INSERT INTO conversations (id, title, project_id, created_at, updated_at, observed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, title, project_id, started, started, started),
    )

    decision_ids: list[int] = []
    written = 0
    offset = 0

    for _, decision_index, turns in SECTIONS:
        for role, content in turns:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    conversation_id,
                    role,
                    content,
                    (start + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
            written += 1
            offset += 4

        if decision_index is not None:
            text, reasoning, alternatives = DECISIONS[decision_index]
            # Through insert_decision, not a raw INSERT: it is the chokepoint
            # that suppresses duplicates (ADR-022b) and keeps the FTS index in
            # step, and a seeder bypassing it would be the one write path in the
            # codebase that does.
            decision_ids.append(
                decision_log.insert_decision(
                    conn,
                    text=text,
                    reasoning=reasoning,
                    alternatives=alternatives,
                    project_id=project_id,
                    confidence=0.9,
                )
            )

    # Now that the last turn's time is known, move updated_at and observed_at to
    # the end of the session rather than its start - a conversation whose last
    # update predates its own final message reads as corrupt.
    stamp = (start + timedelta(minutes=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "UPDATE conversations SET updated_at = ?, observed_at = ? WHERE id = ?",
        (stamp, stamp, conversation_id),
    )
    conn.commit()

    return {
        "conversation_id": conversation_id,
        "title": title,
        "project_id": project_id,
        "decision_ids": decision_ids,
        "messages": written,
        "seeded_at": stamp,
    }


def undo(conn, manifest: dict) -> dict:
    """
    Remove exactly what one run wrote, and nothing else.

    Deleting rather than retracting - see the module docstring. ADR-022 is about
    decisions you actually took and later left behind; these are rows a script
    put in, and marking them abandoned would assert a history that did not
    happen.
    """
    messages = conn.execute(
        "DELETE FROM messages WHERE conversation_id = ?", (manifest["conversation_id"],)
    ).rowcount
    conversations = conn.execute(
        "DELETE FROM conversations WHERE id = ?", (manifest["conversation_id"],)
    ).rowcount

    decisions = 0
    for decision_id in manifest.get("decision_ids", []):
        decisions += conn.execute(
            "DELETE FROM decision_log WHERE id = ?", (decision_id,)
        ).rowcount
    conn.commit()
    return {"messages": messages, "conversations": conversations, "decisions": decisions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a five-part worked example.")
    parser.add_argument("--project", default="PIP", help="project to file it against")
    parser.add_argument("--title", default=TITLE, help="conversation title")
    parser.add_argument("--undo", default=None, help="manifest from a previous run")
    args = parser.parse_args(argv)

    refuse_if_pip_is_running()
    conn = _db.connect()
    try:
        if args.undo:
            manifest = json.loads(pathlib.Path(args.undo).read_text(encoding="utf-8"))
            removed = undo(conn, manifest)
            print(
                f"Removed {removed['conversations']} conversation, "
                f"{removed['messages']} messages, {removed['decisions']} decisions."
            )
            return 0

        project_id = find_project(conn, args.project)
        result = seed(conn, project_id, title=args.title)
    finally:
        conn.close()

    manifest_path = profiles.data_dir() / f"demo_seed_{result['seeded_at'].replace(':', '')}.json"
    manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print()
    print(f"Wrote {result['messages']} messages across {len(SECTIONS)} sections")
    print(f"  conversation: {result['title']}")
    print(f"  project:      {args.project}")
    print(f"  decisions:    {len(result['decision_ids'])} logged {result['decision_ids']}")
    print()
    for index, (name, decision_index, turns) in enumerate(SECTIONS, start=1):
        marks = " (logs a decision)" if decision_index is not None else ""
        print(f"  {index}. {name} - {len(turns)} turns{marks}")
    print()
    print(f"Manifest: {manifest_path}")
    print("Undo with:")
    print(f"  .venv\\Scripts\\python.exe scripts\\seed_demo_conversation.py --undo \"{manifest_path}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
