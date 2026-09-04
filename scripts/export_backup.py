"""
Export an encrypted backup of the PIP database (Part 10.2).

    python scripts/export_backup.py [--db-path PATH] [--out PATH]
    python scripts/export_backup.py --readable --out PATH

Produces a .pipbak file: a complete SQLCipher database encrypted under a
SEPARATE backup password, so a compromise of the live key does not compromise
the backups, and vice versa.

--readable produces something else entirely - a plaintext JSON dump, for
reading rather than restoring - and is fenced accordingly. See THE READABLE
DUMP below.

ONE FILE, NOT A PACKAGE
-----------------------
A .pipbak is a single SQLCipher database file. There is no manifest, no
directory, no sidecar metadata: everything the restore needs is either in the
file's own header (SQLCipher's salt and KDF parameters) or in its schema. A
package format would add a second thing to keep in sync with the first, and
the failure mode of that - a manifest that disagrees with the database it
describes - is a worse problem than the one it would solve.

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

WHO IS ALLOWED TO RUN THIS
--------------------------
The export is gated on the live password, and the gate is real only under
the password model (Part 10.1). Which model an installation is on is a fact
about its data directory, not a setting: salt.bin and no db_key.txt means
the key is derived from something only the owner knows, and db_key.txt means
the key is a file sitting next to the database.

Under the password model authenticate() demands that password and proves it
against the database before anything else happens, and PIP_DB_KEY in the
environment does NOT satisfy it. That exclusion is the point rather than an
inconvenience. The launcher derives the key at startup and exports it into
the backend process, so it is present in the environment of anything
descended from a running PIP - and honouring it here would mean a script
started from that environment could produce a complete copy of the profile
without anyone proving they are the owner. A password prompt that any
ambient variable can skip is not an authentication step.

Under the random-key model there is no secret the owner knows: the key IS
db_key.txt. No prompt can fix that, because anything that can read the file
can also read the database directly, and a prompt in front of it would be
theatre - the appearance of a gate on a door with no wall. So that case says
plainly what is and is not protecting the data, and points at the migration
that changes the answer.

What this gate is worth, stated exactly, because a security control described
in bigger terms than it deserves is how the next person builds something on
top of it that does not hold. It stops the export from being authorised by a
key that merely happened to be lying around in the environment - an inherited
PIP_DB_KEY, a shell left open beside a running PIP, a script someone ran from
the launcher's own console. It does not stop, and cannot stop, somebody who
can already run code with the live key in hand: that person does not need
this script, because ten lines of sqlcipher3 read the database directly. The
boundary is the operating system account. Within it, this makes taking a full
copy of the profile a deliberate act by someone who knows the password.

THE READABLE DUMP
-----------------
--readable writes every row as plaintext JSON. It exists because an encrypted
backup you cannot read is a poor answer to "what does this thing actually know
about me?", and that question deserves an answer that does not require
restoring anything.

The file it writes is the single most dangerous artefact this project can
produce: every profile field, decision, conversation and observation, in the
clear, with no password on it. So it is fenced three ways.

  It has NO default location, and refuses to write into data/. Every other
  output in this project defaults into data/, and a plaintext dump landing
  there would be swept up by the *.pipbak sibling glob's neighbours, by a
  backup of the data directory, or by any future "archive everything" step -
  each of which would silently promote a deliberate one-off into a permanent
  plaintext copy. Requiring an explicit path outside data/ makes the location
  a decision somebody made rather than one nothing made.

  It says what it is before it writes, and waits for the word "yes".

  It is created with owner-only permissions where the platform honours them.

None of this makes the file safe. It makes the file deliberate.
"""

import argparse
import base64
import getpass
import hmac
import json
import os
import pathlib
import stat
import sys
from datetime import datetime, timezone

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

import sqlcipher3

REPO_ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "pip.db"
KEY_PATH = DATA_DIR / "db_key.txt"

# FTS5 keeps shadow tables whose row counts are an implementation detail of the
# index, not user data - comparing them across an export proves nothing.
_FTS_SHADOW_SUFFIXES = ("_data", "_idx", "_docsize", "_content", "_config")


