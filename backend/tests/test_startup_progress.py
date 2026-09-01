"""
Tests for the startup phase file the launch screen reads.

The screen this feeds used to choose between two sentences with a retry
counter, so it said "Still preparing things" after eight seconds whether the
database was being decrypted or nothing was running at all. What has to hold
here is that the replacement never becomes another way of guessing: phases are
recorded when they happen, in order, and a failure to record one costs the
detail rather than the launch.
"""

import json

import pytest

from backend.api import server
from backend.core import startup_progress


@pytest.fixture(autouse=True)
def isolated_progress(tmp_path, monkeypatch):
    path = tmp_path / "startup.jsonl"
    monkeypatch.setenv("PIP_STARTUP_PROGRESS_PATH", str(path))
    return path


def test_phases_are_appended_in_the_order_they_happen(isolated_progress):
    startup_progress.report("ollama", "already running")
    startup_progress.report("key", "database key derived")
    startup_progress.report("ready")

    assert [entry["phase"] for entry in startup_progress.read()] == ["ollama", "key", "ready"]
    assert startup_progress.read()[0]["detail"] == "already running"


def test_each_phase_is_one_json_line(isolated_progress):
    """
    Append-only, one object per line, because a phase is a fact that happened
    rather than a state to overwrite - and because the launcher writes to this
    same file from PowerShell without coordinating with Python.
    """
    startup_progress.report("ollama")
    startup_progress.report("key")

    lines = isolated_progress.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "ollama"


def test_reset_clears_a_previous_run(isolated_progress):
    startup_progress.report("ready")
    startup_progress.reset()

    # Otherwise a launch screen opens onto the last run's completed checklist
    # and calls it progress.
    assert startup_progress.read() == []


def test_a_torn_line_does_not_hide_the_phases_before_it(isolated_progress):
    startup_progress.report("ollama")
    with open(isolated_progress, "a", encoding="utf-8") as handle:
        handle.write('{"phase": "key", "det')

    # A reader can arrive mid-write. The phases before the torn line are still
    # true and must survive it.
    assert [entry["phase"] for entry in startup_progress.read()] == ["ollama"]


def test_reading_before_anything_was_written_is_not_an_error(isolated_progress):
    assert startup_progress.read() == []


def test_reporting_never_raises_when_the_path_is_unusable(monkeypatch, tmp_path):
    """
    A launch screen is a courtesy. Taking down a startup because the courtesy
    could not be written would invert the priority, the same way
    trace.stage_log() already declines to.
    """
    # A directory where the file should be: open() for append will fail.
    blocked = tmp_path / "startup.jsonl"
    blocked.mkdir()
    monkeypatch.setenv("PIP_STARTUP_PROGRESS_PATH", str(blocked))

    startup_progress.report("ollama")  # must not raise
    startup_progress.reset()  # must not raise
    assert startup_progress.read() == []


def test_the_running_backend_records_the_lock_and_then_ready(tmp_path, monkeypatch, isolated_progress):
    """
    The two phases only the backend can report. 'ready' is written last, right
    before serving, so the launch screen turns it into "listening" only when a
    request would genuinely be answered.
    """
    from fastapi.testclient import TestClient

    from backend.core import auth

    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    auth.get_or_create_token(tmp_path / "api_token.txt")

    with TestClient(server.app):
        pass

    phases = [entry["phase"] for entry in startup_progress.read()]
    assert "lock" in phases
    assert "ready" in phases
    assert phases.index("lock") < phases.index("ready")


def test_the_backgrounded_catch_up_is_not_reported(tmp_path, monkeypatch, isolated_progress):
    """
    The Observer drain runs in the background precisely so nobody waits on it -
    server.py records that putting it inline hung launch for over two minutes.
    A launch screen listing it would tell the user to wait for the exact thing
    that was moved off the launch path.
    """
    from fastapi.testclient import TestClient

    from backend.core import auth

    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    auth.get_or_create_token(tmp_path / "api_token.txt")

    with TestClient(server.app):
        pass

    phases = [entry["phase"] for entry in startup_progress.read()]
    assert not any("catch" in phase for phase in phases)
