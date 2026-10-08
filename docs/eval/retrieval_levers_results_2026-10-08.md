# The two levers on the 0.30 cut-off — results (2026-10-08)

Follows `retrieval_e2e_results_2026-10-08.md`. Question, levers (the exact prompt rule and the 1800-word budget),
conditions, the 40 held-out questions and the decision rule were committed before any run (`a1e5f97`); the harness
before its first full run (`f02ca55`). Tool: `scripts/eval_retrieval_levers.py`. Answers:
`retrieval_levers_answers_2026-10-08.json`. Sheet, key and labels: `retrieval_levers_grading_2026-10-08/`.

## Verdict, by the rule fixed in advance

**Neither lever, nor both together, is supported.** Each fails the same condition: wrong answers among the 30
held-out answerable questions must not rise above the shipped setting's 4, and they were 6 (rule), 8 (budget) and
7 (both). Correct answers rose by 12 or 13 for all three, with no question getting worse, and not one of the 10
questions no document answers drew an invented answer. The validity guard was met: plain 0.30 (condition C) did
reproduce the problem on the held-out questions (8 wrong against the shipped setting's 4), so the held-out set could
have shown a fix and did not. The verdict is the same under the strict and the lenient reading of my 30
borderline calls.

| held-out, 30 answerable | A: shipped (0.60) | C: 0.30 | D: C + document rule | E: C + 1800-word budget | F: both |
|---|---|---|---|---|---|
| CORRECT | 0 | 12 | **13** | 12 | 12 |
| DECLINES | 25 | 9 | 9 | 9 | 10 |
| WRONG | 4 | **8** | **6** | **8** | **7** |
| VAGUE | 1 | 1 | 2 | 1 | 1 |
| invented, of 10 unanswerable | 0 | 0 | 0 | 0 | 0 |

## What happened

**1. The held-out questions behave like the first set.** Lowering the cut-off to 0.30 took correct answers from 0 to
12 of 30 and wrong ones from 4 to 8. When the answer was in the prompt the model was nearly always right: 12 of 13 at
0.30. Of the 15 questions that got passages with no answer in the prompt, none was answered correctly, 8 were declined and
6 answered wrongly.

**2. The prompt rule did not change what the model does with a misleading passage.** For those 15 questions it left the
split exactly where it was (8 declined, 6 wrong, 1 vague, the same six). The only two held-out grades it did change
were a question with no passages at all (`ho-conv-wc`, wrong to vague) and one with the answer in the prompt
(`ho-vald-probes`, wrong to correct), which is what a different phrasing of the same prompt would do on 30 questions.
A 7B model told "do not fill the gap from the surrounding text" went on filling it.

**3. The larger budget did not help here, because it had nothing to rescue.** On the held-out questions the answer was
never retrieved-but-cut by the 800-word cap (0 of 30), so the budget changed the prompt without changing what the
model needed. It changed five grades, two up and two down: `ho-obsv-interp` went from correct to wrong and
`ho-migr-drain` from correct to vague as more text sat around the passage that mattered, against two gains
(`ho-fl-ollama-gate`, `ho-vald-probes`).

**4. On the development questions the levers looked better, which is exactly why they were not used to decide.**
Against the previous run's 0.30 on the 54 answerable questions, rule D took wrong answers from 9 to 5 and the budget E took
correct answers from 26 to 32 - on the set the rule was written against, where the cut-off cases lived. The held-out
set showed far less (D: wrong 8 to 6, correct 12 to 13; E: correct 12 to 12, wrong 8 to 8). A gain that appears on the questions a fix was written for and not on fresh ones is what
tuning to a test set looks like.

## What this supports, and what it does not

- Nothing in the pipeline is changed. By the rule I set, the prompt rule and the budget do not earn a place, and the
  cut-off alone was not supported in `retrieval_e2e_results_2026-10-08.md`.
- The honest summary of the trade, for the owner to weigh: as shipped, the documents feature answers 0 of 30
  questions about its own documents and declines 25 (and fabricates 4, from the model's own knowledge). At 0.30 it
  answers 12 of 30 correctly, declines 9 and answers 8 wrongly. The rule I fixed in advance counts the second as a
  failure; whether a feature that is right 40% of the time and wrong 27% of the time beats one that is right
  never is a product decision.
- What would help is not a cut-off or a prompt rule but retrieval that returns fewer passages with no answer in them -
  a better embedder, smaller or token-aware chunks, or checking a passage against the question before using it. None was
  tested here.

## Limits

- **One hand again**: questions, running and grading are mine, blind to condition but not to style. 30 borderline
  calls are listed with strict and lenient readings in `retrieval_levers_grading_2026-10-08/make_grades.py`.
- **Small numbers.** 30 answerable questions: one question is 3.3 points.
- **Reproducibility.** Answers within this run are fixed by temperature 0 and a seed, but re-running 12 development
  questions under `num_ctx` 8192 reproduced the earlier answers' text for only 9 of 24 runs (the same 6 correct and
  6 wrong overall). Exact text is not portable across Ollama settings; the grades were.
- **One corpus, one 7B model, temperature 0.** As before.

---

# Appendix — generated tables (main grading)

Model qwen2.5:7b, num_ctx 8192, temperature 0, snapshot `1577473`. Conditions: A = {'similarity_threshold': 0.6, 'note': 'as shipped'}; C = {'similarity_threshold': 0.3, 'note': "the previous run's best cut-off, no lever; the baseline for the levers"}; D = {'similarity_threshold': 0.3, 'document_rule': True}; E = {'similarity_threshold': 0.3, 'rag_chunks_tokens': 1800}; F = {'similarity_threshold': 0.3, 'document_rule': True, 'rag_chunks_tokens': 1800}.

### Held-out set (the verdict is drawn from this)

**answerable, 30 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A | 1 | 17 | 0 | 25 | 4 | 1 |
| C | 28 | 732 | 12 | 9 | 8 | 1 |
| D | 28 | 732 | 13 | 9 | 6 | 2 |
| E | 28 | 1294 | 12 | 9 | 8 | 1 |
| F | 28 | 1294 | 12 | 10 | 7 | 1 |

**no document answers it, 10 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A | 0 | 0 | 0 | 10 | 0 | 0 |
| C | 9 | 699 | 0 | 10 | 0 | 0 |
| D | 9 | 699 | 0 | 10 | 0 | 0 |
| E | 9 | 1199 | 0 | 10 | 0 | 0 |
| F | 9 | 1199 | 0 | 10 | 0 | 0 |

### Development set (reported only)

**answerable, 12 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A | 0 | 0 | 0 | 9 | 1 | 2 |
| C | 12 | 756 | 6 | 0 | 6 | 0 |
| D | 47 | 647 | 25 | 21 | 5 | 3 |
| E | 47 | 1107 | 32 | 11 | 5 | 6 |

**no document answers it, 12 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| D | 12 | 759 | 0 | 12 | 0 | 0 |
| E | 12 | 1284 | 0 | 12 | 0 | 0 |

### Decision rule (held-out set, relative to A)

Validity guard: WRONG under C = 8, under A = 4; the problem is reproduced when C exceeds A by 2 or more: **yes**.

- **D**: (1) CORRECT 0 -> 13, 13 up / 0 down, p = 0.000, needs net 6+ and p < 0.05: met; (2) WRONG 4 -> 6 (must not rise): NOT met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 13 against C's 12 (at most 3 lower): met. **NOT SUPPORTED** (strict reading: NOT SUPPORTED; lenient reading: NOT SUPPORTED)
- **E**: (1) CORRECT 0 -> 12, 12 up / 0 down, p = 0.000, needs net 6+ and p < 0.05: met; (2) WRONG 4 -> 8 (must not rise): NOT met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 12 against C's 12 (at most 3 lower): met. **NOT SUPPORTED** (strict reading: NOT SUPPORTED; lenient reading: NOT SUPPORTED)
- **F**: (1) CORRECT 0 -> 12, 12 up / 0 down, p = 0.000, needs net 6+ and p < 0.05: met; (2) WRONG 4 -> 7 (must not rise): NOT met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 12 against C's 12 (at most 3 lower): met. **NOT SUPPORTED** (strict reading: NOT SUPPORTED; lenient reading: NOT SUPPORTED)

### Held-out answers that changed grade relative to C

- D: ho-conv-wc: WRONG -> VAGUE; ho-vald-probes: WRONG -> CORRECT
- E: ho-arch-ws-spec: VAGUE -> DECLINES; ho-fl-ollama-gate: DECLINES -> CORRECT; ho-migr-drain: CORRECT -> VAGUE; ho-obsv-interp: CORRECT -> WRONG; ho-vald-probes: WRONG -> CORRECT
- F: ho-arch-ws-spec: VAGUE -> DECLINES; ho-conv-wc: WRONG -> VAGUE; ho-fl-setup-catchup: WRONG -> DECLINES; ho-fl-ollama-gate: DECLINES -> CORRECT; ho-migr-drain: CORRECT -> WRONG; ho-obsv-interp: CORRECT -> WRONG; ho-vald-probes: WRONG -> CORRECT

### What the model was shown (held-out, answerable)

| condition | answer in the prompt: CORRECT of | answer retrieved but cut: CORRECT of | passages without the answer: CORRECT / DECLINES / WRONG / VAGUE | no passages: CORRECT / DECLINES / WRONG / VAGUE |
|---|---|---|---|---|
| A | 0 of 0 | 0 of 0 | 0 / 0 / 1 / 0 | 0 / 25 / 3 / 1 |
| C | 12 of 13 | 0 of 0 | 0 / 8 / 6 / 1 | 0 / 1 / 1 / 0 |
| D | 13 of 13 | 0 of 0 | 0 / 8 / 6 / 1 | 0 / 1 / 0 / 1 |
| E | 11 of 13 | 0 of 0 | 1 / 8 / 6 / 0 | 0 / 1 / 1 / 0 |
| F | 11 of 13 | 0 of 0 | 1 / 9 / 5 / 0 | 0 / 1 / 0 / 1 |

### Checks

- distinct prompts run: 340; every status success: True
- largest prompt Ollama counted: 3571 tokens (num_ctx 8192)
- answers that hit the 400-token limit: 1
- development replication (A and C re-run under the new options on 12 questions): answers identical to the earlier run's for 9 of 24 A/C runs
