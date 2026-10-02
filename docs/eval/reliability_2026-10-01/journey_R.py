"""Restart state: what the backend serves between launch and the client choosing a profile."""
import json
import sqlite3
import sys
from pathlib import Path

from journey import API, Backend, log, turn

root = Path(sys.argv[1]).resolve()
b = Backend(root)
b.start()
slug = b.post(f"{API}/auth/profiles", {"name": "Alice"}).json()["slug"]
assert b.post(f"{API}/auth/setup", {"password": "alice-password-1", "profile": slug}).status_code == 200
b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
log("graceful1", b.graceful())
log("root_db_before_restart", (root / "pip.db").exists())

b.start()
log("state_after_restart", b.get(f"{API}/auth/state").json())
log("root_db_after_state", (root / "pip.db").exists())
r = b.get(f"{API}/status")
log("status_before_profile_chosen", (r.status_code, r.text[:120]))
log("root_db_after_status", (root / "pip.db").exists())
log("profiles_list_now", b.get(f"{API}/auth/profiles").json())
r = b.post(f"{API}/memory/correct", {"field": "name", "value": "Alice Q. Private"})
log("write_before_profile_chosen", (r.status_code, r.text[:120]))
b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
with b.ws() as ws:
    ws.recv(timeout=30)
    log("chat_before_profile_chosen", turn(ws, "My bank PIN hint is PLAINTEXT-CANARY-42, remember it."))
b.graceful()

if (root / "pip.db").exists():
    head = (root / "pip.db").read_bytes()[:16]
    log("root_db_header", head)
    c = sqlite3.connect(f"file:{root / 'pip.db'}?mode=ro", uri=True)
    log("root_db_identity", c.execute("select name from identity").fetchall())
    log("root_db_messages", c.execute("select role, content from messages").fetchall())
    c.close()
    log("canary_in_plaintext_bytes", b"PLAINTEXT-CANARY-42" in (root / "pip.db").read_bytes()
        or any(b"PLAINTEXT-CANARY-42" in p.read_bytes() for p in root.glob("pip.db*")))
b.start()
log("profiles_list_next_launch", b.get(f"{API}/auth/profiles").json())
log("state_next_launch", b.get(f"{API}/auth/state").json())
b.graceful()
