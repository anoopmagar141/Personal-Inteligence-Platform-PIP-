# V-2 validity baseline: protocol (parts b, c, d)

Written and committed 2026-10-17, BEFORE any of these runs (BLUEPRINT card V-2, final plan step 2, issue #22).
Part (a), the long chats, gets its own protocol section, committed before its run, once its chats are written.
Nothing here changes `backend/`. Nothing is tuned on these sets. Every result file carries the S-1 run stamp
(`scripts/_stamp.py`).

## Setting, fixed

- Ollama 0.40.3, started as `ollama.exe serve` (not the CLI or the tray app, which can install an update).
  Its log at start: `OLLAMA_CONTEXT_LENGTH:0`, "vram-based default context ... default_num_ctx=4096" on the
  RTX 4060 Laptop GPU (8 GiB). PIP sends no `num_ctx`, so 4096 is the window the shipped Observer gets.
- Models already installed (nothing is downloaded): `qwen2.5:7b` digest `845dbda0ea48...`, the same digest as
  the 2026-10-12 recording; `llama3.1:8b` digest `46e0c10c039e...`.
- Code: the commit that holds this protocol, plus no change in `backend/`. The Observer's prompt and schema
  hash `9e3a633b21bb...` today, the same as in the 2026-10-12 recording's stamp, so the prompt is unchanged.
- Cases: `backend/tests/observer_cases.py`, 37 short chats (12-60 words), 23 stated facts and 25 traps per
  run. Three runs per model (`--repeat 3`), as in 2026-10-12, so each total is out of 69 facts and 75 traps.
- The harness (`scripts/eval_observer_end_to_end.py`) uses the app's own `OllamaProvider` (no temperature,
  no `num_ctx` sent: the model's default sampling applies, so runs differ from each other) on a fresh
  profile per case. No backend test suite runs at the same time.

## Measures (the harness's own definitions, unchanged)

- precision: learned rows labelled TRUE / (TRUE + TRAP), summed over runs;
- stated facts learned: facts with a written or queued row, out of 69 (written and queued-only shown apart);
- traps reaching a belief table: out of 75;
- also: UNLABELLED learned rows, errored cases, model seconds per run.

Bounds are reported with every count: 0 of N means at most about 3/N (95%, rule of three);
N of N means at least about 1 - 3/N.

## (b) qwen2.5:7b on Ollama 0.40.3

Commands, in this order:

1. Today's code on the OLD raw outputs (no model): replay `docs/eval/observer_raw_recording_2026-10-12.json`.
   This separates what the code changed since 2026-10-12 from what the Ollama update changed.
2. The new recording: `--model qwen2.5:7b --repeat 3 --save-raw observer_recording_qwen2.5_7b_ollama0.40.3.json`.
3. Replay of the new recording (no model): must reproduce step 2's numbers exactly (a check of the replay).

Why step 2 matters beyond the Ollama update: today's evidence gate (A-1, FREEZE_LIST 7.37) was tuned on the
2026-10-12 recording, so the 0 of 75 and 39 of 39 it gives on step 1 are on the outputs it was shaped on.
Step 2's fresh samples are the first outputs it was not tuned on.

Rule, fixed now:
- **Holds on Ollama 0.40.3** if, in step 2, traps reaching a belief table are 0 of 75 AND no learned row is
  labelled TRAP. Otherwise the trust numbers do not carry over to the current Ollama, and the report says so.
- Stated facts learned is reported next to step 1's count, with no bar: sampling at the model's default
  temperature moves it from run to run (2026-10-12: 12, 12 and 13 of 23 per run).
- If step 3 does not reproduce step 2 exactly, the replay is broken and every replayed number is suspect.

## (c) llama3.1:8b, the second model

Command: `--model llama3.1:8b --repeat 3 --save-raw observer_recording_llama3.1_8b_ollama0.40.3.json`.

Claim, if supported, worded exactly: "the guard's accept and reject rules hold on a second model's
phrasings". llama proposes different candidates, so this is not a paired comparison of the two models.

Rule, fixed now, BOTH halves needed:
1. traps reaching a belief table are 0 of 75 on llama3.1:8b AND 0 of 75 on qwen2.5:7b in (b) step 2; and
2. llama3.1:8b's stated facts learned (written or queued, over 69) is at least half of qwen2.5:7b's count in
   (b) step 2 (rounded down). This half stops a guard that simply rejects most of a new model's phrasings
   from passing as safe.

Verdicts: both hold: SUPPORTED. Half 1 fails: NOT SUPPORTED, a trap reached a belief table (name the case).
Half 1 holds and half 2 fails: NOT SUPPORTED, the guard may be rejecting llama's phrasings rather than
judging them. More than 11 of 111 llama cases errored: INCONCLUSIVE (the model's output, not the guard).

## (d) the context-window probe (report only)

`docs/eval/context_window_2026-10-16/probe_num_ctx.py` on qwen2.5:7b, now with the S-1 stamp. Three calls:
a ~6,800-word prompt with a secret word in its first line and no `num_ctx` (as shipped), the same with
`num_ctx` 16384, and the Observer's instruction block for tokens per word. Reported: the window the loaded
model got (`/api/ps`), `prompt_eval_count` against the words sent, and whether the first line survived.
No bar: it measures; W-1 decides the window from it.

## Order and machine time (estimates)

(d) about 2 minutes; (b) step 1 and step 3 under a minute each, step 2 about 11 minutes (2026-10-12: about
200 s per run); (c) about 12-15 minutes. Results go in this folder.

## (a) long chats (added 2026-10-18, committed before its run)

Cases: `long_chats/long_chat_cases.json`, built by `long_chats/build_long_chats.py` (deterministic). Made-up
chats, nothing real or personal: general study and programming Q&A in which the user says nothing about
themselves, plus nine planted exchanges, the same nine in every chat:

- three TRUE facts about the user: F1 a tool (Excalidraw), F2 a project (Lanternfish), F3 a goal (an exam);
- three trick statements: T1 a flatmate's tool, T2 a hypothetical, T3 the assistant asserting something
  false about the user, which the user corrects;
- three NEAR-MISSES, each with a true fact's sentence shape and a different entity that is not the user's:
  N1 a supervisor's tool, N2 a cousin's project, N3 a friend's exam goal. Each sits next to its fact.

Three lengths (about 1,400, 2,700 and 4,800 words), three rotations that put each block of (fact, near-miss,
trick) at the start, middle and end once, and three profile ages, 7, 21 and 63 days (weeks 1, 3 and 9: one,
two and three pieces of evidence needed). 27 cases, one run each. A trick statement or near-miss counts as
a hit if a row naming it reaches ANY table the harness reads.

Command (from the clean checkout of the commit that holds this section; nothing in `backend/` changes):
`--cases long_chats/long_chat_cases.json --model qwen2.5:7b --unload-between --count-prompt-tokens 16384
--save-raw observer_recording_long_qwen2.5_7b.json --json a_long_qwen.json --out a_long_qwen_harness.md`,
then `long_chats/score_long_chats.py a_long_qwen.json long_chats/long_chat_cases.json a_long_qwen.md`.
`--unload-between` empties Ollama's cache before each case, so the tokens it reports reading are not
shortened by a cached prefix; load time is reported apart and left out of the Observer's time. The whole
prompt is counted afterwards in a 16,384 window (16,384 holds the longest, about 8k tokens).

Rule, fixed now:
- **Trust holds on long chats** if 0 of 162 trick statements and near-misses (27 x 6) reach a belief table
  AND no learned row is labelled TRAP. Otherwise the 0 of 75 trap figure does not carry over to long chats,
  and the report names every hit.
- More than 3 of 27 errored cases: INCONCLUSIVE.
- Learning (true facts written or asked, by position, length and age), the share of the prompt Ollama read,
  and the Observer's time per chat are reported, not judged: they are the baseline W-1 and #19 are measured
  against. Expected from (d), and stated before the run so it cannot be fitted afterwards: at the shipped
  4096 window the longer chats are cut from the front, so the Observer's instructions and the start of the
  chat are not read.

Machine time (estimate): about 15-20 minutes.
