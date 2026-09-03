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
             backup_password=BACKUP_PASSWORD, confirm="yes"):
    _answers(monkeypatch, restore_script, backup_password, new_password, new_password)
    # The confirmation is the one answer that is not a secret, so it comes
    # through input() rather than getpass and is stubbed separately.
    monkeypatch.setattr("builtins.input", lambda prompt="": confirm)
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


# ---------------------------------------------------------------------------
# Confirm before overwrite
# ---------------------------------------------------------------------------
#
# Moving the old files aside is not the same as asking. The two cases that make
# this worth a prompt are restoring the wrong .pipbak onto a working
# installation, and restoring a stale one over a database that was never lost.
# Both are recoverable from the superseded files; both are much better avoided.


def test_declining_the_confirmation_replaces_nothing(restore_script, monkeypatch, backup, tmp_path):
    out = tmp_path / "restored.db"
    out.write_bytes(b"the database that was there all along")
    salt_path = db_key_module.salt_path()
    salt_path.write_bytes(b"the salt that went with it")

    assert _restore(restore_script, monkeypatch, backup, out, confirm="no") != 0

    assert out.read_bytes() == b"the database that was there all along"
    assert salt_path.read_bytes() == b"the salt that went with it"
    assert not list(tmp_path.glob("restored.db.superseded-*"))


def test_declining_leaves_no_temporary_files_behind(restore_script, monkeypatch, backup, tmp_path):
    """
    A cancel that littered the data directory with half-built databases would
    leave the next launch something to trip over, and the next restore a
    directory it cannot reason about.
    """
    out = tmp_path / "restored.db"

    _restore(restore_script, monkeypatch, backup, out, confirm="no")

    assert not list(tmp_path.glob("restore-*.tmp.db"))
    assert not list(tmp_path.glob("restore-*.tmp.salt"))


def test_anything_other_than_yes_is_not_a_yes(restore_script, monkeypatch, backup, tmp_path):
    """
    A typed word, not a keypress. "y" is what somebody hits to make a prompt go
    away; the prompt asks for "yes" and means it.
    """
    out = tmp_path / "restored.db"
    out.write_bytes(b"still here")

    assert _restore(restore_script, monkeypatch, backup, out, confirm="y") != 0

    assert out.read_bytes() == b"still here"


def test_the_confirmation_names_the_files_it_is_about_to_replace(
    restore_script, monkeypatch, backup, tmp_path, capsys
):
    """
    "Are you sure?" is not a confirmation, because it does not say what of.
    """
    out = tmp_path / "restored.db"
    out.write_bytes(b"the old database")

    _restore(restore_script, monkeypatch, backup, out, confirm="no")

    printed = capsys.readouterr().out
    assert str(out) in printed
    assert "About to replace" in printed


def test_yes_skips_the_prompt_entirely(restore_script, monkeypatch, backup, tmp_path):
    """--yes is for scripted runs; it must not still block on input()."""
    _answers(monkeypatch, restore_script, BACKUP_PASSWORD, NEW_LIVE_PASSWORD, NEW_LIVE_PASSWORD)

    def _no_prompting(prompt=""):
        raise AssertionError("--yes must not reach the confirmation prompt")

    monkeypatch.setattr("builtins.input", _no_prompting)
    out = tmp_path / "restored.db"

    assert restore_script.main(["--from", str(backup), "--out", str(out), "--yes"]) == 0
    assert out.exists()


# ---------------------------------------------------------------------------
# ChromaDB is rebuilt, not restored
# ---------------------------------------------------------------------------


def test_the_vector_index_is_not_rebuilt_for_a_restore_to_a_copy(
    restore_script, monkeypatch, backup, tmp_path, capsys
):
    """
    There is one ChromaDB directory, and it belongs to the live database.
    Rebuilding it to match a database restored somewhere else would leave the
    installation still in use pointing at an index describing something else.
    """
    called = []
    monkeypatch.setattr(restore_script, "rebuild_vector_index",
                        lambda *a, **k: called.append(a))

    _restore(restore_script, monkeypatch, backup, tmp_path / "restored.db")

    assert called == []
    assert "not the live database" in capsys.readouterr().out


def test_a_failing_index_rebuild_does_not_fail_the_restore(
    restore_script, monkeypatch, backup, tmp_path, capsys
):
    """
    The index is derived (ADR-026) and the data is already on disk and verified
    by the time it runs. A missing chromadb install, or a documents directory
    that only ever existed on the other machine, must not turn a good restore
    into a reported failure.
    """
    out = tmp_path / "restored.db"
    monkeypatch.setattr(restore_script, "DB_PATH", out)

    def _explode(*_args, **_kwargs):
        raise RuntimeError("no embedding model on this machine")

    monkeypatch.setattr(restore_script, "rebuild_vector_index", _explode)

    assert _restore(restore_script, monkeypatch, backup, out) == 0

    printed = capsys.readouterr().out
    assert "index rebuild failed" in printed
    assert "no embedding model on this machine" in printed
    assert _rows(out, db_key_module.derive_key_from_stored_salt(NEW_LIVE_PASSWORD),
                 is_password=False)["decisions"] == 1


