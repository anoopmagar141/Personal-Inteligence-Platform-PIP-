"""
One settings block for the local model: which model, how big a window, what
temperature (BLUEPRINT W-1, issues #4, #6 and the 16k half of #5).

What was wrong, measured in V-2 (FREEZE_LIST 7.55): OllamaProvider.chat sent
only num_predict, so chat and the Observer ran in Ollama's default window,
4096 tokens on this machine's GPU, and a longer prompt was cut silently from
the FRONT - for the Observer, the front is its instructions. The default model
was llama3.1:8b in code while every measured number is on qwen2.5:7b (DEC-17),
and settings.json named a model nothing read. PIP budgets in words; the
tokenizer turns a word into 1.41 tokens of prose and 1.86 of the Observer's
instructions (V-2 part d).

These pin the request Ollama receives (a fake /api/chat server records it),
that every place that names the default agrees, and that the Observer's own
prompt fits the window it now asks for.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from backend.config.settings import get_settings
from backend.core import pipeline
from backend.providers import ollama_provider
from backend.providers.ollama_provider import OllamaProvider, is_cloud_model
from backend.stages import stage_11_observer as observer


class _Ollama:
    def __init__(self, prompt_eval_count=1234, load_duration=0):
        self.bodies: list[dict] = []
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                stub.bodies.append(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
                body = b"".join(json.dumps(c).encode() + b"\n" for c in [
                    {"message": {"content": "hi"}, "done": False},
                    {"message": {"content": ""}, "done": True, "prompt_eval_count": prompt_eval_count,
                     "eval_count": 2, "load_duration": load_duration, "done_reason": "stop"},
                ])
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

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


def _llm():
    return get_settings()["llm"]


def test_every_request_asks_for_the_configured_window(ollama):
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)

    list(provider.chat([{"role": "user", "content": "hello"}], max_tokens=50))

    options = ollama.bodies[-1]["options"]
    assert options["num_ctx"] == _llm()["num_ctx"]
    assert options["num_predict"] == 50


def test_the_temperature_is_sent_only_once_it_has_been_chosen(ollama, monkeypatch):
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)
    unset = {**_llm(), "temperature": None}
    monkeypatch.setattr(ollama_provider, "_llm_settings", lambda: unset)
    list(provider.chat([{"role": "user", "content": "hello"}]))
    assert "temperature" not in ollama.bodies[-1]["options"]

    chosen = {**_llm(), "temperature": 0.3}
    monkeypatch.setattr(ollama_provider, "_llm_settings", lambda: chosen)
    list(provider.chat([{"role": "user", "content": "hello"}]))
    assert ollama.bodies[-1]["options"]["temperature"] == 0.3


def test_the_window_is_one_number_for_chat_and_the_observer(ollama):
    # A different num_ctx reloads the model (seconds each time), so the
    # Observer must not ask for its own.
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)
    list(provider.chat([{"role": "user", "content": "chat"}], max_tokens=2000))
    list(provider.chat([{"role": "user", "content": "observer"}], max_tokens=2000, timeout_seconds=180,
                       response_format={"type": "object"}))

    assert ollama.bodies[0]["options"]["num_ctx"] == ollama.bodies[1]["options"]["num_ctx"]


def test_every_place_that_names_the_default_model_agrees_and_it_is_the_measured_one():
    # DEC-17: every thesis number was measured on qwen2.5:7b. The default used
    # to be llama3.1:8b in three places that could each drift on their own.
    assert pipeline.DEFAULT_MODEL_NAME == OllamaProvider().model_name == _llm()["default_model"] == "qwen2.5:7b"
    assert "model" not in get_settings()["observer"], "a second, unread model setting is back"
    assert not is_cloud_model(_llm()["default_model"])


def test_a_new_profile_uses_the_default_model(tmp_path, db_key):
    from backend.memory.profile_store import get_connection, initialize_schema

    conn = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    try:
        initialize_schema(conn)
        assert pipeline.get_active_model_name(conn) == "qwen2.5:7b"
    finally:
        conn.close()


def test_the_observer_prompt_and_its_reply_fit_the_window():
    # The largest transcript the Observer will send, in words, at the safe
    # tokens-per-word ratio, plus its instructions and its reply, must fit.
    llm = _llm()
    huge = "\n".join(f"User: line {i} " + "word " * 20 for i in range(3000))
    capped = observer._cap_transcript(huge)
    words = len((observer._EXTRACTION_PROMPT_PREFIX + capped).split())

    assert words * llm["tokens_per_word"] + observer.OBSERVER_MAX_TOKENS <= llm["num_ctx"]
    assert len(capped.split()) > 1000, "the cap should still leave a long transcript room"


def test_the_safe_ratio_is_above_every_measured_one():
    # V-2 part (d): 1.41 tokens per word for prose, 1.86 for the Observer's
    # instructions. A ratio below a measured one would let a prompt overflow.
    assert _llm()["tokens_per_word"] >= 1.86


def test_the_chat_budget_fits_the_window():
    pipeline_budget = get_settings()["pipeline"]["context_token_budget"]  # words, reply included
    assert pipeline_budget * _llm()["tokens_per_word"] <= _llm()["num_ctx"]


def test_ollama_s_own_count_is_kept_for_the_trace(ollama):
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)

    list(provider.chat([{"role": "user", "content": "hello"}]))

    assert provider.last_counts["prompt_eval_count"] == 1234
    assert provider.last_counts["num_ctx"] == _llm()["num_ctx"]
    assert provider.last_counts["window_full"] is False


def test_a_prompt_that_would_not_fit_is_flagged_before_it_is_cut(ollama, monkeypatch):
    small = {**_llm(), "num_ctx": 512}
    monkeypatch.setattr(ollama_provider, "_llm_settings", lambda: small)
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)

    list(provider.chat([{"role": "user", "content": "word " * 300}], max_tokens=100))

    assert provider.last_counts["window_full"] is True


# --- the trace: what Ollama actually read ---------------------------------


@pytest.fixture
def conn(tmp_path, db_key):
    from backend.memory.profile_store import get_connection, initialize_schema

    connection = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(connection)
    yield connection
    connection.close()


def _trace(conn, stage):
    return [r["message"] for r in conn.execute("SELECT message FROM trace_log WHERE stage = ? ORDER BY id", (stage,))]


def test_the_chat_trace_says_how_many_prompt_tokens_ollama_read(conn, ollama):
    from backend.core import response_cache

    response_cache.clear()
    provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)
    pipeline.run_sync(conn, "Explain a hash table", providers=[provider])
    response_cache.clear()

    message = _trace(conn, "stage_09_llm_streaming")[-1]
    assert "prompt_tokens_read=1234" in message
    assert f"window={_llm()['num_ctx']}" in message


@pytest.mark.asyncio
async def test_the_observer_trace_says_how_many_prompt_tokens_ollama_read(tmp_path, db_key, ollama):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from backend.core import session_lifecycle
    from backend.memory.profile_store import get_connection, initialize_schema

    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    def _open():
        c = get_connection(str(tmp_path / "obs.db"), db_key=db_key)
        initialize_schema(c)
        return c

    c = await loop.run_in_executor(executor, _open)
    try:
        provider = OllamaProvider(model_name="qwen2.5:7b", host=ollama.url)
        await session_lifecycle.run_observer_now(
            loop, executor, c, [{"role": "user", "content": "I use Neovim"}], provider,
        )
        messages = await loop.run_in_executor(executor, _trace, c, "stage_11_observer")
    finally:
        await loop.run_in_executor(executor, c.close)
        executor.shutdown(wait=True)

    assert any("prompt_tokens_read=1234" in m and f"window={_llm()['num_ctx']}" in m for m in messages), messages
