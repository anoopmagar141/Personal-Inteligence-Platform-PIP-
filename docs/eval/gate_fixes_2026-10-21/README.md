# D-38, D-40, D-42: the gate before and after (2026-10-21, no model)

The evidence for FREEZE_LIST §7.67. "Before" is 35974b9; "after" is 35974b9 plus the three changed files of the
commit that adds this folder. Both were clean worktrees under `D:\FINAL YEAR PROJECT\pip-work\`.

## 1. Replays of seven recordings

The six G-4 replayed (§7.60) and G-4's own long-chat run, each through both trees, no model:

    .venv\Scripts\python.exe scripts\eval_observer_end_to_end.py --replay <recording> [--cases <long_chat_cases.json>] --json <out>

Recordings: `docs/eval/observer_raw_recording_2026-10-12.json`, `docs/eval/v2_2026-10-17/observer_recording_qwen2.5_7b_ollama0.40.3.json`,
`.../observer_recording_llama3.1_8b_ollama0.40.3.json`, `.../observer_recording_long_qwen2.5_7b.json` (long),
`docs/eval/w1_2026-10-18/observer_recording_long_16k.json` (long), `.../observer_recording_short_t0.0.json`,
`docs/eval/g4_2026-10-18/observer_recording_long_16k.json` (long). Long ones take
`--cases docs/eval/v2_2026-10-17/long_chats/long_chat_cases.json`. The raw outputs (2.6 MB) are not kept: they are
rebuilt by the command. `compare_replays.py <dir>` reads `<name>_before.json` / `<name>_after.json` and prints every
candidate whose path (gate / Constitution / Stage 13) changed, every changed decision with the model's quote, and
the totals: `replays_changed.txt`.

## 2. M-1(a)'s 116 graded items

`m1a_regrade.py docs/eval/m1a_2026-10-20/key.json`, run from each tree's root, rebuilds each item's turn from the key
(the turn before it and the user's message) and prints the gate's verdict per item:
`m1a_verdicts_35974b9.json` and `m1a_verdicts_fixed.json`. The rebuilt verdicts on 35974b9 agree with the recorded
ones (accepted or not) on all 116. Six differ between the two files: items 31, 37, 53, 77, 94 and 105, all graded
D or U in `../m1a_2026-10-20/grades.txt`. This is not a new measurement of Promise 4: the fixes were written from
these items.
