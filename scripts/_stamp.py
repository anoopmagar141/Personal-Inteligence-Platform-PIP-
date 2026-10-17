"""
One run stamp for every evaluation result (BLUEPRINT card S-1).

A number from an evaluation is only comparable with another number if both
came from the same system, and "the same system" has more parts than the
result files used to record:

- The model tag is not the model. `qwen2.5:7b` names whatever weights were
  pulled under that tag last; a re-pull can point it at different ones. The
  digest is what identifies the weights.
- Ollama updates itself (it moved once during this project), and a new
  version can change sampling, templates and the default context window.
- What PIP sends changes what the model does. PIP sends no temperature and no
  num_ctx today, so Ollama's or the model's own default applies; a harness
  that pins temperature 0 measures something a user never sees.
- The code and the Constitution change from commit to commit, and a run made
  on a working tree with uncommitted edits is not reproducible from the
  commit alone.

Before this, one harness (eval_observer_end_to_end's --save-raw) stamped the
digest and the commit, each of the others recorded some subset by hand or
nothing, and a hand-written stamp drifts. So every evaluation calls
run_stamp() at the start of a run, before any number exists, and writes the
result into every result file and report it produces.

Standard library only, on purpose: eval_evidence_gate.py runs under any
interpreter (tests/test_venv_guard.py holds it to that) and calls this too.
It also only reads: it asks Ollama over HTTP and never runs the ollama CLI,
which starts the Ollama app when it is not running and can install an update.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
import urllib.error
import urllib.request
from typing import Any, Optional

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OLLAMA_HOST = "http://localhost:11434"
CONSTITUTION = pathlib.Path("backend") / "core" / "constitutional.json"

# A first call to a cold Ollama can take seconds while it starts; a short
# timeout would turn a slow start into "no stamp" (the old harness learned
# this: test_observer_replay pins at least 15 s).
_TIMEOUT_SECONDS = 15

OPTIONS_NOTE = (
    "options_sent lists what the harness put in Ollama's request options. A key "
    "whose value is null was not sent, so Ollama's or the model's own default "
    "applied (the model's own defaults are under model.parameters)."
)


class StampError(ValueError):
    """The run cannot say which model it used, so it must not produce a number."""


def _ollama(host: str, path: str, payload: Optional[dict] = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        host + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _git(repo_root: pathlib.Path, *args: str) -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _git_stamp(repo_root: pathlib.Path) -> dict[str, Any]:
    commit = _git(repo_root, "rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "dirty": None, "changed": None}
    # Tracked files only. Untracked notes and scratch files do not change what
    # the code does, and in a shared checkout there are always some; a flag
    # that is always true says nothing. The changed paths are listed so a
    # reader can see whether the edits touched backend/ or only docs/.
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no") or ""
    changed = sorted(line[3:].strip() for line in status.splitlines() if line.strip())
    return {"commit": commit.strip(), "dirty": bool(changed), "changed": changed}


def _constitution_stamp(repo_root: pathlib.Path) -> dict[str, Any]:
    path = repo_root / CONSTITUTION
    try:
        raw = path.read_bytes()
    except OSError:
        return {"version": None, "sha256": None}
    # The version string alone is not enough: the rules have changed without
    # it being bumped (BLUEPRINT G-5). The hash is of the text with line
    # endings made LF, so a Windows checkout (CRLF) and the committed blob (LF)
    # of the same rules get the same hash.
    text = raw.decode("utf-8").replace("\r\n", "\n")
    try:
        version = json.loads(text).get("version")
    except ValueError:
        version = None
    return {"version": version, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def run_stamp(
    model: Optional[str] = None,
    *,
    options_sent: Optional[dict[str, Any]] = None,
    host: str = OLLAMA_HOST,
    repo_root: pathlib.Path = REPO_ROOT,
) -> dict[str, Any]:
    """
    The stamp for a run that is about to start.

    model: the Ollama tag the run will call, or None for a run that calls no
    model (the evidence gate, retrieval-only measurement, a replay of recorded
    outputs). With a model, Ollama's version and the model's digest must both
    be readable, or StampError is raised: a result that cannot say which
    weights produced it is not one to keep.

    options_sent: what the harness puts in Ollama's request options, with None
    for a key it does not send (see OPTIONS_NOTE).
    """
    stamp: dict[str, Any] = {
        "stamp_version": 1,
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "git": _git_stamp(repo_root),
        "constitution": _constitution_stamp(repo_root),
        "ollama": None,
        "model": None,
        "options_sent": None,
    }
    if model is None:
        stamp["note"] = "This run calls no model."
        return stamp

    try:
        version = _ollama(host, "/api/version").get("version")
        tags = _ollama(host, "/api/tags").get("models", [])
    except (OSError, urllib.error.URLError, ValueError) as exc:
        raise StampError(f"Cannot read Ollama's version and the model digest from {host}: {exc}") from exc
    if not isinstance(version, str) or not version.strip():
        raise StampError(f"Ollama at {host} did not report its version")
    digest = next((m.get("digest") for m in tags if m.get("name") == model or m.get("model") == model), None)
    if not isinstance(digest, str) or not digest.strip():
        raise StampError(f"Ollama model {model!r} is missing or has no digest")

    # The model's own defaults (its Modelfile PARAMETER lines). Best effort:
    # useful for reading options_sent, not needed to identify the weights.
    try:
        parameters = _ollama(host, "/api/show", {"model": model}).get("parameters")
    except (OSError, urllib.error.URLError, ValueError):
        parameters = None

    stamp["ollama"] = {"host": host, "version": version}
    stamp["model"] = {"tag": model, "digest": digest, "parameters": parameters}
    stamp["options_sent"] = dict(options_sent or {})
    stamp["note"] = OPTIONS_NOTE
    return stamp


def resumable_state(path, initial: dict[str, Any], stamp: dict[str, Any]) -> dict[str, Any]:
    """
    The state of a run that can be stopped and resumed (the retrieval
    harnesses save after every answer): the saved one if the file exists,
    otherwise `initial`, with this start's stamp appended to state["stamps"].

    A list, not one stamp, because a resumed run is several runs: if Ollama
    updated itself or the commit moved between two starts, the answers in one
    file came from two systems, and the report has to be able to say so.
    """
    path = pathlib.Path(path)
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    else:
        state = dict(initial)
    state.setdefault("stamps", []).append(stamp)
    return state


def markdown(stamps) -> str:
    """
    The stamp, or a list of stamps (one per start of a resumable run), as
    lines for the top of a report. A result file from before stamps existed
    says so, rather than leaving the reader to assume one.
    """
    if not stamps:
        return "Run stamp: none recorded (this result predates run stamps, BLUEPRINT S-1).\n"
    if isinstance(stamps, dict):
        stamps = [stamps]
    lines = []
    for index, stamp in enumerate(stamps, 1):
        label = "Run stamp" if len(stamps) == 1 else f"Run stamp {index} of {len(stamps)} (a resumed run)"
        git = stamp.get("git") or {}
        constitution = stamp.get("constitution") or {}
        dirty = git.get("dirty")
        dirty_text = "unknown" if dirty is None else ("yes: " + ", ".join(git.get("changed") or [])) if dirty else "no"
        lines.append(f"{label}: {stamp.get('date')}")
        lines.append(f"- commit {git.get('commit')}, uncommitted changes to tracked files: {dirty_text}")
        lines.append(
            f"- Constitution version {constitution.get('version')}, sha256 {constitution.get('sha256')}"
        )
        model = stamp.get("model")
        if model is None:
            lines.append(f"- model: none ({stamp.get('note', 'this run calls no model')})")
        elif not isinstance(model, dict):
            # The observer harness's own stamp before S-1 kept the tag as a
            # string and the digest beside it (observer_raw_recording_2026-10-12).
            lines.append(f"- model {model}, digest {stamp.get('digest')} (an older stamp)")
        else:
            ollama = stamp.get("ollama") or {}
            lines.append(f"- model {model.get('tag')}, digest {model.get('digest')}; Ollama {ollama.get('version')}")
            sent = stamp.get("options_sent") or {}
            shown = ", ".join(f"{k}={'not sent' if v is None else v}" for k, v in sent.items()) or "none"
            lines.append(f"- options sent: {shown}")
        for key, value in stamp.items():
            if key not in {"stamp_version", "date", "git", "constitution", "ollama", "model", "options_sent", "note"}:
                lines.append(f"- {key}: {json.dumps(value, sort_keys=True)}")
    return "\n".join(lines) + "\n"
