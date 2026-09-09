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

import json
import threading
import time
from unittest.mock import patch

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
    # The cancel flag is module-level for the same reason and leaks the same
    # way: left set, it stops the next test's pull before it transfers
    # anything, which reads as a pull that silently refused to start.
    server._pull_cancel.clear()
    yield
    with server._pull_lock:
        server._pull_state.update(status="idle", model=None, completed=0,
                                  total=0, detail="", error=None)
    server._pull_cancel.clear()


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

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
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
    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
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
    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
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

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
        seen["name"] = name

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)

    server.api_start_pull({"model_name": "hf.co/someone/their-own-model:Q4_K_M"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "done")

    assert seen["name"] == "hf.co/someone/their-own-model:Q4_K_M"


def test_a_second_pull_is_refused_while_one_is_running(monkeypatch):
    release = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
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


# --- stopping a download ---------------------------------------------------
#
# Ollama has no cancel endpoint; abandoning the response stream is how its own
# CLI stops a pull, and the blobs already written stay in its store so the same
# model resumes rather than restarting. What is worth pinning here is that a
# cancel is reported as its own outcome rather than as a failure - a 4GB
# download somebody chose to stop is not an error, and calling it one would put
# a red message under a deliberate act.


def test_a_running_pull_can_be_stopped(monkeypatch):
    running = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
        running.set()
        while not (should_cancel and should_cancel()):
            time.sleep(0.01)
        raise ollama_provider.PullCancelled("stopped")

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)
    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert running.wait(5)

    answer = server.api_cancel_pull()

    assert answer["status"] == "cancelling"
    assert answer["model_name"] == "qwen2.5:7b"
    assert _wait_until(lambda: server.api_pull_status()["status"] == "cancelled")


def test_a_cancelled_pull_is_not_reported_as_an_error(monkeypatch):
    """A red line under something the user chose to do is the wrong answer."""
    running = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
        running.set()
        while not (should_cancel and should_cancel()):
            time.sleep(0.01)
        raise ollama_provider.PullCancelled("stopped")

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)
    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert running.wait(5)
    server.api_cancel_pull()
    assert _wait_until(lambda: server.api_pull_status()["status"] == "cancelled")

    final = server.api_pull_status()
    assert final["error"] is None
    assert final["status"] != "error"


def test_cancelling_when_nothing_is_downloading_is_refused():
    assert server.api_pull_status()["status"] != "pulling"
    with pytest.raises(ValueError, match="nothing is downloading"):
        server.api_cancel_pull()


def test_a_cancel_does_not_leak_into_the_next_pull(monkeypatch):
    """
    The flag is cleared when a pull STARTS, not when one ends. Cleared only on
    the way out, a cancel that arrived while nothing was running would sit set
    and stop the next download before it had transferred anything - which would
    look like a pull that silently refused to start.
    """
    running = threading.Event()

    def cancellable(name, on_progress, host="http://localhost:11434", should_cancel=None):
        running.set()
        while not (should_cancel and should_cancel()):
            time.sleep(0.01)
        raise ollama_provider.PullCancelled("stopped")

    monkeypatch.setattr(ollama_provider, "pull_model", cancellable)
    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert running.wait(5)
    server.api_cancel_pull()
    assert _wait_until(lambda: server.api_pull_status()["status"] == "cancelled")

    def completes(name, on_progress, host="http://localhost:11434", should_cancel=None):
        assert not (should_cancel and should_cancel()), "the previous cancel was still set"
        on_progress({"status": "downloading", "completed": 10, "total": 10})

    monkeypatch.setattr(ollama_provider, "pull_model", completes)
    server.api_start_pull({"model_name": "mistral:7b"})

    assert _wait_until(lambda: server.api_pull_status()["status"] == "done")


def test_pull_model_stops_reading_when_told_to():
    """
    The provider half, against a real stream. Closing the response is what
    actually ends the transfer - there is nothing to tell Ollama.
    """
    lines = [json.dumps({"status": "downloading", "completed": i, "total": 100}).encode()
             for i in range(50)]
    read = []

    class _Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def __iter__(self): return iter(lines)

    seen = {"n": 0}

    def on_progress(event):
        read.append(event)

    def should_cancel():
        seen["n"] += 1
        return seen["n"] > 3

    with patch("urllib.request.urlopen", return_value=_Response()):
        with pytest.raises(ollama_provider.PullCancelled):
            ollama_provider.pull_model("x", on_progress, should_cancel=should_cancel)

    assert len(read) < len(lines), "it read the whole stream after being told to stop"


