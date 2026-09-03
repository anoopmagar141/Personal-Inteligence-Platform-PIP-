"""
Tests for scripts/merge_projects.py.

Two rows described the same project - "PIP" and "pip", differing only in case,
which `name TEXT NOT NULL UNIQUE` does not catch. project_id is the join key for
decisions, documents and conversations, so the two halves of one project's
history were filed under ids that nothing relates.

The property that matters is that a merge moves EVERYTHING and loses NOTHING.
Both halves are load-bearing: a merge that misses a table silently strands rows
under a project the UI no longer shows, and a merge that deletes rather than
retracts throws away the fact that there were ever two.
"""

import importlib.util
import pathlib
import sys

import pytest

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32


def _load(name: str):
    """scripts/ is not a package - the same by-path load the sibling tests use."""
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(monkeypatch):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    return _load("merge_projects")


@pytest.fixture
def db(tmp_path, monkeypatch):
    """
    The duplicate as it actually occurred: one project made through the UI and
    one by a seed script, each holding part of the same history.
    """
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)

    keep = profile_store.create_project(conn, "PIP", "the one in the UI", timestamp="2026-09-02T10:00:00Z")
    lose = profile_store.create_project(conn, "pip", "the seeded one", timestamp="2026-09-02T12:00:00Z")
    profile_store.update_project_status(conn, lose, "completed")
    # update_project_status restamps last_active with now(), which would make
    # the losing project the OLDER of the two and quietly stop the timestamp
    # test from testing anything. Put it back to what the fixture describes.
    conn.execute(
        "UPDATE active_projects SET last_active = ? WHERE project_id = ?",
        ("2026-09-02T12:00:00Z", lose),
    )

    decision_log.insert_decision(conn, text="Use SQLCipher end to end", project_id=keep)
    decision_log.insert_decision(conn, text="Observer collapses onto llama3.1", project_id=lose)
    decision_log.insert_decision(conn, text="WS for chat, REST for CRUD", project_id=lose)
    conn.execute(
        "INSERT INTO conversations (id, title, project_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("c1", "a chat about the pipeline", lose, "2026-09-01T09:00:00Z", "2026-09-01T09:30:00Z"),
    )
    conn.commit()
    conn.close()
    return path, keep, lose


@pytest.fixture
def conn(db):
    path, _, _ = db
    connection = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    yield connection
    connection.close()


def _run(script, db, monkeypatch, *args, answer="yes"):
    path, _, _ = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    return script.main(list(args))


def test_everything_filed_against_the_loser_moves(script, db, monkeypatch, conn, capsys):
    """The whole point: one project_id afterwards, holding both halves."""
    _, keep, lose = db

    assert _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP") == 0

    assert script.reference_counts(conn, lose) == {
        "decision_log": 0, "documents": 0, "conversations": 0
    }
    assert script.reference_counts(conn, keep) == {
        "decision_log": 3, "documents": 0, "conversations": 1
    }


def test_no_decision_is_lost_in_the_move(script, db, monkeypatch, conn):
    """
    Counted per text, not just totalled. A merge that moved two rows and
    dropped a third would still leave a plausible-looking number behind.
    """
    _, keep, _ = db
    before = {r["decision_text"] for r in conn.execute("SELECT decision_text FROM decision_log")}

    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    after = {
        r["decision_text"]
        for r in conn.execute("SELECT decision_text FROM decision_log WHERE project_id = ?", (keep,))
    }
    assert after == before
    assert len(after) == 3


def test_the_losing_project_is_retracted_not_erased(script, db, monkeypatch, conn):
    """
    ADR-022's posture, and the schema's own comment: 'deleted' is a retraction.
    After a merge nothing points at the row, so a DELETE would be safe - and
    "these were once two projects" is exactly what somebody reads the log later
    to find out.
    """
    _, _, lose = db

    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    row = conn.execute(
        "SELECT name, status FROM active_projects WHERE project_id = ?", (lose,)
    ).fetchone()
    assert row is not None, "the row was erased rather than retracted"
    assert row["status"] == "deleted"
    assert row["name"] == "pip"


def test_the_merged_project_is_the_only_one_the_ui_shows(script, db, monkeypatch, conn):
    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    assert [p["name"] for p in profile_store.list_projects(conn)] == ["PIP"]


def test_the_survivor_inherits_the_later_timestamp(script, db, monkeypatch, conn):
    """
    It now holds work that happened at the losing project's last_active, so
    keeping the earlier one would misdate the merged whole.
    """
    _, keep, _ = db

    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    last_active = conn.execute(
        "SELECT last_active FROM active_projects WHERE project_id = ?", (keep,)
    ).fetchone()["last_active"]
    assert last_active >= "2026-09-02T12:00:00Z"


def test_declining_writes_nothing(script, db, monkeypatch, conn):
    _, keep, lose = db

    assert _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP", answer="no") != 0

    assert script.reference_counts(conn, lose)["decision_log"] == 2
    assert script.reference_counts(conn, keep)["decision_log"] == 1
    assert len(profile_store.list_projects(conn)) == 2


