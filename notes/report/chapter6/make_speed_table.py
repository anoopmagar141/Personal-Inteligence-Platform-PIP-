"""Writes Table 6.2 (answer speed, before and after the D-50 fix) as Markdown and Word-ready HTML.

Reads measure_speed.py's result files in results/:
  speed_2026-10-21_app.json            before: the app as shipped at 6a51798 (Ollama at "localhost")
  speed_2026-10-22_app_after-fix.json  after: the same app with the D-50 fix (Ollama at 127.0.0.1), on 52db009
  speed_2026-10-21_app-ipv4.json       the 2026-10-21 prediction: the harness forced 127.0.0.1, no code changed
  speed_2026-10-21_pinned.json         the model handed in directly, which skips the availability check
No backend, shared or scripts file differs between 6a51798 and 52db009, so "before" holds for 52db009 too.

Run: .venv/Scripts/python.exe -I notes/report/chapter6/make_speed_table.py
"""
import json
import os
import statistics
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
PC = "Intel Core i9-14900HX, 16 GB RAM, NVIDIA GeForce RTX 4060 Laptop GPU (8 GB), Windows 11 Home"
TITLE = "Table 6.2: Answer speed of PIP on the test PC, before and after the D-50 fix"
HEAD = ["Message", "First word, before (s)", "First word, after (s)", "Full answer, before (s)",
        "Full answer, after (s)", "Tokens written", "Speed (tokens/s)"]


def load(name):
    return json.load(open(os.path.join(RESULTS, name), encoding="utf-8"))


def med(values, digits=1, spread=True):
    values = [v for v in values if v is not None]
    if not values:
        return "–"
    m = statistics.median(values)
    if not spread or len(values) == 1:
        return f"{m:.{digits}f}"
    return f"{m:.{digits}f} ({min(values):.{digits}f}–{max(values):.{digits}f})"


def rate(run):
    first, full, out = run.get("first_word_s"), run.get("full_answer_s"), run.get("tokens_out")
    if first is None or full is None or not out or full <= first:
        return None
    return out / (full - first)


def runs(rec, qid):
    return [r for r in rec["runs"] if r["question"] == qid and r.get("status") == "success"]


