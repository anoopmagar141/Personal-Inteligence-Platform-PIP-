"""
An export taken while the app is writing still works, and a failed one says so
truthfully (FREEZE_LIST D-17).

export_backup.py counted every table's rows, asked for the backup password
twice, checkpointed, and only then exported; verify() demanded that the
backup's counts equal the FIRST count exactly. The Backup screen starts the
export while the backend is running, and nothing paused it, so a commit in that
window that changed a table's row count - an insert or a delete - failed the
export with "row counts differ". The Observer's session-end pass is exactly such
a commit, and the person is sitting at a password prompt for as long as they
take to type.

Two things are held:

  The counts and the copy come from ONE read snapshot. A row committed by
  another connection while the person types is simply in both; one committed
  after the snapshot is taken is in neither. WAL mode lets the writer carry on
  meanwhile - it is the app, and it must not be blocked by a backup.

  A failed export leaves no file. launcher says "The export did not complete.
  Nothing was written." for every non-zero exit; for these failures it was
  false - a file was written, listed unmarked at the top of the Backups list,
  and in the shortcut's pick - and a file that failed its own verification is
  one nobody should be handed as a backup.
"""

import importlib.util
import pathlib
import sys

import pytest
import sqlcipher3

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "a-different-password"


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
def script():
    return _load("export_backup")


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Anup", language_preference="English", skills=[])
    decision_log.insert_decision(conn, text="The first decision")
    conn.commit()
    conn.close()
    return path


def _another_writer_commits(live_db, text):
    """What the running app does: a second connection, its own commit."""
    conn = profile_store.get_connection(str(live_db), db_key=LIVE_KEY)
    try:
        decision_log.insert_decision(conn, text=text)
        conn.commit()
    finally:
        conn.close()


def _decisions_in(backup):
    conn = sqlcipher3.connect(str(backup))
    try:
        conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
        return conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    finally:
        conn.close()


def _decisions_live(live_db):
    conn = profile_store.get_connection(str(live_db), db_key=LIVE_KEY)
    try:
        return conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    finally:
        conn.close()


def _run(script, monkeypatch, live_db, out, getpass=None):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", getpass or (lambda prompt="": BACKUP_PASSWORD))
    monkeypatch.setattr(script.sys, "argv", ["export_backup.py", "--db-path", str(live_db), "--out", str(out)])
    return script.main()


# ---------------------------------------------------------------------------
# One snapshot
# ---------------------------------------------------------------------------


def test_a_commit_while_the_password_is_typed_does_not_fail_the_export(script, monkeypatch, live_db, tmp_path):
    """The measured case: the Observer's pass commits while the person types."""
    typed = {"n": 0}

    def getpass(prompt=""):
        typed["n"] += 1
        if typed["n"] == 1:
            _another_writer_commits(live_db, "Written while the password was being typed")
        return BACKUP_PASSWORD

    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out, getpass)

    assert out.exists()
    assert _decisions_in(out) == _decisions_live(live_db) == 2


def test_a_commit_between_the_count_and_the_copy_is_in_neither(script, monkeypatch, live_db, tmp_path):
    """
    The window the snapshot closes. The counts are taken, another connection
    commits, and the copy is made: without one snapshot across both, the copy
    holds a row the counts do not, and verification fails.
    """
    real_row_counts = script.row_counts
    fired = {"n": 0}

    def counts_then_a_commit(conn, names):
        result = real_row_counts(conn, names)
        if conn.in_transaction and not fired["n"]:
            fired["n"] += 1
            _another_writer_commits(live_db, "Written after the counts were taken")
        return result

    monkeypatch.setattr(script, "row_counts", counts_then_a_commit)
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    assert fired["n"] == 1, "the counts were not taken inside a read snapshot"
    assert out.exists()
    assert _decisions_in(out) == 1, "the copy held a row the counts did not"
    assert _decisions_live(live_db) == 2, "the writer was blocked by the backup"


# ---------------------------------------------------------------------------
# A failed export is not a file
# ---------------------------------------------------------------------------


def test_an_export_that_fails_verification_leaves_no_file(script, monkeypatch, live_db, tmp_path):
    def verify_fails(*args, **kwargs):
        raise SystemExit("ERROR: row counts differ between source and backup: {}")

    monkeypatch.setattr(script, "verify", verify_fails)
    out = tmp_path / "backup.pipbak"

    with pytest.raises(SystemExit):
        _run(script, monkeypatch, live_db, out)

    assert not out.exists(), "an unverified file was left where it will be listed as a backup"


def test_an_export_that_fails_while_marking_leaves_no_file(script, monkeypatch, live_db, tmp_path):
    def cannot_mark(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(script.backup_mark, "finish", cannot_mark)
    out = tmp_path / "backup.pipbak"

    with pytest.raises(RuntimeError):
        _run(script, monkeypatch, live_db, out)

    assert not out.exists()


def test_a_failed_export_never_removes_a_file_it_did_not_write(script, monkeypatch, live_db, tmp_path):
    """The out path already existing is refused before anything is written, and
    cleaning up after that refusal must not delete the file that was there."""
    out = tmp_path / "backup.pipbak"
    out.write_bytes(b"somebody's earlier backup")

    with pytest.raises(SystemExit):
        _run(script, monkeypatch, live_db, out)

    assert out.read_bytes() == b"somebody's earlier backup"


def test_a_good_export_is_still_kept(script, monkeypatch, live_db, tmp_path):
    out = tmp_path / "backup.pipbak"

    _run(script, monkeypatch, live_db, out)

    assert out.exists() and _decisions_in(out) == 1


def test_an_export_that_fails_while_copying_leaves_no_file(script, monkeypatch, live_db, tmp_path):
    """
    The window in which the backup is still attached to the live connection.
    Windows will not delete a file SQLite holds open, so the tidy-up has to wait
    for the detach; done inside the window it fails with WinError 32 and the file
    stays, which is what a test on the verification-failure path cannot see.
    """
    real_row_counts = script.row_counts

    def counts_fail_inside_the_copy(conn, names):
        # Only once the backup is attached and the snapshot is open: the first
        # count is taken before the file exists, and failing there proves nothing.
        if conn.in_transaction:
            raise RuntimeError("the disk went away")
        return real_row_counts(conn, names)

    monkeypatch.setattr(script, "row_counts", counts_fail_inside_the_copy)
    out = tmp_path / "backup.pipbak"

    with pytest.raises(RuntimeError):
        _run(script, monkeypatch, live_db, out)

    assert not out.exists()
    assert not (tmp_path / "backup.pipbak-journal").exists()
    assert _decisions_live(live_db) == 1, "the live database was changed by a failed export"