def _ensure_repo_on_path() -> None:
    """backend.core.db_key lives above this script's directory, not beside it."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))


def _sql_quote(value: str) -> str:
    """Single-quoted SQL string literal. ATTACH and PRAGMA will not take bind parameters."""
    return "'" + value.replace("'", "''") + "'"


def _hex_key_pragma(db_key: str) -> str:
    """Raw-hex form, matching profile_store.get_connection()."""
    return f"\"x'{db_key}'\""


def key_model() -> str:
    """
    Which model this installation is actually on: "password" or "random-key".

    Read from the data directory rather than from configuration, because the
    data directory is what decides. Part 10.1 is explicit that implemented is
    not the same as active, and collapsing that distinction has already caused
    one defect in this project - encryption that was specified, implemented,
    and never switched on.

    db_key.txt wins when both are present. That combination means a migration
    started and did not finish, so the database is still keyed the old way;
    demanding a password there would reject the owner for a migration that
    failed rather than for a password they got wrong.
    """
    if KEY_PATH.exists():
        return "random-key"

    _ensure_repo_on_path()
    from backend.core import db_key as db_key_module

    return "password" if db_key_module.salt_path().exists() else "unknown"


def authenticate(db_path: pathlib.Path) -> str:
    """
    Prove the person running this owns the profile, and return the live key.

    Three attempts, because a mistyped password is the overwhelmingly likely
    reason for a failure here and exiting on the first one just makes somebody
    retype the command. It is not a meaningful limit on an attacker - they can
    re-run the script - so it buys patience for the owner and nothing for
    anyone else. The real cost to a guesser is KDF_ITERATIONS, which is paid
    per attempt by design.

    Verified against the database, not against a stored hash. There is no hash
    to check: the password IS the key, so the only test of it that means
    anything is whether the database opens.
    """
    model = key_model()

    if model == "random-key":
        print("  NOTE: this installation stores its key in data/db_key.txt, so this")
        print("        export is authorised by being able to read that file and")
        print("        nothing more. A password prompt here would not change that -")
        print("        anything that can read the key can read the database.")
        print("        Run scripts/set_db_password.py to move to a password-derived")
        print("        key; after that, this command asks for the password.")
        env_key = os.environ.get("PIP_DB_KEY")
        return env_key.strip() if env_key else KEY_PATH.read_text(encoding="utf-8").strip()

    if model == "unknown":
        # No installation here: no salt, no key file. Whatever --db-path points
        # at, this machine has no record of owning it, so the only thing that
        # can authorise the export is the caller naming the key themselves.
        # Knowing the 64-character key IS possession of the secret - it is the
        # thing a password would have been derived into.
        #
        # This is not the ambient-inheritance case the password branch refuses.
        # There, PIP_DB_KEY arrives from a launcher the user did not think about
        # and stands in for a password they were never asked for. Here there is
        # no password to stand in for and nothing ambient about it.
        env_key = os.environ.get("PIP_DB_KEY")
        if env_key:
            return env_key.strip()

        _ensure_repo_on_path()
        from backend.core import db_key as db_key_module

        sys.exit(
            f"ERROR: no key material found, and PIP_DB_KEY is not set.\n"
            f"       Expected {KEY_PATH} (random-key model) or "
            f"{db_key_module.salt_path()} (password model)."
        )

    _ensure_repo_on_path()
    from backend.core import db_key as db_key_module

    if os.environ.get("PIP_DB_KEY"):
        # Said out loud rather than silently ignored, so nobody concludes the
        # variable is broken and goes looking for a way to make it work.
        print("  PIP_DB_KEY is set and is being ignored: an export has to be")
        print("  authorised by the person running it, not by the environment it")
        print("  inherited. Enter the live password.")

    for remaining in (2, 1, 0):
        password = getpass.getpass("Live database password: ")
        if not password:
            sys.exit("ERROR: no password entered.")

        live_key = db_key_module.derive_key_from_stored_salt(password)
        if db_key_module.verify_key(str(db_path), live_key):
            return live_key

        if remaining:
            print(f"  that password does not open {db_path.name} - "
                  f"{remaining} attempt{'s' if remaining > 1 else ''} left")

    sys.exit(
        "ERROR: authentication failed. Nothing was read and nothing was written.\n"
       "       A forgotten live password is unrecoverable by design (Part 10.1),\n"
       "       but an existing .pipbak still opens with its own backup password."
    )


def _is_live_secret(candidate: str, live_key: str) -> bool:
    """
    Whether `candidate` is the live secret, in either of the two forms it takes.

    The live secret wears two faces and a real check has to catch both. Under
    the random-key model it IS the 64-char hex key, which someone might paste
    straight out of db_key.txt. Under the password model the user has never seen
    that hex - they know a password, which only becomes the key after the KDF.
    So comparing the typed string directly catches the first case and nothing
    else; catching the second means loading the salt and deriving.

    That derivation costs a full PBKDF2 pass, which is deliberately slow (see
    KDF_ITERATIONS). Paid once, at a prompt the user is already sitting at.
    """
    if hmac.compare_digest(candidate.strip(), live_key):
        return True

    _ensure_repo_on_path()
    from backend.core import db_key as db_key_module

    try:
        derived = db_key_module.derive_key_from_stored_salt(candidate)
    except Exception:
        # No salt, or an unreadable one: there is no password model here for the
        # entry to collide with, so the direct comparison above was the whole test.
        return False
    return hmac.compare_digest(derived, live_key)


def prompt_backup_password(live_key: str) -> str:
    """
    The password this backup file is encrypted under, entered twice.

    It has to differ from the LIVE password, and the prompt says so, because the
    whole value of this file is that it survives the loss or compromise of the
    live key. Reusing the live password would make the backup exactly as
    compromised as the thing it is meant to outlive.

    It does NOT have to differ from your previous backups, and the wording is
    careful about that after the earlier phrasing ("New password for this
    backup") read as "invent a fresh one every run". Nothing here tracks past
    exports; one backup password, reused forever, is the intended usage. Two
    secrets total, not one per file.

    getpass, so it is never echoed, never in shell history, never in a log.
    """
    first = getpass.getpass("Password for this backup file (same one every time is fine): ")
    if not first:
        sys.exit("ERROR: an empty backup password would leave the file unencrypted in practice.")
    if _is_live_secret(first, live_key):
        sys.exit(
            "ERROR: that is the live database secret. The backup needs a different one - "
            "the point of this file is to stay safe if the live key is lost or stolen, and "
            "sharing a password with it gives up exactly that."
        )
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


def warn_about_missing_documents(conn) -> list[str]:
    """
    Say so if a document's bytes are not in the database.

    Ingestion stores them, and initialize_schema() backfills anything older,
    so the only way to reach this is a file that was moved or deleted after it
    was ingested. The registry row is still true and the chunks may still be in
    the index, so this is not an error - but the backup will carry the record
    of that document and not the document, and finding that out on the machine
    you are restoring onto is finding it out too late.
    """
    try:
        missing = [
            row[0]
            for row in conn.execute(
                "SELECT d.file_path FROM documents d "
                "LEFT JOIN document_blobs b ON b.document_id = d.id "
                "WHERE d.status = 'active' AND b.document_id IS NULL"
            )
        ]
    except Exception:
        # A database predating document_blobs. Nothing to warn about that the
        # user can act on, and refusing to back it up would be absurd.
        return []

    if missing:
        print(f"  NOTE: {len(missing)} document(s) have no stored copy - the backup will")
        print("        carry the record of them but not their content:")
        for path in missing:
            print(f"          {path}")
        print("        Put the file back where it was and open PIP once to store it.")
    return missing


def checkpoint(conn) -> None:
    """
    PRAGMA wal_checkpoint(TRUNCATE), immediately before the copy.

    Folds the -wal file back into the database proper. This project verified
    empirically that sqlcipher_export() does NOT need it - the export reads
    through SQLite's page layer, so committed-but-unckeckpointed rows come
    across regardless, and test_phase9_roundtrip.py pins that by exporting
    with this call removed and finding the row anyway.

    Kept, and kept here rather than earlier, because it costs nothing and it
    is the one line that would be load-bearing for any future backup method
    that copies file bytes instead of reading pages. A checkpoint run at the
    top of main() would still be defence in depth against a threat that no
    longer exists by the time the copy happens.

    Non-fatal: a database that will not checkpoint is still one this export
    can read, and refusing to back it up would be the wrong trade.
    """
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as e:
        print(f"  note: WAL checkpoint skipped ({e}) - the export reads through the SQL layer anyway")


def default_backup_path() -> pathlib.Path:
    """
    data/pip_backup_YYYYMMDD.pipbak, the name the spec fixes.

    Dated, not timestamped, so the file a user goes looking for a month later
    is the one they can name from memory. The cost is that a second export on
    the same day collides, and the collision is resolved by suffixing rather
    than by overwriting - a backup command whose second run destroys its first
    run's output is the exact failure this feature exists to prevent, and
    refusing outright would be a strange way to punish somebody for making an
    extra backup.

    UTC, matching every other stamp this project writes.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    candidate = DATA_DIR / f"pip_backup_{stamp}.pipbak"
    n = 2
    while candidate.exists():
        candidate = DATA_DIR / f"pip_backup_{stamp}-{n}.pipbak"
        n += 1
    return candidate


def _confirm(prompt: str) -> bool:
    """
    A typed "yes", not a y/n keypress.

    The thing being confirmed writes every private thing PIP holds to an
    unencrypted file. Making the answer a word somebody has to type is the
    difference between a decision and a reflex.
    """
    try:
        return input(prompt).strip().lower() == "yes"
    except EOFError:
        return False


def resolve_readable_out(raw: str | None) -> pathlib.Path:
    """
    Where a plaintext dump is allowed to go: somewhere the user named, outside data/.

    Both halves are load-bearing. No default, because a plaintext copy of
    everything should never be somewhere nothing chose. Not data/, because that
    directory is what every backup, sync and archive step in and around this
    project treats as "the state worth keeping" - a dump left there stops being
    a one-off the moment anything copies the directory.
    """
    if not raw:
        sys.exit(
            "ERROR: --readable has no default location, on purpose.\n"
            "       Pass --out with a path you have chosen deliberately, outside data/.\n"
            "       This file is every profile field, decision and conversation in the\n"
            "       clear, with no password on it; it should not land anywhere by default."
        )

    out_path = pathlib.Path(raw).expanduser()
    resolved = out_path.resolve()
    data_dir = DATA_DIR.resolve()
    if resolved == data_dir or data_dir in resolved.parents:
        sys.exit(
            f"ERROR: refusing to write a plaintext dump inside {data_dir}.\n"
            f"       {resolved} is in the directory that every backup and sync step\n"
            "       treats as the state worth keeping - a dump there would be copied\n"
            "       along with everything else, forever. Choose a path outside it."
        )
    if resolved.exists():
        sys.exit(f"ERROR: {resolved} already exists. Move it aside or pass a different --out.")
    return out_path


def _json_safe(value):
    """
    BLOBs are the only thing sqlite hands back that json cannot take.

    Base64 rather than a lossy repr: the point of this file is that somebody
    can read the whole of what PIP holds, and a column silently rendered as
    "<bytes>" would be a hole in exactly that promise.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__base64__": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def dump_tables(conn, names: list[str]) -> dict:
    """Every row of every real table, keyed by column name."""
    tables = {}
    for name in names:
        cursor = conn.execute(f'SELECT * FROM "{name}"')
        columns = [d[0] for d in cursor.description]
        tables[name] = [
            {column: _json_safe(value) for column, value in zip(columns, row)}
            for row in cursor.fetchall()
        ]
    return tables


def export_readable(src, db_path: pathlib.Path, out_path: pathlib.Path, names: list[str],
                    *, assume_yes: bool) -> pathlib.Path:
    """
    The plaintext branch. Warns, waits for "yes", then writes owner-only.

    FTS5 shadow tables are excluded for the same reason the row-count check
    excludes them: they are an implementation detail of the index, reconstructible
    from decision_log, and dumping them would pad the file with binary noise a
    reader has no use for.
    """
    print()
    print("  !!  PLAINTEXT EXPORT  !!")
    print()
    print("  This writes an UNENCRYPTED file containing everything PIP knows about you:")
    print("  every profile field, every decision, every stored conversation and every")
    print("  observation, readable by anyone who opens it. There is no password on it.")
    print()
    print(f"  Source:      {db_path}")
    print(f"  Destination: {out_path.resolve()}")
    print()
    print("  It is for reading, not for restoring - /restore takes a .pipbak, not this.")
    print("  Delete it when you are done with it.")
    print()

    if not assume_yes and not _confirm('  Type "yes" to write it: '):
        sys.exit("Nothing was written.")

    tables = dump_tables(src, comparable_tables(names))
    payload = {
        "format": "pip-readable-export",
        "version": 1,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": str(db_path),
        "warning": "PLAINTEXT. Contains the full contents of the PIP database, unencrypted.",
        "tables": tables,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Best effort: Windows ignores the mode bits, which is a reason to also say
    # out loud what the file is, not a reason to skip the call on POSIX.
    try:
        out_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    rows = sum(len(v) for v in tables.values())
    print(f"\nPlaintext dump written: {out_path}  ({rows:,} rows across {len(tables)} tables)")
    print("It is not encrypted. Treat it like the contents of your password manager.")
    return out_path


def main(argv: list[str] | None = None) -> pathlib.Path:
    parser = argparse.ArgumentParser(description="Export an encrypted PIP backup.")
    parser.add_argument("--db-path", default=str(DB_PATH), help="database to back up")
    parser.add_argument("--out", default=None,
                        help="destination (default: data/pip_backup_YYYYMMDD.pipbak; "
                             "required, and must be outside data/, with --readable)")
    parser.add_argument("--readable", action="store_true",
                        help="write an UNENCRYPTED JSON dump instead of a .pipbak (requires --out)")
    parser.add_argument("--yes", action="store_true",
                        help="skip the interactive confirmation --readable asks for")
    args = parser.parse_args(argv)

    db_path = pathlib.Path(args.db_path)
    if not db_path.exists():
        sys.exit(f"ERROR: no database at {db_path}")

    if args.readable:
        # Resolved before the database is opened, so a rejected path costs nothing
        # and a live-password prompt is never the thing standing between somebody
        # and being told their --out was invalid.
        out_path = resolve_readable_out(args.out)
    elif args.out:
        out_path = pathlib.Path(args.out)
        # Never silently overwrite: the thing being overwritten is somebody's only
        # copy of everything, and a backup command that destroys a backup is the
        # exact failure this whole feature exists to prevent. A default path
        # suffixes instead (see default_backup_path); an explicit one is refused,
        # because renaming what somebody typed is its own kind of surprise.
        if out_path.exists():
            sys.exit(f"ERROR: {out_path} already exists. Move it aside or pass a different --out.")
    else:
        out_path = default_backup_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Before the database is opened, before an output path is committed to, and
    # before either branch below can read a single row.
    live_key = authenticate(db_path)

    src = sqlcipher3.connect(str(db_path))
    try:
        src.execute(f"PRAGMA key = {_hex_key_pragma(live_key)}")

        # Under the password model authenticate() has already proven this key
        # opens the database. Under the random-key model nothing has, and this
        # is where a key file that has been corrupted or swapped shows up -
        # SQLCipher defers the real check to first page access, so it takes a
        # query that touches the schema, and the table list is one the export
        # needs anyway.
        try:
            names = table_names(src)
        except Exception:
            sys.exit(
                f"ERROR: could not read {db_path.name} with the key from "
                f"{KEY_PATH.name}. The key file and the database do not match."
            )

        compared = comparable_tables(names)
        expected = row_counts(src, compared)
        print(f"  {len(names)} tables, {sum(expected.values())} rows across {len(compared)} compared tables")

        warn_about_missing_documents(src)

        # The plaintext branch forks here rather than earlier, so it inherits the
        # same proof the encrypted one gets: the line just printed is evidence the
        # live key opened the database. It needs no backup password - there is no
        # encryption on what it writes, which is the entire warning.
        if args.readable:
            checkpoint(src)
            return export_readable(src, db_path, out_path, names, assume_yes=args.yes)

        # Only now is it worth the user's time to choose a backup password: the
        # line just printed is proof the live password was right. Prompting for
        # it first meant one typo up there cost three entries before anything
        # admitted the first was wrong.
        backup_password = prompt_backup_password(live_key)

        checkpoint(src)

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
    print("  verified: integrity ok, row counts match")
    print(f"\nBackup written: {out_path}  ({size_mb:.1f} MB)")
    print("Keep it somewhere other than this machine, and remember the password -")
    print("there is no recovery path for a .pipbak whose password is lost.")
    return out_path


if __name__ == "__main__":
    main()
