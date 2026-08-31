"""
Export an encrypted backup of the PIP database (Part 10.2).

    python scripts/export_backup.py [--db-path PATH] [--out PATH]

Produces a .pipbak file: a complete SQLCipher database encrypted under a
SEPARATE backup password, so a compromise of the live key does not compromise
the backups, and vice versa.

WHY THIS IS A SCRIPT AND NOT AN ENDPOINT
----------------------------------------
Part 23 lists /export as a command and Part 15's endpoint list does not contain
it, which is the right call for a reason worth writing down.

The live connection is already open with the real key. An HTTP endpoint doing
this work would let anyone who can call the API produce a full copy of the
database re-encrypted under a password of their own choosing - without ever
knowing the live key. The API is bound to 127.0.0.1 and token-gated, but the
threat model here explicitly treats other local processes as untrusted, and
data/api_token.txt is readable by anything running as this user.

That matters most after the password migration. The point of deriving the key
from a password is that the key is not on disk; an export endpoint authenticated
by a token that IS on disk would hand it straight back. Running the export as a
script, from a shell someone already controls, grants no capability they did not
already have.

WHAT sqlcipher_export() BUYS
---------------------------
One encryption technology end to end, and no plaintext intermediate state -
not on disk, not in memory. It reads through SQLite's page layer rather than
raw file bytes, so generated columns are recomputed correctly in the copy and
committed-but-not-checkpointed WAL content comes across without a checkpoint.
Both were verified empirically for this project before it was specified.

The WAL checkpoint below is therefore defence in depth rather than the
mechanism, kept because it costs nothing.
"""

import argparse
import getpass
import os
import pathlib
import sys
from datetime import datetime, timezone

try:
    import sqlcipher3
except ImportError:  # pragma: no cover - environment guard, not logic
    sys.exit(
        "ERROR: sqlcipher3 is not installed, so an encrypted database cannot be read.\n"
        "       pip install -r requirements.txt"
    )

REPO_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "pip.db"
KEY_PATH = DATA_DIR / "db_key.txt"

# FTS5 keeps shadow tables whose row counts are an implementation detail of the
# index, not user data - comparing them across an export proves nothing.
_FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_docsize", "_content", "_config")


def _sql_quote(value: str) -> str:
    """Single-quoted SQL string literal. ATTACH and PRAGMA will not take bind parameters."""
    return "'" + value.replace("'", "''") + "'"


def _hex_key_pragma(db_key: str) -> str:
    """Raw-hex form, matching profile_store.get_connection()."""
    return f"\"x'{db_key}'\""


def resolve_live_key() -> str:
    """
    The key the database is currently encrypted with.

    PIP_DB_KEY wins if set, matching what a running backend would have been
    handed. Otherwise data/db_key.txt, the file both launchers read.

    An installation migrated to the password model has salt.bin and no
    db_key.txt; that path asks for the live password and derives the key with
    the project's own KDF parameters rather than reimplementing them here.
    """
    env_key = os.environ.get("PIP_DB_KEY")
    if env_key:
        return env_key.strip()

    if KEY_PATH.exists():
        return KEY_PATH.read_text(encoding="utf-8").strip()

    sys.path.insert(0, str(REPO_ROOT))
    from backend.core import db_key as db_key_module

    if not db_key_module.salt_path().exists():
        sys.exit(
            f"ERROR: no key material found.\n"
            f"       Expected {KEY_PATH} (random-key model) or "
            f"{db_key_module.salt_path()} (password model)."
        )

    password = getpass.getpass("Live database password: ")
    if not password:
        sys.exit("ERROR: no password entered.")
    return db_key_module.derive_key_from_stored_salt(password)


