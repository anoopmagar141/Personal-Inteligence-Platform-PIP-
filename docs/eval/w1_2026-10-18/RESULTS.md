# W-1 measurement: results

Rules: `PROTOCOL.md`, committed with the W-1 code in b3f1eb2 before any run. Runs 2026-10-18 from a clean
worktree of b3f1eb2 (stamp: commit b3f1eb2; for run 2 the worktree's `settings.json` held the candidate
temperature, and the stamp lists it as the one changed file), Ollama 0.40.3 started as `ollama serve`,
qwen2.5:7b digest 845dbda0ea48, the desktop and Brave (10 processes) open, the machine held awake.

## Run 1: the window on V-2's 27 long chats - NOT MET (bars 1 and 3 met, bar 2 not)

| bar | result |
|---|---|
| 1. every prompt read in full | **met**: 27 of 27; the 4,800-word chat now 6,506 of 6,506 tokens (V-2: 2,050) |
| 2. not worse than V-2: facts by position not lower | met: 2 of 81 (1 middle, 1 end; V-2 0 of 81) |
| 2. trick statements + near-misses not higher than 1 of 162, TRAP rows not higher than 1 | **not met: 2 of 162, 2 TRAP rows** |
| 3. fits on the GPU, observed | **met**: `size_vram` equal to `size` (5.47 GB) in all 39 polls with the model loaded, window 16384; `nvidia-smi` 6,569-6,768 of 8,188 MiB in use |

By the rule fixed before the run, W-1's "done when" is not met. What the two hits were:

- Both are near-misses, both in the SHORTEST chats (1,400 words), whose prompt was read whole in V-2 too
  (2,572 tokens in both runs); the window changed nothing they were given.
- In both, the evidence gate REJECTED the near-miss as a memory (EVIDENCE_NOT_ENTAILING, also when run alone).
  They reached a belief table through the Observer's DECISION path, which skips the gate (issue #3, BLUEPRINT
  G-4, step 4): "pass the Azure Fundamentals exam by March" (the friend's goal) and "store ingredients in a
  separate table with a join table in Pebblebox" (advice about the cousin's project) were logged as the
  user's decisions.
- So the difference from V-2's 1 of 162 is the model sampling differently at its default temperature on the
  same input (one run per chat), meeting G-4's known gap. It is not something the window does; it is also not
  a reason to call the bar met.

Learning, by the labels: 2 of 81 true facts (V-2: 0 of 81); the gate's wording rules still reject most of
them (the V-2 finding, the #19 baseline). The decision path logged 12 rows from these chats, the 2 hits among
them (V-2: 5, none a hit).

## Run 2: the temperature - 0.0

The 37 short chats, 3 runs each. qwen2.5:7b sets no temperature of its own, so "not sent" is Ollama's default.

| temperature | traps reaching a belief table | TRAP rows | stated facts learned (per run) | written |
|---|---|---|---|---|
| not sent (V-2 part b) | 0 of 75 | 0 | 35 of 69 (10, 13, 12) | 20 |
| 0.3 | 0 of 75 | 0 | 36 of 69 (12, 12, 12) | 19 |
| 0.0 | 0 of 75 | 0 | 36 of 69 (12, 12, 12) | 18 |

No candidate is out; 35, 36 and 36 are within 3 of each other, a tie by the rule, and a tie goes to the lower
temperature: **0.0**, now in `settings.json`. At 0.0 the three runs were identical, output for output, so its
"3 runs" are one draw repeated; at 0.3 only 6 of 37 outputs matched between two runs. Chat answers at 0.0 were
not measured for quality; the rule was the Observer's.
