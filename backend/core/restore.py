"""
Restoring a .pipbak from inside the running application.

WHY THIS WAS SAID TO BE IMPOSSIBLE, AND WHAT CHANGED
----------------------------------------------------
frontend/flutter/lib/screens/backup_view.dart said there could be no restore
button: a restore replaces the database file the running backend has open, and
scripts/restore_backup.py refuses while PIP holds the lock. That reasoning was
correct about the SWAP and wrong about the whole operation, because a restore
is two separable things:

  1. Turning a backup into a live database. Needs the backup password and the
     new live password, and produces a new file beside the old one. Touches
     nothing that is open.
  2. Putting that file where the database lives. Needs no passwords at all,
     and cannot be done while the file is held.

Step 1 happens here, now, while the application is running and holding both
passwords in memory. Step 2 is recorded and carried out at the next start,
before anything opens a database - the same mechanism profiles.py already uses
to finish a deletion the process could not complete.

WHY THE SPLIT IS NOT A CONVENIENCE
----------------------------------
It is what keeps Part 10.1 intact. Deferring the WHOLE restore would mean
writing two passwords to disk for the next launch to read, which is the one
thing this application refuses to do with a password. Deferring only the
rename means the marker names two files and nothing else; anybody who reads it
learns which files are about to be moved, which they could see by looking at
the directory anyway.

WHAT IS PROVEN BEFORE ANYTHING IS RECORDED
------------------------------------------
The backup opens under its password, its integrity_check passes, and the newly
written database opens under the new key and has the same row counts. Only
then is the marker written. A staged restore is therefore already known to be
installable; the next launch is doing a rename, not a gamble.

scripts/restore_backup.py still exists and still does the whole job in one
pass. It is the path for a machine with no app window - a fresh install, or one
whose database is gone - which is exactly when a button inside the app is not
reachable.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from backend.core import db_key as db_key_module
from backend.core import profiles
from backend.core.types import now_utc

logger = logging.getLogger(__name__)

PENDING_RESTORE_NAME = "pending-restore.json"

# FTS5 keeps shadow tables whose row counts are an implementation detail rather
# than the user's data; comparing them would fail a restore for a reason that
# has nothing to do with whether anything was preserved.
_FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_content", "_docsize", "_config")


class RestoreError(Exception):
    """Something about the backup or the passwords is wrong. Nothing written."""


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _hex_key_pragma(key: str) -> str:
    return f"\"x'{key}'\""


def pending_restore_path() -> Path:
    return profiles.data_dir() / PENDING_RESTORE_NAME


def pending_restore() -> dict[str, Any] | None:
    """The staged restore, or None. Never raises."""
    path = pending_restore_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"{PENDING_RESTORE_NAME} could not be read ({e}) - ignoring it.")
        return None


def stage_restore(
    backup_path: str | Path,
    backup_password: str,
    new_password: str,
    *,
    db_path: str | Path,
    salt_path: str | Path,
) -> dict[str, Any]:
    """
    Convert *backup_path* into a live database under *new_password*, and record
    that it should replace *db_path* at the next start.

    Everything irreversible about a restore is in the swap, and the swap is not
    done here. What this leaves behind is two temporary files and a marker; if
    the user never restarts, or deletes the marker, the installation is exactly
    as it was.
    """
    import sqlcipher3

    source = Path(backup_path)
    db_path = Path(db_path)
    salt_path = Path(salt_path)

    if not source.exists():
        raise RestoreError(f"There is no file at {source}.")
    if not new_password or len(new_password) < 8:
        raise RestoreError("The new password must be at least 8 characters.")

    backup = sqlcipher3.connect(str(source))
    try:
        backup.execute(f"PRAGMA key = {_sql_quote(backup_password)}")
        try:
            # SQLCipher defers the real key check to the first page access, so
            # PRAGMA key alone never fails. This read is what turns a wrong
            # password into a clear answer here rather than a confusing one
            # several steps later.
            backup.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception:
            raise RestoreError(
                f"{source.name} did not open with that password. Nothing was written."
            )

        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RestoreError(f"The backup is damaged: integrity_check said {integrity!r}.")

        names = [
            r[0]
            for r in backup.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        comparable = [n for n in names if not n.endswith(_FTS_SHADOW_SUFFIXES)]
        expected = {n: backup.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in comparable}

        # Written beside the destination rather than in a temp directory: the
        # swap at the next start is a rename, and a rename across volumes is a
        # copy that can fail halfway.
        work = db_path.parent
        work.mkdir(parents=True, exist_ok=True)
        stamp = now_utc().replace(":", "").replace("-", "")
        tmp_db = work / f"restore-{stamp}.tmp.db"
        tmp_salt = work / f"restore-{stamp}.tmp.salt"

        salt = db_key_module.create_salt(tmp_salt)
        new_key = db_key_module.derive_key(new_password, salt)

        backup.execute(
            f"ATTACH DATABASE {_sql_quote(str(tmp_db))} AS restored KEY {_hex_key_pragma(new_key)}"
        )
        backup.execute("SELECT sqlcipher_export('restored')")
        backup.execute("DETACH DATABASE restored")
    finally:
        backup.close()

    # Proven before anything is recorded - the entire point of the temp file.
    check = sqlcipher3.connect(str(tmp_db))
    try:
        check.execute(f"PRAGMA key = {_hex_key_pragma(new_key)}")
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RestoreError(f"The restored database failed integrity_check: {integrity!r}.")
        actual = {n: check.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in expected}
    finally:
        check.close()

    mismatched = {t: (expected[t], actual.get(t)) for t in expected if expected[t] != actual.get(t)}
    if mismatched:
        detail = ", ".join(f"{t}: {a} -> {b}" for t, (a, b) in mismatched.items())
        raise RestoreError(f"Rows did not survive the copy ({detail}). Nothing was replaced.")

    payload = {
        "db": str(tmp_db),
        "salt": str(tmp_salt),
        "target_db": str(db_path),
        "target_salt": str(salt_path),
        "source": str(source),
        "rows": sum(expected.values()),
        "tables": len(expected),
        "staged_at": now_utc(),
    }
    path = pending_restore_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)

    logger.info(
        f"Restore staged from {source.name}: {payload['rows']} rows across "
        f"{payload['tables']} tables, waiting for the next start."
    )
    return payload


def _install(staged: dict[str, Any]) -> str | None:
    """
    Move the verified pair into place, putting back what it moved if the OS
    refuses one of the renames.

    The rollback is the point. Windows will not rename a file another process
    holds open, and a restore runs precisely when things are not normal. Without
    it the first refusal leaves the installation half-swapped - the old database
    moved aside, the new one not yet in place - which is worse than either
    doing nothing or finishing.

    Returns None on success, or the failure message once everything it had
    already moved has been moved back.
    """
    tmp_db = Path(staged["db"])
    tmp_salt = Path(staged["salt"])
    target_db = Path(staged["target_db"])
    target_salt = Path(staged["target_salt"])
    stamp = now_utc().replace(":", "").replace("-", "")

    undo: list[tuple[Path, Path]] = []
    try:
        for existing, label in ((target_db, "database"), (target_salt, "salt")):
            if existing.exists():
                kept = existing.with_name(f"{existing.name}.superseded-{stamp}")
                shutil.move(str(existing), str(kept))
                undo.append((kept, existing))
                logger.info(f"Previous {label} kept as {kept.name}")

        shutil.move(str(tmp_db), str(target_db))
        undo.append((target_db, tmp_db))
        shutil.move(str(tmp_salt), str(target_salt))
    except OSError as e:
        # Reversed, so the newly installed database goes back to its temporary
        # name before the superseded one is moved back over the space it left.
        for source, destination in reversed(undo):
            try:
                shutil.move(str(source), str(destination))
            except OSError:
                pass
        return str(e)
    return None


def drain_pending_restore() -> dict[str, Any] | None:
    """
    Carry out a staged restore. Called at startup, before anything opens a
    database - which is the whole reason the swap was deferred.

    A marker whose temporary files have gone is cleared rather than retried:
    something removed them, and there is nothing left to install. A swap that
    fails leaves the marker in place, so it is attempted again next launch
    instead of being silently forgotten.
    """
    staged = pending_restore()
    if not staged:
        return None

    tmp_db = Path(staged.get("db", ""))
    tmp_salt = Path(staged.get("salt", ""))
    if not tmp_db.exists() or not tmp_salt.exists():
        logger.warning(
            "A restore was staged but its files are gone - clearing the marker."
        )
        pending_restore_path().unlink(missing_ok=True)
        return None

    failure = _install(staged)
    if failure:
        logger.error(f"Staged restore could not be installed ({failure}) - it stays pending.")
        return None

    pending_restore_path().unlink(missing_ok=True)
    logger.info(
        f"Restore installed: {staged.get('rows')} rows from {Path(staged.get('source','')).name}. "
        f"The vector index is rebuilt on demand from the documents in the database."
    )
    return staged


def cancel_pending_restore() -> bool:
    """Discard a staged restore and its temporary files. Returns whether there
    was one."""
    staged = pending_restore()
    if not staged:
        return False
    for key in ("db", "salt"):
        try:
            Path(staged.get(key, "")).unlink(missing_ok=True)
        except OSError:
            pass
    pending_restore_path().unlink(missing_ok=True)
    logger.info("Staged restore cancelled.")
    return True
