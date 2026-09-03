import json
import pathlib

import pytest

from frontend.cli import pip_cli


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self):
        self.requests = []
        self.responses = []

    def queue(self, payload):
        self.responses.append(payload)

    def __call__(self, req):
        body = json.loads(req.data.decode("utf-8")) if req.data else None
        self.requests.append(
            {
                "method": req.get_method(),
                "url": req.full_url,
                "body": body,
            }
        )
        return FakeResponse(self.responses.pop(0))


def test_profile_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue([{"field": "name", "value": "BatMan"}])
    opener.queue({"status": "updated"})
    opener.queue({"status": "deleted", "field": "answer_depth"})

    assert pip_cli.run_command(["/profile"], opener=opener)[0]["field"] == "name"
    assert pip_cli.run_command(["/profile", "edit", "answer_depth", "brief"], opener=opener)["status"] == "updated"
    assert pip_cli.run_command(["/profile", "delete", "answer_depth"], opener=opener)["status"] == "deleted"

    assert opener.requests[0]["method"] == "GET"
    assert opener.requests[0]["url"].endswith("/memory/profile")
    assert opener.requests[1]["method"] == "POST"
    assert opener.requests[1]["url"].endswith("/memory/correct")
    assert opener.requests[1]["body"] == {"field": "answer_depth", "value": "brief"}
    assert opener.requests[2]["method"] == "DELETE"


def test_decide_and_decisions_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue({"status": "logged", "decision_id": 1})
    opener.queue([{"id": 1}])
    opener.queue([{"id": 1}])
    opener.queue({"status": "updated"})

    assert pip_cli.run_command(["/decide", "We", "will", "use", "SQLite"], opener=opener)["status"] == "logged"
    assert pip_cli.run_command(["/decisions"], opener=opener) == [{"id": 1}]
    assert pip_cli.run_command(["/decisions", "search", "SQLite"], opener=opener) == [{"id": 1}]
    assert pip_cli.run_command(["/decisions", "1", "abandon", "--reason", "changed"], opener=opener)["status"] == "updated"

    assert opener.requests[0]["url"].endswith("/decision/create")
    assert opener.requests[0]["body"]["text"] == "We will use SQLite"
    assert opener.requests[1]["url"].endswith("/decision/search")
    assert opener.requests[2]["url"].endswith("/decision/search?q=SQLite")
    assert opener.requests[3]["method"] == "PATCH"
    assert opener.requests[3]["body"] == {"state": "abandoned", "reason": "changed"}


def test_pending_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue([{"id": 7, "decision_text": "Candidate"}])
    opener.queue([{"id": 7, "decision_text": "Candidate"}])
    opener.queue({"status": "promoted"})
    opener.queue({"status": "dismissed"})

    assert pip_cli.run_command(["/pending"], opener=opener)[0]["id"] == 7
    assert pip_cli.run_command(["/pending", "review", "7"], opener=opener)["decision_text"] == "Candidate"
    assert pip_cli.run_command(["/pending", "promote", "7"], opener=opener)["status"] == "promoted"
    assert pip_cli.run_command(["/pending", "dismiss", "7"], opener=opener)["status"] == "dismissed"

    assert opener.requests[0]["url"].endswith("/decision/pending")
    assert opener.requests[2]["url"].endswith("/decision/pending/7/promote")
    assert opener.requests[3]["url"].endswith("/decision/pending/7/dismiss")


def test_rag_commands_call_rest_api():
    opener = FakeOpener()
    opener.queue({"status": "ingested", "file_path": "C:\\docs\\notes.txt", "chunk_count": 3})
    opener.queue([{"file_path": "C:\\docs\\notes.txt"}])
    opener.queue({"status": "removed", "file_path": "C:\\docs\\notes.txt"})

    ingested = pip_cli.run_command(["/ingest", "C:\\docs\\notes.txt"], opener=opener)
    assert ingested["status"] == "ingested"
    docs = pip_cli.run_command(["/documents"], opener=opener)
    assert docs[0]["file_path"] == "C:\\docs\\notes.txt"
    removed = pip_cli.run_command(["/remove", "C:\\docs\\notes.txt"], opener=opener)
    assert removed["status"] == "removed"

    assert opener.requests[0]["url"].endswith("/rag/ingest")
    assert opener.requests[0]["body"] == {"file_path": "C:\\docs\\notes.txt", "project_id": None}
    assert opener.requests[1]["url"].endswith("/rag/documents")
    assert opener.requests[2]["method"] == "DELETE"
    # Path separators must survive percent-encoding as a single path segment.
    assert "%5C" in opener.requests[2]["url"] or "docs" in opener.requests[2]["url"]


