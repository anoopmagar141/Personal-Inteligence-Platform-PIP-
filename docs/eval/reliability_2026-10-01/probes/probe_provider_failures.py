"""
PROBE: provider failure conditions through the real pipeline and the real
local Ollama (no model is deleted - the 'missing' model is a name that was
never pulled, written into llm_settings the way a later `ollama rm` would
leave it).
"""
import socket
import threading
import time

import pytest

from backend.api import server
from backend.core import pipeline, response_cache
from backend.memory import vector_store
from backend.providers import ollama_provider
from backend.providers.ollama_provider import OllamaProvider


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    response_cache.clear()
    c = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield c
    c.close()
    response_cache.clear()


def _events(conn, msg, **kw):
    return list(pipeline.run(conn, msg, **kw))


def test_PF1_active_model_removed_from_ollama(conn):
    conn.execute("INSERT OR REPLACE INTO llm_settings (id, model_name) VALUES (1, 'no-such-model:1b')")
    conn.commit()
    t0 = time.time()
    ev = _events(conn, "explain recursion in one line")
    kinds = [e["type"] for e in ev]
    err = [e for e in ev if e["type"] == "error"]
    done = [e for e in ev if e["type"] == "pipeline_complete"][0]["data"]
    print("PF1 kinds:", kinds, "secs:", round(time.time() - t0, 1))
    print("PF1 error event:", err)
    print("PF1 final:", {k: done.get(k) for k in ("status", "error")})
    assert err, "no error event reached the client"
    assert "pull" in str(err).lower() or "model" in str(err).lower()


def test_PF2_ollama_down(conn, monkeypatch):
    # point the provider at a closed port instead of stopping the user's Ollama
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    real_init = OllamaProvider.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        self.host = f"http://127.0.0.1:{port}"

    monkeypatch.setattr(OllamaProvider, "__init__", init)
    t0 = time.time()
    ev = _events(conn, "explain recursion in one line")
    err = [e for e in ev if e["type"] == "error"]
    print("PF2 error:", err, "secs:", round(time.time() - t0, 1))
    assert err


def test_PF3_ollama_hangs_is_bounded(conn, monkeypatch):
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(5)
    port = srv.getsockname()[1]
    held = []
    threading.Thread(target=lambda: [held.append(srv.accept()) for _ in range(5)], daemon=True).start()
    real_init = OllamaProvider.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        self.host = f"http://127.0.0.1:{port}"

    monkeypatch.setattr(OllamaProvider, "__init__", init)
    t0 = time.time()
    ev = _events(conn, "explain recursion in one line", timeout_seconds=10)
    secs = time.time() - t0
    print("PF3 kinds:", [e["type"] for e in ev], "secs:", round(secs, 1))
    srv.close()
    assert secs < 60, f"a hung provider held the turn for {secs:.0f}s"
