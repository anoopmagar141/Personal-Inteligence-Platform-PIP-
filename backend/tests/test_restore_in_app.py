"""
Restoring a .pipbak from inside the running application.

backup_view.dart said there could be no restore button, and was right about the
part it described: the swap cannot happen while the database is open. What it
missed is that a restore is two things, and only one of them is blocked. So
what is tested here is the split, and the properties that make it safe:

  Nothing is recorded until the restore is known to work. The backup opens
  under its password, its integrity passes, and the newly written database
  opens under the NEW key with the same row counts. A staged restore is
  therefore already proven installable - the next launch performs a rename,
  not a gamble.

  No password reaches the disk. Deferring the whole restore would mean writing
  two passwords for the next launch to read, which is the one thing this
  application refuses to do with a password. The marker names two files and
  nothing else.

  Staging replaces nothing. Everything irreversible is in the swap, and the
  swap is not done at stage time - so a user who never restarts, or who
  cancels, has an installation exactly as it was.
"""

import json

import pytest
import sqlcipher3

from backend.core import db_key, profiles, restore
from backend.memory import profile_store

BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-new-live-password"


@pytest.fixture
def live(tmp_path, monkeypatch):
    """A profile with a database, and a .pipbak beside it holding two rows."""
    monkeypatch.setenv("PIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))

    salt = db_key.create_salt(tmp_path / "salt.bin")
    key = db_key.derive_key("the-old-live-password", salt)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), key)
    profile_store.initialize_schema(conn)
    conn.execute(
        "INSERT INTO identity (id, name, language_preference, timezone) "
        "VALUES (1, 'Live', 'English', 'UTC')"
    )
    conn.commit()
    conn.close()
    return tmp_path


def make_backup(tmp_path, name="backup.pipbak", password=BACKUP_PASSWORD, rows=2):
    """A .pipbak is a SQLCipher database keyed by a passphrase."""
    path = tmp_path / name
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{password}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(rows):
        conn.execute("INSERT INTO identity (id, name) VALUES (?, ?)", (i + 1, f"restored-{i}"))
    conn.commit()
    conn.close()
    return path


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def test_a_backup_is_converted_and_recorded(live):
    backup = make_backup(live)

    staged = restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )

    assert staged["rows"] == 2
    assert restore.pending_restore() is not None
    from pathlib import Path
    assert Path(staged["db"]).exists() and Path(staged["salt"]).exists()


def test_staging_replaces_nothing(live):
    """Everything irreversible is in the swap, and the swap is not done here."""
    backup = make_backup(live)
    before = (live / "pip.db").read_bytes()

    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )

    assert (live / "pip.db").read_bytes() == before, "the live database was touched"


def test_no_password_is_written_to_the_marker(live):
    """
    The reason the conversion happens now rather than at the next start.
    Deferring the whole restore would mean persisting two passwords, which is
    the one thing this application refuses to do with a password.
    """
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )

    raw = restore.pending_restore_path().read_text(encoding="utf-8")
    assert BACKUP_PASSWORD not in raw
    assert NEW_PASSWORD not in raw

    # Asserted on the structure rather than by searching the text for the word
    # "password": pytest names its tmp directory after the test, so the paths
    # in this very marker contain it, and a substring check passes or fails on
    # what the test is called.
    marker = json.loads(raw)
    assert set(marker) == {
        "db", "salt", "target_db", "target_salt", "source", "rows", "tables", "staged_at",
    }
    # Every value is a path, a count or a timestamp - nothing derived from a
    # secret, so the marker cannot be used to open anything.
    assert marker["rows"] == 2 and marker["tables"] >= 1


def test_a_wrong_backup_password_is_refused_and_records_nothing(live):
    backup = make_backup(live)

    with pytest.raises(restore.RestoreError, match="did not open"):
        restore.stage_restore(
            backup, "not-the-backup-password", NEW_PASSWORD,
            db_path=live / "pip.db", salt_path=live / "salt.bin",
        )

    assert restore.pending_restore() is None


def test_a_short_new_password_is_refused(live):
    backup = make_backup(live)
    with pytest.raises(restore.RestoreError, match="at least 8"):
        restore.stage_restore(
            backup, BACKUP_PASSWORD, "short",
            db_path=live / "pip.db", salt_path=live / "salt.bin",
        )
    assert restore.pending_restore() is None


