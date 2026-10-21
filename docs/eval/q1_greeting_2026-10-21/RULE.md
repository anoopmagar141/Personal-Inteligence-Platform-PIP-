# Q-1 rule: does a new user's greeting get "I don't have a record"? (fixed 2026-10-21, before the run)

BLUEPRINT card Q-1 (#11). Owner: "when I type hi, PIP says I don't have a record of it; it feels dumb". The
2026-10-17 probe (`docs/eval/greeting_2026-10-17/`) found it on llama3.1:8b (3 of 30) and phi3:mini (12 of 30), never
on qwen2.5:7b (0 of 15 for a new user, too few to bound the rate). This run measures qwen2.5:7b only, as shipped.
Nothing in PIP is changed by it.

## What runs

- **Code:** commit 33dd522 (W-1's settings and step 6's date line included), in a clean worktree.
- **Model:** qwen2.5:7b on Ollama, started with `ollama serve` only. Sent exactly what the app sends: the real
  `OllamaProvider` (the 16384-token window, temperature 0.0, up to 2000 tokens, no seed).
- **Path:** the real pipeline, `pipeline.run_sync(conn, message)` with no provider given, so the profile's active
  model is used (checked to be qwen2.5:7b), on a fresh made-up profile per user. Every backend path points at a
  temporary folder (as the tests do); `data/` is never opened.
- **A new user:** a database just onboarded with `profile_store.complete_onboarding` (a name, an optional calling
  name, English) and nothing else: no project, no chat record, no history. Each message is the first of its chat.
  The answer cache is emptied before each user, so no reply comes from another user.
- **Users (4, made up):** Alex Rai (calls themself Alex); Sita Gurung (no calling name); Bikash Thapa (Bikash);
  Maria Lopez (no calling name).
- **Messages (26, fixed now):** the 3 already used (hi, hi pip, hello), the card's 6 (hey there, good morning,
  namaste, hii pip, yo, how's it going) and 17 more chosen now, in no list in PIP's code: hey, hello there!, good
  evening, good afternoon pip, hiya, what's up, howdy, heyy, hi, how are you?, hello pip, nice to meet you, hey pip,
  how are you doing today?, morning!, hi :), hola, sup, greetings, good day.
- **N = 4 x 26 = 104 replies**, each asked once (at temperature 0 a repeat gives the same reply). One warm-up
  message on a fifth throwaway user loads the model and the embedder first and is not counted. A reply that fails
  (an error or a timeout) is reported; if fewer than 100 replies come back, the run is incomplete and says so.

## What counts

- **A no-record reply** tells the user, unasked, that PIP has no record, information or details about them, their
  projects or earlier chats.
- **Found by** the 2026-10-17 pattern, unchanged (`NO_RECORD` in `probe_greeting.py`). Then every one of the 104
  replies is read by hand: a pattern match that does not say this is not counted, and a reply that says it in other
  words is counted. Both kinds of correction are listed with the reply. The bar is applied to the count after reading.
- **Reported, not part of the bar:** replies that use the user's name; replies that invent a previous chat, a project
  or a fact about the user.

## The bar

- **At most 1 of 104 no-record replies: Q-1 closes with no code change.** The finding is kept for the write-up.
- **2 or more:** the run stops there and is reported. The next step, the card's greeting line tested on qwen with the
  same bar (plus: a regular user stays at 0; a new user asking "what are my projects?" still gets "none"), is a
  change to the rules and waits for the owner's go-ahead.
