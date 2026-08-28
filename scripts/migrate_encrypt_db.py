"""
One-time migration: plaintext data/pip.db -> SQLCipher-encrypted, in place.

Why this exists
---------------
ADR-026 specifies SQLCipher for all structured data, and
profile_store.get_connection() has always supported it - but nothing on
either real startup path (scripts/run_dev.ps1, scripts/launch_pip.ps1) ever
set PIP_DB_KEY, so every real launch silently took the unencrypted sqlite3
fallback. Those launchers now generate and export a key, which means an
EXISTING plaintext pip.db would be handed to SQLCipher on the next start and
fail with "file is not a database" on the first query. This script carries
the existing data across so that fix lands without either breaking the app
or throwing away the profile/decision log/conversation history.

Why sqlcipher_export() rather than a dump-and-replay
----------------------------------------------------
Two things in schema.sql defeat a naive copy:
  - three `confidence REAL GENERATED ALWAYS AS (...) STORED` columns
    (skill_memory, preference_memory, interaction_style). A generated column
    cannot be INSERTed into, so `INSERT INTO t SELECT * FROM t` fails.
  - decision_fts is an FTS5 virtual table with five shadow tables
    (_data/_idx/_content/_docsize/_config). Copying shadow tables as if they
    were ordinary tables produces a corrupt index.
sqlcipher_export() operates at the schema/SQL layer and handles both - the
"empirically verified to survive generated columns and WAL data" claim in
ADR-027.

Safety posture
--------------
Nothing is destroyed until the encrypted copy has been verified: the export
goes to a temp file, that file is opened fresh with the key and checked
(integrity_check, per-table row counts vs source, and a real FTS5 query to
prove the index survived), and only then are the files swapped. The original
plaintext DB is kept as a .plaintext-backup sidecar.

That backup is itself plaintext - the very thing this migration exists to
remove. It is kept by default because losing a final-year project's decision
log to a failed migration is worse than a short-lived extra copy, but it is
NOT the end state: re-run with --remove-plaintext-backup (or delete it by
hand) once you've confirmed the app starts and your data is intact. Note
that deleting it does not scrub the bytes from the underlying disk.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\migrate_encrypt_db.py
    .venv\\Scripts\\python.exe scripts\\migrate_encrypt_db.py --remove-plaintext-backup

Idempotent: if pip.db is already encrypted, it reports that and exits 0.

The vector index is rebuilt too
-------------------------------
PIP_DB_KEY protects more than pip.db. backend/memory/vector_store.py encrypts
chunk text and file paths with a Fernet key derived from it, and addresses
chunks by HMAC(PIP_DB_KEY, file_path). Everything ingested before this
migration was written in passthrough mode - plain text, plain `file_path`, no
`file_path_enc` - so the moment a key exists, query() looks for a field that
is not there, skips every chunk it finds, and RAG returns nothing on every
query with no error anywhere. The documents keep listing in the sidebar
throughout, which is what makes it hard to notice.

So step 6 re-embeds every active document under the new key, from the SQLite
`documents` registry. It runs after the swap is verified and is never fatal:
the index is derived data, and a failure costs a re-upload rather than a
profile.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import sqlcipher3
except ImportError:
    print(
        "ERROR: the sqlcipher3 package is not installed in this interpreter.\n"
        "       Run this with the project venv:  .venv\\Scripts\\python.exe "
        "scripts\\migrate_encrypt_db.py",
        file=sys.stderr,
    )
    raise SystemExit(2)


ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "pip.db"
KEY_PATH = DATA_DIR / "db_key.txt"

# Newly required: this script talked to sqlcipher3 directly and imported
# nothing from the project until rebuild_vector_index() had to reach
# backend.memory. Without it the script works when launched from the project
# root and dies with ModuleNotFoundError from anywhere else - which is exactly
# how a one-shot migration script gets run.
sys.path.insert(0, str(ROOT))

# The plaintext SQLite header. An encrypted SQLCipher file starts with random
# ciphertext instead, which is exactly how "already migrated" is detected.
SQLITE_MAGIC = b"SQLite format 3\x00"

# FTS5 shadow tables are an implementation detail of decision_fts. They are
# compared via a real MATCH query against the parent table instead of by raw
# row count, since their internal representation is not required to be
# byte-identical across an export.
_FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_content", "_docsize", "_config")


def _sql_quote(value: str) -> str:
    """Single-quoted SQL string literal. ATTACH/PRAGMA won't take bind params."""
    return "'" + value.replace("'", "''") + "'"


