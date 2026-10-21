"""
Q-1 (BLUEPRINT card Q-1, #11): does a NEW user's greeting get "I don't have a record"?

The rule, fixed before the run, is RULE.md next to this file; its SHA-256 goes into the results. This is the
2026-10-17 probe (docs/eval/greeting_2026-10-17/probe_greeting.py) moved onto the real path: the real pipeline
(pipeline.run_sync, no provider given, so the profile's active model through the real OllamaProvider and its
shipped options), on fresh made-up profiles, with the same no-record pattern.

Run (Ollama up via `ollama serve`, qwen2.5:7b pulled, from a clean worktree at the commit RULE.md names):
    .venv\\Scripts\\python.exe docs\\eval\\q1_greeting_2026-10-21\\probe_q1.py
Writes results_qwen2.5_7b.json next to this file.
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TMP = pathlib.Path(tempfile.mkdtemp(prefix="pip-q1-"))

# Every real-file path the backend has, pointed at a temporary folder BEFORE anything from backend/ is imported
# (backend/tests/conftest.py's table): nothing here may open, or create anything in, data/.
_ISOLATED_PATHS = {
    "PIP_LOCK_PATH": "pip.lock",
    "PIP_DB_PATH": "pip.db",
    "PIP_TOKEN_PATH": "api_token.txt",
    "PIP_SALT_PATH": "salt.bin",
    "PIP_STARTUP_PROGRESS_PATH": "startup.jsonl",
    "PIP_DOCUMENTS_ROOT": "documents",
    "PIP_CHROMA_PATH": "chroma",
    "PIP_DATA_DIR": ".",
}
for _variable, _name in _ISOLATED_PATHS.items():
    os.environ[_variable] = str(TMP / _name)
os.environ["PIP_PROFILE"] = "default"
_data = (REPO / "data").resolve()
assert all(_data not in pathlib.Path(os.environ[v]).resolve().parents for v in _ISOLATED_PATHS), "a path is in data/"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import _stamp  # noqa: E402
from backend.core import pipeline, response_cache  # noqa: E402
from backend.memory import profile_store  # noqa: E402
from backend.memory.profile_store import get_connection, initialize_schema  # noqa: E402
from backend.providers import ollama_provider  # noqa: E402

# The code measured is the checkout this file sits in, not another one on the path.
assert REPO in pathlib.Path(pipeline.__file__).resolve().parents, pipeline.__file__

MODEL = "qwen2.5:7b"
DB_KEY = "22" * 32  # a throwaway key for throwaway databases
RULE = HERE / "RULE.md"

# Verbatim from docs/eval/greeting_2026-10-17/probe_greeting.py (fixed 2026-10-17).
NO_RECORD = re.compile(
    r"(don't|do not|doesn't|does not)\s+(have|see|seem to have)\b[^.]{0,40}\b(record|information|details|in front of me|data)"
    r"|\bno (record|records|information)\b|not recorded|in front of me",
    re.IGNORECASE,
)

USERS = [
    {"name": "Alex Rai", "preferred_name": "Alex"},
    {"name": "Sita Gurung", "preferred_name": None},
    {"name": "Bikash Thapa", "preferred_name": "Bikash"},
    {"name": "Maria Lopez", "preferred_name": None},
]
MESSAGES = [
    "hi", "hi pip", "hello",
    "hey there", "good morning", "namaste", "hii pip", "yo", "how's it going",
    "hey", "hello there!", "good evening", "good afternoon pip", "hiya", "what's up", "howdy", "heyy",
    "hi, how are you?", "hello pip, nice to meet you", "hey pip, how are you doing today?", "morning!", "hi :)",
    "hola", "sup", "greetings", "good day",
]
assert len(USERS) * len(MESSAGES) == 104 and len(set(MESSAGES)) == len(MESSAGES)

# What the real provider was given, recorded without changing what it sends.
_seen: list[dict] = []
_real_chat = ollama_provider.OllamaProvider.chat


def _recording_chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
    _seen.append({"model": self.model_name, "context": context or "", "messages": list(messages),
                  "options": self.request_options(max_tokens)})
    yield from _real_chat(self, messages, context=context, max_tokens=max_tokens,
                          timeout_seconds=timeout_seconds, response_format=response_format)


ollama_provider.OllamaProvider.chat = _recording_chat


def new_user(index: int, user: dict):
    folder = TMP / f"user{index}"
    folder.mkdir()
    conn = get_connection(str(folder / "pip.db"), db_key=DB_KEY)
    initialize_schema(conn)
    profile_store.complete_onboarding(conn, name=user["name"], preferred_name=user["preferred_name"],
                                      language_preference="English")
    assert pipeline.get_active_model_name(conn) == MODEL, pipeline.get_active_model_name(conn)
    return conn


def ask(conn, message: str) -> dict:
    before = len(_seen)
    started = time.perf_counter()
    try:
        result = pipeline.run_sync(conn, message)
        error = None
    except Exception as exc:  # reported, not hidden
        result, error = {}, f"{type(exc).__name__}: {exc}"
    sent = _seen[before:]
    return {
        "reply": (result.get("response_text") or "").strip(),
        "status": result.get("status"),
        "error": error,
        "seconds": round(time.perf_counter() - started, 1),
        "model_calls": len(sent),
        "model": sent[-1]["model"] if sent else None,
        "options": sent[-1]["options"] if sent else None,
        "system_prompt": sent[-1]["context"] if sent else None,
    }


def main():
    rule_sha = hashlib.sha256(RULE.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    options = ollama_provider.OllamaProvider(MODEL).request_options(2000)
    stamp = _stamp.run_stamp(MODEL, options_sent=options)
    print(_stamp.markdown([stamp]))
    print(f"rule sha256 {rule_sha}; temp folder {TMP}")

    warm = new_user(0, {"name": "Warm Up", "preferred_name": None})
    w = ask(warm, "warm-up check, please ignore")
    print(f"warm-up: {w['seconds']} s, model calls {w['model_calls']}, error {w['error']}")
    warm.close()

    rows = []
    for i, user in enumerate(USERS, start=1):
        response_cache.clear()
        conn = new_user(i, user)
        for message in MESSAGES:
            r = ask(conn, message)
            r.update({"user": user["name"], "message": message,
                      "pattern_no_record": bool(NO_RECORD.search(r["reply"])),
                      "uses_name": any(part.lower() in r["reply"].lower()
                                       for part in filter(None, [user["preferred_name"], user["name"].split()[0]]))})
            rows.append(r)
            flag = "NO-RECORD?" if r["pattern_no_record"] else ""
            print(f"[{len(rows):3}] {user['name']:<12} {message!r:<38} {r['seconds']:>5}s {flag} "
                  f"{(r['error'] or r['reply'])[:110]!r}")
        conn.close()

    answered = [r for r in rows if r["reply"] and not r["error"]]
    out = {
        "stamp": stamp,
        "rule_sha256": rule_sha,
        "pattern": NO_RECORD.pattern,
        "n_asked": len(rows),
        "n_answered": len(answered),
        "pattern_no_record": sum(r["pattern_no_record"] for r in answered),
        "uses_name": sum(r["uses_name"] for r in answered),
        "errors": [r for r in rows if r["error"] or not r["reply"]],
        "every_call_was_the_model": sorted({r["model"] for r in rows if r["model"]}),
        "options_sent": sorted({json.dumps(r["options"], sort_keys=True) for r in rows if r["options"]}),
        "replies": rows,
    }
    (HERE / "results_qwen2.5_7b.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"answered {out['n_answered']} of {out['n_asked']}; pattern no-record {out['pattern_no_record']}; "
          f"uses the name {out['uses_name']}; models {out['every_call_was_the_model']}; options {out['options_sent']}")
    print("wrote results_qwen2.5_7b.json")


if __name__ == "__main__":
    main()
