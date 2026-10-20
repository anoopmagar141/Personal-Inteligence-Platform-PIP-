"""
M-1(a): build the blind grading sheet and its hidden key (DESIGN.md beside this file, committed in b03f928).

    .venv\\Scripts\\python.exe docs\\eval\\m1a_2026-10-20\\build_sheet.py --repo <code root> --sheet SHEET.md --key KEY.json

The items come from the real Stage 11 path: each recorded model answer is replayed through observer.run() (parsing,
sanitising, grounding), and each memory candidate it keeps is put to evidence_gate.adjudicate() with the chat's
ledger, as run_session_end does. Kept: candidates whose quote is genuinely the user's (SUFFICIENT, NOT_ENTAILING,
CONTRADICTORY). One item per recording + chat + claim + quote. All accepted items, and as many rejected ones drawn
with seed 20261020; then shuffled with the same seed. The sheet shows no verdict, model, run or recording.
"""

import argparse
import json
import os
import random
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--sheet", required=True)
parser.add_argument("--key", required=True)
args = parser.parse_args()
sys.path.insert(0, args.repo)
sys.path.insert(0, os.path.join(args.repo, "scripts"))

import _stamp  # noqa: E402
from backend.core import evidence_gate  # noqa: E402
from backend.core.evidence_gate import EvidenceLedger, EvidenceState, normalize  # noqa: E402
from backend.memory.profile_store import get_connection, initialize_schema  # noqa: E402
from backend.providers.base_provider import BaseLLMProvider  # noqa: E402
from backend.stages import stage_11_observer as observer  # noqa: E402
from backend.tests.observer_cases import CASES  # noqa: E402

SEED = 20261020
GENUINE = {EvidenceState.EVIDENCE_SUFFICIENT, EvidenceState.EVIDENCE_NOT_ENTAILING,
           EvidenceState.EVIDENCE_CONTRADICTORY}
LONG = os.path.join(args.repo, "docs/eval/v2_2026-10-17/long_chats/long_chat_cases.json")
RECORDINGS = [
    ("v2qwen", "docs/eval/v2_2026-10-17/observer_recording_qwen2.5_7b_ollama0.40.3.json", "short"),
    ("v2llama", "docs/eval/v2_2026-10-17/observer_recording_llama3.1_8b_ollama0.40.3.json", "short"),
    ("v2long", "docs/eval/v2_2026-10-17/observer_recording_long_qwen2.5_7b.json", "long"),
]
CASE_SETS = {
    "short": {c["id"]: c for c in CASES},
    "long": {c["id"]: c for c in json.load(open(LONG, encoding="utf-8"))},
}


class _Replay(BaseLLMProvider):
    def __init__(self, raw):
        self.raw = raw

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield self.raw

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "replay"}


def claim_in_words(c):
    table, field, value = c["target_table"], c["field_name"], c["proposed_value"]
    if table == "preference_memory":
        return f'a preference: "{field}" is "{value}"'
    if table == "skill_memory":
        return f'a skill: "{field}", at level {value} (0 = none, 1 = expert)'
    if table == "goal_memory":
        return f'a goal: "{value}"'
    if table == "active_projects":
        return f'a project of yours: "{field}" ({value})'
    if table == "interaction_style":
        return f'how PIP should answer you: "{value}"'
    if table == "topic_interests":
        return f'a topic you are interested in: "{field}"'
    return f"{table}.{field} = {value}"


def source_turns(ledger, quote):
    for t in ledger.locate(normalize(quote)):
        if t["role"] == "user":
            before = ledger.turns[t["index"] - 1] if t["index"] > 0 else None
            return t["text"], (before["text"] if before and before["role"] == "assistant" else None)
    raise AssertionError(f"a genuine quote is not in any user turn: {quote!r}")


items = {}
with tempfile.TemporaryDirectory() as tmp:
    conn = get_connection(os.path.join(tmp, "m1a.db"))
    initialize_schema(conn)
    for name, path, kind in RECORDINGS:
        runs = json.load(open(os.path.join(args.repo, path), encoding="utf-8"))["runs"]
        for run_index, run in enumerate(runs):
            for recorded in run:
                case = CASE_SETS[kind][recorded["id"]]
                out = observer.run(case["transcript"], _Replay(recorded["raw"]), conn)
                ledger = EvidenceLedger.from_transcript(case["transcript"])
                for cand in out["memory_candidates"]:
                    verdict = evidence_gate.adjudicate(cand, ledger)
                    if verdict.state not in GENUINE:
                        continue
                    key = (name, case["id"], cand["target_table"], str(cand["field_name"]).lower(),
                           str(cand["proposed_value"]).lower(), normalize(cand["evidence_text"]))
                    if key in items:
                        continue
                    message, before = source_turns(ledger, cand["evidence_text"])
                    items[key] = {
                        "recording": name, "chat": case["id"], "run": run_index, "gate": verdict.state,
                        "gate_detail": verdict.detail, "table": cand["target_table"], "field": cand["field_name"],
                        "value": cand["proposed_value"], "label": cand.get("label"), "quote": cand["evidence_text"],
                        "claim": claim_in_words(cand), "message": message, "before": before,
                    }
    conn.close()

ordered = [items[k] for k in sorted(items)]
accepted = [i for i in ordered if i["gate"] == EvidenceState.EVIDENCE_SUFFICIENT]
rejected = [i for i in ordered if i["gate"] != EvidenceState.EVIDENCE_SUFFICIENT]
rng = random.Random(SEED)
chosen = accepted + rng.sample(rejected, k=min(len(accepted), len(rejected)))
rng.shuffle(chosen)

stamp = _stamp.run_stamp(model=None)
key = {"stamp": stamp, "seed": SEED, "population": {"accepted": len(accepted), "rejected": len(rejected)},
       "items": {str(n): item for n, item in enumerate(chosen, 1)}}
with open(args.key, "w", encoding="utf-8", newline="\n") as f:
    json.dump(key, f, indent=1, ensure_ascii=False)

lines = [
    "# M-1(a) grading sheet",
    "",
    "For each item, PIP proposed to remember something about the user, citing the user's own words. Decide whether",
    "those words support it. Answer each item with one letter:",
    "",
    "- **S** (SUPPORTS): the user's own words in their message say this about themselves; the claim is a fair reading",
    "  of what they said about themselves, not more.",
    "- **D** (DOES NOT): the words do not say it - they are about someone else, a question, a guess, a plan they have",
    "  not made, something in the past, said the other way round, or the claim says more than they did.",
    "- **U** (UNCLEAR): you cannot tell.",
    "",
    "For a topic, S means the user themselves raised it (asking about it counts). For a skill, the words have to show",
    "the skill and roughly that level. Judge each item on its own. Nothing else on this sheet says what PIP did.",
    "",
]
for n, item in enumerate(chosen, 1):
    lines += [f"## {n}", f"PIP would remember about you: {item['claim']}", f"Quote: \"{item['quote']}\"",
              f"Your message: \"{item['message']}\""]
    if item["before"]:
        lines.append(f"PIP's message just before: \"{item['before']}\"")
    lines.append("")
with open(args.sheet, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

print(f"population: {len(accepted)} accepted, {len(rejected)} rejected; sheet: {len(chosen)} items")
