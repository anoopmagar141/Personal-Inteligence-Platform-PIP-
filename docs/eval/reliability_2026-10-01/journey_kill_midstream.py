"""Journey K (probe, not part of PIP): what a hard stop (the launcher's taskkill) costs when it lands in the middle of an answer.
Real backend process, live qwen2.5:7b, isolated scratch directory; never touches the repo's data/."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from journey import API, PW, Backend, log, turn  # noqa: E402

root = Path(sys.argv[1]).resolve()
b = Backend(root)
log("start1_secs", b.start())
slug = b.post(f"{API}/auth/profiles", {"name": "Kill Probe"}).json()["slug"]
b.post(f"{API}/auth/setup", {"password": PW, "profile": slug})
b.post(f"{API}/onboarding/complete", {"name": "Kill Probe", "language_preference": "English"})
b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})

ws = b.ws()
ws.recv(timeout=30)
log("turn1", turn(ws, "I've decided to use Postgres for my thesis project because I need JSON columns."))
cid = b.get(f"{API}/conversations").json()[0]["id"]

# the turn that is cut off: send, wait for tokens to start, then hard-stop the process
ws.send(json.dumps({"message": "Write a long, detailed essay on the history of relational databases."}))
tokens = 0
while tokens < 8:
    ev = json.loads(ws.recv(timeout=120))
    if ev["type"] == "token":
        tokens += 1
before = [(m["role"], (m.get("content") or "")[:60]) for m in b.get(f"{API}/conversations/{cid}/messages").json()]
log("messages_just_before_kill", before)
b.kill()
try:
    ws.close()
except Exception:
    pass

log("start2_secs", b.start())
log("unlock", b.post(f"{API}/auth/unlock", {"password": PW, "profile": slug}).status_code)
after = [(m["role"], (m.get("content") or "")[:60]) for m in b.get(f"{API}/conversations/{cid}/messages").json()]
log("messages_after_restart", after)
log("conversation_listed", [c["id"] for c in b.get(f"{API}/conversations").json()])

# the same conversation can be resumed and answers
ws2 = b.ws(conversation_id=cid)
info = json.loads(ws2.recv(timeout=30))
log("resume_session_info_type", info.get("type"))
log("turn_after_restart", turn(ws2, "What database did I say I decided on, and why?"))
ws2.close()

# the memory pass for the cut-off session is picked up by the next start
deadline = time.time() + 300
seen = None
while time.time() < deadline:
    dec = b.get(f"{API}/decision/search", params={"q": "Postgres"}).json()
    pend = b.get(f"{API}/memory/pending").json()
    dpend = b.get(f"{API}/decision/pending").json()
    seen = {"decisions": dec, "memory_pending": pend, "decision_pending": dpend}
    if dec or pend or dpend:
        break
    time.sleep(10)
log("after_catch_up", seen)
b.graceful()
log("done", True)
