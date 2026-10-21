import argparse
import importlib.util
import json
import pathlib
import sys
from typing import Any, Callable
from urllib import parse, request


BASE_URL = "http://localhost:8765/api/v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# The scopes POST /providers/<id>/consent accepts. This MUST hold the same
# values as VALID_CONSENT_SCOPES in backend/api/server.py, the list the server
# refuses a grant against; test_cli.py's
# test_the_cli_offers_exactly_the_scopes_the_server_accepts fails when the two
# part. (The same four are also written out in backend/core/constitutional.json,
# provider_consent.scope_values, and in the CHECK on provider_consent in
# backend/core/schema.sql.) It is a copy rather than an import because
# importing server.py pulls the whole backend - FastAPI, the pipeline, the
# providers, about ten seconds - into a client that otherwise imports nothing
# but the standard library and talks to the backend only over HTTP.
#
# Narrowest first, as the Flutter dialog lists them. Once there is no default
# (D-30, below in _consent) the order a refusal lists the choices in is the
# nearest a typed command comes to preselecting one, and leading with the
# broadest would be that. "none" is last: the server accepts it, but it records
# a consent to nothing, which Flutter leaves out for that reason and /revoke
# says without the ambiguity. It stays here because this list is the server's.
CONSENT_SCOPES = ("embedding_only", "web_search_only", "full_inference", "none")


