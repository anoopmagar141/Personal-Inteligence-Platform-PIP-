"""
scripts/restore_backup.py leaves nothing behind when it is interrupted.

The script converts the backup into a temporary live database beside the destination
(a full copy of the person's data, re-encrypted under the password they just chose)
and only then asks "Type yes to proceed". Declining cleaned both temporary files up;
anything ELSE that ended the run at or after that point did not: Ctrl+C at the prompt,
a closed console, an unexpected error. They stayed in data/ - found when a test hook
crashed that prompt during the real-window check of the import, 2026-10-08 - a complete
copy of the data, openable with a password nobody was told is still valid, until the
next restore or never.

What is held is the directory afterwards: no restore-*.tmp.* and the installation
untouched, whichever way the run ended.
"""

import importlib.util
import pathlib
import sys

import pytest

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-brand-new-live-password"


def _load(name):
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Anup", language_preference="English", skills=[])
    decision_log.insert_decision(conn, text="A decision")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def backup(monkeypatch, live_db, tmp_path):
    export = _load("export_backup")
    out = tmp_path / "backup.pipbak"
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", str(live_db), "--out", str(out)])
    export.main()
    monkeypatch.delenv("PIP_DB_KEY")
    return out


def _run(monkeypatch, backup, out, prompt):
    script = _load("restore_backup")
    answers = iter([BACKUP_PASSWORD, NEW_PASSWORD, NEW_PASSWORD])
    monkeypatch.setattr(script.getpass, "getpass", lambda p="": next(answers))
    monkeypatch.setattr("builtins.input", prompt)
    monkeypatch.setattr(script.sys, "argv", ["restore_backup.py", "--from", str(backup), "--out", str(out), "--no-index-rebuild"])
    return script.main()


def _nothing_left(tmp_path):
    return not list(tmp_path.glob("restore-*.tmp.*"))


def test_ctrl_c_at_the_confirmation_prompt_leaves_no_temporary_copy(monkeypatch, live_db, backup, tmp_path):
    before = live_db.read_bytes()

    def interrupted(prompt=""):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _run(monkeypatch, backup, live_db, interrupted)

    assert _nothing_left(tmp_path), "a full re-encrypted copy of the data was left in data/"
    assert live_db.read_bytes() == before


def test_an_unexpected_error_at_the_prompt_leaves_no_temporary_copy(monkeypatch, live_db, backup, tmp_path):
    def broken(prompt=""):
        raise RuntimeError("the console went away")

    with pytest.raises(RuntimeError):
        _run(monkeypatch, backup, live_db, broken)

    assert _nothing_left(tmp_path)


def test_declining_still_leaves_nothing(monkeypatch, live_db, backup, tmp_path):
    assert _run(monkeypatch, backup, live_db, lambda prompt="": "no") == 1
    assert _nothing_left(tmp_path)


def test_a_finished_restore_still_installs(monkeypatch, live_db, backup, tmp_path):
    out = tmp_path / "elsewhere" / "pip.db"

    assert _run(monkeypatch, backup, out, lambda prompt="": "yes") == 0

    assert out.exists()
    assert _nothing_left(out.parent)
