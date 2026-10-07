"""
The mark that says a .pipbak is a COMPLETE export, and the check that reads it
(FREEZE_LIST D-18).

WHAT WAS WRONG
--------------
A backup was only ever checked against itself. Both restores opened it under
its password, ran integrity_check, and compared the restored copy with row
counts taken from the backup. All three of those are true of a file with
nothing in it: SQLCipher opens a zero-length file as a new, empty database
under any key, so a 0-byte "backup" passed every check, was reported as
"checked and ready", and at the next backend start replaced the person's real
profile with an empty one under a password they had just typed. An export
killed part-way passes the same way, only less visibly - sqlcipher_export
commits table by table, so what is left opens with integrity_check ok and some
tables empty. A check that PIP's tables are present would not catch that one.

WHAT THIS DOES INSTEAD
----------------------
Something has to vouch for the file that is not the file's own contents. The
export writes that something in two steps, and the order is the whole point:

  begin()   before a single row is copied, a one-row table in the backup says
            state = 'writing'. A file that is killed, or that fails its own
            verification, therefore carries the sentence "I never finished".
  finish()  only after verify() has compared every table with the source, the
            row becomes state = 'complete' and records the table counts.

A mark written only at the end would fail the other way round: a file killed
half-way would have NO mark, and "no mark" has to mean "from before marks
existed", which is a file we must still accept (below). Writing the unfinished
state first is what lets the two be told apart.

Kept inside the file rather than beside it, for the reason export_backup.py's
docstring gives for being one file and not a package: a manifest that
disagrees with the database it describes is a worse problem than the one it
would solve. A table inside the backup cannot be separated from it.

BACKUPS FROM BEFORE MARKS
-------------------------
Have nothing to compare against, and are accepted on weaker evidence: the file
has tables, and one of them is PIP's own. Refusing them would strand the people
a restore is for - they are holding exactly those files. The limit is stated
rather than hidden: an older backup that was cut short and still has an
identity table cannot be told from a whole one. check() says which kind it
read, so the caller can tell the person.

THE MARK DOES NOT FOLLOW THE DATA
---------------------------------
It describes the file, not the profile. Both restores drop it from the
database they build, and exclude it from the row counts they compare; left in
the live database it would be copied into the next export, where a stale
'complete' would be sitting beside a fresh one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

MARK_TABLE = "pip_backup_mark"
FORMAT_VERSION = 1

# A table every PIP database has had since the first schema, so its presence is
# what separates "an older PIP backup" from "some other SQLCipher file".
SIGNATURE_TABLE = "identity"


class IncompleteBackup(Exception):
    """The file is not a complete PIP export. The message is shown to the person."""


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def begin(conn: Any, schema: str) -> None:
    """
    Write the unfinished mark into the attached backup, before anything else.

    *conn* is the live connection and *schema* the name the backup is attached
    under. Committed on its own so it is on disk before sqlcipher_export starts
    copying: it is no use as evidence if it is only in the transaction that was
    killed.
    """
    conn.execute(
        f"CREATE TABLE {schema}.{MARK_TABLE} ("
        "state TEXT NOT NULL, format_version INTEGER NOT NULL, "
        "exported_at TEXT, table_counts TEXT)"
    )
    conn.execute(
        f"INSERT INTO {schema}.{MARK_TABLE} (state, format_version) VALUES ('writing', ?)",
        (FORMAT_VERSION,),
    )
    conn.commit()


def finish(path: Any, password: str, counts: dict[str, int], connect: Any) -> None:
    """
    Turn the mark into 'complete', and read it back.

    Called only after the export has been verified against the source. *connect*
    is sqlcipher3.connect, passed in so this module does not import a driver the
    restore side does not otherwise need. The read-back is part of the job: a
    mark nobody has read is the same belief-without-proof the whole export was
    written to avoid.
    """
    conn = connect(str(path))
    try:
        conn.execute(f"PRAGMA key = {_sql_quote(password)}")
        conn.execute(
            f"UPDATE {MARK_TABLE} SET state = 'complete', format_version = ?, "
            "exported_at = ?, table_counts = ?",
            (
                FORMAT_VERSION,
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                json.dumps(counts, sort_keys=True),
            ),
        )
        conn.commit()
        check(conn)
    finally:
        conn.close()


def table_names(conn: Any) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def data_tables(names: list[str]) -> list[str]:
    """The tables that are the person's data: everything but the mark."""
    return [n for n in names if n != MARK_TABLE]


def check(conn: Any) -> dict[str, Any]:
    """
    Raise IncompleteBackup unless *conn*, open and keyed on a backup, holds a
    complete PIP export. Otherwise return {"marked": bool}.

    Each refusal is a sentence about what the person is holding, because it is
    shown to them as the reason nothing happened.
    """
    names = table_names(conn)
    if not names:
        raise IncompleteBackup(
            "This file has no tables in it: it is empty, not a PIP backup. "
            "Nothing was written."
        )

    if MARK_TABLE not in names:
        if SIGNATURE_TABLE not in names:
            raise IncompleteBackup(
                "This file is not a PIP backup (none of PIP's tables are in it). "
                "Nothing was written."
            )
        return {"marked": False}

    row = conn.execute(
        f"SELECT state, format_version, table_counts FROM {MARK_TABLE}"
    ).fetchone()
    if row is None or row[0] != "complete":
        raise IncompleteBackup(
            "This backup did not finish being written: its export was interrupted "
            "or failed its own check, so it may be missing data. Export again, and "
            "use a file whose export said it was verified. Nothing was written."
        )
    if (row[1] or 0) > FORMAT_VERSION:
        raise IncompleteBackup(
            "This backup was made by a newer version of PIP than this one, so it "
            "cannot be checked here. Update PIP, then try again. Nothing was written."
        )

    try:
        expected = json.loads(row[2] or "{}")
    except ValueError:
        expected = None
    if not isinstance(expected, dict) or not expected:
        raise IncompleteBackup(
            "This backup's completeness record is unreadable, so it cannot be "
            "trusted. Nothing was written."
        )

    present = set(names)
    mismatched = []
    for table, count in sorted(expected.items()):
        if table not in present:
            mismatched.append(f"{table}: {count} -> missing")
            continue
        actual = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if actual != count:
            mismatched.append(f"{table}: {count} -> {actual}")
    if mismatched:
        raise IncompleteBackup(
            "This backup has lost data since it was written (" + ", ".join(mismatched)
            + "). It was complete when exported and is not now. Nothing was written."
        )
    return {"marked": True}