# --- removing a pulled model -----------------------------------------------
#
# A different class of delete from anything else in PIP, and the ceremony is
# lighter on purpose: nothing of the user's is inside a model. It is several
# gigabytes of somebody else's weights that the same name pulls again, so what
# this recovers is disk space and what it costs is a download.
#
# The two refusals are where the care goes, because each prevents a failure
# that would surface somewhere else entirely.


@pytest.fixture
def conn(tmp_path):
    from backend.memory import profile_store
    connection = profile_store.get_connection(str(tmp_path / "pip.db"), None)
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_a_pulled_model_can_be_deleted(conn, monkeypatch):
    deleted = []
    monkeypatch.setattr(ollama_provider, "delete_model", lambda name, **k: deleted.append(name))

    answer = server.api_delete_model(conn, {"model_name": "mistral:7b"})

    assert answer == {"status": "deleted", "model_name": "mistral:7b"}
    assert deleted == ["mistral:7b"]


def test_the_model_pip_is_using_cannot_be_deleted(conn, monkeypatch):
    """
    Deleting it would leave the pipeline pointing at a name Ollama no longer
    has, and the failure would surface as a broken chat rather than as anything
    to do with the screen the button was on.
    """
    from backend.core import pipeline

    active = pipeline.get_active_model_name(conn)
    monkeypatch.setattr(
        ollama_provider, "delete_model",
        lambda *a, **k: pytest.fail("the active model was deleted"),
    )

    with pytest.raises(ValueError, match="the model PIP is using"):
        server.api_delete_model(conn, {"model_name": active})


def test_a_model_being_downloaded_cannot_be_deleted(conn, monkeypatch):
    """Deleting a store Ollama is actively writing into is a race with no
    useful outcome. Cancel is the button for that, and it is next to it."""
    release = threading.Event()

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
        release.wait(5)

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)
    monkeypatch.setattr(
        ollama_provider, "delete_model",
        lambda *a, **k: pytest.fail("a downloading model was deleted"),
    )
    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "pulling")

    try:
        with pytest.raises(ValueError, match="downloading right now"):
            server.api_delete_model(conn, {"model_name": "qwen2.5:7b"})
    finally:
        release.set()


def test_a_different_model_can_be_deleted_during_a_download(conn, monkeypatch):
    """The guard is about the one being written, not about downloads in
    general - a 4GB pull is no reason to refuse freeing 4GB elsewhere."""
    release = threading.Event()
    deleted = []

    def fake_pull(name, on_progress, host="http://localhost:11434", should_cancel=None):
        release.wait(5)

    monkeypatch.setattr(ollama_provider, "pull_model", fake_pull)
    monkeypatch.setattr(ollama_provider, "delete_model", lambda name, **k: deleted.append(name))
    server.api_start_pull({"model_name": "qwen2.5:7b"})
    assert _wait_until(lambda: server.api_pull_status()["status"] == "pulling")

    try:
        server.api_delete_model(conn, {"model_name": "phi3:mini"})
    finally:
        release.set()

    assert deleted == ["phi3:mini"]


def test_an_empty_name_is_refused_rather_than_deleting_something(conn, monkeypatch):
    monkeypatch.setattr(
        ollama_provider, "delete_model",
        lambda *a, **k: pytest.fail("an empty name reached Ollama"),
    )
    with pytest.raises(ValueError, match="model_name is required"):
        server.api_delete_model(conn, {"model_name": "  "})


def test_ollama_refusing_the_delete_is_reported_not_swallowed(conn, monkeypatch):
    """"It was already gone" and "you typed it wrong" look identical from
    here, and only one of them is fine."""
    from backend.providers.base_provider import ProviderExecutionError

    def _refuse(name, **k):
        raise ProviderExecutionError("Ollama would not delete 'nope': 404 not found")

    monkeypatch.setattr(ollama_provider, "delete_model", _refuse)

    with pytest.raises(ProviderExecutionError, match="404"):
        server.api_delete_model(conn, {"model_name": "nope"})
