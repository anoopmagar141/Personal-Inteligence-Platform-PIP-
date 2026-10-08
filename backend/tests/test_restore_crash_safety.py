"""
A restore interrupted at any point is finished by the next start, never left half-done
(power loss between "staged" and "restart" was on the 2026-10-03 re-run's not-covered list).

The swap that installs a staged restore is several renames: the replaced database (and
its salt) go aside, the new database moves into place, then the new salt. An OSError in
the middle is rolled back in-process. A process that DIES in the middle - a power cut, a
kill, a blue screen - is not an OSError and rolls nothing back, so what matters is what
the NEXT start finds and does with it. drain_pending_restore() used to read "the
temporary database is gone" as "something removed the staged files, nothing left to
install" and cleared the marker. After a death between the database rename and the salt
rename that is the wrong reading: the new database is already in place, its salt is
still sitting in the temporary file, and clearing the marker left a profile whose
password opens nothing - the replaced salt gone aside and the new one never installed.

The crash is injected as a BaseException from shutil.move at the Nth rename, which no
`except OSError` catches and nothing in the swap rolls back, as a dead process would
not. What is asserted is the outcome a person meets: after the next start the NEW
password opens the restored profile, the replaced files are kept, and no staged file or
marker is left over.
"""

import pytest
import sqlcipher3

from backend.core import db_key, restore
from backend.memory import profile_store

BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-new-live-password"
OLD_PASSWORD = "the-old-live-password"


class Crash(BaseException):
    """The process died. Not an OSError, so nothing in the swap handles it."""


@pytest.fixture
def live(tmp_path):
    folder = tmp_path / "profile"
    folder.mkdir()
    salt = db_key.create_salt(folder / "salt.bin")
    conn = profile_store.get_connection(str(folder / "pip.db"), db_key.derive_key(OLD_PASSWORD, salt))
    profile_store.initialize_schema(conn)
    conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Old', 'English', 'UTC')")
    conn.commit()
    conn.close()
    return folder


def _backup(tmp_path):
    path = tmp_path / "backup.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO identity (id, name) VALUES (1, 'Restored')")
    conn.commit()
    conn.close()
    return path


def _stage(live, tmp_path):
    return restore.stage_restore(
        _backup(tmp_path), BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=live / "pip.db", salt_path=live / "salt.bin",
    )


def _die_at_rename(monkeypatch, n):
    real = restore.shutil.move
    seen = {"n": 0}

    def move(src, dst, *args, **kwargs):
        seen["n"] += 1
        if seen["n"] == n:
            raise Crash(f"died before rename {n}: {src} -> {dst}")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(restore.shutil, "move", move)
    return lambda: monkeypatch.setattr(restore.shutil, "move", real)


def _name_after_next_start(live):
    """What the person meets: the NEW password against whatever is installed."""
    salt = db_key.load_salt(live / "salt.bin")
    conn = profile_store.get_connection(str(live / "pip.db"), db_key.derive_key(NEW_PASSWORD, salt))
    try:
        return conn.execute("SELECT name FROM identity WHERE id = 1").fetchone()[0]
    finally:
        conn.close()


def _nothing_left_over(live):
    return not restore.pending_restore_path().exists() and not list(live.glob("restore-*.tmp.*"))


# The renames of a swap with nothing but a database and a salt to replace:
#   1 database aside   2 salt aside   3 new database in   4 new salt in
@pytest.mark.parametrize("n, where", [
    (2, "after the replaced database went aside, before its salt did"),
    (3, "after both replaced files went aside, before the new database moved in"),
    (4, "after the new database moved in, before the new salt did"),
])
def test_a_swap_that_died_is_finished_by_the_next_start(live, tmp_path, monkeypatch, n, where):
    _stage(live, tmp_path)
    undo = _die_at_rename(monkeypatch, n)
    with pytest.raises(Crash):
        restore.drain_pending_restore()
    undo()

    restore.drain_pending_restore()

    assert _name_after_next_start(live) == "Restored", f"the restore was not finished ({where})"
    assert _nothing_left_over(live)
    kept = sorted(p.name for p in live.glob("*.superseded-*"))
    assert any(k.startswith("pip.db.superseded-") for k in kept), f"the replaced database was lost ({where})"
    assert any(k.startswith("salt.bin.superseded-") for k in kept), f"the replaced salt was lost ({where})"


def test_a_swap_that_finished_but_died_before_clearing_the_marker_is_not_done_twice(live, tmp_path):
    """Everything is in place and the marker is still there. The next start must
    notice that, and not move the freshly installed database aside again."""
    staged = _stage(live, tmp_path)
    assert restore._install(staged) is None  # the whole swap, and then the process "died"
    assert restore.pending_restore_path().exists()

    restore.drain_pending_restore()

    assert _name_after_next_start(live) == "Restored"
    assert _nothing_left_over(live)
    superseded_dbs = [p for p in live.glob("pip.db.superseded-*")]
    assert len(superseded_dbs) == 1, "the restored database was moved aside by a second swap"


def test_a_normal_swap_is_unchanged(live, tmp_path):
    _stage(live, tmp_path)

    restore.drain_pending_restore()

    assert _name_after_next_start(live) == "Restored"
    assert _nothing_left_over(live)


def test_a_staged_database_removed_by_somebody_leaves_the_old_pair_working(live, tmp_path):
    """
    The case the interrupted-swap rule must not be confused with: nothing was
    swapped, somebody deleted the staged database, and the staged salt is still
    there. The old database and its own salt are intact and must stay a working
    pair - installing the staged salt beside the old database would make the
    OLD password stop opening it.
    """
    staged = _stage(live, tmp_path)
    from pathlib import Path
    Path(staged["db"]).unlink()

    restore.drain_pending_restore()

    salt = db_key.load_salt(live / "salt.bin")
    conn = profile_store.get_connection(str(live / "pip.db"), db_key.derive_key(OLD_PASSWORD, salt))
    try:
        assert conn.execute("SELECT name FROM identity WHERE id = 1").fetchone()[0] == "Old"
    finally:
        conn.close()
    assert not restore.pending_restore_path().exists()
