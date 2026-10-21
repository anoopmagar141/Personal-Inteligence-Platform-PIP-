# Why "hi" gets "I don't have a record" (probe, 2026-10-17, report only)

Owner's report: typing "hi" makes PIP say it has no record, and PIP "feels less intelligent". Nothing in PIP was
changed. Script: `probe_greeting.py` (made-up profiles, never `data/`). Ollama 0.40.3, started as `ollama serve` only
and stopped afterwards. Stage 7's real output for a greeting was sent the way `OllamaProvider.chat()` sends it.
Messages "hi", "hi pip", "hello". A "no-record reply" is a fixed pattern decided before the run; every counted reply
was read by hand and is genuine (one phi3 reply in D is a prompt leak that also says "not recorded").

| Condition | qwen2.5:7b | llama3.1:8b | phi3:mini |
|---|---|---|---|
| A shipped rules, NEW user (no projects, no last-session note) | 0 of 15 | 2 of 15; 3 of 30 | 5 of 15; 12 of 30 |
| B shipped rules, regular user (projects + note) | 0 of 15 | 0 of 15 | 0 of 15 |
| C rules removed, regular user | 0 of 15 | 0 of 15 | 0 of 15 |
| D rules + one greeting line, regular user | 0 of 15 | 0 of 15 | 1 of 15 |
| E rules + one greeting line, NEW user | - | 1 of 30 | 2 of 30 |

(The "of 30" runs used seeds 1-10; the "of 15" runs seeds 1-5. Files: `results_<model>*.json`.)

**What it shows.**
- The reply is real but depends on the model and on the user being NEW. For a new user, Stage 7 tells the model
  "Projects: none recorded." (`_ASSERT_EMPTY_FOR`, `active_projects` is always looked up) next to rule 3 ("say so
  plainly"), so on a greeting the model volunteers "I do not have a record of any projects". Most failures were on
  "hello" (llama 2 of 3, phi3 9 of 12).
- qwen2.5:7b never did it (0 of 60). llama3.1:8b sometimes (3 of 30 for a new user). phi3:mini often (12 of 30), and
  it also leaks the prompt text and invents a dialogue with itself: it is too small for PIP's prompt.
- One greeting line in the rules cut the new-user failures from 3 to 1 of 30 (llama) and 12 to 2 of 30 (phi3), and made
  replies use the user's name more (llama 25 -> 30 of 30). Its wording about "where you left off" made llama once
  invent a previous session for a new user; a fix would word that part more carefully.
- Not tested: the real app end to end (the real profile, conversation history, the response cache), or which model
  the owner's own profile uses for chat.
