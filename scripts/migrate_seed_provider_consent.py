"""
scripts/migrate_seed_provider_consent.py

One-time migration: seeds the provider_consent table in an existing
(pre-Phase-3) local dev database that was initialized before
seed_provider_consent() existed in profile_store.py.

Safe to run against any DB:
  - If provider_consent already has rows -> no-op (idempotent).
  - If provider_consent is empty -> inserts the default rows from
    config/provider_consent.json.

Usage (from repo root):
    python scripts/migrate_seed_provider_consent.py [--db-path PATH]

Default DB path: data/pip.db (matches the local dev default).
"""

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure backend package is importable from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.memory.profile_store import seed_provider_consent, CONSENT_SEED_PATH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        default="data/pip.db",
        help="Path to the SQLite database file (default: data/pip.db)",
    )
    parser.add_argument(
        "--seed-path",
        default=None,
        help="Path to provider_consent.json seed file (default: config/provider_consent.json)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    seed_path = Path(args.seed_path) if args.seed_path else CONSENT_SEED_PATH

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    before = conn.execute("SELECT COUNT(*) FROM provider_consent").fetchone()[0]
    print(f"provider_consent rows before: {before}")

    if before > 0:
        print("Table already seeded - no-op. Exiting.")
        conn.close()
        return

    seed_provider_consent(conn, seed_path=seed_path)

    after = conn.execute("SELECT COUNT(*) FROM provider_consent").fetchone()[0]
    print(f"provider_consent rows after:  {after}")

    rows = conn.execute(
        "SELECT provider_id, is_cloud, user_consented, consent_scope, revoked FROM provider_consent"
    ).fetchall()
    for r in rows:
        print(f"  -> {dict(r)}")

    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