def test_a_file_that_is_not_a_backup_is_refused(live):
    junk = live / "notes.txt"
    junk.write_text("this is not a database", encoding="utf-8")

    with pytest.raises(restore.RestoreError):
        restore.stage_restore(
            junk, BACKUP_PASSWORD, NEW_PASSWORD,
            db_path=live / "pip.db", salt_path=live / "salt.bin",
        )
    assert restore.pending_restore() is None


def test_a_missing_file_is_refused(live):
    with pytest.raises(restore.RestoreError, match="no file"):
        restore.stage_restore(
            live / "nothing-here.pipbak", BACKUP_PASSWORD, NEW_PASSWORD,
            db_path=live / "pip.db", salt_path=live / "salt.bin",
        )


# ---------------------------------------------------------------------------
# Installing, at the next start
# ---------------------------------------------------------------------------


def test_the_swap_installs_the_restored_database(live):
    backup = make_backup(live, rows=3)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )

    installed = restore.drain_pending_restore()

    assert installed is not None
    assert restore.pending_restore() is None, "the marker outlived the install"
    # The live database is now the backup's contents, under the NEW password.
    key = db_key.derive_key(NEW_PASSWORD, db_key.load_salt(live / "salt.bin"))
    conn = profile_store.get_connection(str(live / "pip.db"), key)
    try:
        assert conn.execute("SELECT COUNT(*) FROM identity").fetchone()[0] == 3
    finally:
        conn.close()


def test_the_old_password_no_longer_opens_it(live):
    """A restore installs the backup under a NEW password; the old one belongs
    to a database that is no longer there."""
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    restore.drain_pending_restore()

    old = db_key.derive_key("the-old-live-password", db_key.load_salt(live / "salt.bin"))
    assert db_key.verify_key(str(live / "pip.db"), old) is False


def test_what_was_replaced_is_kept_not_deleted(live):
    """ADR-024's posture: replacing somebody's database is not consent to
    destroy the one that was there."""
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    restore.drain_pending_restore()

    assert list(live.glob("pip.db.superseded-*")), "the previous database was destroyed"
    assert list(live.glob("salt.bin.superseded-*")), "the previous salt was destroyed"


def test_draining_with_nothing_staged_does_nothing(live):
    assert restore.drain_pending_restore() is None


def test_a_marker_whose_files_are_gone_is_cleared(live):
    backup = make_backup(live)
    staged = restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    from pathlib import Path
    Path(staged["db"]).unlink()

    assert restore.drain_pending_restore() is None
    assert restore.pending_restore() is None, "a marker with no files stayed pending"


def test_an_unreadable_marker_does_not_stop_anything(live):
    restore.pending_restore_path().write_text("{ not json", encoding="utf-8")
    assert restore.pending_restore() is None
    assert restore.drain_pending_restore() is None


def test_cancelling_removes_the_staged_files(live):
    backup = make_backup(live)
    staged = restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    from pathlib import Path
    before = (live / "pip.db").read_bytes()

    assert restore.cancel_pending_restore() is True

    assert restore.pending_restore() is None
    assert not Path(staged["db"]).exists()
    assert not Path(staged["salt"]).exists()
    assert (live / "pip.db").read_bytes() == before


def test_cancelling_when_nothing_is_staged(live):
    assert restore.cancel_pending_restore() is False


def test_a_failed_swap_leaves_the_marker_for_the_next_launch(live, monkeypatch):
    """
    One attempt per launch, and never a silent surrender. A rename Windows
    refuses today may succeed once whatever held the file has gone.
    """
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    monkeypatch.setattr(restore, "_install", lambda staged: "[WinError 32] in use")

    assert restore.drain_pending_restore() is None
    assert restore.pending_restore() is not None, "a failed swap forgot the restore"


def test_a_failed_swap_leaves_the_live_database_intact(live, monkeypatch):
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    before = (live / "pip.db").read_bytes()
    monkeypatch.setattr(restore, "_install", lambda staged: "refused")

    restore.drain_pending_restore()

    assert (live / "pip.db").read_bytes() == before
