import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import json
import tempfile
import pytest

from eval_observer_end_to_end import main
import eval_observer_end_to_end as eval_script
from backend.tests.observer_cases import CASES

def test_observer_replay_reproduces_live_funnel(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_script, "CASES", [CASES[0]])
    monkeypatch.setattr(eval_script, "get_stamp", lambda model: {"model": model, "wall_clock_seconds": []})
    
    class CannedProvider(eval_script.RecordingProvider):
        def chat(self, *args, **kwargs):
            if self._is_replay:
                yield self.raw
                return
            canned_text = json.dumps({
                "memory_candidates": [{
                    "target_table": "preference_memory",
                    "field_name": "preferred_tools",
                    "proposed_value": "Neovim",
                    "label": "explicit",
                    "evidence_count": 1,
                    "evidence_text": "I use Neovim for all my coding"
                }],
                "decision_candidates": [],
                "session_snapshot": {
                    "topic": "test topic",
                    "open_problems": [],
                    "last_decisions": [],
                    "suggested_next_step": "next"
                }
            })
            self.raw = canned_text
            yield canned_text

    monkeypatch.setattr(eval_script, "RecordingProvider", CannedProvider)
    
    save_file = tmp_path / "save.json"
    json_out1 = tmp_path / "out1.json"
    
    res1 = main(["--only", CASES[0]["id"], "--save-raw", str(save_file), "--json", str(json_out1)])
    assert res1 == 0
    assert save_file.exists()
    
    json_out2 = tmp_path / "out2.json"
    res2 = main(["--only", CASES[0]["id"], "--replay", str(save_file), "--json", str(json_out2)])
    assert res2 == 0
    
    with open(json_out1) as f:
        out1 = json.load(f)
    with open(json_out2) as f:
        out2 = json.load(f)
        
    # --json holds {"stamp", "runs"} since every result carries its run stamp (S-1).
    assert out1["runs"][0][0]["funnel"] == out2["runs"][0][0]["funnel"]
    assert out1["runs"][0][0]["learned"] == out2["runs"][0][0]["learned"]

def test_observer_replay_break_it(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_script, "CASES", [CASES[0]])
    monkeypatch.setattr(eval_script, "get_stamp", lambda model: {"model": model, "wall_clock_seconds": []})
    
    class CannedProvider(eval_script.RecordingProvider):
        def chat(self, *args, **kwargs):
            if self._is_replay:
                yield self.raw
                return
            canned_text = json.dumps({
                "memory_candidates": [{
                    "target_table": "preference_memory",
                    "field_name": "preferred_tools",
                    "proposed_value": "Neovim",
                    "label": "explicit",
                    "evidence_count": 1,
                    "evidence_text": "I use Neovim for all my coding"
                }],
                "decision_candidates": [],
                "session_snapshot": {
                    "topic": "test topic",
                    "open_problems": [],
                    "last_decisions": [],
                    "suggested_next_step": "next"
                }
            })
            self.raw = canned_text
            yield canned_text

    monkeypatch.setattr(eval_script, "RecordingProvider", CannedProvider)
    
    save_file = tmp_path / "save.json"
    json_out1 = tmp_path / "out1.json"
    
    res1 = main(["--only", CASES[0]["id"], "--save-raw", str(save_file), "--json", str(json_out1)])
    assert res1 == 0
    
    with open(save_file) as f:
        data = json.load(f)
        
    data["runs"][0][0]["raw"] = json.dumps({
        "memory_candidates": [{
            "target_table": "preference_memory",
            "field_name": "preferred_tools",
            "proposed_value": "VSCode",
            "label": "explicit",
            "evidence_count": 1,
            "evidence_text": "I use Neovim for all my coding"
        }],
        "decision_candidates": [],
        "session_snapshot": {
            "topic": "test topic",
            "open_problems": [],
            "last_decisions": [],
            "suggested_next_step": "next"
        }
    })
    
    with open(save_file, "w") as f:
        json.dump(data, f)
        
    json_out2 = tmp_path / "out2.json"
    res2 = main(["--only", CASES[0]["id"], "--replay", str(save_file), "--json", str(json_out2)])
    
    with open(json_out1) as f:
        out1 = json.load(f)
    with open(json_out2) as f:
        out2 = json.load(f)
        
    assert out1["runs"][0][0]["funnel"] != out2["runs"][0][0]["funnel"] or out1["runs"][0][0]["learned"] != out2["runs"][0][0]["learned"]


def test_replay_refuses_missing_case_before_running_any_model(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_script, "CASES", [CASES[0], CASES[1]])
    raw_file = tmp_path / "incomplete.json"
    raw_file.write_text(json.dumps({"runs": [[{"id": CASES[0]["id"], "raw": "{}"}]]}))
    monkeypatch.setattr(
        eval_script, "run_case",
        lambda *args, **kwargs: pytest.fail("incomplete replay must not invoke a provider"),
    )

    with pytest.raises(SystemExit) as exc:
        main(["--replay", str(raw_file)])

    assert exc.value.code == 2


class _FakeOllama:
    """
    Stands in for urlopen against Ollama. get_stamp goes through the shared
    run stamp (scripts/_stamp.py, BLUEPRINT S-1), which asks for Ollama's
    version as well as the model list, so the fake answers by path.
    """

    def __init__(self, digest):
        self.digest = digest
        self.kwargs = []

    def __call__(self, request, **kwargs):
        self.kwargs.append(kwargs)
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url.endswith("/api/version"):
            body = {"version": "0.40.3"}
        elif url.endswith("/api/tags"):
            body = {"models": [{"name": "qwen2.5:7b", "digest": self.digest}]}
        else:
            body = {}
        return _Response(body)


class _Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def test_recording_stamp_requires_a_model_digest(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _FakeOllama(""))

    with pytest.raises(ValueError, match="digest"):
        eval_script.get_stamp("qwen2.5:7b")


def test_recording_stamp_allows_ollama_startup_time(monkeypatch):
    import urllib.request
    fake = _FakeOllama("sha256:test")
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(eval_script, "get_settings", lambda: {"observer": {"max_session_tokens": 8000}})

    eval_script.get_stamp("qwen2.5:7b")

    assert fake.kwargs and all(k["timeout"] >= 15 for k in fake.kwargs)


def test_recording_stamp_does_not_call_transcript_cap_model_context(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _FakeOllama("sha256:test"))
    monkeypatch.setattr(eval_script, "get_settings", lambda: {"observer": {"max_session_tokens": 8000}})

    stamp = eval_script.get_stamp("qwen2.5:7b")

    # The window recorded is the one the app's provider sends (W-1: the settings
    # block), and the transcript cap is kept apart from it rather than passed off as it.
    from backend.config.settings import get_settings
    assert stamp["options_sent"]["num_ctx"] == get_settings()["llm"]["num_ctx"]
    assert stamp["transcript_token_cap"] == 8000
