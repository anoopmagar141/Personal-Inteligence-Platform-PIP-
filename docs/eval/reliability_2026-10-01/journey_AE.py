"""Journey A (new user) + E (force-kill and crash recovery), real process, live qwen2.5:7b."""
import sys
import time
from pathlib import Path

from journey import API, PW, Backend, log, turn

root = Path(sys.argv[1]).resolve()
b = Backend(root)
log("start1_secs", b.start())
log("state_fresh", b.get(f"{API}/auth/state").json())
log("profiles_fresh", b.get(f"{API}/auth/profiles").json())

slug = b.post(f"{API}/auth/profiles", {"name": "Zarqa Venn"}).json()["slug"]
log("setup_short_pw", b.post(f"{API}/auth/setup", {"password": "short", "profile": slug}).status_code)
r = b.post(f"{API}/auth/setup", {"password": PW, "profile": slug})
log("setup", (r.status_code, r.text[:200]))
log("setup_again", b.post(f"{API}/auth/setup", {"password": PW, "profile": slug}).status_code)

# Onboarding validation
log("onboard_empty", (lambda r: (r.status_code, r.text[:160]))(b.post(f"{API}/onboarding/complete", {})))
ob = {"name": "Zarqa Venn", "language_preference": "English", "timezone": "Asia/Kathmandu",
      "current_project": "Heliotrope", "skills": [], "preferred_tools": []}
log("onboard", (lambda r: (r.status_code, r.text[:160]))(b.post(f"{API}/onboarding/complete", ob)))
log("onboard_dup", (lambda r: (r.status_code, r.text[:160]))(b.post(f"{API}/onboarding/complete", ob)))
log("projects_after_dup_onboard", b.get(f"{API}/projects").json())

# Missing model: default model is not pulled on this machine
log("active_model_default", b.get(f"{API}/llm/active-model").json())
with b.ws() as ws:
    info = __import__("json").loads(ws.recv(timeout=30))
    log("session_info", {k: (v if k != "messages" else len(v)) for k, v in info.get("data", info).items()} if isinstance(info, dict) else info)
    log("turn_missing_model", turn(ws, "hello there"))

log("set_model", b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"}).json())
log("set_bad_model", (lambda r: (r.status_code, r.text[:160]))(b.post(f"{API}/llm/active-model", {"model_name": "no-such-model:1b"})))

msgs = [
    "Hi! Quick context: I work mostly in Python and I'm building my thesis backend.",
    "I've decided to go with FastAPI for the backend because Flask has no native async.",
    "What did I say I'm using for the backend, and why?",
]
convos_before = b.get(f"{API}/conversations").json()
ws = b.ws()
ws.recv(timeout=30)
results = [turn(ws, m) for m in msgs]
for i, res in enumerate(results):
    log(f"turn{i+1}", res)
log("stop_turn", turn(ws, "Write a very long, detailed essay about the history of databases.", stop_after_first_token=True))
convos = b.get(f"{API}/conversations").json()
log("conversations_before_kill", convos)
cid = convos[0]["id"] if isinstance(convos, list) and convos else None
msgs_before = b.get(f"{API}/conversations/{cid}/messages").json() if cid else None
log("messages_before_kill", [(m.get("role"), (m.get("content") or "")[:50]) for m in msgs_before] if msgs_before else msgs_before)

# ---- force-kill with the WebSocket still open (session never ended) ----
b.kill()
try:
    ws.close()
except Exception:
    pass
log("lock_after_kill", (root / "pip.lock").read_text() if (root / "pip.lock").exists() else None)

log("start2_secs", b.start())
log("state_after_restart", b.get(f"{API}/auth/state").json())
log("profiles_after_restart", b.get(f"{API}/auth/profiles").json())
log("ws_while_locked", "see below")
try:
    with b.ws() as w2:
        w2.recv(timeout=10); log("ws_locked", "ACCEPTED (unexpected)")
except Exception as e:
    log("ws_locked", f"refused: {type(e).__name__} {str(e)[:80]}")
log("unlock_wrong", (lambda r: (r.status_code, r.text[:120]))(b.post(f"{API}/auth/unlock", {"password": "wrong-password-x", "profile": slug})))
t0 = time.time()
log("unlock", (lambda r: (r.status_code, r.text[:120]))(b.post(f"{API}/auth/unlock", {"password": PW, "profile": slug})))
log("unlock_secs", round(time.time() - t0, 1))
msgs_after = b.get(f"{API}/conversations/{cid}/messages").json()
log("messages_after_restart", [(m.get("role"), (m.get("content") or "")[:50]) for m in msgs_after])
log("transcript_identical", [(m.get("role"), m.get("content")) for m in msgs_after] == [(m.get("role"), m.get("content")) for m in msgs_before])

# Catch-up runs the Observer on the killed session in the background.
deadline = time.time() + 420
seen = None
while time.time() < deadline:
    pend = b.get(f"{API}/memory/pending").json()
    dpend = b.get(f"{API}/decision/pending").json()
    dec = b.get(f"{API}/decision/search", params={"q": "FastAPI"}).json()
    prof = b.get(f"{API}/memory/profile").json()
    st = b.get(f"{API}/status").json()
    seen = {"memory_pending": pend, "decision_pending": dpend, "decisions": dec, "status": st}
    if (pend or dpend or dec) and time.time() - deadline < -30:
        break
    time.sleep(15)
log("after_catch_up", seen)
log("profile_after_catch_up", prof)

# Graceful shutdown
code = b.graceful()
log("graceful_exit", code)
log("lock_after_graceful", (root / "pip.lock").read_text() if (root / "pip.lock").exists() else "released")
log("files", sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and "chroma" not in p.parts)[:40])
