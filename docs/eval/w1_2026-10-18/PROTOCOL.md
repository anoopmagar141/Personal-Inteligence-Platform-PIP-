# W-1 measurement: protocol

Written and committed 2026-10-18 with the W-1 code, BEFORE any run (BLUEPRINT card W-1). Every run from a clean
worktree of that commit, Ollama 0.40.3 started as `ollama serve`, nothing else on the GPU but the desktop and the
owner's browser, every result stamped (S-1). Nothing is tuned on these sets.

## Setting, fixed

- The W-1 code: one settings block (`settings.json` `llm`): `qwen2.5:7b`, `num_ctx` 16384 on every request
  (the owner's decision; the probe in V-2 part d proposed it), temperature not sent unless set,
  `tokens_per_word` 2.0. The Observer's transcript cap follows from them: 6,576 words.
- Bar sets from V-2 (`docs/eval/v2_2026-10-17/`): the 27 long chats (`long_chats/long_chat_cases.json`) and the
  37 short chats (`backend/tests/observer_cases.py`, 3 runs).

## Run 1: the window (the card's "done when")

`scripts/eval_observer_end_to_end.py --cases docs/eval/v2_2026-10-17/long_chats/long_chat_cases.json --model
qwen2.5:7b --unload-between --count-prompt-tokens 16384 --save-raw ... --json ... --out ...`, scored with
`long_chats/score_long_chats.py`. Temperature not sent, as in V-2's baseline, so the window is the only change.

Rule, fixed now, all three needed:
1. **Every prompt is read in full**: for each of the 27 cases, the tokens Ollama read equal the prompt's whole
   length (both counted on an empty cache).
2. **Not worse than V-2's baseline**: true facts learned (written or asked) by position not lower than V-2's
   (0 of 9 in every cell), and trick statements plus near-misses reaching a belief table not higher than 1 of
   162, and learned rows labelled TRAP not higher than 1.
3. **Fits on the GPU, observed**: while run 1's model is loaded, `/api/ps` shows `size_vram` equal to `size`
   (nothing on the CPU), and `nvidia-smi` memory in use is recorded with the desktop and a browser open. An
   estimate is not the bar.

If 1 or 3 fails, 16384 is not the window for this machine, and the report says what was seen.

## Run 2: the temperature (chosen by measurement before any later bar is set)

Candidates: not sent (the model's default; V-2 part b measured it: 0 of 75 traps, 35 of 69 learned), 0.3 and 0.0.
Each of 0.3 and 0.0 runs the 37 short chats 3 times (`--repeat 3`), with the setting changed in the clean
worktree's `settings.json` only for that run, and is stamped (the stamp records the temperature sent).

Rule, fixed now:
- A candidate is out if any trap reaches a belief table or any learned row is TRAP.
- Of the rest, the one with the most stated facts learned (written or asked, out of 69) wins; a difference of 3
  or fewer counts as a tie, and a tie goes to the lower temperature (more repeatable answers).
- The chosen value is then written into `settings.json` in its own commit, which cites this result. Not sent stays
  not sent if it wins.

## Machine time (estimates)

Run 1 about 20 minutes (the long prompts are now read whole); run 2 about 20 minutes (two candidates, about 10
minutes each, as V-2 part b).
