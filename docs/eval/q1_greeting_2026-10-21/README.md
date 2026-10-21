# Q-1 result: a new user's greeting on qwen2.5:7b (run 2026-10-21, report only)

The owner's report (#11): typing "hi" makes PIP say it has no record, and PIP "feels dumb". The 2026-10-17 probe
(`../greeting_2026-10-17/`) found this on llama3.1:8b (3 of 30) and phi3:mini (12 of 30), never on qwen2.5:7b (0 of 15
for a new user). This run measures the shipped model on the real pipeline. Nothing in PIP was changed.

- **Rule:** `RULE.md`, fixed before the run (sha256 `9c049a47c4f65046cd832e1bc839ad35e3a47d7c79cddbf45308580f337186e6`,
  LF). Script `probe_q1.py`; results `results_qwen2.5_7b.json` (every reply and its system prompt); log `run_log.txt`.
- **Stamp:** commit 33dd522, no uncommitted changes to tracked files (a clean worktree); Constitution 1.1; qwen2.5:7b,
  digest 845dbda0ea48...; Ollama 0.40.3, started with `ollama serve` and stopped after; options sent num_ctx 16384,
  temperature 0.0, num_predict 2000 (the real `OllamaProvider`; every one of the 104 calls was qwen2.5:7b).
- **Run:** 4 made-up new users (onboarded with a name and English, nothing else) x 26 greetings = 104, each the first
  message of its chat, through `pipeline.run_sync` with the profile's active model. All 104 answered.

## Result

**0 of 104 no-record replies.** The pattern found none, and reading all 104 by hand added none and removed none.
**The bar (at most 1 of 104) is met: Q-1 closes with no code change.** Over these wordings and users the rate is
below about 3% (95%, by the rule of three).

Report only:
- The reply used the user's name in 103 of 104. The one that did not: Maria Lopez's "hola", answered in Spanish,
  though her profile says English.
- Sita Gurung (no calling name) was called by her full name in 7 of 26 replies.
- No reply invented a previous chat, a project or a fact about the user.
- Every prompt held "Projects: none recorded." and "Today is Wednesday, 21 October 2026."; qwen did not volunteer
  either. 55 of 104 replies were exactly one line, "Hello <name>! How can I assist you today?".

## Found on the way: D-45, a greeting that asks for a web search

"hey pip, how are you doing today?" is a web-search question: "today" is one of Stage 6's trigger words, and Stage 1
files the message as `external_information`. So Stage 8 was asked to allow a web search 4 times (once per user) and
refused, because these profiles never consented to web search. **With web search consented, the greeting's first 12
words would be sent to the search provider**, and its results put into the prompt. Not fixed here (Q-1 changes no
code); the owner decides, and the owner's rule rules out answering it with another word list.

## What it does not show

- llama3.1:8b and phi3:mini still do it (2026-10-17); this is qwen2.5:7b only. Kept for the write-up: the model's
  behaviour varies while the deterministic guard does not.
- The chat socket and the app window were not used (the pipeline was); one PC; English only; made-up users.
