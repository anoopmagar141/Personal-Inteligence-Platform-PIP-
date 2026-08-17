import argparse
import json
import sys
from typing import Any, Callable
from urllib import parse, request


BASE_URL = "http://localhost:8765/api/v1"


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

    raise ValueError(f"unknown command: {command}")


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
    """Usage: /consent PROVIDER_ID [--scope SCOPE]

    Grant consent for PROVIDER_ID. Default scope: full_inference.
    Example: /consent web_search --scope web_search_only
    """
    parser = argparse.ArgumentParser(prog="/consent", add_help=False)
    parser.add_argument("provider_id")
    parser.add_argument("--scope", default="full_inference", dest="consent_scope")
    parsed = parser.parse_args(args)
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
