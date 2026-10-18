# G-4: results

The evidence for FREEZE_LIST §7.60 (G-4: the Observer's decisions go through the evidence gate). Code 69252d9.

## 1. Replays of six recordings, before and after G-4 (no model)

Every recording replayed with `scripts/eval_observer_end_to_end.py --replay` through 934cf04 (before G-4) and
69252d9 (G-4): the 2026-10-12 recording (3 x 37 chats), V-2's qwen and llama recordings (3 x 37 each) and long chats
(27), W-1's long (27) and short temperature-0.0 (3 x 37) recordings. Rule (the card's): no trap newly reaching a
belief table, the four §7.14 cases not logged, dropped true decisions counted.

- No learned row was added anywhere. The only rows removed are decisions.
- Of 197 decisions that reached routing on 934cf04 (74 logged, 123 queued), G-4 removed 154 (48 logged, 106 queued)
  and kept 43 (26 logged, 17 queued). Every changed decision, with its quote: `replays_decisions_changed.txt`.
- Read by hand (`classify_removed.py`, output `classification.txt`): 124 right to remove; real decisions removed,
  9 on a strict reading (7 of them because the model's quote carried the "User:" label, D-38) and 30 on a lenient
  one.

## 2. W-1's run 1 again, with the model, on the G-4 code

W-1's run-1 rule (`../w1_2026-10-18/PROTOCOL.md`), committed before W-1 and unchanged: the 27 long chats, from a
clean worktree at 69252d9, Ollama 0.40.3 started as `ollama serve`, qwen2.5:7b (digest 845dbda0ea48), num_ctx 16384,
temperature 0.0 (the setting committed in 0ae28db; W-1's run 1 sent none). Files: `run1_long_16k.json`,
`run1_long_16k_harness.md`, `observer_recording_long_16k.json`, scored into `run1_long_16k.md` with
`../v2_2026-10-17/long_chats/score_long_chats.py`; `gpu_observed_run1.jsonl`.

| bar | W-1 (b3f1eb2) | G-4 (69252d9) |
|---|---|---|
| 1. every prompt read in full | 27 of 27 | 27 of 27 (2,572 / 4,058 / 6,506 tokens for S / M / L) |
| 2. tricks and near-misses reaching a belief table (V-2: 1 of 162) | 2 of 162: **not met** | **0 of 162: met** |
| 2. learned rows labelled TRAP (V-2: 1) | 2 | 0 |
| 2. true facts learned per cell (V-2: 0 of 9 everywhere) | 2 of 81 (1 of 9 in two week-1 cells) | 0 of 9 everywhere |
| 3. whole model on the GPU, observed | yes in all 39 loaded polls, 6,569-6,768 of 8,188 MiB, Brave open | yes in all 42 loaded polls, 6,817-6,848 of 8,188 MiB, no browser open |

- **The same model answers through the code before G-4** (`replay_on_934cf04.json`): 12 learned rows, 3 of them
  TRAP, 3 of 162 tricks or near-misses reaching a belief table. So the change between the columns is G-4's on these
  answers, not the model's.
- **True facts learned: 0 of 81**, on both codes for these answers. W-1's own run queued 2 (its model answers
  differed: no temperature was sent then). The memory path is unchanged by G-4.
- **The 15 decisions the gate refused here:** 9 "I do all my diagrams in Excalidraw these days" (a true habit, not a
  decision; the memory gate also refuses that wording, V-2's finding), 3 the assistant's answer about a friend's
  exam, 3 the assistant's answer about a cousin's recipe app. Before G-4, 12 of the 15 would have been logged.
- **Time:** 725 s of model time for the 27 chats (W-1: 664 s).