def test_the_rebuild_is_run_with_the_new_key(restore_script, monkeypatch, backup, tmp_path):
    """
    vector_store reads the live key from the environment to derive its chunk
    keys. Handed the old key - or none - it would write an index the restored
    database cannot address.
    """
    out = tmp_path / "restored.db"
    monkeypatch.setattr(restore_script, "DB_PATH", out)
    seen = {}
    monkeypatch.setattr(restore_script, "rebuild_vector_index",
                        lambda path, key: seen.update(path=path, key=key))

    _restore(restore_script, monkeypatch, backup, out)

    assert seen["path"] == out
    assert seen["key"] == db_key_module.derive_key_from_stored_salt(NEW_LIVE_PASSWORD)


def test_no_index_rebuild_is_honoured(restore_script, monkeypatch, backup, tmp_path, capsys):
    out = tmp_path / "restored.db"
    monkeypatch.setattr(restore_script, "DB_PATH", out)
    monkeypatch.setattr(restore_script, "rebuild_vector_index",
                        lambda *a, **k: pytest.fail("--no-index-rebuild must skip this"))
    _answers(monkeypatch, restore_script, BACKUP_PASSWORD, NEW_LIVE_PASSWORD, NEW_LIVE_PASSWORD)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")

    assert restore_script.main(
        ["--from", str(backup), "--out", str(out), "--no-index-rebuild"]
    ) == 0
    assert "--no-index-rebuild" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The move into place, when the OS says no
# ---------------------------------------------------------------------------


def test_a_refused_rename_puts_everything_back(restore_script, monkeypatch, backup, tmp_path):
    """
    Windows will not rename a file another process holds open, and a restore is
    run exactly when things are not normal - a backend that crashed without
    releasing its handle, a scanner mid-pass, a shell still sitting on the file.
    refuse_if_pip_is_running() covers PIP itself and nothing else.

    The state this guards against is the half-swapped one: old database moved
    aside, new one not yet in place. That is worse than both doing nothing and
    finishing, and it is the only outcome the rest of this script does not
    already exclude.
    """
    out = tmp_path / "restored.db"
    out.write_bytes(b"the database that is still open somewhere")
    salt_path = db_key_module.salt_path()
    salt_path.write_bytes(b"the salt beside it")

    real_move = restore_script.shutil.move
    calls = []

    def _refuse_the_second_move(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError(32, "The process cannot access the file")
        return real_move(src, dst)

    monkeypatch.setattr(restore_script.shutil, "move", _refuse_the_second_move)

    assert _restore(restore_script, monkeypatch, backup, out) != 0

    assert out.read_bytes() == b"the database that is still open somewhere"
    assert salt_path.read_bytes() == b"the salt beside it"
    assert not list(tmp_path.glob("*.superseded-*")), "the moved-aside copy was not put back"
    assert not list(tmp_path.glob("restore-*.tmp.*")), "temporary files were left behind"


def test_the_refusal_is_reported_rather_than_raised(
    restore_script, monkeypatch, backup, tmp_path, capsys
):
    """A traceback is not a restore outcome. It should read as a clean failure."""
    out = tmp_path / "restored.db"
    out.write_bytes(b"held open")

    def _refuse(src, dst):
        raise OSError(32, "The process cannot access the file")

    monkeypatch.setattr(restore_script.shutil, "move", _refuse)

    assert _restore(restore_script, monkeypatch, backup, out) != 0

    printed = capsys.readouterr()
    assert "could not be replaced" in printed.err
    assert "Nothing was replaced." in printed.err


def test_a_restore_elsewhere_does_not_touch_the_live_salt(
    restore_script, monkeypatch, backup, tmp_path
):
    """
    The accident somebody has while being careful.

    Rehearsing a restore to a scratch path used to write the new salt into
    data/salt.bin anyway, because that is where salt_path() points. The salt is
    half the key derivation, so the live database - untouched, perfectly intact -
    would stop opening with the password that had always opened it, and the
    person who caused it was doing the responsible thing at the time.
    """
    live_data = tmp_path / "data"
    live_data.mkdir()
    live_salt = live_data / "salt.bin"
    live_salt.write_bytes(b"the live installation's salt")
    monkeypatch.setenv("PIP_SALT_PATH", str(live_salt))
    monkeypatch.setattr(restore_script, "DB_PATH", live_data / "pip.db")

    rehearsal = tmp_path / "rehearsal"
    rehearsal.mkdir()

    assert _restore(restore_script, monkeypatch, backup, rehearsal / "pip.db") == 0

    assert live_salt.read_bytes() == b"the live installation's salt", (
        "the live salt was replaced by a restore that was not aimed at it"
    )
    assert not list(live_data.glob("salt.bin.superseded-*"))
    assert (rehearsal / "salt.bin").exists(), "the copy needs its own salt to be openable"


def test_a_normal_restore_still_replaces_the_live_salt(
    restore_script, monkeypatch, backup, tmp_path
):
    """
    The other half. A restore aimed at the live database MUST replace
    data/salt.bin - a new password needs a new salt, and that path is where
    every entry point looks for it.
    """
    live_db = tmp_path / "pip.db"
    salt_path = db_key_module.salt_path()
    salt_path.write_bytes(b"0123456789abcdef")
    monkeypatch.setattr(restore_script, "DB_PATH", live_db)

    assert _restore(restore_script, monkeypatch, backup, live_db) == 0

    assert salt_path.read_bytes() != b"0123456789abcdef"
    assert len(list(salt_path.parent.glob(f"{salt_path.name}.superseded-*"))) == 1
