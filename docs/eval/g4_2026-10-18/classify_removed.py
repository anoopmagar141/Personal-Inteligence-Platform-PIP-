"""
Hand classification of every decision the evidence gate removed in G-4's replays (FREEZE_LIST section 7.60).

Reads replays_decisions_changed.txt beside this file: every recording replayed through 934cf04 (before G-4) and
69252d9 (G-4), one line per decision whose outcome changed, with its decision text and quote. Each quote prefix
below was read with its chat. Strict = a decision the user plainly made; lenient adds the borderline calls that
FREEZE_LIST section 7.14's hand review counted as decisions (a settled habit, "I'll pass", the corrected deadline).

    .venv\\Scripts\\python.exe docs\\eval\\g4_2026-10-18\\classify_removed.py
"""
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = [  # (quote prefix, category)
    ("User: Good, I'll stay put", "REAL strict: stay with Docker Compose (quote carries 'User:')"),
    ("User: I've decided to move our database to Postgres", "REAL strict: Postgres (quote carries 'User:')"),
    ("One more thing about me: I want to pass the AWS", "REAL strict: AWS exam goal (quote ends in a question)"),
    ("User: One more thing about me: I want to pass the AWS", "REAL strict: AWS exam goal (quote carries 'User:')"),
    ("Ha, I'll pass", "REAL lenient: won't learn Java"),
    ("I'll pass", "REAL lenient: won't learn Java"),
    ("Sorry, I mean May", "REAL lenient: beta in May"),
    ("I always write my tests with pytest", "REAL lenient: keep using pytest (a habit)"),
    ("I do all my diagrams in Excalidraw", "REAL lenient: Excalidraw (a habit)"),
    ("Quick aside before the next question: I do all my diagrams in Excalidraw", "REAL lenient: Excalidraw (a habit)"),
    ("Yes, next week", "REAL lenient: migration plan next week"),
    ("User: Yes, next week", "REAL lenient: migration plan next week"),
    ("I don't use Emacs, never have, and I don't plan to", "REAL lenient: will not use Emacs"),
    # Right to drop.
    ("Spaced practice beats cramming", "ok: the assistant's words"),
    ("I'll go into more detail then", "ok: the assistant's words"),
    ("For an entry-level exam", "ok: the assistant's words"),
    ("For small scripts, yes", "ok: the assistant's words"),
    ("An ingredient table plus", "ok: the assistant's words"),
    ("Usually yes: an ingredient table", "ok: the assistant's words"),
    ("Plain nouns that match", "ok: the assistant's words"),
    ("A load balancer sits", "ok: the assistant's words"),
    ("You need a merge rule", "ok: the assistant's words"),
    ("my friend wants to pass the Azure", "ok: someone else's"),
    ("My flatmate swears by Notepad++", "ok: someone else's"),
    ("My supervisor does all her diagrams", "ok: someone else's"),
    ("Please keep your answers short", "ok: a preference, not a decision"),
    ("I'd like shorter answers", "ok: a preference, not a decision"),
    ("Please answer me in French", "ok: a preference, not a decision"),
]
TENTATIVE = "ok: tentative, a question, a fragment or no decision"

counts = Counter()
for line in open(os.path.join(HERE, "replays_decisions_changed.txt"), encoding="utf-8"):
    if " -> rejected" not in line:
        continue
    quote = re.sub(r"^.*\| quote ", "", line.rstrip("\n"))[1:]
    cat = next((c for p, c in RULES if quote.startswith(p)), TENTATIVE)
    counts[cat] += 1
    if cat == TENTATIVE:
        counts["  (" + quote[:60] + ")"] += 1
total = sum(v for k, v in counts.items() if not k.startswith("  ("))
print("removed decisions:", total)
for k, v in sorted(counts.items()):
    if not k.startswith("  ("):
        print(f"  {v:3d}  {k}")
strict = sum(v for k, v in counts.items() if k.startswith("REAL strict"))
lenient = strict + sum(v for k, v in counts.items() if k.startswith("REAL lenient"))
print(f"real decisions removed: strict {strict}, lenient {lenient}; right to remove: {total - lenient}")
print("tentative bucket, for reading:")
for k, v in sorted(counts.items()):
    if k.startswith("  ("):
        print(f"  {v:3d} {k}")
