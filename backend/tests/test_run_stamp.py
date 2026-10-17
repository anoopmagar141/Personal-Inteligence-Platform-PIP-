"""
The run stamp every evaluation writes into its results (BLUEPRINT card S-1).

Two halves. The helper, scripts/_stamp.py, against a stub Ollama, a throwaway
git repository and the real Constitution: does it record what identifies the
run, and does it refuse to stamp a model run it cannot identify? And the
scripts: does each evaluation's result carry the stamp? A result without one
cannot be compared with any other, which is the defect this card exists for:
the observer harness stamped only with --save-raw, and the other four
recorded the model tag at most, never its digest or Ollama's version.
"""

import ast
import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _stamp  # noqa: E402

MODEL = "qwen2.5:7b"
DIGEST = "sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"


class _Ollama:
    """Answers the three read-only Ollama calls and records every request."""

    def __init__(self, models=None, version="0.40.3"):
        self.requests: list[tuple[str, str]] = []
        models = [{"name": MODEL, "model": MODEL, "digest": DIGEST}] if models is None else models
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                stub.requests.append(("GET", self.path))
                if self.path == "/api/version":
                    self._send({"version": version})
                elif self.path == "/api/tags":
                    self._send({"models": models})
                else:
                    self.send_error(404)

            def do_POST(self):
                stub.requests.append(("POST", self.path))
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.path == "/api/show":
                    self._send({"parameters": 'stop "<|im_end|>"'})
                else:
                    self.send_error(404)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def ollama():
    server = _Ollama()
    yield server
    server.close()


def _closed_port_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    server.server_close()
    return url


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


# --- the helper --------------------------------------------------------------


def test_a_model_run_records_the_weights_the_server_and_what_was_sent(ollama):
    stamp = _stamp.run_stamp(MODEL, options_sent={"temperature": None, "num_ctx": None}, host=ollama.url)

    assert stamp["ollama"] == {"host": ollama.url, "version": "0.40.3"}
    assert stamp["model"] == {"tag": MODEL, "digest": DIGEST, "parameters": 'stop "<|im_end|>"'}
    assert stamp["options_sent"] == {"temperature": None, "num_ctx": None}
    assert "not sent" in stamp["note"] or "null" in stamp["note"]
    # It only reads: nothing that runs, pulls or changes a model.
    assert ollama.requests == [("GET", "/api/version"), ("GET", "/api/tags"), ("POST", "/api/show")]


def test_a_model_the_server_does_not_have_is_refused(ollama):
    with pytest.raises(_stamp.StampError, match="llama3.1:8b"):
        _stamp.run_stamp("llama3.1:8b", host=ollama.url)


def test_a_model_with_no_digest_is_refused():
    server = _Ollama(models=[{"name": MODEL, "digest": ""}])
    try:
        with pytest.raises(_stamp.StampError, match="digest"):
            _stamp.run_stamp(MODEL, host=server.url)
    finally:
        server.close()


def test_a_server_that_does_not_report_its_version_is_refused():
    server = _Ollama(version="")
    try:
        with pytest.raises(_stamp.StampError, match="version"):
            _stamp.run_stamp(MODEL, host=server.url)
    finally:
        server.close()


def test_a_model_run_with_ollama_down_is_refused():
    with pytest.raises(_stamp.StampError):
        _stamp.run_stamp(MODEL, host=_closed_port_url())


def test_a_run_that_calls_no_model_needs_no_ollama():
    stamp = _stamp.run_stamp(None, host=_closed_port_url())

    assert stamp["ollama"] is None and stamp["model"] is None and stamp["options_sent"] is None
    assert stamp["note"] == "This run calls no model."


def test_the_commit_and_the_dirty_flag_come_from_git(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "code.py")
    _git(repo, "commit", "-q", "-m", "first")
    head = _git(repo, "rev-parse", "HEAD")

    clean = _stamp.run_stamp(None, repo_root=repo)["git"]
    assert clean == {"commit": head, "dirty": False, "changed": []}

    # An untracked file changes nothing the code does.
    (repo / "scratch.txt").write_text("notes", encoding="utf-8")
    assert _stamp.run_stamp(None, repo_root=repo)["git"]["dirty"] is False

    (repo / "code.py").write_text("x = 2\n", encoding="utf-8")
    dirty = _stamp.run_stamp(None, repo_root=repo)["git"]
    assert dirty == {"commit": head, "dirty": True, "changed": ["code.py"]}


def test_outside_a_git_checkout_the_commit_is_unknown_not_invented(tmp_path):
    assert _stamp.run_stamp(None, repo_root=tmp_path)["git"] == {"commit": None, "dirty": None, "changed": None}


def test_the_real_checkout_is_stamped_with_its_head():
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert _stamp.run_stamp(None)["git"]["commit"] == head


def test_the_constitution_is_stamped_by_version_and_by_content(tmp_path):
    real = (ROOT / "backend" / "core" / "constitutional.json").read_bytes().decode("utf-8").replace("\r\n", "\n")
    stamp = _stamp.run_stamp(None)["constitution"]
    assert stamp["version"] == json.loads(real)["version"]
    assert stamp["sha256"] == hashlib.sha256(real.encode("utf-8")).hexdigest()

    # The same rules hash the same with either line ending; a changed rule
    # hashes differently even when nobody bumped the version.
    def constitution_in(folder, text):
        path = folder / "backend" / "core"
        path.mkdir(parents=True)
        (path / "constitutional.json").write_bytes(text.encode("utf-8"))
        return _stamp.run_stamp(None, repo_root=folder)["constitution"]

    lf = constitution_in(tmp_path / "lf", '{"version": "1.0",\n "rule": "a"}\n')
    crlf = constitution_in(tmp_path / "crlf", '{"version": "1.0",\r\n "rule": "a"}\r\n')
    changed = constitution_in(tmp_path / "changed", '{"version": "1.0",\n "rule": "b"}\n')
    assert lf == crlf
    assert changed["version"] == lf["version"] and changed["sha256"] != lf["sha256"]