def request_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    base_url: str = BASE_URL,
    opener: Callable = request.urlopen,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(
        f"{base_url}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with opener(req) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else None


def run_command(argv: list[str], *, base_url: str = BASE_URL, opener: Callable = request.urlopen) -> Any:
    if not argv:
        raise ValueError("command is required")

    command = argv[0]
    args = argv[1:]

    if command == "/profile":
        return _profile(args, base_url=base_url, opener=opener)
    if command == "/decide":
        return _decide(args, base_url=base_url, opener=opener)
    if command == "/decisions":
        return _decisions(args, base_url=base_url, opener=opener)
    if command == "/pending":
        return _pending(args, base_url=base_url, opener=opener)
    if command == "/providers":
        return _providers(args, base_url=base_url, opener=opener)
    if command == "/consent":
        return _consent(args, base_url=base_url, opener=opener)
    if command == "/revoke":
        return _revoke(args, base_url=base_url, opener=opener)
    if command == "/ingest":
        return _ingest(args, base_url=base_url, opener=opener)
    if command == "/documents":
        return _documents(args, base_url=base_url, opener=opener)
    if command == "/remove":
        return _remove(args, base_url=base_url, opener=opener)

    # The two commands below take no opener and no base_url, and that is the
    # whole design rather than an oversight. Every command above talks to the
    # backend over REST; these run locally, in this process, against the
    # database file directly.
    #
    # ADR-027 is explicit about why /export must not be an endpoint: the live
    # connection is already open with the real key, so an HTTP route doing this
    # work would let anything that can read data/api_token.txt - which is any
    # process running as this user - obtain a complete copy of the database
    # re-encrypted under a password of its own choosing, without ever knowing
    # the live key. That is precisely the capability the password model exists
    # to withhold. /restore inherits the argument and adds its own: it replaces
    # the file the running backend has open, and refuses to run at all while
    # PIP holds the lock.
    #
    # So the slash command is a front door to the script, not to the API. It
    # grants no capability the person at this shell did not already have.
    if command == "/export":
        return _export(args)
    if command == "/restore":
        return _restore(args)

    raise ValueError(f"unknown command: {command}")


def _load_script(name: str):
    """
    Load a module from scripts/, which is a directory and not a package.

    scripts/ goes on sys.path first because each script reaches its sibling
    _venv helper by plain import - that works when the script is the entry
    point and sys.path[0] is its own directory, and not otherwise.

    In-process rather than a subprocess, so getpass reads from the terminal the
    user is already sitting at and the script's own prompts, warnings and
    progress lines land where they expect them.
    """
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _export(args: list[str]) -> Any:
    """
    /export                      -> data/pip_backup_YYYYMMDD.pipbak, encrypted
    /export --out PATH           -> the same, somewhere you chose
    /export --readable --out P   -> a plaintext JSON dump, with a warning first

    Flags pass straight through rather than being re-parsed here: one argument
    parser for this command, in the script that owns it, so a flag can never
    mean one thing typed as a slash command and another typed at a shell.
    """
    path = _load_script("export_backup").main(args)
    return {"status": "exported", "file": str(path)}


def _restore(args: list[str]) -> Any:
    """
    /restore              -> the newest .pipbak in data/
    /restore FILE         -> that one

    A bare first argument is the file, per the command's specified form. It is
    translated to --from rather than added as a positional to the script, which
    keeps `python scripts/restore_backup.py` reading exactly as its own
    docstring has always documented it.
    """
    if args and not args[0].startswith("-"):
        argv = ["--from", args[0], *args[1:]]
    else:
        argv = list(args)

    code = _load_script("restore_backup").main(argv)
    if code != 0:
        # The script has already printed why and left the data directory
        # untouched; this turns its exit code into the nonzero exit main()
        # gives every other failure, rather than printing a cheerful status.
        raise RuntimeError("restore did not complete - nothing was replaced")
    return {"status": "restored"}


def _profile(args: list[str], *, base_url: str, opener: Callable) -> Any:
    if not args:
        return request_json("GET", "/memory/profile", base_url=base_url, opener=opener)

    action = args[0]
    if action == "edit" and len(args) >= 3:
        return request_json(
            "POST",
            "/memory/correct",
            {"field": args[1], "value": " ".join(args[2:])},
            base_url=base_url,
            opener=opener,
        )
    if action == "delete" and len(args) == 2:
        field = parse.quote(args[1])
        return request_json("DELETE", f"/memory/profile/{field}", base_url=base_url, opener=opener)

    raise ValueError("usage: /profile [edit FIELD VALUE | delete FIELD]")


def _decide(args: list[str], *, base_url: str, opener: Callable) -> Any:
    parser = argparse.ArgumentParser(prog="/decide", add_help=False)
    parser.add_argument("text", nargs="+")
    parser.add_argument("--reasoning")
    parser.add_argument("--alternatives")
    parser.add_argument("--project-id")
    parsed = parser.parse_args(args)
    return request_json(
        "POST",
        "/decision/create",
        {
            "text": " ".join(parsed.text),
            "reasoning": parsed.reasoning,
            "alternatives": parsed.alternatives,
            "project_id": parsed.project_id,
        },
        base_url=base_url,
        opener=opener,
    )


def _decisions(args: list[str], *, base_url: str, opener: Callable) -> Any:
    if not args:
        return request_json("GET", "/decision/search", base_url=base_url, opener=opener)

    if args[0] == "search" and len(args) >= 2:
        query = parse.urlencode({"q": " ".join(args[1:])})
        return request_json("GET", f"/decision/search?{query}", base_url=base_url, opener=opener)

    if len(args) >= 3 and args[1] in {"supersede", "abandon"}:
        decision_id = int(args[0])
        state = "superseded" if args[1] == "supersede" else "abandoned"
        reason = _extract_reason(args[2:])
        return request_json(
            "PATCH",
            f"/decision/{decision_id}/state",
            {"state": state, "reason": reason},
            base_url=base_url,
            opener=opener,
        )

    raise ValueError("usage: /decisions [search QUERY | ID supersede --reason REASON | ID abandon --reason REASON]")


def _pending(args: list[str], *, base_url: str, opener: Callable) -> Any:
    if not args:
        return request_json("GET", "/decision/pending", base_url=base_url, opener=opener)

    if len(args) == 2 and args[0] == "review":
        pending = request_json("GET", "/decision/pending", base_url=base_url, opener=opener)
        candidate_id = int(args[1])
        return next((row for row in pending if row["id"] == candidate_id), None)

    if len(args) == 2 and args[0] in {"promote", "dismiss"}:
        candidate_id = int(args[1])
        return request_json(
            "POST",
            f"/decision/pending/{candidate_id}/{args[0]}",
            base_url=base_url,
            opener=opener,
        )

    raise ValueError("usage: /pending [review ID | promote ID | dismiss ID]")


def _extract_reason(args: list[str]) -> str:
    if args[0] == "--reason" and len(args) >= 2:
        return " ".join(args[1:])
    return " ".join(args)


def _providers(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /providers"""
    return request_json("GET", "/providers", base_url=base_url, opener=opener)


def _consent(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /consent PROVIDER_ID --scope SCOPE

    Grant consent for PROVIDER_ID, for SCOPE only. There is no default scope:
    SCOPE must be typed, and is one of CONSENT_SCOPES.
    Example: /consent web_search --scope web_search_only
    """
    # The usage line is given, not generated: argparse would print "[--scope
    # CONSENT_SCOPE] provider_id" for input it refuses itself (a missing value, a
    # missing provider), the scope in brackets as if optional, beside a refusal
    # saying there is no default (found reviewing D-30, FREEZE_LIST §7.72).
    parser = argparse.ArgumentParser(prog="/consent", add_help=False, usage="/consent PROVIDER_ID --scope SCOPE")
    parser.add_argument("provider_id")
    # No default, and that absence is the fix for D-30 (FREEZE_LIST §7.51).
    # This was default="full_inference": typing `/consent web_search` granted
    # the broadest of the four scopes - your prompts and assembled context sent
    # to the provider - when the person had chosen nothing at all. Promise 6
    # rules out a default the person did not choose; the Flutter dialog
    # preselects nothing and the old web client no longer grants at all (G-6).
    # So a missing scope is refused here, before any request, with the scopes
    # it could have been named in the refusal.
    parser.add_argument("--scope", dest="consent_scope", metavar="SCOPE")
    parsed = parser.parse_args(args)

    usage = f"usage: /consent PROVIDER_ID --scope SCOPE, where SCOPE is one of: {', '.join(CONSENT_SCOPES)}"
    if parsed.consent_scope is None:
        raise ValueError(f"/consent needs a scope; there is no default.\n{usage}")
    # Refused here rather than left to the server, which would refuse it too
    # (422) - but urllib turns that into "HTTP Error 422: Unprocessable Entity"
    # with the server's reason dropped, so the person would learn that it
    # failed and not which scopes there are. A ValueError rather than argparse's
    # choices=, whose error is a SystemExit from inside run_command that main()
    # does not catch; the hand-written usage errors here (/profile, /revoke,
    # /remove) are ValueErrors too.
    if parsed.consent_scope not in CONSENT_SCOPES:
        raise ValueError(f"unknown scope '{parsed.consent_scope}'.\n{usage}")
    return request_json(
        "POST",
        f"/providers/{parsed.provider_id}/consent",
        {"consent_scope": parsed.consent_scope},
        base_url=base_url,
        opener=opener,
    )


def _revoke(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /revoke PROVIDER_ID"""
    if not args:
        raise ValueError("usage: /revoke PROVIDER_ID")
    provider_id = args[0]
    return request_json(
        "POST",
        f"/providers/{provider_id}/revoke",
        base_url=base_url,
        opener=opener,
    )


def _ingest(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /ingest FILE_PATH [--project-id ID]"""
    parser = argparse.ArgumentParser(prog="/ingest", add_help=False)
    parser.add_argument("file_path")
    parser.add_argument("--project-id")
    parsed = parser.parse_args(args)
    return request_json(
        "POST",
        "/rag/ingest",
        {"file_path": parsed.file_path, "project_id": parsed.project_id},
        base_url=base_url,
        opener=opener,
    )


def _documents(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /documents"""
    return request_json("GET", "/rag/documents", base_url=base_url, opener=opener)


def _remove(args: list[str], *, base_url: str, opener: Callable) -> Any:
    """Usage: /remove FILE_PATH

    NOTE: file_path is used as the document's REST identifier (there is no
    separate document id). Path separators are percent-encoded with safe=""
    so a Windows path's backslashes/colons/forward-slashes all survive as a
    single path segment.
    """
    if not args:
        raise ValueError("usage: /remove FILE_PATH")
    ref = parse.quote(args[0], safe="")
    return request_json("DELETE", f"/rag/documents/{ref}", base_url=base_url, opener=opener)


def main(argv: list[str] | None = None) -> int:
    try:
        result = run_command(argv or sys.argv[1:])
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
