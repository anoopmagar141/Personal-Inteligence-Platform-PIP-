"""Measures how fast PIP answers on this PC, for report section 6.6.

What runs: the app's own chat path, pipeline.run() (Stages 0-10), with the app's own OllamaProvider and its
shipped settings (qwen2.5:7b, num_ctx 16384, temperature 0, max_tokens 2000 as the chat socket uses), on a
throwaway encrypted test profile in a temporary folder. The user's own data is never opened.

The rules, fixed before the first run (they are also written into the result file):
- Eight questions, one per kind of message a user sends (below). Each is asked three times, in three rounds
  (q1..q8, then again, then again), with the answer cache emptied before every question, so every timed answer
  goes through the model.
- Measured per answer, by the wall clock from the moment the message enters the pipeline:
    first word   = the first streamed token reaches the caller (what the user sees start to move),
    full answer  = the pipeline's final event (the whole reply is on screen),
    PIP's own steps = time until the model is called (Stages 0-8: routing, memory, decisions, documents,
                      context assembly, consent check),
  plus Ollama's own counts: prompt tokens read, tokens written, model load seconds.
- Also measured: a cold start (the model unloaded from the GPU first, then one question), and three answers
  served from the answer cache (the same first message asked twice; the second is timed).
- Reported: the median of the three runs per question, with the lowest and highest. No run is dropped; a failed
  run is recorded as failed.
- Three conditions (--mode). "pinned": the harness hands the pipeline the app's OllamaProvider, so the app's own
  provider choice (_default_providers, which first asks is_available()) is skipped. "app": the pipeline picks its
  provider exactly as the chat socket does. "app-ipv4": as "app", but the harness makes OllamaProvider talk to
  127.0.0.1 instead of localhost; no PIP code is changed. The first run (pinned) showed every model call waiting
  about 2 s before its first token although Ollama itself answered in 0.05-0.26 s; "localhost" resolves to ::1
  first on this PC, Ollama listens on 127.0.0.1 only, and the fallback costs 2.04 s per request. The "app" and
  "app-ipv4" conditions were added after that run to measure the as-shipped cost and what using 127.0.0.1 would
  give; the questions and rules above were not changed.

Run (from a clean checkout of the commit being measured, with Ollama already serving):
  .venv/Scripts/python.exe -I notes/report/chapter6/measure_speed.py --repo <checkout> --out <result.json>
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

MODEL = "qwen2.5:7b"
HOST = "http://127.0.0.1:11434"
ROUNDS = 3

DOC_NAME = "lanternfish_design_note.txt"
DOC_TEXT = """Lanternfish design note

Lanternfish is a budgeting app for students who share a hostel room. Each room has one shared budget. Every
member can add an expense, and the app splits it between the members who took part in it.

How budgets are shared: a budget belongs to the room, not to one student. When an expense is added, the person
who paid chooses who shares it; the app divides the amount equally between them unless a different split is
typed in. At the end of each month the app shows who owes whom, and suggests the fewest payments that settle
every debt. Nobody can delete an expense that someone else added; they can only flag it for discussion.

Data: expenses, members and rooms are stored in PostgreSQL. Receipts are stored as images beside the expense.
The mobile client works offline and sends its changes when the phone is back online.

