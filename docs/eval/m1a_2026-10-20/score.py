"""
M-1(a): score the blind grades against the key, by the rule in DESIGN.md (committed in b03f928, before grading).

    .venv\\Scripts\\python.exe docs\\eval\\m1a_2026-10-20\\score.py > docs\\eval\\m1a_2026-10-20\\RESULTS.md

Reads key.json (whose SHA-256 was committed in KEY_SHA256.txt before grading; checked here) and grades.txt (one line
per item: number, S/D/U, a reason for D and U), both beside this file.
"""
import hashlib
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
key_bytes = open(os.path.join(HERE, "key.json"), "rb").read()
committed = open(os.path.join(HERE, "KEY_SHA256.txt"), encoding="utf-8").read().split()[-1]
assert hashlib.sha256(key_bytes).hexdigest() == committed, "key.json is not the key fingerprinted before grading"
key = json.loads(key_bytes)
items = key["items"]

grades = {}
for line in open(os.path.join(HERE, "grades.txt"), encoding="utf-8"):
    if line.strip():
        number, letter, *reason = line.split()
        assert letter in "SDU", line
        grades[number] = (letter, " ".join(reason))
assert sorted(grades, key=int) == sorted(items, key=int), "one grade per item"


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(k, n):
    lo, hi = wilson(k, n)
    return f"{k} of {n} ({100 * k / n:.0f}%; 95% interval {100 * lo:.0f}-{100 * hi:.0f}%)"


accepted = [n for n, i in items.items() if i["gate"] == "EVIDENCE_SUFFICIENT"]
rejected = [n for n, i in items.items() if i["gate"] != "EVIDENCE_SUFFICIENT"]
letters = {n: grades[n][0] for n in items}
false_accept = {"strict": [n for n in accepted if letters[n] in "DU"], "lenient": [n for n in accepted if letters[n] == "D"]}
false_reject = {"strict": [n for n in rejected if letters[n] == "S"], "lenient": [n for n in rejected if letters[n] in "SU"]}

strict_count = len(false_accept["strict"])
verdict = "HOLDS" if strict_count == 0 else "MOSTLY HOLDS" if strict_count <= 3 else "DOES NOT HOLD"

out = ["# M-1(a): results", ""]
out.append(f"Population (genuine user quotes, one per recording + chat + claim + quote): {key['population']['accepted']} "
           f"accepted, {key['population']['rejected']} rejected for support. Graded: all {len(accepted)} accepted and "
           f"{len(rejected)} rejected drawn by seed {key['seed']}, mixed and shuffled, the verdict hidden; one grader, a "
           "fresh Claude session that had not seen the verdicts. Key fingerprint checked.")
out.append("")
out.append("| | strict (U counts against the claim) | lenient (U counts for it) |")
out.append("|---|---|---|")
out.append(f"| accepted but NOT supported (false accepts) | {pct(len(false_accept['strict']), len(accepted))} | "
           f"{pct(len(false_accept['lenient']), len(accepted))} |")
out.append(f"| rejected but supported (false rejects) | {pct(len(false_reject['strict']), len(rejected))} | "
           f"{pct(len(false_reject['lenient']), len(rejected))} |")
out.append("")
out.append(f"**Verdict on Promise 4's wording (rule fixed in DESIGN.md): {verdict}** "
           f"({strict_count} accepted item(s) graded DOES NOT or UNCLEAR on the strict reading; 0 = holds, 1-3 = mostly "
           "holds, 4 or more = does not hold).")
out.append("")


def describe(n):
    i = items[n]
    letter, reason = grades[n]
    return (f"- {n} [{letter}] {i['recording']} {i['chat']}: {i['claim']}; quote \"{i['quote']}\""
            + (f" - grader: {reason}" if reason else "") + f" (gate: {i['gate']})")


out.append("## Accepted items the grader did not find supported")
out += [describe(n) for n in sorted(false_accept["strict"], key=int)] or ["- none"]
out.append("")
out.append("## Rejected items the grader found supported")
out += [describe(n) for n in sorted(false_reject["lenient"], key=int)] or ["- none"]
out.append("")
by_table = {}
for n in accepted:
    t = items[n]["table"]
    by_table.setdefault(t, [0, 0])
    by_table[t][0] += 1
    by_table[t][1] += letters[n] in "DU"
out.append("## Accepted items by table (graded / not supported, strict)")
out += [f"- {t}: {a} / {b}" for t, (a, b) in sorted(by_table.items())]
print("\n".join(out))
