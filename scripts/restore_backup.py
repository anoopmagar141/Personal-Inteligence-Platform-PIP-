"""
Rebuild the live database from a .pipbak backup (the other half of Part 10.2).

    python scripts/restore_backup.py [--from PATH] [--out PATH]

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
"""

from __future__ import annotations

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

import argparse
import getpass
import hmac
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


def _fail(message: str, *cleanup: pathlib.Path) -> int:
    for path in cleanup:
        if path and path.exists():
            path.unlink()
    print(f"ERROR: {message}", file=sys.stderr)
    print("Nothing was replaced.", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the live database from a .pipbak backup.")
    parser.add_argument("--from", dest="source", default=None,
                        help="backup to restore (default: the newest in data/)")
    parser.add_argument("--out", default=str(DB_PATH), help="where the restored database goes")
    args = parser.parse_args()

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

    for existing, label in ((out_path, "database"), (db_key_module.salt_path(), "salt")):
        if existing.exists():
            kept = existing.with_name(f"{existing.name}.superseded-{stamp}")
            shutil.move(str(existing), str(kept))
            print(f"  previous {label} kept as {kept.name}")

    shutil.move(str(tmp_db), str(out_path))
    shutil.move(str(tmp_salt), str(db_key_module.salt_path()))

    print()
    print(f"Restored {out_path}. Launch PIP and enter the NEW password.")
    print("The superseded files are still in data/ - delete them once you have")
    print("logged in and are satisfied nothing is missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
