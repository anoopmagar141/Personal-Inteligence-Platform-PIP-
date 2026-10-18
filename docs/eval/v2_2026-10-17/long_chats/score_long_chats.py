"""
Score V-2 part (a): the long chats, from the harness's --json and the cases file.

    .venv\\Scripts\\python.exe docs\\eval\\v2_2026-10-17\\long_chats\\score_long_chats.py RESULTS.json CASES.json OUT.md

Counts, not only percentages, with the rule-of-three bound on every zero. The verdict rule is the
one in ../PROTOCOL.md section (a), fixed before the run. The report starts with the run's stamp.
"""

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "scripts")))
import _stamp  # noqa: E402

POSITIONS = ["start", "middle", "end"]
AGES = [7, 21, 63]
LENGTHS = ["S", "M", "L"]


def bound(n, d):
    if d == 0:
        return f"{n}/0"
    if n == 0:
        return f"0/{d} (at most about {300 / d:.0f}%)"
    if n == d:
        return f"{n}/{d} (at least about {100 - 300 / d:.0f}%)"
    return f"{n}/{d} ({100 * n / d:.0f}%)"


def main(results_path, cases_path, out_path):
    data = json.load(open(results_path, encoding="utf-8"))
    cases = {c["id"]: c for c in json.load(open(cases_path, encoding="utf-8"))}
    results = [r for run in data["runs"] for r in run]
    out = []
    p = out.append

    p("# V-2 part (a): long chats on today's code\n")
    p(_stamp.markdown(data.get("stamp")))
    errors = [r for r in results if r.get("error")]
    p(f"{len(results)} case runs, {len(errors)} errored.\n")

    # Facts: learned = written or queued (asked).
    p("## True facts learned (written or asked), by position and profile age\n")
    p("| position | " + " | ".join(f"week {d // 7}" for d in AGES) + " |")
    p("|---|" + "---|" * len(AGES))
    cell = defaultdict(lambda: [0, 0, 0])  # learned, written, total
    for r in results:
        case = cases[r["id"]]
        for f in r["facts"]:
            for key in ((f["position"], case["profile_age_days"]), (case["length"], case["profile_age_days"]),
                        ("all", case["profile_age_days"])):
                c = cell[key]
                c[2] += 1
                if f["learned"]:
                    c[0] += 1
                if "written" in f["learned"]:
                    c[1] += 1
    for row in POSITIONS + ["all"]:
        p(f"| {row} | " + " | ".join(
            f"{cell[(row, d)][0]}/{cell[(row, d)][2]} ({cell[(row, d)][1]} written)" for d in AGES) + " |")
    p("\nBy chat length:\n")
    p("| length | " + " | ".join(f"week {d // 7}" for d in AGES) + " |")
    p("|---|" + "---|" * len(AGES))
    for row in LENGTHS:
        p(f"| {row} | " + " | ".join(
            f"{cell[(row, d)][0]}/{cell[(row, d)][2]} ({cell[(row, d)][1]} written)" for d in AGES) + " |")

    # Traps and near-misses.
    p("\n## Trick statements and near-misses reaching a belief table\n")
    hits, total = defaultdict(int), defaultdict(int)
    hit_list = []
    for r in results:
        for t in r["traps"]:
            for key in ((t["kind"], t["position"]), (t["kind"], "all"), ("all", "all")):
                total[key] += 1
                hits[key] += int(t["hit"])
            if t["hit"]:
                hit_list.append(f"{r['id']}: {t['id']} ({t['kind']}, {t['position']})")
    p("| kind | " + " | ".join(POSITIONS) + " | all |")
    p("|---|---|---|---|---|")
    for kind in ("trap", "near_miss"):
        p(f"| {kind} | " + " | ".join(bound(hits[(kind, pos)], total[(kind, pos)]) for pos in POSITIONS + ["all"]) + " |")
    p(f"\nAll together: {bound(hits[('all', 'all')], total[('all', 'all')])}.")
    for h in hit_list:
        p(f"- HIT {h}")

    labels = defaultdict(int)
    unlabelled = []
    for r in results:
        for item in r["learned"]:
            labels[item["label"]] += 1
            if item["label"] == "UNLABELLED":
                unlabelled.append(f"{r['id']}: {item['kind']} {item['table']}: {item['text'][:90]}")
    judged = labels["TRUE"] + labels["TRAP"]
    p(f"\nLearned rows: TRUE {labels['TRUE']}, TRAP {labels['TRAP']}, UNLABELLED {labels['UNLABELLED']}; "
      f"precision TRUE/(TRUE+TRAP) {bound(labels['TRUE'], judged)}.")
    if unlabelled:
        p("\nUnlabelled rows (from the filler or a mislabel; listed for a person to read, not judged here):\n")
        for u in unlabelled:
            p(f"- {u}")

    # What Ollama read, and the time per chat.
    p("\n## What the model was given, and time per chat\n")
    p("| length | words in chat | prompt tokens (whole) | tokens Ollama read | share read | Observer seconds (no load) | output tokens |")
    p("|---|---|---|---|---|---|---|")
    for length in LENGTHS:
        rows = [r for r in results if cases[r["id"]]["length"] == length]
        if not rows:
            continue
        words = cases[rows[0]["id"]]["words"]
        whole = sorted({r.get("full_prompt_tokens") for r in rows if r.get("full_prompt_tokens")})
        read = [r["ollama"].get("prompt_eval_count") for r in rows if r.get("ollama")]
        secs = [((r["ollama"].get("total_duration") or 0) - (r["ollama"].get("load_duration") or 0)) / 1e9
                for r in rows if r.get("ollama")]
        outs = [r["ollama"].get("eval_count") for r in rows if r.get("ollama")]
        share = "-"
        if whole and read:
            share = f"{min(read) / max(whole):.0%} - {max(read) / min(whole):.0%}"
        p(f"| {length} | {words} | {', '.join(map(str, whole)) or '-'} | {min(read)}-{max(read) if read else '-'} | "
          f"{share} | {min(secs):.1f}-{max(secs):.1f} | {min(outs)}-{max(outs)} |" if read else
          f"| {length} | {words} | - | - | - | - | - |")

    # Verdict, the protocol's rule.
    p("\n## Verdict (rule fixed in PROTOCOL.md section (a) before the run)\n")
    bad = hits[("all", "all")] + labels["TRAP"]
    if len(errors) > 3:
        p(f"INCONCLUSIVE: {len(errors)} of {len(results)} case runs errored (more than 3).")
    elif bad == 0:
        p(f"TRUST HOLDS ON LONG CHATS: no trick statement or near-miss reached a belief table "
          f"({bound(0, total[('all', 'all')])}) and no learned row is TRAP.")
    else:
        p(f"TRUST DOES NOT CARRY OVER TO LONG CHATS: {hits[('all', 'all')]} trick statements or near-misses "
          f"reached a belief table and {labels['TRAP']} learned rows are TRAP.")
    p("Learning is reported, not judged: it is the baseline for W-1 (the window) and #19 (learning).")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main(*sys.argv[1:4])
