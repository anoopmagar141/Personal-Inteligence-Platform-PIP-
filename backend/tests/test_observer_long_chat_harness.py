"""
The Observer harness's additions for V-2 part (a), the long chats
(scripts/eval_observer_end_to_end.py).

What these protect: the long-chat numbers are only worth something if the
harness measures the shipped call. So the counts are read by wrapping Ollama's
response, and the request is pinned to be byte-for-byte what OllamaProvider
sends; the profile age a case asks for must reach the Constitution; and a
planted statement's position must reach the results, or "learned by position"
cannot be computed.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import eval_observer_end_to_end as harness  # noqa: E402
from backend.providers.ollama_provider import OllamaProvider  # noqa: E402
from backend.tests.observer_cases import CASES  # noqa: E402


class _Ollama:
    """Records every request body; answers /api/chat with a short stream ending in counts."""

    def __init__(self):
        self.bodies: list[tuple[str, dict]] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                stub.bodies.append((self.path, body))
                if body.get("stream") is False:
                    payload = json.dumps({"done": True, "prompt_eval_count": 7777}).encode()
                else:
                    payload = b"".join(json.dumps(c).encode() + b"\n" for c in [
                        {"message": {"content": "{}"}, "done": False},
                        {"message": {"content": ""}, "done": True, "prompt_eval_count": 2050,
                         "eval_count": 3, "done_reason": "stop", "load_duration": 4_000_000_000},
                    ])
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

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


def test_the_counted_request_is_the_app_s_request_and_its_counts_are_kept(ollama):
    import urllib.request
    real_urlopen = urllib.request.urlopen
    messages = [{"role": "user", "content": "extract from this"}]

    app = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)
    app_tokens = list(app.chat(messages, max_tokens=2000, timeout_seconds=30))
    recorder = harness.RecordingProvider("qwen2.5:7b")
    recorder.host = ollama.url
    recorder_tokens = list(recorder.chat(messages, max_tokens=2000, timeout_seconds=30))

    assert ollama.bodies[0] == ollama.bodies[1], "the harness changed what is sent"
    assert "num_ctx" not in ollama.bodies[1][1]["options"], "the shipped call sends no window"
    assert recorder_tokens == app_tokens and "".join(recorder_tokens) == "{}"
    assert recorder.counts["prompt_eval_count"] == 2050
    assert recorder.counts["done_reason"] == "stop"
    # The wrapper is removed afterwards: nothing else in the process is counted.
    assert urllib.request.urlopen is real_urlopen


def test_counting_the_whole_prompt_uses_a_big_window_and_unloads(ollama):
    messages = [{"role": "user", "content": "x " * 50}]

    assert harness.count_prompt_tokens(ollama.url, "qwen2.5:7b", messages, 16384) == 7777

    path, body = ollama.bodies[-1]
    assert path == "/api/chat"
    assert body["messages"] == messages
    assert body["options"]["num_ctx"] == 16384 and body["options"]["num_predict"] == 1
    assert body["keep_alive"] == 0


def test_unloading_asks_ollama_to_drop_the_model(ollama):
    harness.unload_model(ollama.url, "qwen2.5:7b")

    assert ollama.bodies[-1] == ("/api/generate", {"model": "qwen2.5:7b", "keep_alive": 0})


def _recorded_raw(case_id: str) -> str:
    recording = json.loads((ROOT / "docs" / "eval" / "observer_raw_recording_2026-10-12.json").read_text(encoding="utf-8"))
    return next(item["raw"] for item in recording["runs"][0] if item["id"] == case_id)


def test_a_case_file_with_ages_and_positions_reaches_the_results(tmp_path):
    # The same recorded extraction ("I use Neovim for all my coding"), on a
    # profile in its first week and on one nine weeks old. In week 1 one
    # explicit statement is enough to write it; at nine weeks the Constitution
    # wants three, so the same output is not written.
    base = next(c for c in CASES if c["id"] == "fact_editor")
    spec = {**base["learn"][0], "position": "middle", "kind": "fact", "id": "F1"}
    cases = [
        {**base, "id": "young", "profile_age_days": 7, "learn": [spec]},
        {**base, "id": "old", "profile_age_days": 63, "learn": [spec]},
    ]
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps(cases), encoding="utf-8")
    raw = _recorded_raw("fact_editor")
    replay = tmp_path / "replay.json"
    replay.write_text(json.dumps({"runs": [[{"id": "young", "raw": raw}, {"id": "old", "raw": raw}]]}), encoding="utf-8")

    assert harness.main(["--cases", str(cases_file), "--replay", str(replay), "--json", str(tmp_path / "r.json")]) == 0

    results = {r["id"]: r for r in json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["runs"][0]}
    assert results["young"]["facts"][0]["learned"] == ["written"]
    assert results["old"]["facts"][0]["learned"] == []
    assert {k: results["old"]["facts"][0][k] for k in ("position", "kind", "id")} == {
        "position": "middle", "kind": "fact", "id": "F1"}
    assert "_messages" not in results["young"]


def test_the_long_chat_cases_are_built_as_the_protocol_says():
    built = json.loads((ROOT / "docs" / "eval" / "v2_2026-10-17" / "long_chats" / "long_chat_cases.json")
                       .read_text(encoding="utf-8"))

    assert len(built) == 27
    assert {c["profile_age_days"] for c in built} == {7, 21, 63}
    for case in built:
        positions = {(s["id"], s["position"]) for s in case["learn"] + case["avoid"]}
        assert len(positions) == 9
        # Every planted statement is in the transcript the Observer is given.
        for keyword in [k for s in case["learn"] + case["avoid"] for k in s["keywords"]]:
            assert keyword in case["transcript"].lower(), (case["id"], keyword)
    # Each fact sits at each position once per length and age (the Latin square).
    for length in "SML":
        for days in (7, 21, 63):
            seen = {(s["id"], s["position"]) for c in built
                    if c["length"] == length and c["profile_age_days"] == days for s in c["learn"]}
            assert seen == {(f, p) for f in ("F1", "F2", "F3") for p in ("start", "middle", "end")}
