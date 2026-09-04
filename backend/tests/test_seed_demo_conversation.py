"""
Tests for scripts/seed_demo_conversation.py.

This script is pointed at a REAL profile - the one with a real decision log in
it - which makes it the only seeder in this repository allowed anywhere near
live data. seed_test_profile.py refuses the default profile outright; this one
cannot, because filing a worked example against the real PIP project is the
entire point.

So the properties worth testing are the ones that make that defensible:

  It writes exactly once. A second run must not quietly double the transcript.
  It writes nothing the Observer will later mistake for an unprocessed session.
  Everything it wrote can be removed, precisely, without touching a neighbouring
  row that happened to be written the same afternoon.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32


def _load():
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        "seed_demo_conversation", root / "scripts" / "seed_demo_conversation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load()


@pytest.fixture
def profile(tmp_path):
    """A profile with a PIP project and a decision already in it."""
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(
        conn, name="Anup", language_preference="English", skills=["Python"]
    )
    project_id = profile_store.create_project(conn, "PIP", "the real one")
    # A pre-existing decision, so "undo removed only what it wrote" has
    # something to be wrong about.
    decision_log.insert_decision(conn, text="Use SQLCipher end to end", project_id=project_id)
    conn.commit()
    return conn, project_id


@pytest.fixture
def connected(script, profile, monkeypatch):
    conn, project_id = profile
    monkeypatch.setattr(script._db, "connect", lambda *a, **k: conn)
    monkeypatch.setattr(script, "refuse_if_pip_is_running", lambda: None)
    return conn, project_id


def test_it_writes_five_sections_of_transcript(script, connected):
    conn, project_id = connected

    result = script.seed(conn, project_id, title="Cross-machine continuity")

    stored = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
        (result["conversation_id"],),
    ).fetchone()[0]
    expected = sum(len(turns) for _, _, turns in script.SECTIONS)

    assert len(script.SECTIONS) == 5
    assert stored == expected == result["messages"]


def test_the_transcript_alternates_and_starts_with_the_user(script, connected):
    """A conversation that opens with the assistant is one nobody had."""
    conn, project_id = connected

    result = script.seed(conn, project_id, title="Cross-machine continuity")

    roles = [
        r["role"]
        for r in conn.execute(
            "SELECT role FROM messages WHERE conversation_id = ? ORDER BY id",
            (result["conversation_id"],),
        )
    ]
    assert roles[0] == "user"
    assert all(a != b for a, b in zip(roles, roles[1:])), "two turns from the same speaker"


def test_the_decisions_land_in_the_log_against_the_project(script, connected):
    conn, project_id = connected

    result = script.seed(conn, project_id, title="Cross-machine continuity")

    assert len(result["decision_ids"]) == len(script.DECISIONS)
    for decision_id in result["decision_ids"]:
        row = conn.execute(
            "SELECT project_id, reasoning, alternatives_considered, state "
            "FROM decision_log WHERE id = ?",
            (decision_id,),
        ).fetchone()
        assert row["project_id"] == project_id
        assert row["state"] == "active"
        assert row["reasoning"], "a decision with no reasoning is half a record"
        assert row["alternatives_considered"], "and one with no alternative is a claim"


def test_the_conversation_is_marked_observed(script, connected):
    """
    NULL observed_at means the Observer never ran, and startup recovery would
    pick this up and spend an LLM pass extracting memory from a transcript that
    was written rather than spoken.
    """
    conn, project_id = connected

    result = script.seed(conn, project_id, title="Cross-machine continuity")

    observed = conn.execute(
        "SELECT observed_at FROM conversations WHERE id = ?", (result["conversation_id"],)
    ).fetchone()["observed_at"]
    assert observed


def test_a_second_run_is_refused(script, connected):
    conn, project_id = connected
    script.seed(conn, project_id, title="Cross-machine continuity")

    with pytest.raises(SystemExit, match="already here"):
        script.seed(conn, project_id, title="Cross-machine continuity")

    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 1


def test_an_unknown_project_is_refused_not_guessed(script, connected):
    """
    A conversation filed against the wrong project is worse than one filed
    against none: Stage 3 looks decisions up by the active project, so a
    misfiled transcript is invisible from where it belongs and noise where it
    does not.
    """
    conn, _ = connected

    with pytest.raises(SystemExit) as exit_info:
        script.find_project(conn, "Not A Project")

    assert "no project named" in str(exit_info.value)
    assert "PIP" in str(exit_info.value), "it should say what is available"


def test_undo_removes_exactly_what_was_written(script, connected):
    conn, project_id = connected
    before_decisions = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]

    result = script.seed(conn, project_id, title="Cross-machine continuity")
    removed = script.undo(conn, result)

    assert removed["conversations"] == 1
    assert removed["messages"] == result["messages"]
    assert removed["decisions"] == len(result["decision_ids"])

    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0] == before_decisions


def test_undo_leaves_the_decision_that_was_already_there(script, connected):
    """
    The property that makes --undo safe to run on a real log months later: it
    works from recorded ids, not from a guess about which rows look seeded.
    """
    conn, project_id = connected
    original = conn.execute("SELECT id, decision_text FROM decision_log").fetchall()

    result = script.seed(conn, project_id, title="Cross-machine continuity")
    script.undo(conn, result)

    after = conn.execute("SELECT id, decision_text FROM decision_log").fetchall()
    assert [dict(r) for r in after] == [dict(r) for r in original]


def test_undo_survives_a_manifest_round_trip_through_json(script, connected, tmp_path):
    """The manifest is written to disk and read back weeks later, not held in memory."""
    conn, project_id = connected
    result = script.seed(conn, project_id, title="Cross-machine continuity")

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    removed = script.undo(conn, json.loads(manifest_path.read_text(encoding="utf-8")))

    assert removed["conversations"] == 1
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_every_section_that_claims_a_decision_has_one(script):
    """
    The transcript and the decision log are written from the same table, so they
    cannot drift - but an index pointing at a decision that does not exist would
    still be a crash at seed time on somebody's real database.
    """
    for name, index, turns in script.SECTIONS:
        assert turns, f"section {name!r} has no turns"
        if index is not None:
            assert 0 <= index < len(script.DECISIONS), f"section {name!r} names decision {index}"
