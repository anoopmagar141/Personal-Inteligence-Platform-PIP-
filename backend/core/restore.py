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
import os
import secrets
import shutil
from pathlib import Path
from typing import Any

from backend.core import backup_mark
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


def _same_file(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def pending_restore_for(db_path: str | Path) -> dict[str, Any] | None:
    """
    The staged restore, only if it is staged for *db_path*'s profile.

    There is ONE pending-restore.json for the installation, because the swap at
    the next start is one operation. What a profile may see of it, cancel or
    replace is a different question, and the routes used to answer it as if the
    marker were the signed-in profile's own (FREEZE_LIST D-19): one profile was
    shown another's staged restore with its file name, and could cancel it
    without the other ever being told.
    """
    staged = pending_restore()
    if staged and _same_file(staged.get("target_db", ""), db_path):
        return staged
    return None


def _another_profiles_restore_is_waiting(db_path: str | Path) -> bool:
    """A marker for somebody else whose staged files are still there. A marker
    whose files have gone is stale - drain_pending_restore clears it at the next
    start - and must not block a restore for the length of the session."""
    staged = pending_restore()
    if not staged or _same_file(staged.get("target_db", ""), db_path):
        return False
    return Path(staged.get("db", "")).exists() and Path(staged.get("salt", "")).exists()


def _discard_staged_files(staged: dict[str, Any]) -> None:
    for key in ("db", "salt"):
        try:
            Path(staged.get(key, "")).unlink(missing_ok=True)
        except OSError:
            pass


def stage_restore(
    backup_path: str | Path,
    backup_password: str,
    new_password: str,
    *,
    db_path: str | Path,
    salt_path: str | Path,
    documents_dir: str | Path | None = None,
    chroma_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Convert *backup_path* into a live database under *new_password*, and record
    that it should replace *db_path* at the next start.

    *documents_dir* and *chroma_dir* are the profile's own folders. They are
    recorded so the swap can move them aside with the database (D-20, see
    _install); left out, the swap touches only the database and its salt, which
    is all a caller that predates them ever asked for.

    Everything irreversible about a restore is in the swap, and the swap is not
    done here. What this leaves behind is two temporary files and a marker; if
    the user never restarts, or deletes the marker, the installation is exactly
    as it was.

    A refusal leaves nothing behind at all, and says why in a sentence
    (FREEZE_LIST D-11). Two things used to break that. A driver error out of a
    damaged backup - "SQL logic error" - was not a RestoreError, so the route
    answered 500 with the driver's own words, to the one person whose backup was
    damaged in a copy and who most needs a plain answer. And a failure AFTER the
    temporary database had been written (a damaged page, a mismatch in the row
    counts) raised with "Nothing was replaced" while the temporary files, a full
    re-encrypted copy of the person's data, stayed in their profile folder.
    """
    import sqlcipher3

    source = Path(backup_path)
    work = Path(db_path).parent
    # One marker serves the installation, so a second restore cannot be staged
    # over somebody else's: it used to be accepted, and the other profile's was
    # then never installed - its old password still opened it and the one it had
    # chosen did not - with its staged files left in its folder (D-19).
    if _another_profiles_restore_is_waiting(db_path):
        raise RestoreError(
            "Another profile has a restore waiting for the next start. Restart PIP "
            "so that one is applied, or sign in as that profile and cancel it, then "
            "try again. Nothing was written."
        )
    before = set(work.glob("restore-*.tmp.*")) if work.exists() else set()
    try:
        return _stage_restore(
            source, backup_password, new_password, db_path, salt_path, documents_dir, chroma_dir
        )
    except Exception as exc:
        # Whatever went wrong, what this call wrote goes with it. Only the
        # files this call made: a staging that is already pending has its own.
        for leftover in (set(work.glob("restore-*.tmp.*")) - before) if work.exists() else ():
            try:
                leftover.unlink()
            except OSError:
                pass
        if isinstance(exc, sqlcipher3.Error) and backup_mark.is_leftover_journal_error(exc):
            raise RestoreError(f"{source.name} could not be read. {backup_mark.LEFTOVER_JOURNAL_SENTENCE}")
        if isinstance(exc, sqlcipher3.Error):
            logger.warning(f"{source.name} could not be read all the way through: {exc}")
            raise RestoreError(
                f"{source.name} could not be read all the way through. It looks damaged - "
                "a copy that was cut short or altered will do this. Try another copy of the "
                "backup. Nothing was written."
            )
        raise


def _stage_restore(
    source: Path,
    backup_password: str,
    new_password: str,
    db_path: str | Path,
    salt_path: str | Path,
    documents_dir: str | Path | None = None,
    chroma_dir: str | Path | None = None,
) -> dict[str, Any]:
    import sqlcipher3

    db_path = Path(db_path)
    salt_path = Path(salt_path)

    if source.is_dir():
        raise RestoreError(
            f"{source.name} is a folder, not a backup file. Choose the .pipbak file itself."
        )
    if not source.exists():
        raise RestoreError(f"There is no file at {source}.")
    if not backup_password:
        raise RestoreError("Enter the backup password.")
    if not new_password or len(new_password) < 8:
        raise RestoreError("The new password must be at least 8 characters.")
    # restore_backup.py has always refused this and stage_restore did not, so
    # the two ways of restoring disagreed about what a valid pair is. The reason
    # is the same here: one secret for both means losing either loses both.
    if new_password == backup_password:
        raise RestoreError(
            "The new password has to be different from the backup password, or "
            "losing either one loses both."
        )

    backup = backup_mark.open_read_only(source, sqlcipher3.connect)
    try:
        backup.execute(f"PRAGMA key = {_sql_quote(backup_password)}")
        try:
            # SQLCipher defers the real key check to the first page access, so
            # PRAGMA key alone never fails. This read is what turns a wrong
            # password into a clear answer here rather than a confusing one
            # several steps later.
            backup.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception as exc:
            if backup_mark.is_leftover_journal_error(exc):
                raise RestoreError(f"{source.name} could not be read. {backup_mark.LEFTOVER_JOURNAL_SENTENCE}")
            raise RestoreError(
                f"{source.name} did not open with that password. Nothing was written."
            )

        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RestoreError(f"The backup is damaged: integrity_check said {integrity!r}.")

        # Everything above is true of a file with nothing in it - SQLCipher
        # opens a zero-length file as an empty database under any key - and
        # everything below compares the copy with the backup itself. Something
        # outside the file's own contents has to say it is a whole export
        # (FREEZE_LIST D-18).
        try:
            backup_mark.check(backup)
        except backup_mark.IncompleteBackup as exc:
            raise RestoreError(str(exc))

        names = backup_mark.data_tables(backup_mark.table_names(backup))
        comparable = [n for n in names if not n.endswith(_FTS_SHADOW_SUFFIXES)]
        expected = {n: backup.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in comparable}

        # Written beside the destination rather than in a temp directory: the
        # swap at the next start is a rename, and a rename across volumes is a
        # copy that can fail halfway.
        work = db_path.parent
        work.mkdir(parents=True, exist_ok=True)
        # Unique per staging, not per second. They were named by the second, and
        # a second staging inside the same second therefore reused the first's
        # temporary database - encrypted under the FIRST salt - and failed
        # opening it under its own new key with "file is not a database". Found
        # by the test for D-19's replace-the-earlier-staging rule, and invisible
        # to the migration harness only because it sleeps over a second between
        # stagings, which a person always does.
        stamp = f"{now_utc().replace(':', '').replace('-', '')}-{secrets.token_hex(3)}"
        tmp_db = work / f"restore-{stamp}.tmp.db"
        tmp_salt = work / f"restore-{stamp}.tmp.salt"

        salt = db_key_module.create_salt(tmp_salt)
        new_key = db_key_module.derive_key(new_password, salt)

        backup.execute(
            f"ATTACH DATABASE {_sql_quote(str(tmp_db))} AS restored KEY {_hex_key_pragma(new_key)}"
        )
        backup.execute("SELECT sqlcipher_export('restored')")
        # The mark describes the file, not the profile; left in, the next
        # export would copy a stale 'complete' into its own backup.
        backup.execute(f"DROP TABLE IF EXISTS restored.{backup_mark.MARK_TABLE}")
        backup.commit()
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
        "target_documents": str(documents_dir) if documents_dir else None,
        "target_chroma": str(chroma_dir) if chroma_dir else None,
        "source": str(source),
        "rows": sum(expected.values()),
        "tables": len(expected),
        "staged_at": now_utc(),
    }
    # This profile's own earlier staging is replaced, not added to: its files
    # were left behind and the app's cancel removed only the newest (D-19).
    earlier = pending_restore_for(db_path)
    if earlier:
        _discard_staged_files(earlier)

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

    # The database goes aside with its sidecars, under the kept copy's name.
    # SQLite pairs a -wal or -journal with a database by name alone: left
    # behind, a crash's uncheckpointed pages are replayed onto the restored
    # file, which then no longer opens with the new password, or opens carrying
    # pages written under the old key (FREEZE_LIST §7.16, D-01); renamed any
    # other way, the kept copy silently loses them. Each is checked on its own,
    # because a sidecar can outlive the database it belonged to.
    kept_db = target_db.with_name(f"{target_db.name}.superseded-{stamp}")
    aside = [(target_db, kept_db, "database")]
    aside += [
        (Path(f"{target_db}{suffix}"), Path(f"{kept_db}{suffix}"), f"{suffix} file")
        for suffix in profiles.SQLITE_SIDECAR_SUFFIXES
    ]
    aside.append((target_salt, target_salt.with_name(f"{target_salt.name}.superseded-{stamp}"), "salt"))
    # The profile's documents and vector index go aside with its database
    # (FREEZE_LIST D-20). They belong to the database being replaced: the index
    # is keyed to its old key, so nothing in it can be addressed under the new
    # one, and the documents folder is where the write-back after the swap
    # puts the BACKUP's files. Left in place, a same-named file of the old
    # profile's was found there at the first sign-in and the restored record was
    # pointed at it instead - wrong content indexed, and the backup's own copy
    # overwritten in the restored database - against a dialog promising that
    # everything, documents included, is replaced. Kept, never deleted, under
    # the same stamp and in the same undo list as the database.
    for key, label in (("target_documents", "documents folder"), ("target_chroma", "vector index")):
        folder = staged.get(key)
        if folder:
            folder = Path(folder)
            aside.append((folder, folder.with_name(f"{folder.name}.superseded-{stamp}"), label))

    undo: list[tuple[Path, Path]] = []
    try:
        for existing, kept, label in aside:
            if existing.exists():
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


def cancel_pending_restore_for(db_path: str | Path) -> bool:
    """
    Discard a staged restore if it would replace *db_path*, and nothing else.
    Returns whether it did.

    For profiles.delete(). A restore staged for a profile that is then deleted
    was installed into its place at the next start anyway - a deleted Default
    listed again, a named profile's folder given a database nobody is
    registered for - and its staged copy is a whole backup of that profile's
    data, left on disk by a delete (FREEZE_LIST §7.17, D-14). A restore staged
    for another profile stays staged.
    """
    staged = pending_restore()
    if not staged:
        return False
    same = os.path.normcase(os.path.abspath(staged.get("target_db", ""))) == os.path.normcase(
        os.path.abspath(db_path)
    )
    return cancel_pending_restore() if same else False