def test_the_report_lines_say_what_the_stamp_says(ollama):
    stamp = _stamp.run_stamp(MODEL, options_sent={"temperature": 0, "num_ctx": None}, host=ollama.url)
    text = _stamp.markdown(stamp)

    assert stamp["git"]["commit"] in text
    assert DIGEST in text and "Ollama 0.40.3" in text
    assert "temperature=0" in text and "num_ctx=not sent" in text
    assert "none recorded" in _stamp.markdown(None)
    assert "Run stamp 2 of 2 (a resumed run)" in _stamp.markdown([stamp, stamp])


def test_a_resumed_run_keeps_every_start_s_stamp(tmp_path):
    path = tmp_path / "state.json"
    first = _stamp.resumable_state(path, {"records": []}, {"date": "first"})
    assert first == {"records": [], "stamps": [{"date": "first"}]}
    path.write_text(json.dumps({"records": [1], "stamps": [{"date": "first"}]}), encoding="utf-8")

    resumed = _stamp.resumable_state(path, {"records": []}, {"date": "second"})

    assert resumed == {"records": [1], "stamps": [{"date": "first"}, {"date": "second"}]}


# --- every evaluation script -------------------------------------------------


def _calls(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                names.add(f"{f.value.id}.{f.attr}")
    return names


EVAL_SCRIPTS = sorted(p.name for p in SCRIPTS.glob("eval_*.py"))


def test_there_are_evaluation_scripts_to_check():
    assert len(EVAL_SCRIPTS) >= 5, EVAL_SCRIPTS


@pytest.mark.parametrize("name", EVAL_SCRIPTS)
def test_every_evaluation_script_stamps_its_run(name):
    # A new evaluation that forgets the stamp fails here, by name.
    assert "_stamp.run_stamp" in _calls(SCRIPTS / name), f"{name} does not call _stamp.run_stamp"


@pytest.mark.parametrize("name", ["eval_retrieval_e2e.py", "eval_retrieval_levers.py"])
def test_the_resumable_model_runs_keep_a_stamp_per_start(name):
    # Their generate step needs a running Ollama and minutes per question, so it
    # is not run here; what is pinned is that the state they write is built
    # with every start's stamp in it, and that their report prints it.
    calls = _calls(SCRIPTS / name)
    assert "_stamp.resumable_state" in calls and "_stamp.markdown" in calls


def test_the_evidence_gate_report_starts_with_the_stamp(capsys):
    import eval_evidence_gate

    eval_evidence_gate.evaluate()
    out = capsys.readouterr().out

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert out.lstrip().startswith("Run stamp:")
    assert head in out


def test_the_observer_results_carry_the_stamp_and_say_what_they_replayed(tmp_path, monkeypatch):
    import eval_observer_end_to_end as eval_script
    from backend.tests.observer_cases import CASES

    monkeypatch.setattr(eval_script, "CASES", [CASES[0]])
    recorded = {"date": "2026-10-12", "model": {"tag": MODEL, "digest": DIGEST}}
    raw = json.dumps({"memory_candidates": [], "decision_candidates": [], "session_snapshot": {
        "topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""}})
    replay = tmp_path / "recording.json"
    replay.write_text(json.dumps({"stamp": recorded, "runs": [[{"id": CASES[0]["id"], "raw": raw}]]}), encoding="utf-8")

    assert eval_script.main(["--replay", str(replay), "--json", str(tmp_path / "r.json"), "--out", str(tmp_path / "r.md")]) == 0

    result = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert result["stamp"]["git"]["commit"]
    assert result["stamp"]["model"] is None, "a replay calls no model"
    assert result["stamp"]["replayed_from"] == recorded
    assert "Run stamp:" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_the_retrieval_results_and_report_carry_the_stamp(tmp_path):
    # A subprocess: the --shim run installs a stand-in sentence_transformers,
    # which must not leak into the rest of the suite.
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "notes.md").write_text(
        "The backup runs every night at two. " * 5 + "Unrelated filler text about gardening. " * 20,
        encoding="utf-8",
    )
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps({
        "snapshot_commit": "local", "local_dir": str(docs), "corpus": ["notes.md"],
        "answerable": [{"id": "a1", "kind": "fact", "source": "notes.md",
                        "question": "When does the backup run?", "key": "every night at two"}],
        "off_topic": [{"id": "o1", "question": "What is the capital of Peru?"}],
        "near_topic": [{"id": "n1", "question": "How big is the backup?"}],
    }), encoding="utf-8")
    results, report = tmp_path / "results.json", tmp_path / "report.md"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PIP_")}
    python = sys.executable

    run = subprocess.run(
        [python, str(SCRIPTS / "eval_retrieval.py"), "run", "--labels", str(labels), "--out", str(results),
         "--chunk-sizes", "100", "--shim"],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    stamp = json.loads(results.read_text(encoding="utf-8"))["stamp"]
    assert stamp["git"]["commit"] and stamp["model"] is None

    rep = subprocess.run(
        [python, str(SCRIPTS / "eval_retrieval.py"), "report", "--results", str(results), "--out", str(report)],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300,
    )
    assert rep.returncode == 0, rep.stdout + rep.stderr
    assert stamp["git"]["commit"] in report.read_text(encoding="utf-8")