def prompt_backup_password() -> str:
    """
    A SEPARATE password for the backup, entered twice.

    Separate on purpose: the whole value of this file is that it survives the
    loss or compromise of the live key. Reusing the live password would make the
    backup exactly as compromised as the thing it is meant to outlive.

    getpass, so it is never echoed, never in shell history, never in a log.
    """
    first = getpass.getpass("New password for this backup (not the live one): ")
    if not first:
        sys.exit("ERROR: an empty backup password would leave the file unencrypted in practice.")
    if first == os.environ.get("PIP_DB_KEY", object()):
        sys.exit("ERROR: that is the live key. Use a different password for the backup.")
    second = getpass.getpass("Repeat it: ")
    if first != second:
        sys.exit("ERROR: the two entries do not match. Nothing was written.")
    return first


def table_names(conn) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def comparable_tables(names: list[str]) -> list[str]:
    return [n for n in names if not n.endswith(_FTS_SHADOW_SUFFIXES)]


def row_counts(conn, names: list[str]) -> dict[str, int]:
    return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}


def verify(backup_path: pathlib.Path, password: str, expected: dict[str, int]) -> None:
    """
    Open the backup as a reader would and prove it is usable.

    An unverified backup is worse than none: it is the same absence of a
    recovery path, plus the belief that one exists. So this opens the file with
    the backup password, runs an integrity check, and compares row counts table
    by table against the source.
    """
    conn = sqlcipher3.connect(str(backup_path))
    try:
        conn.execute(f"PRAGMA key = {_sql_quote(password)}")

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            sys.exit(f"ERROR: integrity_check on the backup returned: {integrity}")

        actual = row_counts(conn, list(expected))
        mismatched = {t: (expected[t], actual.get(t)) for t in expected if expected[t] != actual.get(t)}
        if mismatched:
            sys.exit(f"ERROR: row counts differ between source and backup: {mismatched}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an encrypted PIP backup.")
    parser.add_argument("--db-path", default=str(DB_PATH), help="database to back up")
    parser.add_argument("--out", default=None, help="destination .pipbak (default: timestamped, in data/)")
    args = parser.parse_args()

    db_path = pathlib.Path(args.db_path)
    if not db_path.exists():
        sys.exit(f"ERROR: no database at {db_path}")

    if args.out:
        out_path = pathlib.Path(args.out)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = DATA_DIR / f"pip-{stamp}.pipbak"

    # Never silently overwrite: the thing being overwritten is somebody's only
    # copy of everything, and a backup command that destroys a backup is the
    # exact failure this whole feature exists to prevent.
    if out_path.exists():
        sys.exit(f"ERROR: {out_path} already exists. Move it aside or pass a different --out.")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    live_key = resolve_live_key()
    backup_password = prompt_backup_password()

    src = sqlcipher3.connect(str(db_path))
    try:
        src.execute(f"PRAGMA key = {_hex_key_pragma(live_key)}")
        try:
            names = table_names(src)
        except Exception:
            sys.exit(
                "ERROR: could not read the database with that key. If this installation has "
                "been migrated to a password, the password entered was wrong."
            )

        compared = comparable_tables(names)
        expected = row_counts(src, compared)
        print(f"  {len(names)} tables, {sum(expected.values())} rows across {len(compared)} compared tables")

        try:
            src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            print(f"  note: WAL checkpoint skipped ({e}) - the export reads through the SQL layer anyway")

        src.execute(
            f"ATTACH DATABASE {_sql_quote(str(out_path))} AS backup KEY {_sql_quote(backup_password)}"
        )
        try:
            src.execute("SELECT sqlcipher_export('backup')")
        finally:
            src.execute("DETACH DATABASE backup")
    finally:
        src.close()

    print("  export complete, verifying ...")
    verify(out_path, backup_password, expected)

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  verified: integrity ok, row counts match")
    print(f"\nBackup written: {out_path}  ({size_mb:.1f} MB)")
    print("Keep it somewhere other than this machine, and remember the password -")
    print("there is no recovery path for a .pipbak whose password is lost.")


if __name__ == "__main__":
    main()