def _key_pragma(db_key: str) -> str:
    # Same form profile_store.get_connection() uses: raw-hex key, not a
    # passphrase to be KDF-stretched.
    return f"\"x'{db_key}'\""


def load_or_create_key() -> tuple[str, bool]:
    """
    Returns (key, created). Reads data/db_key.txt - the same file the two
    launchers read - so running this before or after a first launch converges
    on one key either way. PIP_DB_KEY in the environment wins if set, to match
    what a currently-running shell would hand the backend.
    """
    env_key = os.environ.get("PIP_DB_KEY")
    if env_key:
        key = env_key.strip()
        if not re.fullmatch(r"[0-9a-fA-F]+", key):
            raise SystemExit("ERROR: PIP_DB_KEY is set but is not hex-encoded.")
        return key, False

    if KEY_PATH.exists():
        key = KEY_PATH.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-fA-F]+", key):
            raise SystemExit(f"ERROR: {KEY_PATH} does not contain a hex key.")
        return key, False

    key = secrets.token_hex(32)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KEY_PATH.write_text(key, encoding="utf-8")
    try:
        os.chmod(KEY_PATH, 0o600)
    except OSError:
        pass  # best-effort; little effect on Windows ACLs, same as auth.py
    return key, True


def is_plaintext(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC


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
    counts = {}
    for name in names:
        counts[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    return counts


def checkpoint_wal(conn) -> None:
    """
    Fold any WAL-resident pages back into the main DB before exporting. The
    export reads through the SQL layer so it would see committed WAL content
    anyway; this mainly keeps the -wal/-shm sidecars from being left behind
    pointing at a file that's about to be replaced.
    """
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        print(f"  note: WAL checkpoint skipped ({e})")


def verify(encrypted_path: Path, db_key: str, expected: dict[str, int]) -> None:
    """Opens the freshly written encrypted DB and proves it is intact."""
    conn = sqlcipher3.connect(str(encrypted_path))
    try:
        conn.execute(f"PRAGMA key = {_key_pragma(db_key)}")

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"ERROR: integrity_check on the encrypted copy returned: {integrity}")

        actual = row_counts(conn, list(expected))
        mismatched = {t: (expected[t], actual.get(t)) for t in expected if expected[t] != actual.get(t)}
        if mismatched:
            detail = ", ".join(f"{t}: {before} -> {after}" for t, (before, after) in mismatched.items())
            raise SystemExit(f"ERROR: row counts differ after export ({detail}). Nothing was replaced.")

        # The shadow tables were excluded from the count comparison, so prove
        # the FTS index actually works rather than merely existing.
        if "decision_fts" in expected:
            conn.execute("SELECT COUNT(*) FROM decision_fts WHERE decision_fts MATCH 'a OR e'").fetchone()
    finally:
        conn.close()


def rebuild_vector_index(db_key: str) -> None:
    """
    Re-indexes ChromaDB under the key the database was just encrypted with.

    Without this the migration silently empties RAG, for the same reason a
    password change did (see scripts/set_db_password.py): PIP_DB_KEY protects
    more than pip.db. vector_store encrypts chunk text and file paths with a
    Fernet key derived from it and addresses chunks by
    HMAC(PIP_DB_KEY, file_path).

    The direction here is plaintext -> encrypted, so the existing chunks were
    written in passthrough mode, with a plain `file_path` in their metadata and
    no `file_path_enc` at all. The moment PIP_DB_KEY is set, query() builds a
    Fernet and looks for `file_path_enc` on every hit - a KeyError it catches
    and skips. So every chunk is skipped, every query returns nothing, no error
    reaches the user, and the documents keep showing in the sidebar the whole
    time.

    Never fatal. The swap above is already committed and verified, and a vector
    index is derived data - SQLite's `documents` table is the registry of what
    should be indexed and the files are still in data/documents. A failure here
    costs a re-upload, not a profile.
    """
    from backend.memory import profile_store

    conn = profile_store.get_connection(str(DB_PATH), db_key)
    try:
        active = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'active'").fetchone()[0]
        if not active:
            # Counted before the import on purpose: vector_store pulls in
            # chromadb and sentence-transformers, seconds of import time that a
            # database with nothing ingested should not pay.
            print("  vector index: nothing ingested, nothing to rebuild")
            return

        print(f"  Re-indexing {active} document(s) under the new key ...")
        print("  (re-embedding on CPU - this is the slow part)")
        from backend.memory import vector_store

        result = vector_store.rebuild_under_key(conn, db_key)
        print(f"  vector index: {len(result['rebuilt'])} document(s) re-indexed")
        for failure in result["failed"]:
            print(f"    COULD NOT RE-INDEX {failure['file_path']}: {failure['reason']}")
        if result["failed"]:
            print("    Those are no longer searchable - re-upload them from the app.")
    except Exception as e:
        print(f"  WARNING: could not rebuild the vector index: {e}")
        print("  The database itself is fine. RAG will return nothing until the")
        print("  documents are re-uploaded from the app.")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--remove-plaintext-backup",
        action="store_true",
        help="Delete the .plaintext-backup sidecar left by a previous run (or by this one) "
             "once the encrypted DB verifies. Does not securely scrub the underlying disk blocks.",
    )
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"No database at {DB_PATH} - nothing to migrate. The next launch will "
              f"create a fresh encrypted one.")
        return 0

    # Clean up / honor an existing backup first, so --remove-plaintext-backup
    # is useful on its own after an earlier successful run.
    existing_backups = sorted(DATA_DIR.glob("pip.db.plaintext-backup*"))

    if not is_plaintext(DB_PATH):
        print(f"{DB_PATH} is already encrypted - nothing to migrate.")
        if existing_backups and args.remove_plaintext_backup:
            for b in existing_backups:
                b.unlink()
                print(f"  removed plaintext backup: {b}")
        elif existing_backups:
            print("  NOTE: plaintext backup(s) still present - these are readable without the key:")
            for b in existing_backups:
                print(f"    {b}")
            print("  Re-run with --remove-plaintext-backup once you've confirmed the app works.")
        return 0

    db_key, created = load_or_create_key()
    print(f"Key: {KEY_PATH}{' (generated now)' if created else ' (existing)'}")
    print(f"Migrating {DB_PATH} -> SQLCipher-encrypted ...")

    tmp_path = DATA_DIR / "pip.db.encrypted-tmp"
    if tmp_path.exists():
        tmp_path.unlink()

    # Opened WITHOUT a key: sqlcipher3 reads a plaintext file exactly as
    # stock sqlite3 does when no PRAGMA key is issued.
    src = sqlcipher3.connect(str(DB_PATH))
    try:
        checkpoint_wal(src)

        all_tables = table_names(src)
        compared = comparable_tables(all_tables)
        expected = row_counts(src, compared)
        print(f"  {len(all_tables)} tables, {sum(expected.values())} rows across {len(compared)} compared tables")

        src.execute(
            f"ATTACH DATABASE {_sql_quote(str(tmp_path))} AS encrypted KEY {_key_pragma(db_key)}"
        )
        src.execute("SELECT sqlcipher_export('encrypted')")
        src.execute("DETACH DATABASE encrypted")
    finally:
        src.close()

    print("  export complete, verifying ...")
    verify(tmp_path, db_key, expected)
    print("  verified: integrity ok, row counts match, FTS index queryable")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = DATA_DIR / f"pip.db.plaintext-backup-{stamp}"
    DB_PATH.rename(backup_path)
    tmp_path.rename(DB_PATH)

    # The old sidecars belong to the now-renamed plaintext file.
    for suffix in ("-wal", "-shm"):
        stale = DATA_DIR / f"pip.db{suffix}"
        if stale.exists():
            stale.unlink()

    print(f"\nDone. {DB_PATH} is now encrypted.")

    # After the swap, deliberately: the key that protects the database now also
    # protects the vector index, and every existing chunk was written before
    # that key existed. See rebuild_vector_index() - skipping this leaves RAG
    # silently returning nothing on every query, forever.
    rebuild_vector_index(db_key)

    if args.remove_plaintext_backup:
        backup_path.unlink()
        print(f"Removed plaintext backup: {backup_path}")
        print("(Deleting a file does not scrub its blocks from the disk.)")
    else:
        print(f"\n  !! {backup_path}")
        print("     is STILL PLAINTEXT and readable without the key.")
        print("     Start the app, confirm your decisions and conversations are intact, then:")
        print("       .venv\\Scripts\\python.exe scripts\\migrate_encrypt_db.py --remove-plaintext-backup")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
