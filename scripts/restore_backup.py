"""
Rebuild the live database from a .pipbak backup (the other half of Part 10.2).

    python scripts/restore_backup.py [--from PATH] [--out PATH] [--yes]

WHY THIS EXISTS
---------------
export_backup.py wrote backups and nothing read them. Its own docstring is the
argument for closing that: "An unverified backup is worse than none: it is the
same absence of a recovery path, plus the belief that one exists." An export
with no restore is that same shape one level up - the file verifiably holds the
data, and there is still no path from it back into a working PIP.

Found the way these things usually are. The live password was lost, which under
the password model is unrecoverable BY DESIGN (Part 10.1: "a forgotten password
means permanent profile loss"), and the only thing between that and starting
from nothing was two .pipbak files and their separate password.

WHAT THE LOST LIVE PASSWORD DOES NOT BLOCK
------------------------------------------
Anything here. A .pipbak is attached with KEY '<passphrase>', so SQLCipher runs
its own KDF over the salt in that file's own header - data/salt.bin is not
involved, and neither is the live key. That separation is exactly what
export_backup.py built the two-secret model for, and this is the case it was
built for.

This therefore MINTS A NEW LIVE PASSWORD rather than recovering the old one.
There is nothing to recover it from.

NOTHING IS REPLACED UNTIL THE REPLACEMENT IS PROVEN
---------------------------------------------------
The rebuilt database is written to a temporary file, opened with the new key,
integrity-checked, and compared table by table against the backup it came from.
Only then are the existing pip.db and salt.bin moved aside - timestamped, never
deleted - and the new pair moved into place. A failure at any earlier step
leaves the data directory exactly as it was found.

salt.bin has to be replaced: the salt is half the derivation, so a new password
needs a new salt, and data/salt.bin is where every entry point looks for it.
The old one is kept beside the old database, which is the only honest thing to
do with a file that is useless without a password nobody has. Keeping it costs
nothing, and deleting the pair would foreclose a recovery nobody has thought of
yet.

AND IT ASKS FIRST
-----------------
Moving files aside is not the same as asking. "The old database is unopenable
anyway" is an assumption about why somebody is running this, and it is wrong
for at least two real cases: restoring the wrong .pipbak onto a working
installation, and restoring a months-old backup over a database that was never
actually lost. Both are recoverable from the superseded files, and both are
much better prevented. So the last step before anything moves prints exactly
which files are about to be replaced and waits for the word "yes".

It asks late, after the rebuilt database has been verified, so the question is
about a replacement that is known to be good rather than one that might still
fail. --yes skips it, for scripted runs.

DOCUMENTS COME BACK
-------------------
They did not always. The documents table records that a file was ingested -
its path, its hash, its chunk count - and for a long time nothing anywhere
held the file, so a restore onto a second machine brought back a registry
pointing at paths that had never existed on it. Everything else arrived and
RAG arrived empty, repairable only by remembering to copy data/documents/ by
hand on the day you were already restoring from a backup.

document_blobs now carries the bytes inside the same .pipbak, and the index
rebuild below writes them into this machine's data/documents/ before
re-embedding. Under each file's own name, not the absolute path recorded on
the old machine: that path may name a drive this machine does not have, and
writing to an arbitrary absolute path out of a restored file would make a
backup into an arbitrary-write primitive.

CHROMADB IS NOT RESTORED
------------------------
It is derived, not authoritative (ADR-026), and it is not in the .pipbak at
all - the backup is one SQLCipher file and the vector index is a separate
directory of embeddings. It is rebuilt from the restored SQLite rows instead,
which is both cheaper than carrying it and more correct: chunk metadata is
keyed with an HMAC of the live key, so every chunk written under the old key
is unaddressable under the new one. Copying the old index across would restore
a directory of orphans.

Re-embedding reads each document from the path SQLite recorded. On a second
machine those files usually are not there, and that is reported rather than
hidden: the documents table, and every project, decision and profile row, are
fully restored either way. What is missing is only the ability to retrieve
passages from files that machine does not have.
"""

from __future__ import annotations

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

import argparse
import getpass
import hmac
import os
import pathlib
import shutil
import sys
from datetime import datetime, timezone

import sqlcipher3

REPO_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "pip.db"
LOCK_PATH = DATA_DIR / "pip.lock"

# The same exclusion export_backup.py applies, for the same reason: FTS5 shadow
# tables are an implementation detail of the index, so comparing their row
# counts across a copy proves nothing.
_FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_docsize", "_content", "_config")


