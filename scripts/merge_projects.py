"""
Merge one project into another, moving everything filed against it.

    python scripts/merge_projects.py                        # list projects
    python scripts/merge_projects.py --from pip --into PIP
    python scripts/merge_projects.py --from pip --into PIP --dry-run

WHY THIS EXISTS
---------------
Two rows described the same project. "PIP", active, and "pip", completed - one
of them created by the user through the UI and the other by a seed script that
had no way to know the first existed. `active_projects.name` is UNIQUE, so
nothing stopped it: the two strings differ by case, and that is enough for
SQLite.

The cost is not cosmetic. project_id is the join key for three tables, so the
decisions, documents and conversations belonging to one project were split
across two ids that nothing relates. Stage 3 looks decisions up by the ACTIVE
project (ADR-022b scopes even duplicate-detection by project_id), so half the
log was invisible from whichever side the user happened to be working in - and
invisible in a way that looks like an empty log rather than a filtered one.

WHAT MERGING ACTUALLY MEANS HERE
--------------------------------
Repoint, then retract. Every row in decision_log, documents and conversations
that names the losing project is updated to name the surviving one, and the
losing project is set to status='deleted'.

Not deleted from the table, and the schema says why in its own comment:

    'deleted' is a retraction, not an erasure ... the row survives so that a
    decision or a conversation still pointing at this project does not dangle.

After a merge nothing points at it, so a DELETE would in fact be safe here -
and it is still the wrong call. ADR-022's posture is that this project's memory
tables record what happened rather than the tidiest version of it, and "these
were once two projects" is exactly the kind of thing somebody reads the log six
months later to find out. list_projects() already excludes 'deleted', so the
row stops appearing in the UI either way; the difference is only whether the
history survives, and there is no reason to spend it.

WHAT IT WILL NOT DO FOR YOU
---------------------------
Deduplicate decisions. Merging can put two identical decision_texts under one
project - both active, which insert_decision() would have refused had they
arrived that way (ADR-022b). They are reported, not resolved, because
collapsing them means choosing which id survives and every reference to the
other is a reference this script cannot see the meaning of. Retract the loser
from the Decisions screen, where the reason gets recorded.
"""

import _venv

_venv.require("sqlcipher3")

import _db

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.memory import profile_store  # noqa: E402

# Every table whose project_id is a foreign key into active_projects. Kept as a
# list rather than three hand-written UPDATEs so that adding a fourth such table
# to schema.sql and forgetting it here is one omission instead of one per
# statement - and so the plan printed before the confirmation is generated from
# the same list that does the work, rather than describing it separately and
# drifting.
REFERENCING_TABLES = ("decision_log", "documents", "conversations")


