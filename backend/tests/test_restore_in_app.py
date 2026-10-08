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
import shutil

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


OLD_PASSWORD = "the-old-live-password"
SIDECARS = ("-wal", "-shm", "-journal")


def crash_leaving_a_wal(db_path, key):
    """
    Leave *db_path* the way an unclean exit does: its newest pages in
    pip.db-wal, not yet in pip.db.

    machine_one's trick from test_phase9_roundtrip.py, plus the step Windows
    adds. Closing the last connection checkpoints the WAL into pip.db and
    deletes it, and nothing may rename a file SQLite holds open - so the pair
    is copied out while the connection is still open, and copied back once it
    has closed.
    """
    conn = profile_store.get_connection(str(db_path), key)
    conn.execute("PRAGMA wal_autocheckpoint = 0")
    # A schema change, because it always rewrites page 1 - the page every open
    # reads first. An UPDATE alone lands in the WAL too, but only on pages the
    # restored database may never ask for; measured that way, the restore
    # survived it and this test would pass for the wrong reason.
    conn.execute("CREATE TABLE written_just_before_the_crash (note TEXT)")
    conn.execute("INSERT INTO written_just_before_the_crash VALUES ('never checkpointed')")
    conn.commit()

    wal = db_path.with_name(db_path.name + "-wal")
    assert wal.exists() and wal.stat().st_size > 0, "nothing is in the WAL to leave behind"

    frozen = db_path.parent / "frozen-at-the-crash"
    frozen.mkdir()
    for path in (db_path, wal):
        shutil.copyfile(path, frozen / path.name)
    conn.close()
    for path in (db_path, wal):
        shutil.copyfile(frozen / path.name, path)
    shutil.rmtree(frozen)


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
        # The profile's own folders, for the swap to move aside (D-20): paths,
        # or null for a caller that did not name them.
        "target_documents", "target_chroma",
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


def _stage_over_a_crashed_profile(live, rows=2):
    backup = make_backup(live, rows=rows)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    # Staged while running, and then the process ended without a checkpoint -
    # the usual way the next start is reached (FREEZE_LIST §7.16, D-09).
    old = db_key.derive_key(OLD_PASSWORD, db_key.load_salt(live / "salt.bin"))
    crash_leaving_a_wal(live / "pip.db", old)


def test_a_wal_left_by_the_replaced_database_does_not_reach_the_restored_one(live):
    """
    D-01. pip.db-wal is named after pip.db rather than kept inside it, so
    moving pip.db aside left the old database's uncheckpointed pages beside the
    new one. SQLite replays a -wal it finds at open, the new key cannot read
    pages written under the old one, and a restore that reported success left a
    profile no password opened.
    """
    _stage_over_a_crashed_profile(live, rows=3)

    assert restore.drain_pending_restore() is not None

    # Checked before anything opens the file: any open, even a failed one,
    # replays a stale WAL and deletes it, which would hide the evidence.
    assert not [s for s in SIDECARS if (live / f"pip.db{s}").exists()], (
        "the replaced database's sidecar is still beside the restored one"
    )
    key = db_key.derive_key(NEW_PASSWORD, db_key.load_salt(live / "salt.bin"))
    conn = profile_store.get_connection(str(live / "pip.db"), key)
    try:
        # Rows, not verify_key: that reads only sqlite_master, which a database
        # with foreign pages folded into it can still answer.
        assert conn.execute("SELECT COUNT(*) FROM identity").fetchone()[0] == 3
    finally:
        conn.close()


def test_the_replaced_database_keeps_its_wal(live):
    """
    ADR-024's posture, one file further: the pages a crash left in the -wal
    belong to the database being replaced, so they go aside with it - under the
    kept copy's own name, the only one SQLite looks for when it is opened.
    """
    _stage_over_a_crashed_profile(live)

    restore.drain_pending_restore()

    kept = next(
        p for p in live.glob("pip.db.superseded-*") if not p.name.endswith(SIDECARS)
    )
    assert (live / f"{kept.name}-wal").exists(), "the replaced database's WAL was not kept with it"
    old_salt = next(live.glob("salt.bin.superseded-*")).read_bytes()
    conn = profile_store.get_connection(str(kept), db_key.derive_key(OLD_PASSWORD, old_salt))
    try:
        note = conn.execute("SELECT note FROM written_just_before_the_crash").fetchone()[0]
    finally:
        conn.close()
    assert note == "never checkpointed"


def test_every_kind_of_sidecar_goes_aside_with_the_database(live):
    """
    -wal is the one a crash usually leaves, but a hot -journal is the same
    hazard: the restored file starts in rollback mode until its first open, and
    a journal beside it is rolled back onto it. -shm is only an index, kept
    with the rest so the set stays whole.
    """
    backup = make_backup(live)
    restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )
    for suffix in SIDECARS:
        (live / f"pip.db{suffix}").write_bytes(f"left behind{suffix}".encode())

    assert restore.drain_pending_restore() is not None

    kept = next(
        p for p in live.glob("pip.db.superseded-*") if not p.name.endswith(SIDECARS)
    )
    for suffix in SIDECARS:
        assert not (live / f"pip.db{suffix}").exists(), f"pip.db{suffix} stayed beside the restored database"
        assert (live / f"{kept.name}{suffix}").read_bytes() == f"left behind{suffix}".encode()


def test_a_wal_whose_database_is_gone_does_not_reach_the_restored_one(live):
    """
    SQLite pairs a WAL with a database by name alone, so a pip.db-wal with no
    pip.db beside it is still replayed onto whatever arrives under that name.
    The sidecars are moved aside on their own account, not only when the
    database they belonged to is there to move.
    """
    _stage_over_a_crashed_profile(live, rows=3)
    (live / "pip.db").unlink()

    assert restore.drain_pending_restore() is not None

    assert not (live / "pip.db-wal").exists(), "the orphaned WAL stayed in place"
    key = db_key.derive_key(NEW_PASSWORD, db_key.load_salt(live / "salt.bin"))
    conn = profile_store.get_connection(str(live / "pip.db"), key)
    try:
        assert conn.execute("SELECT COUNT(*) FROM identity").fetchone()[0] == 3
    finally:
        conn.close()


def test_a_refused_move_leaves_the_old_database_with_its_wal(live, monkeypatch):
    """
    The rollback has to put the sidecars back too. Undo pip.db without its WAL
    and the old database is whole on disk but missing its newest pages, which
    is the half-swapped state the rollback exists to prevent.
    """
    _stage_over_a_crashed_profile(live)
    real_move = restore.shutil.move

    def refuse_the_salt(src, dst):
        if str(src).endswith("salt.bin"):
            raise OSError(32, "The process cannot access the file")
        return real_move(src, dst)

    monkeypatch.setattr(restore.shutil, "move", refuse_the_salt)

    assert restore.drain_pending_restore() is None
    assert restore.pending_restore() is not None, "a failed swap forgot the restore"

    assert (live / "pip.db-wal").exists(), "the WAL was not put back beside its database"
    assert not list(live.glob("pip.db.superseded-*")), "a moved-aside file was not put back"
    old = db_key.derive_key(OLD_PASSWORD, db_key.load_salt(live / "salt.bin"))
    conn = profile_store.get_connection(str(live / "pip.db"), old)
    try:
        note = conn.execute("SELECT note FROM written_just_before_the_crash").fetchone()[0]
    finally:
        conn.close()
    assert note == "never checkpointed"


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