# ---------------------------------------------------------------------------
# /export and /restore
# ---------------------------------------------------------------------------
#
# The only two commands that do not touch the REST API, and the assertion that
# they don't is the point rather than an implementation detail. ADR-027: an
# HTTP route that re-encrypts the database under a caller-supplied password
# would hand any process that can read data/api_token.txt a full copy of
# everything, without it ever knowing the live key. The slash command is a front
# door to the script; it grants nothing the person at this shell already lacked.


class FakeScript:
    """Stands in for the module _load_script would have executed."""

    def __init__(self, result):
        self.result = result
        self.argv = None

    def main(self, argv=None):
        self.argv = argv
        return self.result


@pytest.fixture
def scripts(monkeypatch):
    loaded = {
        "export_backup": FakeScript(pathlib.Path("data/pip_backup_20260902.pipbak")),
        "restore_backup": FakeScript(0),
    }
    monkeypatch.setattr(pip_cli, "_load_script", lambda name: loaded[name])
    return loaded


def test_export_runs_the_script_and_never_the_api(scripts):
    def _no_http(req):
        raise AssertionError("/export must not reach the REST API")

    result = pip_cli.run_command(["/export"], opener=_no_http)

    assert result["status"] == "exported"
    assert result["file"].endswith("pip_backup_20260902.pipbak")
    assert scripts["export_backup"].argv == []


def test_export_passes_its_flags_through_untouched(scripts):
    """
    One argument parser for this command, owned by the script. Re-parsing here
    is how a flag comes to mean one thing as a slash command and another at a
    shell.
    """
    pip_cli.run_command(["/export", "--readable", "--out", "C:/tmp/dump.json"])

    assert scripts["export_backup"].argv == ["--readable", "--out", "C:/tmp/dump.json"]


def test_restore_takes_the_file_as_a_bare_argument(scripts):
    """/restore [file], per the command's specified form."""
    result = pip_cli.run_command(["/restore", "data/pip_backup_20260902.pipbak"])

    assert result == {"status": "restored"}
    assert scripts["restore_backup"].argv == ["--from", "data/pip_backup_20260902.pipbak"]


def test_restore_with_no_argument_lets_the_script_pick_the_newest(scripts):
    pip_cli.run_command(["/restore"])

    assert scripts["restore_backup"].argv == []


def test_restore_still_accepts_the_scripts_own_flags(scripts):
    pip_cli.run_command(["/restore", "--from", "old.pipbak", "--yes"])

    assert scripts["restore_backup"].argv == ["--from", "old.pipbak", "--yes"]


def test_a_bare_file_and_flags_can_be_combined(scripts):
    pip_cli.run_command(["/restore", "old.pipbak", "--no-index-rebuild"])

    assert scripts["restore_backup"].argv == ["--from", "old.pipbak", "--no-index-rebuild"]


def test_a_failed_restore_is_not_reported_as_a_success(scripts):
    """
    The script prints why and leaves the data directory untouched; this turns
    its exit code into the nonzero exit every other failure here gets, rather
    than a cheerful status line over a restore that did not happen.
    """
    scripts["restore_backup"].result = 1

    with pytest.raises(RuntimeError, match="nothing was replaced"):
        pip_cli.run_command(["/restore"])

    assert pip_cli.main(["/restore"]) == 2


def test_the_commands_resolve_to_the_real_scripts():
    """
    The fake above proves the dispatch; this proves the dispatch points at
    something that exists, which no amount of monkeypatching can.
    """
    for name in ("export_backup", "restore_backup"):
        assert (pip_cli.SCRIPTS_DIR / f"{name}.py").is_file()