def refuse_if_pip_is_running() -> None:
    """
    A merge rewrites the join key of rows a running session is holding.

    The stale UI is the harmless half. The real problem is the session-end
    Observer: it writes decisions against the project the session started under,
    and if that project was retracted mid-session the write either lands on a
    'deleted' row or fails the foreign key outright. Neither is a thing to
    discover afterwards.

    The pid is checked rather than the file's existence, reusing instance_lock's
    own platform handling - this project leaves stale locks around, and
    refusing on one would block a merge for no reason.
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
        sys.exit(
            f"ERROR: PIP appears to be running (pid {pid} holds {lock_path}).\n"
            "       Close it first, then run this again. The merge changes which\n"
            "       project a live session's decisions would be filed against."
        )


def reference_counts(conn, project_id: str) -> dict[str, int]:
    return {
        table: conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        for table in REFERENCING_TABLES
    }


def all_projects(conn) -> list[dict]:
    """
    Every project including retracted ones, which list_projects() hides.

    A merge has to be able to name a row the UI has stopped showing: undoing a
    merge by hand, or merging into something retracted by mistake, both need the
    id to be visible somewhere.
    """
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM active_projects "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, last_active DESC"
        )
    ]


def resolve(conn, token: str) -> dict:
    """
    A project id, or a name, or a name in the wrong case.

    Names are what the user has in front of them; the ids are UUIDs nobody
    reads. Case-insensitive matching is last and only when it is unambiguous,
    because "PIP" and "pip" being different rows is the entire situation this
    script exists for - resolving them to each other would be the one mistake
    that cannot be undone by running it again.
    """
    projects = all_projects(conn)

    for project in projects:
        if project["project_id"] == token:
            return project
    for project in projects:
        if project["name"] == token:
            return project

    folded = [p for p in projects if p["name"].casefold() == token.casefold()]
    if len(folded) == 1:
        return folded[0]
    if len(folded) > 1:
        sys.exit(
            f"ERROR: {token!r} matches {len(folded)} projects, differing only in case:\n"
            + "\n".join(f"       {p['project_id']}  {p['name']}" for p in folded)
            + "\n       Name them by project_id instead."
        )

    sys.exit(f"ERROR: no project matching {token!r}. Run with no arguments to list them.")


def collisions(conn, source_id: str, target_id: str) -> list[tuple[str, int, int]]:
    """
    Decision texts that would end up active twice under the surviving project.

    insert_decision() refuses these on write (ADR-022b) and a merge can create
    them anyway, because the rule is scoped per project and this changes which
    project rows are in. Normalised the way find_active_duplicate() normalises -
    casefolded with internal whitespace collapsed - so this reports what that
    function would have called a duplicate rather than a stricter or looser set.
    """
    def normalise(text: str) -> str:
        return " ".join(text.split()).casefold()

    def active(project_id: str) -> dict[str, int]:
        return {
            normalise(row["decision_text"]): row["id"]
            for row in conn.execute(
                "SELECT id, decision_text FROM decision_log "
                "WHERE project_id = ? AND state = 'active'",
                (project_id,),
            )
        }

    moving, staying = active(source_id), active(target_id)
    return [
        (text, staying[text], moving[text]) for text in sorted(set(moving) & set(staying))
    ]


def describe(project: dict, counts: dict[str, int]) -> str:
    total = sum(counts.values())
    detail = ", ".join(f"{n} {table}" for table, n in counts.items() if n)
    return (
        f"  {project['name']}  [{project['status']}]\n"
        f"    {project['project_id']}\n"
        f"    last active {project['last_active']}\n"
        f"    {total} row(s) filed against it" + (f": {detail}" if detail else "")
    )


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() == "yes"
    except EOFError:
        return False


def list_projects_and_exit(conn) -> int:
    projects = all_projects(conn)
    if not projects:
        print("No projects.")
        return 0

    print(f"{len(projects)} project(s):\n")
    for project in projects:
        print(describe(project, reference_counts(conn, project["project_id"])))
        print()

    print("To merge:")
    print("  python scripts/merge_projects.py --from <losing> --into <surviving>")
    return 0


def merge(conn, source: dict, target: dict, *, assume_yes: bool, dry_run: bool) -> int:
    source_id, target_id = source["project_id"], target["project_id"]

    if source_id == target_id:
        sys.exit("ERROR: --from and --into name the same project.")

    moving = reference_counts(conn, source_id)
    staying = reference_counts(conn, target_id)

    print("MOVING FROM (will be retracted, status='deleted'):")
    print(describe(source, moving))
    print()
    print("MERGING INTO (survives):")
    print(describe(target, staying))
    print()

    if not sum(moving.values()):
        print("  Nothing is filed against the losing project - this only retracts it.")
        print()

    clashes = collisions(conn, source_id, target_id)
    if clashes:
        print(f"  NOTE: {len(clashes)} decision(s) will end up active twice under "
              f"{target['name']}:")
        for text, kept_id, moved_id in clashes:
            print(f"    #{kept_id} and #{moved_id}: {text[:60]}")
        print("  Not resolved here - retract one from the Decisions screen, where the")
        print("  reason is recorded. Merging leaves both readable either way.")
        print()

    if dry_run:
        print("--dry-run: nothing was written.")
        return 0

    print("  Take a backup first if you have not: python scripts/export_backup.py")
    print()
    if not assume_yes and not _confirm('  Type "yes" to merge: '):
        print("Nothing was written.")
        return 1

    # One transaction. A merge that repointed decisions and then failed before
    # retracting the project would leave two projects where one has silently
    # been emptied - the confusing state, not the safe one.
    conn.execute("BEGIN")
    try:
        for table in REFERENCING_TABLES:
            conn.execute(
                f"UPDATE {table} SET project_id = ? WHERE project_id = ?",
                (target_id, source_id),
            )
        # The surviving project inherits the later of the two timestamps: it now
        # holds work that happened at the losing project's last_active, so
        # keeping the earlier one would misdate the merged whole.
        conn.execute(
            "UPDATE active_projects SET last_active = ? WHERE project_id = ?",
            (max(source["last_active"], target["last_active"]), target_id),
        )
        conn.execute(
            "UPDATE active_projects SET status = 'deleted' WHERE project_id = ?",
            (source_id,),
        )
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.commit()

    remaining = reference_counts(conn, source_id)
    if sum(remaining.values()):
        sys.exit(f"ERROR: rows still point at the retracted project: {remaining}")

    merged = reference_counts(conn, target_id)
    print()
    print(f"Merged. {target['name']} now holds "
          + ", ".join(f"{n} {table}" for table, n in merged.items()) + ".")
    print(f"{source['name']} is retracted - its row survives so nothing dangles, and")
    print("list_projects() excludes it, so it is gone from the Projects screen.")
    print("Restart PIP if it was open, so it re-reads the projects.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge one PIP project into another.")
    parser.add_argument("--from", dest="source", default=None,
                        help="the project to merge away (id or name)")
    parser.add_argument("--into", dest="target", default=None,
                        help="the project that survives (id or name)")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would move and write nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation")
    args = parser.parse_args(argv)

    if bool(args.source) != bool(args.target):
        sys.exit("ERROR: --from and --into are given together, or neither.")

    if not args.dry_run and args.source:
        refuse_if_pip_is_running()

    conn = _db.connect()
    try:
        profile_store.initialize_schema(conn)

        if not args.source:
            return list_projects_and_exit(conn)

        return merge(
            conn,
            resolve(conn, args.source),
            resolve(conn, args.target),
            assume_yes=args.yes,
            dry_run=args.dry_run,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
