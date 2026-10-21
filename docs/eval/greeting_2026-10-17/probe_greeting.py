"""
Probe: why does "hi" get "I don't have a record of that"?

The owner, 2026-10-17: typing "hi" makes PIP answer that it has no record, and PIP "feels less
intelligent". Reading the code gave a suspected cause, not a measured one:
  * Stage 1 has no greeting category: "hi" is general_knowledge with skip_rag (checked).
  * Stage 7 sends _DEFAULT_SYSTEM_INSTRUCTIONS on every turn: six rules, most about NOT stating
    what is not in the context ("say you do not have it in front of you, and stop").
  * A 7B model may apply rule 4 to a greeting.
This probe builds the exact (context, messages) Stage 7 builds for a greeting, from made-up
profiles (never the owner's data/), sends it to the local model the way OllamaProvider.chat()
does (context as the system message, no num_ctx, no temperature set), and counts the replies
that claim to have no record.

Conditions (same messages, same seeds, only the named thing changes):
  A  shipped rules, NEW user (identity only, no projects, no snapshot)
  B  shipped rules, REGULAR user (identity, answer style, two projects, a "where we left off" note)
  C  as B, but the six rules replaced by one persona line          -> isolates the rules
  D  as B, plus one line about greetings appended to the rules      -> does a cheap rule fix it?
Messages: "hi", "hi pip", "hello". Seeds 1-5. 4 x 3 x 5 = 60 replies.

A reply is counted as a "no-record reply" by a fixed pattern (NO_RECORD below), decided before the
run; every reply is saved so the count can be checked by hand.

Run (Ollama up, qwen2.5:7b pulled, no test suite running):
    .venv\\Scripts\\python.exe docs\\eval\\greeting_2026-10-17\\probe_greeting.py
Writes results_<model>.json next to this file. Other models: set PROBE_MODEL (e.g. llama3.1:8b).
"""
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)

from backend.stages import stage_01_intent_classifier as s1  # noqa: E402
from backend.stages import stage_04_memory_lookup as s4  # noqa: E402
from backend.stages import stage_07_context_assembly as s7  # noqa: E402

HOST = "http://127.0.0.1:11434"
MODEL = os.environ.get("PROBE_MODEL", "qwen2.5:7b")
MESSAGES = ["hi", "hi pip", "hello"]
SEEDS = list(range(1, int(os.environ.get("PROBE_SEEDS", "5")) + 1))

NO_RECORD = re.compile(
    r"(don't|do not|doesn't|does not)\s+(have|see|seem to have)\b[^.]{0,40}\b(record|information|details|in front of me|data)"
    r"|\bno (record|records|information)\b|not recorded|in front of me",
    re.IGNORECASE,
)

IDENTITY = [
    {"table": "identity", "field": "name", "value": "Alex Rai"},
    {"table": "identity", "field": "calling_name", "value": "Alex"},
    {"table": "identity", "field": "language", "value": "English"},
]
REGULAR_EXTRA = [
    {"table": "interaction_style", "field": "answer_style", "value": "short and direct"},
    {"table": "active_projects", "field": "PIP", "value": "final-year project: a private personal assistant"},
    {"table": "active_projects", "field": "Garden log", "value": "a small app to track plants"},
]
SNAPSHOT = {
    "topic": "testing why document search finds too little",
    "last_decisions": ["keep the 0.60 cut-off until the owner's documents are tested"],
    "open_problems": ["search misses most passages in long prose files"],
    "suggested_next_step": "run the cut-off test on two more documents",
}
PERSONA_ONLY = "You are PIP, a locally-run personal assistant."
GREETING_LINE = (
    "\n7. If the user only greets you or makes small talk, reply warmly and briefly in your own "
    "words, use their name if the context has it, and offer to pick up where you left off if a "
    "last-session note is present. A greeting is not a request for a record."
)


def build(message, profile, snapshot, rules):
    category = s1.run(message)["category"]
    expected = s4.tables_for_category(category)
    fields = [f for f in profile if f["table"] in expected]
    return category, s7.run(
        message,
        system_instructions=rules,
        profile_fields=fields,
        session_snapshot=snapshot,
        decision_log_entries=[],
        rag_chunks=[],
        web_results=[],
        conversation_history=[],
        context_depth_modifier=0,  # a new chat opened soon after the last one
        category=category,
    )


def ask(assembled, seed):
    # Same shape as OllamaProvider.chat(): context first as the system message, num_predict only.
    # The seed is added so a rerun is reproducible; it does not change the sampling settings.
    messages = [{"role": "system", "content": assembled["context"]}] + assembled["messages"]
    payload = {"model": MODEL, "messages": messages, "stream": False,
               "options": {"num_predict": 200, "seed": seed}}
    req = urllib.request.Request(HOST + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"].strip()


def main():
    version = json.loads(urllib.request.urlopen(HOST + "/api/version", timeout=10).read())["version"]
    tags = [m["name"] for m in json.loads(urllib.request.urlopen(HOST + "/api/tags", timeout=10).read())["models"]]
    if MODEL not in tags:
        sys.exit(f"{MODEL} is not pulled; stopping (this probe downloads nothing). Pulled: {tags}")

    shipped = s7._DEFAULT_SYSTEM_INSTRUCTIONS
    conditions = {
        "A_shipped_rules_new_user": (IDENTITY, None, shipped),
        "B_shipped_rules_regular_user": (IDENTITY + REGULAR_EXTRA, SNAPSHOT, shipped),
        "C_no_rules_regular_user": (IDENTITY + REGULAR_EXTRA, SNAPSHOT, PERSONA_ONLY),
        "D_rules_plus_greeting_line": (IDENTITY + REGULAR_EXTRA, SNAPSHOT, shipped + GREETING_LINE),
        # Added after the first run: A was the only condition that failed, and D had been tried on
        # the regular user only, so the greeting line was untested where it matters.
        "E_rules_plus_greeting_line_new_user": (IDENTITY, None, shipped + GREETING_LINE),
    }
    only = os.environ.get("PROBE_ONLY")
    if only:
        conditions = {k: v for k, v in conditions.items() if k.split("_")[0] in only.split(",")}
    out = {"ollama_version": version, "model": MODEL, "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
           "pattern": NO_RECORD.pattern, "conditions": {}}
    for name, (profile, snapshot, rules) in conditions.items():
        rows, prompt_example = [], None
        for message in MESSAGES:
            category, assembled = build(message, profile, snapshot, rules)
            if prompt_example is None:
                prompt_example = assembled["context"]
            for seed in SEEDS:
                reply = ask(assembled, seed)
                rows.append({"message": message, "category": category, "seed": seed,
                             "no_record": bool(NO_RECORD.search(reply)),
                             "uses_name": "alex" in reply.lower(), "reply": reply})
        n_bad = sum(r["no_record"] for r in rows)
        n_name = sum(r["uses_name"] for r in rows)
        out["conditions"][name] = {"no_record_replies": n_bad, "uses_name": n_name, "total": len(rows),
                                   "system_prompt_for_hi": prompt_example, "replies": rows}
        print(f"{name}: no-record {n_bad} of {len(rows)}; uses the name {n_name} of {len(rows)}")
        for r in rows[:3]:
            print("   ", repr(r["message"]), "->", r["reply"][:140].replace("\n", " "))
    name = "results_" + re.sub(r"[^a-z0-9.]+", "_", MODEL.lower())
    if only:
        name += "_" + only.replace(",", "") + "_seeds" + str(len(SEEDS))
    name += ".json"
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("wrote " + name)


if __name__ == "__main__":
    main()
