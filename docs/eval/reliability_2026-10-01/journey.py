"""
Real-process journey driver (probe, not part of PIP).

Runs the backend as its own OS process (uvicorn, embedding shim - see
pip_embed_shim.py), every PIP_* path inside one scratch directory, a live
local model through Ollama. Drives the same HTTP/WS surface the Flutter
client uses, force-kills the process, restarts it, and checks recovery.
Prints a JSON-ish log of observations; never touches the repo's data/.
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import atexit
from pathlib import Path

import httpx

_ALL = []
atexit.register(lambda: [subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                         for p in _ALL if p.poll() is None])
from websockets.sync.client import connect

REPO = Path(__file__).resolve().parents[3]
PY = REPO / ".venv" / "Scripts" / "python.exe"
HARNESS = Path(__file__).parent
API = "/api/v1"
PW = "zarqa-password-1"


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class Backend:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.port = free_port()
        self.proc = None
        self.root.mkdir(parents=True, exist_ok=True)

    def env(self):
        e = dict(os.environ)
        d = self.root
        e.update({
            "PIP_DATA_DIR": str(d), "PIP_LOCK_PATH": str(d / "pip.lock"),
            "PIP_TOKEN_PATH": str(d / "api_token.txt"), "PIP_DB_PATH": str(d / "pip.db"),
            "PIP_SALT_PATH": str(d / "salt.bin"), "PIP_STARTUP_PROGRESS_PATH": str(d / "startup.jsonl"),
            "PIP_DOCUMENTS_ROOT": str(d / "documents"), "PIP_CHROMA_PATH": str(d / "chroma"),
            "PYTHONPATH": f"{HARNESS};{REPO}", "PYTHONUNBUFFERED": "1",
        })
        e.pop("PIP_DB_KEY", None)
        e.pop("PIP_PROFILE", None)
        return e

    def start(self, wait=90):
        log = open(self.root / f"backend-{int(time.time())}.log", "w")
        code = ("import pip_embed_shim, uvicorn; "
                f"uvicorn.run('backend.api.server:app', host='127.0.0.1', port={self.port}, log_level='info')")
        self.proc = subprocess.Popen([str(PY), "-c", code], cwd=str(REPO), env=self.env(),
                                     stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        _ALL.append(self.proc)
        t0 = time.time()
        while time.time() - t0 < wait:
            if self.proc.poll() is not None:
                raise RuntimeError(f"backend exited {self.proc.returncode}")
            try:
                tok = (self.root / "api_token.txt").read_text().strip()
                r = httpx.get(self.url(f"{API}/auth/state"), headers={"Authorization": f"Bearer {tok}"}, timeout=2)
                if r.status_code == 200:
                    self.token = tok
                    return time.time() - t0
            except Exception:
                pass
            time.sleep(0.5)
        raise TimeoutError("backend did not come up")

    def url(self, p):
        return f"http://127.0.0.1:{self.port}{p}"

    def h(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, p, **k):
        return httpx.get(self.url(p), headers=self.h(), timeout=120, **k)

    def post(self, p, js=None, **k):
        return httpx.post(self.url(p), headers=self.h(), json=js, timeout=300, **k)

    def kill(self):
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
        self.proc.wait(10)

    def graceful(self):
        self.proc.send_signal(signal.CTRL_BREAK_EVENT)
        try:
            return self.proc.wait(60)
        except subprocess.TimeoutExpired:
            self.kill(); return "timeout->killed"

    def ws(self, conversation_id=None):
        q = f"?token={self.token}" + (f"&conversation_id={conversation_id}" if conversation_id else "")
        return connect(f"ws://127.0.0.1:{self.port}/ws/chat{q}", open_timeout=30, max_size=None)


def turn(ws, message, stop_after_first_token=False, timeout=300):
    ws.send(json.dumps({"message": message}))
    text, events, t0 = "", [], time.time()
    while True:
        ev = json.loads(ws.recv(timeout=timeout))
        events.append(ev["type"])
        if ev["type"] == "token":
            text += ev["data"]
            if stop_after_first_token and len(text) > 0 and "stop" not in events:
                ws.send(json.dumps({"type": "stop"})); events.append("stop")
        if ev["type"] in ("done", "error", "stopped"):
            return {"final": ev["type"], "text": text, "error": ev.get("data") if ev["type"] == "error" else None,
                    "secs": round(time.time() - t0, 1), "n_tokens": events.count("token")}


def log(k, v):
    print(f"[{k}] {json.dumps(v, default=str)[:900]}", flush=True)
