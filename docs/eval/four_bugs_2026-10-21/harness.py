"""
Scores a candidate replacement for evidence_gate._topic_raising_text (D-41, D-46) against the current one.

    <venv python> harness.py --impl my_rule.py [--probes probes.json] [--skip-pytest] [--json out.json]

my_rule.py must define  topic_raising_text(quote: str, user_sources: list) -> str  (same contract as the gate's
_topic_raising_text: the part of the normalised quote that raises a topic as the USER's). It may import helpers from
backend.core.evidence_gate. Nothing in the repository is edited: the function is swapped in memory, and pytest runs
with a plugin that swaps it the same way.

Reports, current rule vs candidate, every verdict that changes:
  1. pytest on the gate/observer test files that touch topics (pass/fail, failing ids)
  2. the labelled corpus (backend/tests/evidence_cases.py), topic cases: expected vs got
  3. M-1(a)'s graded topic items (docs/eval/m1a_2026-10-20/key.json + grades.txt): S/D/U per changed item
  4. every topic_interests candidate the model proposed in seven recordings (raw model output kept in the replays),
     re-judged against its chat; labelled TRUE / TRAP / UNLABELLED from the chat's own learn/avoid specs
  5. probe sentences (expect accept / refuse)
"""
import argparse, importlib.util, json, os, re, subprocess, sys
from collections import Counter
from pathlib import Path

REPO = Path(r"D:\FINAL YEAR PROJECT\Personal Inteligence Platform (PIP)")
HERE = Path(__file__).resolve().parent
REPLAYS = HERE.parent / "replays"
ORIG = Path.cwd()
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from backend.core import evidence_gate as eg  # noqa: E402
from backend.core.evidence_gate import EvidenceLedger, adjudicate  # noqa: E402

BASELINE = eg._topic_raising_text
TEST_FILES = [
    "backend/tests/test_evidence_gate.py", "backend/tests/test_topic_raised_by_the_user.py",
    "backend/tests/test_observer_decisions_through_the_gate.py", "backend/tests/test_stage_11_observer.py",
    "backend/tests/test_observer_coverage.py", "backend/tests/test_observer_governance.py",
    "backend/tests/test_shortfall_questions.py", "backend/tests/test_half_wired_tables.py",
]


def load_impl(path):
    spec = importlib.util.spec_from_file_location("topic_impl", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.topic_raising_text


def verdict_with(fn, cand, transcript):
    eg._topic_raising_text = fn
    try:
        return adjudicate(cand, EvidenceLedger.from_transcript(transcript))
    finally:
        eg._topic_raising_text = BASELINE


def both(impl, cand, transcript):
    return verdict_with(BASELINE, cand, transcript), verdict_with(impl, cand, transcript)


def topic(field, value, quote):
    return {"target_table": "topic_interests", "field_name": field, "proposed_value": value, "label": "explicit",
            "evidence_count": 1, "evidence_text": quote}


def run_pytest(impl_path):
    env = dict(os.environ, TOPIC_IMPL=str(impl_path), PYTHONPATH=str(HERE) + os.pathsep + str(REPO))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
                        "-p", "patch_plugin", *TEST_FILES], cwd=REPO, env=env, capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    return {"summary": lines[-1] if lines else r.stderr[-300:],
            "failed": [l.split(" ", 1)[1][:200] for l in lines if l.startswith("FAILED ")]}


def corpus(impl):
    from backend.tests.evidence_cases import CASES, HELD_OUT, NEW_HELD_OUT
    out = {"cases": 0, "changed": []}
    for c in CASES + HELD_OUT + NEW_HELD_OUT:
        if c["candidate"].get("target_table") != "topic_interests":
            continue
        out["cases"] += 1
        b, a = both(impl, c["candidate"], c["transcript"])
        if b.state != a.state:
            out["changed"].append({"id": c["id"], "expected": c["expected_state"], "before": b.state, "after": a.state})
    return out