def _ensure_repo_on_path() -> None:
    """backend.core lives above this script's directory, not beside it."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def _sql_quote(value: str) -> str:
    """Single-quoted SQL literal. ATTACH and PRAGMA will not take bind parameters."""
    return "'" + value.replace("'", "''") + "'"


def _hex_key_pragma(db_key: str) -> str:
    """Raw-hex form, matching profile_store.get_connection()."""
    return '''"x'{}'"'''.format(db_key)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def newest_backup() -> pathlib.Path:
    backups = sorted(DATA_DIR.glob("*.pipbak"))
    if not backups:
        sys.exit(f"ERROR: no .pipbak files in {DATA_DIR}")
    return backups[-1]


def refuse_if_pip_is_running() -> None:
    """
    A restore replaces the file a running backend has open.

    A STALE lock is not a reason to stop - this project has left several around
    - so the pid is checked rather than the file's existence, reusing
    instance_lock's own platform handling rather than reimplementing it here.
    """
    _ensure_repo_on_path()
    from backend.core import instance_lock

    # instance_lock._lock_path(), not a constant of our own: it is the single
    # definition of where the lock lives and it honours PIP_LOCK_PATH, so this
    # check follows the same override every other entry point does instead of
    # reading a path that only happens to match today.
    lock_path = instance_lock._lock_path()
    if not lock_path.exists():
        return
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip())
    except ValueError:
        return
    if instance_lock._pid_is_running(pid):
        sys.exit(
            f"ERROR: PIP appears to be running (pid {pid} holds {lock_path}). "
            "Close it first - a restore replaces the database it has open."
        )


def table_names(conn) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def row_counts(conn, names: list[str]) -> dict[str, int]:
    return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}


def open_backup(path: pathlib.Path, password: str):
    """
    Opens the backup and proves the password before anything else happens.

    SQLCipher defers the real key check to the first page access, so PRAGMA key
    alone never fails - the read below is what turns a wrong password into a
    clear message here instead of a confusing failure several steps later.
    """
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = {_sql_quote(password)}")
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlcipher3.DatabaseError:
        conn.close()
        sys.exit(
            f"ERROR: {path.name} did not open with that password. Nothing was "
            "written. If you have more than one backup, try --from with the other."
        )
    return conn


def prompt_new_live_password(backup_password: str) -> str:
    """
    The password the restored database will be encrypted under.

    It must differ from the backup password, for the reason export_backup.py
    refuses the mirror image of this: the value of a backup is that it survives
    the loss or compromise of the live secret, and one password for both gives
    that up. Two secrets total, as before.
    """
    first = getpass.getpass("NEW password for the restored database: ")
    if not first:
        sys.exit("ERROR: an empty password would leave the database unencrypted in practice.")
    if hmac.compare_digest(first, backup_password):
        sys.exit(
            "ERROR: that is the backup password. The restored database needs a "
            "different one, or losing either secret loses both."
        )
    second = getpass.getpass("Repeat it: ")
    if first != second:
        sys.exit("ERROR: the two entries do not match. Nothing was written.")
    return first


def _confirm(prompt: str) -> bool:
    """
    A typed "yes", not a keypress.

    Separated from getpass deliberately: everything else this script reads is a
    secret, and routing the one non-secret answer through getpass would hide
    the user's own confirmation from them as they typed it.
    """
    try:
        return input(prompt).strip().lower() == "yes"
    except EOFError:
        return False


def confirm_replacement(out_path: pathlib.Path, salt_path: pathlib.Path,
                        *, assume_yes: bool) -> bool:
    """
    Names every file about to be replaced, then waits.

    Lists only what actually exists, because a list padded with files that were
    never there reads as a bigger loss than the one being agreed to - and on a
    fresh second machine, which is the case this whole feature exists for, the
    honest answer is that nothing is being replaced at all.
    """
    existing = [p for p in (out_path, salt_path) if p.exists()]

    print()
    if not existing:
        print(f"  Nothing to replace - {out_path} does not exist yet.")
    else:
        print("  About to replace:")
        for path in existing:
            print(f"    {path}")
        print()
        print("  Each is kept alongside the new one as .superseded-<timestamp>, not deleted.")
        print("  The restored database opens with the NEW password you just chose; the")
        print("  superseded database still needs whatever password it always did.")
    print()

    if assume_yes:
        print("  --yes given, proceeding.")
        return True
    return _confirm('  Type "yes" to proceed: ')


def rebuild_vector_index(out_path: pathlib.Path, new_key: str) -> None:
    """
    Rebuild ChromaDB from the restored SQLite rows.

    The old index is moved aside first, not merged into. Chunk metadata carries
    an HMAC of the live key, so nothing written under the previous key can be
    matched - let alone deleted - under the new one; re-ingesting on top would
    leave every old chunk behind as an unreachable duplicate.

    Best effort by design. The data is already restored and verified by the time
    this runs, so a missing chromadb install, an absent embedding model or a
    documents directory that only existed on the other machine must not turn a
    successful restore into a failed one. The index is derived; it can be
    rebuilt again at any time, and the startup mismatch check will do it.
    """
    _ensure_repo_on_path()
    try:
        from backend.memory import profile_store, vector_store
    except Exception as e:
        print(f"  index rebuild skipped: {e}")
        print("  The database is restored. Launch PIP to have it rebuild the index.")
        return

    chroma_dir = pathlib.Path(vector_store.CHROMA_DB_PATH)
    if chroma_dir.exists():
        kept = chroma_dir.with_name(f"{chroma_dir.name}.superseded-{_stamp()}")
        shutil.move(str(chroma_dir), str(kept))
        print(f"  previous vector index kept as {kept.name}")

    # vector_store reads the live key from the environment, and the live key is
    # now the one just derived - the process that ran the restore has never had
    # it set, and the chunk encryption would silently fall back to plaintext.
    os.environ["PIP_DB_KEY"] = new_key

    conn = profile_store.get_connection(str(out_path), db_key=new_key)
    try:
        result = vector_store.rebuild_from_sqlite(conn)
    finally:
        conn.close()

    rebuilt, failed = result["rebuilt"], result["failed"]
    materialised = result.get("materialised", [])
    if materialised:
        print(f"  {len(materialised)} document(s) written back to data/documents/")
    print(f"  vector index rebuilt from {len(rebuilt)} document(s)")
    if failed:
        print(f"  {len(failed)} document(s) could not be re-embedded:")
        for item in failed:
            print(f"    {item['file_path']}: {item['reason']}")
        print("  Their rows in the database are intact - only the searchable text is")
        print("  missing. These were ingested before the backup carried document")
        print("  content, or their file was gone by the time it was written.")


def salt_destination(out_path: pathlib.Path, db_key_module) -> pathlib.Path:
    """
    Where the new salt goes: beside the database it belongs to.

    For a normal restore that is data/salt.bin, which is where every entry point
    looks, and this returns exactly what it always did.

    For a restore to any other --out it is NOT data/salt.bin, and the difference
    matters more than it looks. The salt is half the key derivation, so writing
    a new one into data/ while building a database somewhere else replaces the
    live installation's salt with one belonging to a different database - and
    the live database, untouched and perfectly intact, stops opening with the
    password that has always opened it.

    That is the exact shape of the accident somebody has while being careful:
    rehearsing a restore to a scratch path before trusting it, and breaking the
    thing they were protecting. The old salt is kept as .superseded-<stamp> and
    renaming it back is the repair, but a repair nobody knew they needed is not
    much of one.

    A salt is not secret - it is stored in the clear next to the database in
    every model this project has had - so putting it beside the copy costs
    nothing and makes the copy independently openable.
    """
    if out_path.resolve() == DB_PATH.resolve():
        return db_key_module.salt_path()
    return out_path.parent / "salt.bin"


def install(out_path: pathlib.Path, salt_path: pathlib.Path,
            tmp_db: pathlib.Path, tmp_salt: pathlib.Path, stamp: str) -> str | None:
    """
    Move the verified pair into place, putting back what it moved if the OS
    refuses one of the renames.

    Windows will not rename a file another process holds open, and a restore
    runs precisely when things are not normal: a backend that crashed without
    releasing its handle, an antivirus scanner mid-pass, a stray shell still
    sitting on the database. refuse_if_pip_is_running() catches the case where
    PIP itself is up, and catches nothing else.

    Without the rollback, the first refusal leaves the installation
    half-swapped - the old database moved aside, the new one not yet in place -
    which is the one outcome worse than either doing nothing or finishing. The
    rest of this script goes to some length to make sure the only two states
    are before and after; four unguarded shutil.move calls at the end would
    have quietly readmitted a third.

    Returns None on success, or the failure message once everything it had
    already moved has been moved back.
    """
    undo: list[tuple[pathlib.Path, pathlib.Path]] = []
    try:
        for existing, label in ((out_path, "database"), (salt_path, "salt")):
            if existing.exists():
                kept = existing.with_name(f"{existing.name}.superseded-{stamp}")
                shutil.move(str(existing), str(kept))
                undo.append((kept, existing))
                print(f"  previous {label} kept as {kept.name}")

        shutil.move(str(tmp_db), str(out_path))
        undo.append((out_path, tmp_db))
        shutil.move(str(tmp_salt), str(salt_path))
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


def _fail(message: str, *cleanup: pathlib.Path) -> int:
    for path in cleanup:
        if path and path.exists():
            path.unlink()
    print(f"ERROR: {message}", file=sys.stderr)
    print("Nothing was replaced.", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the live database from a .pipbak backup.")
    parser.add_argument("--from", dest="source", default=None,
                        help="backup to restore (default: the newest in data/)")
    parser.add_argument("--out", default=str(DB_PATH), help="where the restored database goes")
    parser.add_argument("--yes", action="store_true",
                        help="skip the confirmation asked before anything is replaced")
    parser.add_argument("--no-index-rebuild", action="store_true",
                        help="do not rebuild the ChromaDB vector index afterwards")
    args = parser.parse_args(argv)

    source = pathlib.Path(args.source) if args.source else newest_backup()
    if not source.exists():
        return _fail(f"no backup at {source}")
    out_path = pathlib.Path(args.out)

    refuse_if_pip_is_running()
    _ensure_repo_on_path()
    from backend.core import db_key as db_key_module

    print(f"Restoring from {source.name} ({source.stat().st_size:,} bytes)")
    backup_password = getpass.getpass("Backup password: ")
    backup = open_backup(source, backup_password)

    try:
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return _fail(f"integrity_check on the backup returned: {integrity}")

        names = table_names(backup)
        comparable = [n for n in names if not n.endswith(_FTS_SHADOW_SUFFIXES)]
        expected = row_counts(backup, comparable)
        print(f"  opened, integrity ok, {len(comparable)} tables, {sum(expected.values()):,} rows")

        new_password = prompt_new_live_password(backup_password)

        # Written beside the destination, so a failure leaves nothing
        # half-installed for the next launch to find.
        work_dir = out_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)
        stamp = _stamp()
        tmp_db = work_dir / f"restore-{stamp}.tmp.db"
        tmp_salt = work_dir / f"restore-{stamp}.tmp.salt"

        salt = db_key_module.create_salt(tmp_salt)
        new_key = db_key_module.derive_key(new_password, salt)

        backup.execute(
            f"ATTACH DATABASE {_sql_quote(str(tmp_db))} AS restored KEY {_hex_key_pragma(new_key)}"
        )
        backup.execute("SELECT sqlcipher_export('restored')")
        backup.execute("DETACH DATABASE restored")
    finally:
        backup.close()

    # Proven before anything is replaced - the entire point of the temp file.
    check = sqlcipher3.connect(str(tmp_db))
    try:
        check.execute(f"PRAGMA key = {_hex_key_pragma(new_key)}")
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return _fail(f"integrity_check on the restored database returned: {integrity}",
                         tmp_db, tmp_salt)
        actual = row_counts(check, list(expected))
        mismatched = {t: (expected[t], actual.get(t)) for t in expected if expected[t] != actual.get(t)}
        if mismatched:
            return _fail(f"row counts differ between backup and restore: {mismatched}",
                         tmp_db, tmp_salt)
    finally:
        check.close()
    print(f"  rebuilt and verified: {sum(actual.values()):,} rows match the backup")

    # Last exit. Everything above this line is reversible by deleting two temp
    # files; everything below it moves the user's current installation aside.
    salt_path = salt_destination(out_path, db_key_module)
    if not confirm_replacement(out_path, salt_path, assume_yes=args.yes):
        return _fail("cancelled at the confirmation prompt", tmp_db, tmp_salt)

    refused = install(out_path, salt_path, tmp_db, tmp_salt, stamp)
    if refused:
        return _fail(
            f"the files could not be replaced: {refused}\n"
            "       Something else on this machine is holding one of them open.\n"
            "       Close it and run this again - everything was put back.",
            tmp_db, tmp_salt,
        )

    # ChromaDB is derived and lives outside the .pipbak, so it is rebuilt rather
    # than restored - and only for the real live database. Restoring to some
    # other --out is a copy, and rebuilding the one shared index to match a copy
    # would corrupt the index the actual installation is still using.
    if args.no_index_rebuild:
        print("  index rebuild skipped (--no-index-rebuild)")
    elif out_path.resolve() != DB_PATH.resolve():
        print(f"  index rebuild skipped: {out_path} is not the live database")
    else:
        try:
            rebuild_vector_index(out_path, new_key)
        except Exception as e:
            print(f"  index rebuild failed: {e}")
            print("  The restore itself succeeded. PIP rebuilds the index on startup")
            print("  when it finds one missing, so this is not a reason to run it again.")

    print()
    print(f"Restored {out_path}. Launch PIP and enter the NEW password.")
    print("Projects, decisions, profile, every conversation and every message came")
    print("back with the database, along with the documents themselves. Transcripts")
    print("are restored as history to read, not replayed into a live session.")
    print("The superseded files are still in data/ - delete them once you have")
    print("logged in and are satisfied nothing is missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
