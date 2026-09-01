"""
Tests for scripts/restore_backup.py.

The property that matters is a full round trip: a live database exported by
export_backup.py must come back through this script as a working live database
under a NEW password, with every row intact and the old files still on disk.

Written because export_backup.py's own docstring makes the argument and then
stops one step short of it - "An unverified backup is worse than none: it is
the same absence of a recovery path, plus the belief that one exists." A
verified backup with no restore is the same sentence one level up. These tests
are what turn "the file contains the data" into "the data comes back".
"""

import importlib.util
import pathlib
import sys

import pytest
import sqlcipher3

from backend.core import db_key as db_key_module
from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_LIVE_PASSWORD = "a-brand-new-live-password"


def _load(name: str):
    """scripts/ is not a package - same by-path load test_export_backup.py uses."""
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def export_script():
    return _load("export_backup")


@pytest.fixture
def restore_script():
    return _load("restore_backup")


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(
        conn, name="Anup", language_preference="English", skills=["Python"]
    )
    decision_log.insert_decision(conn, text="Use SQLCipher end to end")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def backup(export_script, monkeypatch, live_db, tmp_path):
    """A real .pipbak, produced by the script that writes them."""
    out = tmp_path / "backup.pipbak"
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export_script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    monkeypatch.setattr(
        export_script.sys, "argv",
        ["export_backup.py", "--db-path", str(live_db), "--out", str(out)],
    )
    export_script.main()
    assert out.exists()
    return out


def _answers(monkeypatch, script, *responses):
    """getpass returns each response in turn, so a run can be driven end to end."""
    queue = list(responses)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": queue.pop(0))


def _restore(restore_script, monkeypatch, backup, out, *, new_password=NEW_LIVE_PASSWORD,
             backup_password=BACKUP_PASSWORD):
    _answers(monkeypatch, restore_script, backup_password, new_password, new_password)
    monkeypatch.setattr(
        restore_script.sys, "argv",
        ["restore_backup.py", "--from", str(backup), "--out", str(out)],
    )
    return restore_script.main()


def _rows(path, key_pragma_value, *, is_password: bool):
    conn = sqlcipher3.connect(str(path))
    quoted = ("'" + key_pragma_value + "'") if is_password else '''"x'{}'"'''.format(key_pragma_value)
    conn.execute(f"PRAGMA key = {quoted}")
    try:
        return {
            "name": conn.execute("SELECT name FROM identity WHERE id = 1").fetchone()[0],
            "decisions": conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0],
        }
    finally:
        conn.close()


def test_a_backup_comes_back_as_a_working_database_under_the_new_password(
    restore_script, monkeypatch, backup, tmp_path
):
    """The whole point: the data survives the loss of the live password."""
    out = tmp_path / "restored.db"

    assert _restore(restore_script, monkeypatch, backup, out) == 0

    new_key = db_key_module.derive_key_from_stored_salt(NEW_LIVE_PASSWORD)
    restored = _rows(out, new_key, is_password=False)
    assert restored["name"] == "Anup"
    assert restored["decisions"] == 1


def test_the_restored_database_refuses_the_backup_password(
    restore_script, monkeypatch, backup, tmp_path
):
    """
    Two secrets, still two. A restore that re-used the backup password would
    collapse them into one and give up exactly what the backup exists for.
    """
    out = tmp_path / "restored.db"
    _restore(restore_script, monkeypatch, backup, out)

    with pytest.raises(sqlcipher3.DatabaseError):
        _rows(out, BACKUP_PASSWORD, is_password=True)


def test_a_new_password_matching_the_backup_password_is_refused(
    restore_script, monkeypatch, backup, tmp_path
):
    out = tmp_path / "restored.db"

    with pytest.raises(SystemExit) as exit_info:
        _restore(restore_script, monkeypatch, backup, out, new_password=BACKUP_PASSWORD)

    assert "backup password" in str(exit_info.value)
    assert not out.exists(), "nothing should have been written"


def test_a_wrong_backup_password_writes_nothing(restore_script, monkeypatch, backup, tmp_path):
    out = tmp_path / "restored.db"

    with pytest.raises(SystemExit) as exit_info:
        _restore(restore_script, monkeypatch, backup, out, backup_password="not-it")

    assert "did not open" in str(exit_info.value)
    assert not out.exists()


def test_an_existing_database_is_kept_rather_than_overwritten(
    restore_script, monkeypatch, backup, tmp_path
):
    """
    The restore replaces a database whose password is, by assumption, lost -
    but "useless to us today" is not the same as "safe to delete", so the old
    pair is moved aside under a timestamp instead.
    """
    out = tmp_path / "restored.db"
    out.write_bytes(b"the old encrypted database nobody can open")

    assert _restore(restore_script, monkeypatch, backup, out) == 0

    superseded = list(tmp_path.glob("restored.db.superseded-*"))
    assert len(superseded) == 1
    assert superseded[0].read_bytes() == b"the old encrypted database nobody can open"


def test_the_old_salt_is_kept_too(restore_script, monkeypatch, backup, tmp_path):
    # conftest points PIP_SALT_PATH at tmp_path, so this is the salt the script
    # will replace - and the old one is as unrecoverable as the database it
    # went with, which is a reason to keep it, not to delete it.
    salt_path = db_key_module.salt_path()
    salt_path.write_bytes(b"0123456789abcdef")

    assert _restore(restore_script, monkeypatch, backup, tmp_path / "restored.db") == 0

    superseded = list(salt_path.parent.glob(f"{salt_path.name}.superseded-*"))
    assert len(superseded) == 1
    assert superseded[0].read_bytes() == b"0123456789abcdef"
    assert salt_path.read_bytes() != b"0123456789abcdef", "a new salt must have been written"


def test_it_refuses_to_run_while_pip_holds_the_lock(
    restore_script, monkeypatch, backup, tmp_path
):
    """
    A restore replaces the file a running backend has open. The check is on the
    pid, not the lock file's existence - this project leaves stale locks around
    routinely, and refusing on one would block a restore for no reason.
    """
    from backend.core import instance_lock

    instance_lock._lock_path().write_text(str(12345), encoding="utf-8")
    monkeypatch.setattr(instance_lock, "_pid_is_running", lambda pid: True)

    out = tmp_path / "restored.db"
    with pytest.raises(SystemExit) as exit_info:
        _restore(restore_script, monkeypatch, backup, out)

    assert "appears to be running" in str(exit_info.value)
    assert not out.exists()


def test_a_stale_lock_does_not_block_a_restore(restore_script, monkeypatch, backup, tmp_path):
    from backend.core import instance_lock

    instance_lock._lock_path().write_text(str(12345), encoding="utf-8")
    monkeypatch.setattr(instance_lock, "_pid_is_running", lambda pid: False)

    assert _restore(restore_script, monkeypatch, backup, tmp_path / "restored.db") == 0