def m1a(impl):
    key = json.load(open(REPO / "docs/eval/m1a_2026-10-20/key.json", encoding="utf-8"))["items"]
    grades = {}
    for line in open(REPO / "docs/eval/m1a_2026-10-20/grades.txt", encoding="utf-8"):
        m = re.match(r"\s*(\d+)\s*[:.\-]?\s*([SDU])\b", line)
        if m:
            grades[m.group(1)] = m.group(2)
    out = {"items": 0, "changed": []}
    for k, it in key.items():
        if it["table"] != "topic_interests":
            continue
        out["items"] += 1
        transcript = (f"Assistant: {it['before']}\n" if it.get("before") else "") + f"User: {it['message']}"
        b, a = both(impl, topic(it["field"], it["value"], it["quote"]), transcript)
        if b.state != a.state:
            out["changed"].append({"item": k, "grade": grades.get(k, "?"), "field": it["field"],
                                   "quote": it["quote"][:140], "before": b.state, "after": a.state})
    return out


def label(text, case):
    t = f" {text.lower()} "
    for spec in case.get("learn", []):
        if "topic_interests" in spec["tables"] and any(k in t for k in spec["keywords"]):
            return "TRUE"
    for spec in case.get("avoid", []):
        if "topic_interests" in spec["tables"] and any(k in t for k in spec["keywords"]):
            return "TRAP"
    return "UNLABELLED"


def replays(impl):
    from backend.tests.observer_cases import CASES
    short = {c["id"]: c for c in CASES}
    long_ = {c["id"]: c for c in json.load(open(REPO / "docs/eval/v2_2026-10-17/long_chats/long_chat_cases.json",
                                                 encoding="utf-8"))}
    totals = {"before": Counter(), "after": Counter()}
    changed = []
    n = 0
    for f in sorted(REPLAYS.glob("*_after.json")):
        name = f.name.replace("_after.json", "")
        for ri, run in enumerate(json.load(open(f, encoding="utf-8"))["runs"]):
            for c in run:
                case = long_.get(c["id"]) or short.get(c["id"])
                try:
                    raw = json.loads(c["raw_text"] or "{}")
                except json.JSONDecodeError:
                    continue
                for m in raw.get("memory_candidates", []):
                    if m.get("target_table") != "topic_interests":
                        continue
                    n += 1
                    lab = label(f"{m.get('field_name')} {m.get('proposed_value')}", case)
                    b, a = both(impl, m, case["transcript"])
                    if b.sufficient:
                        totals["before"][lab] += 1
                    if a.sufficient:
                        totals["after"][lab] += 1
                    if b.sufficient != a.sufficient:
                        changed.append({"rec": name, "run": ri, "case": c["id"], "label": lab,
                                        "field": str(m.get("field_name"))[:40], "quote": str(m.get("evidence_text"))[:140],
                                        "before": b.state, "after": a.state})
    return {"topic_candidates": n, "accepted_before": dict(totals["before"]), "accepted_after": dict(totals["after"]),
            "changed": changed}


def probes(impl, path):
    out = []
    for p in json.load(open(path, encoding="utf-8")):
        b, a = both(impl, topic(p["field"], p["field"], p["turn"]), f"User: {p['turn']}\nAssistant: I see.\n")
        got = "accept" if a.sufficient else "refuse"
        out.append({"turn": p["turn"], "expect": p["expect"], "before": "accept" if b.sufficient else "refuse",
                    "after": got, "ok": got == p["expect"], "after_state": a.state})
    return {"ok": sum(o["ok"] for o in out), "of": len(out), "items": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True)
    ap.add_argument("--probes", default=str(HERE / "probes_dev.json"))
    ap.add_argument("--skip-pytest", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    for k in ("impl", "probes", "json"):
        if getattr(args, k):
            setattr(args, k, str((ORIG / getattr(args, k)).resolve()))
    impl = load_impl(args.impl)
    report = {"impl": args.impl}
    if not args.skip_pytest:
        report["pytest"] = run_pytest(Path(args.impl).resolve())
    report["corpus"] = corpus(impl)
    report["m1a"] = m1a(impl)
    report["replays"] = replays(impl)
    report["probes"] = probes(impl, args.probes)
    text = json.dumps(report, indent=1)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