def build():
    before, after = load("speed_2026-10-21_app.json"), load("speed_2026-10-22_app_after-fix.json")
    predicted, pinned = load("speed_2026-10-21_app-ipv4.json"), load("speed_2026-10-21_pinned.json")
    rows = []
    for q in before["questions"]:
        b, a = runs(before, q["id"]), runs(after, q["id"])
        rows.append((
            f"{q['kind']}: “{q['message']}”" + (" (after 2 earlier turns)" if q["history_turns"] else ""),
            med([r["first_word_s"] for r in b]), med([r["first_word_s"] for r in a]),
            med([r["full_answer_s"] for r in b]), med([r["full_answer_s"] for r in a]),
            med([r["tokens_out"] for r in b + a], 0, spread=False), med([rate(r) for r in b + a], 0, spread=False),
        ))
    cb, ca = before["cold"], after["cold"]
    rows.append((
        "Cold start: “What is a hash map?” with the model not yet loaded "
        f"(loading: {cb.get('load_s')} s and {ca.get('load_s')} s)",
        med([cb.get("first_word_s")]), med([ca.get("first_word_s")]),
        med([cb.get("full_answer_s")]), med([ca.get("full_answer_s")]),
        med([cb.get("tokens_out"), ca.get("tokens_out")], 0, spread=False), med([rate(cb), rate(ca)], 0, spread=False),
    ))
    rows.append((
        "The same first message asked again (from the answer cache, no model call)",
        med([h.get("first_word_s") for h in before["cache_hits"]], 2),
        med([h.get("first_word_s") for h in after["cache_hits"]], 2),
        med([h.get("full_answer_s") for h in before["cache_hits"]], 2),
        med([h.get("full_answer_s") for h in after["cache_hits"]], 2),
        "–", "–",
    ))

    def first_words(rec):
        return med([r["first_word_s"] for r in rec["runs"] if r.get("status") == "success"], 2)

    def steps(rec):
        return med([r["pip_steps_ms"] / 1000 for r in rec["runs"] if r.get("pip_steps_ms") is not None], 2)

    total = sum(len(rec["runs"]) + 1 + len(rec["cache_hits"]) for rec in (before, after))
    failed = sum(len([r for r in rec["runs"] if r.get("status") != "success"]) for rec in (before, after))
    sb, sa = before["stamp"], after["stamp"]
    note = (
        "Each row is the median of 3 runs, with the lowest and highest in brackets; the cold start is one run. "
        "Times are wall-clock seconds from the moment a message enters PIP's pipeline, run exactly as the chat "
        "uses it: first word = the first streamed token, full answer = the whole reply. "
        f"Before = PIP as shipped (commit {sb['git']['commit'][:7]}, {sb['date'][:10]}): it called Ollama at "
        "\"localhost\", which on this PC resolves to the IPv6 address ::1 first while Ollama listens on 127.0.0.1 "
        "only, so every request waited 2.04 s before falling back, twice per message (the availability check and "
        f"the answer). After = the D-50 fix, Ollama called at 127.0.0.1 (commit {sa['git']['commit'][:7]} plus the "
        f"fix, {sa['date'][:10]}). Over all 24 runs the first word took a median {first_words(before)} s before and "
        f"{first_words(after)} s after; the day before the fix, the test script forcing 127.0.0.1 without changing "
        f"PIP had predicted {first_words(predicted)} s. PIP's own steps before the model (Stages 0–8, the "
        f"availability check included) took {steps(before)} s before and {steps(after)} s after. With the model "
        f"handed in directly (no availability check, still localhost) the first word took "
        f"{med([r['first_word_s'] for r in pinned['runs']], 1, spread=False)} s, one 2 s wait. Full-answer times "
        "also follow the answer's length, which differed between runs and days even at temperature 0 (the "
        "explanation was 262 or 662 tokens before and 395 after), so the first word is the clean comparison; "
        "tokens written and speed are medians over both. The answer cache was emptied before every timed question. "
        f"Test PC: {PC}. Model {sb['model']['tag']} (Q4_K_M, digest {sb['model']['digest'][:12]}) on Ollama "
        f"{sb['ollama']['version']}, 16,384-token window, temperature 0. A throwaway test profile, never the user's "
        f"own data. Failed runs: {failed} of {total}."
    )
    return rows, note


def write(rows, note):
    md = [f"# {TITLE}", "", "| " + " | ".join(HEAD) + " |", "|" + "---|" * len(HEAD)]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    md += ["", f"*Note.* {note}", ""]
    with open(os.path.join(HERE, "table_6_2_answer_speed.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    body = "\n".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{TITLE}</title>
<style>
  body {{ font-family: "Times New Roman", serif; font-size: 10pt; margin: 24px; background: #fff; color: #000; }}
  p.cap {{ font-size: 12pt; margin: 0 0 6px 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #000; padding: 3px 5px; vertical-align: top; text-align: left; }}
  td + td {{ white-space: nowrap; }}
  th {{ background: #d9d9d9; font-weight: bold; }}
  p.note {{ font-size: 10pt; margin-top: 6px; }}
</style></head><body>
<p class="cap"><b>{TITLE}</b></p>
<table><thead><tr>{''.join(f'<th>{escape(h)}</th>' for h in HEAD)}</tr></thead>
<tbody>
{body}
</tbody></table>
<p class="note"><i>Note.</i> {escape(note)}</p>
</body></html>
"""
    with open(os.path.join(HERE, "table_6_2_answer_speed.html"), "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    rows, note = build()
    write(rows, note)
    for r in rows:
        print(" | ".join(str(c) for c in r).encode("ascii", "replace").decode())
    print(note.encode("ascii", "replace").decode())
