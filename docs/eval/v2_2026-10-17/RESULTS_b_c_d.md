# V-2 results: parts (b), (c) and (d)

Rules: `PROTOCOL.md`, committed in 1ca8dd4 before any run. Every run below ran from a clean checkout of
1ca8dd4 (a separate git worktree; stamp: commit 1ca8dd4, no uncommitted changes), on Ollama 0.40.3 started
as `ollama serve`, with nothing else running. A first attempt on 2026-10-17 was killed after 9 minutes when
the machine slept (Ollama and the run ended together; nothing from it was kept); the runs below are the
rerun of 2026-10-18 with the machine held awake. Bounds: 0 of N is at most about 3/N; N of N at least
about 1 - 3/N.

## (b) qwen2.5:7b on Ollama 0.40.3 - HOLDS

| | step 1: today's code, 2026-10-12 recording (0.32.14) | step 2: new recording, 0.40.3 |
|---|---|---|
| traps reaching a belief table | 0 of 75 | **0 of 75** (at most about 4%) |
| learned rows labelled TRAP | 0 | **0** |
| precision TRUE / (TRUE + TRAP) | 39 of 39 | 36 of 36 (at least about 92%) |
| stated facts learned (written or asked) | 37 of 69 (12, 12, 13 per run) | 35 of 69 (10, 13, 12 per run); 20 written |
| unlabelled learned rows | 8 | 13 |
| errored cases | 0 of 111 | 0 of 111 |

- Step 1 reproduces the thesis figures exactly on today's code: nothing committed since 2026-10-12 moved them.
- Step 2 is the first set of model outputs today's evidence gate was not tuned on (A-1 was tuned on the
  2026-10-12 recording). Same model digest, same Observer prompt hash; what changed is Ollama (0.32.14 to
  0.40.3) and the samples.
- Step 3, the replay of step 2's recording, reproduces step 2 case for case (111 of 111) once the
  timestamps in decision-log rows are set aside. The replay is sound.
- Model time per run: 210, 191 and 205 seconds (2026-10-12: 210, 200, 199).

## (c) llama3.1:8b, the second model - SUPPORTED

| | qwen2.5:7b (b, step 2) | llama3.1:8b |
|---|---|---|
| traps reaching a belief table | 0 of 75 | **0 of 75** (at most about 4%) |
| learned rows labelled TRAP | 0 | **0** |
| stated facts learned | 35 of 69 | **33 of 69** (10, 11, 12 per run); 13 written; the bar was at least 17 |
| candidates proposed / surviving grounding | 110 / 107 | 174 / 168 |
| errored cases | 0 of 111 | 0 of 111 |
| model time | 606 s | 756 s |

Both halves of the rule hold, so, worded exactly: **the guard's accept and reject rules hold on a second
model's phrasings.** llama proposed 58% more candidates than qwen and the guard still let no trap through,
while learning about as many stated facts. This is not a paired comparison of the two models.

## Not counted by the rule, and reported here so it is not hidden

- **The decision log.** The Observer's decisions skip the evidence gate (issue #3, BLUEPRINT G-4, step 4).
  Decision-log rows written: 11 (step 1), 16 (qwen, step 2) and 15 (llama). Of these, rows from a chat whose
  whole point is a trick statement: 2, 2 and 6. qwen logged "decided not to rewrite the backend in Elixir"
  from the hypothetical twice; llama logged "I'll pass" and "the user will not learn Java" (the sister
  chat), "user does not have a choice in using Jira", "I won't use Fortran", "will not use Emacs" and a
  sarcastic remark as decisions. A further tentative remark ("I'm not convinced we should move to Java",
  a mixed chat) was logged as a decision 2 and 3 times. None of these is a trap hit under the harness's
  labels, which do not name the decision log for these chats; they are exactly the defect #3 fixes.
- **One topic row from a trick statement on llama:** "my sister loves Java" left `java` in
  `topic_interests` once. That chat's labels name the belief tables (preferences, skills, goals, projects,
  style, identity) and not topics, so the rule does not count it; as a belief about the user it is wrong.
- The rule's counts are on 37 short chats (12-60 words). Part (a) measures long ones.

## (d) the context window, as shipped - report only

| call | words sent | window | tokens Ollama read | answer |
|---|---|---|---|---|
| A: no `num_ctx` (what PIP sends) | 7,562 | 4096 (Ollama's default for 8 GiB of VRAM) | **2,050** of 10,639 | wrong: the first line was not read |
| B: `num_ctx` 16384 | 7,562 | 16384 | 10,639 | right |
| C: the Observer's instructions | 488 | 16384 | 908 | - |

- As shipped, a prompt longer than the window is cut from the FRONT, silently, to about half the window:
  about a fifth of this prompt was read. The Observer puts its instructions first, so on a long chat the
  instructions are the part that is lost.
- Tokens per word: 1.41 for plain prose, 1.86 for the Observer's instruction block (PIP budgets in words).
- Memory: the loaded model took 4.75 GB at 4096 and 5.47 GB at 16384, all on the GPU (about 0.7 GB more).
- This is what W-1 decides the window from.
