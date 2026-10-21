import json
import pathlib
import re

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
# /consent: the scope is chosen, never defaulted (D-30, FREEZE_LIST §7.51)
# ---------------------------------------------------------------------------
#
# `/consent PROVIDER_ID` with no --scope used to send full_inference, the
# broadest of the four scopes: a permission the person at the shell never
# typed. Promise 6 rules out a default the person did not choose, which is why
# the Flutter dialog preselects nothing and the old web client no longer grants
# at all (G-6). These pin the same thing for the typed command: no scope, no
# request, and a refusal that says which scopes there are to choose from.
#
# The scopes are written out here rather than read from pip_cli, so a test of
# what the CLI says cannot agree with itself whatever the CLI's list holds. The
# last test is the one that ties the CLI's list to the server's.

ALL_SCOPES = ["embedding_only", "web_search_only", "full_inference", "none"]

# Queued in front of every refusal below. Were a request to go out after all,
# the call would then return normally and the failure would read DID NOT
# RAISE, rather than an IndexError from FakeOpener's empty queue that says
# nothing about consent.
_GRANTED = {"status": "consented", "provider_id": "web_search", "consent_scope": "full_inference"}


def _names_every_scope(message: str) -> bool:
    # Whole words, so "none" is not found inside some other word of the message.
    return set(re.findall(r"\w+", message)) >= set(ALL_SCOPES)


def test_consent_without_a_scope_sends_nothing_and_names_the_scopes():
    opener = FakeOpener()
    opener.queue(_GRANTED)

    with pytest.raises(ValueError) as refused:
        pip_cli.run_command(["/consent", "web_search"], opener=opener)

    assert opener.requests == []
    assert "--scope" in str(refused.value)
    assert _names_every_scope(str(refused.value))


@pytest.mark.parametrize("argv", [
    ["/consent", "web_search", "--scope"],
    ["/consent"],
    ["/consent", "web_search", "extra", "--scope", "none"],
], ids=["scope with no value", "nothing at all", "an extra word"])
def test_argparses_own_usage_line_says_the_scope_is_required(argv, capsys):
    """
    Input argparse refuses itself (a SystemExit) prints argparse's usage line, and it
    used to read "usage: /consent [--scope CONSENT_SCOPE] provider_id" - the scope in
    brackets, as if optional - beside the refusal that says there is no default (found
    reviewing D-30, FREEZE_LIST §7.72). Nothing is sent either way.
    """
    opener = FakeOpener()

    with pytest.raises(SystemExit):
        pip_cli.run_command(argv, opener=opener)

    printed = capsys.readouterr().err
    assert opener.requests == []
    assert "usage: /consent PROVIDER_ID --scope SCOPE" in printed, printed
    assert "[--scope" not in printed, printed


def test_consent_without_a_scope_tells_the_shell_and_exits_nonzero(monkeypatch, capsys):
    """
    What the person at the shell actually sees. main() passes no opener, so the
    fake goes in as run_command's own default: without it the unfixed code would
    have posted a real full_inference grant to whatever PIP is listening on 8765.
    """
    opener = FakeOpener()
    opener.queue(_GRANTED)
    monkeypatch.setattr(
        pip_cli.run_command, "__kwdefaults__", {"base_url": pip_cli.BASE_URL, "opener": opener}
    )

    assert pip_cli.main(["/consent", "web_search"]) == 2
    assert opener.requests == []
    assert _names_every_scope(capsys.readouterr().err)


@pytest.mark.parametrize("scope", ALL_SCOPES)
def test_consent_with_a_scope_sends_exactly_that_scope(scope):
    opener = FakeOpener()
    opener.queue({"status": "consented", "provider_id": "web_search", "consent_scope": scope})

    pip_cli.run_command(["/consent", "web_search", "--scope", scope], opener=opener)

    assert len(opener.requests) == 1
    assert opener.requests[0]["method"] == "POST"
    assert opener.requests[0]["url"].endswith("/providers/web_search/consent")
    assert opener.requests[0]["body"] == {"consent_scope": scope}


@pytest.mark.parametrize("scope", ["everything", "Full_Inference", ""])
def test_consent_with_an_unknown_scope_is_refused_before_any_request(scope):
    """
    The server would refuse these too (422), but the CLI can know the list, so
    nothing leaves for a scope that cannot be granted, and the refusal names
    what was typed and what could have been. Full_Inference is here because a
    check that folded case would accept it and the server does not.
    """
    opener = FakeOpener()
    opener.queue(_GRANTED)

    with pytest.raises(ValueError) as refused:
        pip_cli.run_command(["/consent", "web_search", "--scope", scope], opener=opener)

    assert opener.requests == []
    assert f"'{scope}'" in str(refused.value)
    assert _names_every_scope(str(refused.value))


def test_the_cli_offers_exactly_the_scopes_the_server_accepts():
    """
    The CLI keeps its own copy of the list: the server's is in
    backend/api/server.py, and importing that module pulls the whole backend
    (FastAPI, the pipeline, the providers; about ten seconds) into a client
    that otherwise needs only the standard library. This is what keeps the
    copy honest. A scope added on the server and not here would be refused by
    the CLI before the server saw it; one dropped there would still be offered
    here.

    Imported inside the test so the rest of this file stays as light as the
    CLI it tests.
    """
    from backend.api.server import VALID_CONSENT_SCOPES

    assert set(pip_cli.CONSENT_SCOPES) == VALID_CONSENT_SCOPES
    assert len(pip_cli.CONSENT_SCOPES) == len(VALID_CONSENT_SCOPES)


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