Open problems: currency conversion for international students, and what happens when a member leaves the room
in the middle of a month.
"""

QUESTIONS = [
    ("q1", "Greeting", "hi", None),
    ("q2", "Short general question", "What is a hash map?", None),
    ("q3", "Explanation", "Explain how vector clocks work in a distributed system.", None),
    ("q4", "Coding request", "Write a Python function that checks whether a string is a palindrome.", None),
    ("q5", "About the user", "What do you know about me?", None),
    ("q6", "About a project decision", "What did we decide about the database for Lanternfish?", None),
    ("q7", "About an uploaded document", "In the Lanternfish design note, how are budgets shared?", None),
    ("q8", "Follow-up in the same chat", "Why is that better than using timestamps?", [
        {"role": "user", "content": "Explain how vector clocks work in a distributed system."},
        {"role": "assistant", "content": "A vector clock is a list of counters, one per node. Each node increments "
                                         "its own counter on every event and sends the whole list with each "
                                         "message; a receiver takes the element-wise maximum. Comparing two "
                                         "vectors tells you whether one event happened before the other or "
                                         "whether they were concurrent."},
    ]),
]


def ollama(path, payload=None, timeout=60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(HOST + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def gpu_now():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.strip()
        return out
    except Exception as e:  # nvidia-smi missing is not a reason to stop
        return f"unavailable: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="checkout of the commit being measured")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("pinned", "app", "app-ipv4"), default="pinned")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    work = Path(tempfile.mkdtemp(prefix="pip_speed_"))
    os.environ["PIP_DATA_DIR"] = str(work / "data")
    os.environ["PIP_DB_PATH"] = str(work / "data" / "pip.db")
    os.environ["PIP_DOCUMENTS_ROOT"] = str(work / "documents")
    os.environ["PIP_CHROMA_PATH"] = str(work / "chroma")
    os.environ["PIP_SALT_PATH"] = str(work / "data" / "salt.bin")
    os.environ["PIP_TOKEN_PATH"] = str(work / "data" / "api_token.txt")
    (work / "data").mkdir(parents=True)
    (work / "documents").mkdir()
    sys.path.insert(0, str(repo / "scripts"))
    sys.path.insert(0, str(repo))

    import _stamp
    from backend.core import db_key, pipeline, response_cache
    if Path(pipeline.__file__).resolve().parents[2] != repo or Path(_stamp.__file__).resolve().parents[1] != repo:
        sys.exit(f"code imported from {pipeline.__file__} / {_stamp.__file__}, not from {repo}")
    from backend.memory import decision_log, profile_store, vector_store
    from backend.providers.ollama_provider import OllamaProvider

    # The app's provider, unchanged, plus the moment the pipeline hands it the prompt. Patched on the class so
    # the instance the pipeline builds for itself (modes "app" and "app-ipv4") is timed too.
    timing = {}
    real_chat = OllamaProvider.chat

    def timed_chat(self, *a, **k):
        timing["t_call"], timing["provider"] = time.perf_counter(), self
        yield from real_chat(self, *a, **k)

    OllamaProvider.chat = timed_chat
    if args.mode == "app-ipv4":
        real_init = OllamaProvider.__init__

        def ipv4_init(self, model_name=None, host=None):
            real_init(self, model_name, "http://127.0.0.1:11434")

        OllamaProvider.__init__ = ipv4_init

    probe = OllamaProvider(model_name=MODEL)
    if not probe.is_available():
        sys.exit("Ollama is not serving on 127.0.0.1:11434")
    stamp = _stamp.run_stamp(MODEL, options_sent=probe.request_options(2000))

    # A throwaway encrypted profile, seeded so personal, project and document questions find something.
    salt = db_key.create_salt(Path(os.environ["PIP_SALT_PATH"]))
    key = db_key.derive_key("speed-test-password", salt)
    os.environ["PIP_DB_KEY"] = key
    conn = profile_store.get_connection(os.environ["PIP_DB_PATH"], key)
    profile_store.initialize_schema(conn)
    conn.execute("INSERT OR REPLACE INTO llm_settings (id, model_name) VALUES (1, ?)", (MODEL,))
    conn.commit()
    profile_store.complete_onboarding(conn, name="Test User", language_preference="English",
                                      timezone="Asia/Kathmandu", skills=["Python"], preferred_tools=["VS Code"])
    pid = profile_store.create_project(conn, "Lanternfish", "a budgeting app for students who share a hostel room")
    decision_log.create_decision(conn, text="We decided to use PostgreSQL for Lanternfish instead of MongoDB",
                                 reasoning="the expenses, members and rooms are relational data",
                                 alternatives="MongoDB", project_id=pid)
    doc = work / "documents" / DOC_NAME
    doc.write_text(DOC_TEXT, encoding="utf-8")
    vector_store.reset_client()
    vector_store.ingest_document(conn, str(doc), pid)

    def ask(message, history, clear_cache=True):
        if clear_cache:
            response_cache.clear()
        timing.clear()
        providers = [OllamaProvider(model_name=MODEL)] if args.mode == "pinned" else None
        t0 = time.perf_counter()
        t_first, result = None, None
        for event in pipeline.run(conn, message, conversation_history=history, providers=providers):
            if event.get("type") == "token" and t_first is None:
                t_first = time.perf_counter()
            if event.get("type") == "pipeline_complete":
                result = event.get("data") or {}
        t_end = time.perf_counter()
        t_call = timing.get("t_call")
        counts = getattr(timing.get("provider"), "last_counts", {}) or {}
        return {
            "status": (result or {}).get("status"),
            "first_word_s": None if t_first is None else round(t_first - t0, 3),
            "full_answer_s": round(t_end - t0, 3),
            "pip_steps_ms": None if t_call is None else round((t_call - t0) * 1000, 1),
            "prompt_tokens": counts.get("prompt_eval_count"),
            "tokens_out": counts.get("eval_count"),
            "load_s": counts.get("load_seconds"),
            "answer_words": len(((result or {}).get("response_text") or "").split()),
        }

    record = {
        "mode": args.mode,
        "protocol": __doc__.split("The rules, fixed before the first run")[1].split("Run (from")[0].strip(),
        "stamp": stamp,
        "gpu_before": gpu_now(),
        "questions": [{"id": q, "kind": k, "message": m, "history_turns": len(h or [])} for q, k, m, h in QUESTIONS],
        "cold": None, "runs": [], "cache_hits": [],
    }

    def save():
        Path(args.out).write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")

    # Cold start: unload the model from the GPU, then ask.
    ollama("/api/generate", {"model": MODEL, "keep_alive": 0})
    time.sleep(3)
    record["cold"] = {"question": "q2", **ask(QUESTIONS[1][2], None)}
    print("cold", record["cold"], flush=True)
    save()

    for rnd in range(1, ROUNDS + 1):
        for qid, kind, message, history in QUESTIONS:
            try:
                r = ask(message, history)
            except Exception as e:  # recorded, never dropped
                r = {"status": "failed", "error": str(e)}
            record["runs"].append({"round": rnd, "question": qid, **r})
            print(rnd, qid, r, flush=True)
            save()

    for i in range(ROUNDS):
        msg = f"What is a hash map? ({i + 1})"
        ask(msg, None)                                # stores the answer
        hit = ask(msg, None, clear_cache=False)       # served from the cache
        record["cache_hits"].append(hit)
        print("cache hit", hit, flush=True)
    record["gpu_after"] = gpu_now()
    save()

    def summary(values):
        values = [v for v in values if v is not None]
        return None if not values else {"median": round(statistics.median(values), 2),
                                        "min": round(min(values), 2), "max": round(max(values), 2)}

    record["summary"] = {
        qid: {f: summary([r.get(f) for r in record["runs"] if r["question"] == qid])
              for f in ("first_word_s", "full_answer_s", "pip_steps_ms", "tokens_out", "prompt_tokens")}
        for qid, *_ in QUESTIONS
    }
    save()
    conn.close()
    print("wrote", args.out)


if __name__ == "__main__":
    main()
