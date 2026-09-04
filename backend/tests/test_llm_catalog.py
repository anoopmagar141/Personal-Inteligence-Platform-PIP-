"""
Tests for choosing and pulling a model.

The feature is "any open-source model", and the two halves that phrase implies
pull against each other:

  ANY. The catalogue must never be a limit. Ollama has no library API, so a
  curated list is guidance at best - and a picker that only offers seven names
  would be a worse product than the terminal it replaced.

  THAT WILL ACTUALLY RUN. An 8GB card cannot hold a 14B model, and finding that
  out after a 9GB download and a session of swapping is finding out too late.

So the catalogue warns and never refuses, and the pull endpoint accepts a name
it has never heard of and lets Ollama be the judge of whether it exists.
"""

import threading
import time

import pytest

from backend.api import server
from backend.providers import ollama_provider


@pytest.fixture(autouse=True)
def idle_pull_state():
    """
    The pull state is module-level, so a test that leaves it 'pulling' would
    make the next one fail for a reason that has nothing to do with it.
    """
    with server._pull_lock:
        server._pull_state.update(status="idle", model=None, completed=0,
                                  total=0, detail="", error=None)
    yield
    with server._pull_lock:
        server._pull_state.update(status="idle", model=None, completed=0,
                                  total=0, detail="", error=None)


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------


def test_the_catalogue_renders_when_ollama_is_unreachable(monkeypatch):
    """
    The case that matters most, and the easiest one to get backwards: choosing
    a model to pull is exactly what you do when nothing is pulled yet, which is
    frequently when Ollama is not up. A picker that 500s here would be useless
    at the only moment it is needed.
    """
    def _refuse(*_a, **_k):
        raise ollama_provider.ProviderUnavailableError("connection refused")

    monkeypatch.setattr(ollama_provider, "list_models", _refuse)

    result = server.api_llm_catalog()

    assert result["models"], "the catalogue vanished because Ollama was down"
    assert result["error"]
    assert all(m["pulled"] is False for m in result["models"])


def test_a_model_too_big_for_the_card_is_flagged(monkeypatch):
    monkeypatch.setattr(ollama_provider, "list_models", lambda *a, **k: [])
    monkeypatch.setattr(ollama_provider, "detect_vram_gb", lambda: 8.0)

    by_name = {m["name"]: m for m in server.api_llm_catalog()["models"]}

    assert by_name["qwen2.5:14b"]["fits"] is False
    assert by_name["llama3.1:8b"]["fits"] is True


def test_unknown_vram_is_null_rather_than_a_guess(monkeypatch):
    """
    A machine with no NVIDIA GPU is not a machine where every model fails - it
    is one where this cannot tell. False would be a claim; null is the truth,
    and the client shows a warning only for an explicit false.
    """
    monkeypatch.setattr(ollama_provider, "list_models", lambda *a, **k: [])
    monkeypatch.setattr(ollama_provider, "detect_vram_gb", lambda: None)

    result = server.api_llm_catalog()

    assert result["vram_gb"] is None
    assert all(m["fits"] is None for m in result["models"])


def test_a_pulled_model_the_catalogue_never_heard_of_is_still_listed(monkeypatch):
    """
    The curated list is guidance, not an allowlist. A model the user pulled
    themselves must not disappear from their own picker.
    """
    monkeypatch.setattr(
        ollama_provider, "list_models",
        lambda *a, **k: [{"name": "some-obscure-model:latest", "size": 3 * 1024 ** 3}],
    )

    models = server.api_llm_catalog()["models"]
    obscure = [m for m in models if m["name"] == "some-obscure-model:latest"]

    assert len(obscure) == 1
    assert obscure[0]["pulled"] is True
    assert obscure[0]["size_gb"] == 3.0
    assert obscure[0]["fits"] is None, "nothing is known about an uncatalogued model's needs"


def test_a_catalogued_model_that_is_pulled_says_so(monkeypatch):
    monkeypatch.setattr(
        ollama_provider, "list_models",
        lambda *a, **k: [{"name": "llama3.1:8b", "size": 4_700_000_000}],
    )

    by_name = {m["name"]: m for m in server.api_llm_catalog()["models"]}

    assert by_name["llama3.1:8b"]["pulled"] is True
    assert by_name["mistral:7b"]["pulled"] is False


def test_detect_vram_returns_none_rather_than_raising(monkeypatch):
    """No nvidia-smi is an answer, not a failure."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _name: None)

    assert ollama_provider.detect_vram_gb() is None


# ---------------------------------------------------------------------------
# Pulling
# ---------------------------------------------------------------------------


def _wait_until(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_a_pull_reports_progress_as_it_goes(monkeypatch):
    events = [
        {"status": "pulling manifest"},
        {"status": "downloading", "completed": 500, "total": 1000},
        {"status": "downloading", "completed": 1000, "total": 1000},
        {"status": "success"},
    ]
    started = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434"):
        started.set()
        for event in events:
            on_progress(event)

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert started.wait(5)
    assert _wait_until(lambda: server.api_pull_status()["status"] == "done")

    final = server.api_pull_status()
    assert final["model"] == "qwen2.5:7b"
    assert final["completed"] == final["total"] == 1000
    assert final["error"] is None


def test_statuses_without_byte_counts_do_not_reset_the_bar(monkeypatch):
    """
    Ollama interleaves manifest and verify statuses that carry no totals. Letting
    those overwrite the counters makes a progress bar that jumps back to zero
    several times during one download - which reads as a restart, not a step.
    """
    def fake_pull(name, on_progress, host="http://localhost:11434"):
        on_progress({"status": "downloading", "completed": 900, "total": 1000})
        on_progress({"status": "verifying sha256 digest"})

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "mistral:7b"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "done")

    assert server.api_pull_status()["completed"] == 1000


def test_a_name_ollama_does_not_know_surfaces_as_an_error(monkeypatch):
    """
    The cost of accepting free text, and the reason it is still right: Ollama is
    a better judge of what exists in its own library than any list PIP ships.
    """
    def fake_pull(name, on_progress, host="http://localhost:11434"):
        raise ollama_provider.ProviderExecutionError(
            f"Ollama could not pull '{name}': file does not exist"
        )

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "not-a-real-model:9b"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "error")

    assert "does not exist" in server.api_pull_status()["error"]


def test_an_uncatalogued_name_is_accepted(monkeypatch):
    """"Any open-source model" is the requirement. A picker limited to seven
    names would be a worse product than the terminal it replaces."""
    seen = {}

    def fake_pull(name, on_progress, host="http://localhost:11434"):
        seen["name"] = name

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "hf.co/someone/their-own-model:Q4_K_M"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "done")

    assert seen["name"] == "hf.co/someone/their-own-model:Q4_K_M"


def test_a_second_pull_is_refused_while_one_is_running(monkeypatch):
    release = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434"):
        release.wait(5)

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "llama3.1:8b"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "pulling")

    try:
        with pytest.raises(ValueError, match="already pulling"):
            server.api_start_pull({"model_name": "mistral:7b"})
    finally:
        release.set()


def test_an_empty_model_name_is_refused():
    with pytest.raises(ValueError, match="model_name is required"):
        server.api_start_pull({"model_name": "   "})