def test_dry_run_writes_nothing_and_needs_no_answer(script, db, monkeypatch, conn, capsys):
    def _no_prompting(prompt=""):
        raise AssertionError("--dry-run must not ask")

    monkeypatch.setattr("builtins.input", _no_prompting)
    path, _, lose = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))

    assert script.main(["--from", "pip", "--into", "PIP", "--dry-run"]) == 0

    assert script.reference_counts(conn, lose)["decision_log"] == 2
    assert "nothing was written" in capsys.readouterr().out


def test_the_plan_is_printed_before_the_confirmation(script, db, monkeypatch, capsys):
    """
    "Merge these?" is not a plan. It has to say which one dies and what moves.
    """
    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP", answer="no")

    printed = capsys.readouterr().out
    assert "will be retracted" in printed
    assert "survives" in printed
    assert "2 decision_log" in printed


def test_a_project_can_be_named_by_id(script, db, monkeypatch, conn):
    _, keep, lose = db

    assert _run(script, db, monkeypatch, "--from", lose, "--into", keep) == 0

    assert [p["name"] for p in profile_store.list_projects(conn)] == ["PIP"]


def test_an_ambiguous_case_insensitive_name_is_refused_not_guessed(script, db, monkeypatch):
    """
    The one mistake that cannot be undone by running this again. "PIP" and
    "pip" being distinct rows IS the situation - folding them together to
    resolve a name would merge in whichever direction the row order happened to
    give, silently.
    """
    path, _, _ = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--from", "PiP", "--into", "PIP", "--dry-run"])

    assert "differing only in case" in str(exit_info.value)


def test_an_exact_name_wins_over_a_case_insensitive_one(script, db, monkeypatch, conn):
    """
    Exact match is tried first, which is what makes --from pip --into PIP
    unambiguous despite the two names folding together.
    """
    _, _, lose = db

    assert _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP") == 0

    assert conn.execute(
        "SELECT status FROM active_projects WHERE project_id = ?", (lose,)
    ).fetchone()["status"] == "deleted"


def test_merging_a_project_into_itself_is_refused(script, db, monkeypatch):
    path, keep, _ = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--from", keep, "--into", keep])

    assert "same project" in str(exit_info.value)


def test_an_unknown_project_is_reported_not_guessed(script, db, monkeypatch):
    path, _, _ = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--from", "nope", "--into", "PIP", "--dry-run"])

    assert "no project matching" in str(exit_info.value)


def test_decisions_that_would_collide_are_reported(script, db, monkeypatch, conn, capsys):
    """
    Merging can put two identical active decision_texts under one project -
    something insert_decision() refuses on write, because ADR-022b scopes
    duplicate detection per project and this changes which project rows are in.
    Reported rather than resolved: collapsing them means choosing which id
    survives, and this script cannot see what references the other.
    """
    _, keep, lose = db
    decision_log.insert_decision(conn, text="Use   SQLCipher end to end", project_id=lose)
    conn.commit()

    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    printed = capsys.readouterr().out
    assert "will end up active twice" in printed
    assert "use sqlcipher end to end" in printed.lower()

    # Reported, and still merged - both rows are readable under the survivor.
    texts = [
        r["decision_text"]
        for r in conn.execute("SELECT decision_text FROM decision_log WHERE project_id = ?", (keep,))
    ]
    assert len([t for t in texts if "SQLCipher" in t]) == 2


def test_listing_shows_every_project_including_retracted_ones(
    script, db, monkeypatch, conn, capsys
):
    """
    list_projects() hides retracted projects, which is right for the UI and
    wrong here: undoing a merge by hand needs the id of a row the UI stopped
    showing.
    """
    _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")
    capsys.readouterr()

    path, _, _ = db
    monkeypatch.setattr(script._db, "connect", lambda *a, **k:
                        profile_store.get_connection(str(path), db_key=LIVE_KEY))
    assert script.main([]) == 0

    printed = capsys.readouterr().out
    assert "PIP" in printed
    assert "deleted" in printed


def test_it_refuses_to_run_while_pip_holds_the_lock(script, db, monkeypatch, conn):
    """
    The session-end Observer files decisions against the project the session
    started under. Retracting that project mid-session means the write lands on
    a 'deleted' row or fails the foreign key outright.
    """
    from backend.core import instance_lock

    instance_lock._lock_path().write_text("12345", encoding="utf-8")
    monkeypatch.setattr(instance_lock, "_pid_is_running", lambda pid: True)

    _, keep, lose = db
    with pytest.raises(SystemExit) as exit_info:
        _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP")

    assert "appears to be running" in str(exit_info.value)
    assert script.reference_counts(conn, lose)["decision_log"] == 2


def test_a_stale_lock_does_not_block_a_merge(script, db, monkeypatch, conn):
    from backend.core import instance_lock

    instance_lock._lock_path().write_text("12345", encoding="utf-8")
    monkeypatch.setattr(instance_lock, "_pid_is_running", lambda pid: False)

    assert _run(script, db, monkeypatch, "--from", "pip", "--into", "PIP") == 0
    assert [p["name"] for p in profile_store.list_projects(conn)] == ["PIP"]
