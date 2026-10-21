# D-46, D-41, D-30, D-29 (and D-48): the evidence (2026-10-21, no model)

The evidence for FREEZE_LIST §7.72. Code: branch `fix/four-small-bugs`, built on 1902c5e and moved onto 66c1f0a (the commit between them changed only records).

## The topic rule (D-46, D-41)

- `harness.py` scores a candidate replacement for `evidence_gate._topic_raising_text` against the current one:
  pytest on 8 gate/observer test files (with `patch_plugin.py` swapping the function in), the labelled corpus,
  M-1(a)'s 12 graded topic items, every `topic_interests` candidate the model proposed in seven recordings (111;
  read from the replay outputs of `../gate_fixes_2026-10-21/`, rebuilt by its command), and probe sentences. Run
  from a scratch folder holding `../replays/<name>_after.json`; the paths at its top are the machine it ran on.
  Controls: `identity_rule.py` (the current rule: no change) and `broken_rule.py` (every sentence counts: 5 test
  failures, 8 replay changes), both run before any design.
- `probes_dev.json` (10 sentences) was written before any design and shown to the designers; `probes_heldout.json`
  (10 more) was written at the same time and read only by the judge. The held-out set is spent: every design was
  scored on it.
- `designs/`: the three rules (reuse-only, clause-position, attack-first), each written by an independent agent and
  measured with the harness, and `designs_and_judge.json`: each design's own report and the judge's re-measurement
  (pytest 324 passed for each; held-out 5, 7 and 9 of 10; replay TRAP topics accepted 4 -> 1 for each), ranking and
  concerns. The judge recommended attack-first; the owner chose reuse-only (no new words), so D-41 stays open.

## The replays of the final code

`replays_changed.txt`: the seven recordings through 1902c5e's gate and through the branch (`compare_replays.py`
from `../gate_fixes_2026-10-21/`). Four topic verdicts change, all refused now: the Elixir trap (written before,
the only learned row that changes), and three the Constitution discarded anyway (Swift "might ... someday", Elixir
twice). Trap rows written 1 -> 0; facts learned 175 of 519 and every decision unchanged. The trimmed-hedge rule
(a hedge cut out of a quote is still read) changed no verdict in the recordings.
