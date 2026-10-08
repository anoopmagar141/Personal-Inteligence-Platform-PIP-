# Cut-off check, end to end — results (2026-10-08)

Follows `retrieval_quality_2026-10-08.md`. The question, the 12 extra questions, the three cut-offs, the grading
scheme and the decision rule were committed before any run (`6e5140a`); the harness before its first full run
(`bf72cf9`). Tool: `scripts/eval_retrieval_e2e.py`. Answers: `retrieval_e2e_answers_2026-10-08.json`. Grading
sheet, key and labels: `retrieval_e2e_grading_2026-10-08/`.

## Verdict, by the rule fixed in advance

**A lower cut-off is not supported, at 0.45 or at 0.30.** Conditions 1 and 2 are met by a wide margin; condition 3
(wrong answers among the 54 answerable questions must not rise) fails: they rose from **4 to 7** at 0.45 and from
**4 to 9** at 0.30. The verdict is the same under the strict and the lenient reading of my nine borderline calls
(below).

| | 0.60 (as shipped) | 0.45 | 0.30 |
|---|---|---|---|
| 54 answerable: CORRECT | 1 | 11 | **26** |
| 54 answerable: DECLINES ("I don't have that in front of me") | 41 | 30 | 15 |
| 54 answerable: WRONG | 4 | 7 | **9** |
| 54 answerable: VAGUE | 8 | 6 | 4 |
| 12 unanswerable: invented an answer | 0 | 0 | **0** |

## What happened

**1. When the answer was in the prompt, the model got it right every time: 20 of 20 at 0.30, 9 of 9 at 0.45.**
As shipped, it answered "I don't have that in front of me" to 41 of 54 questions about PIP's own documents,
because the cut-off let a passage through for only 3 of them.

**2. It never invented an answer to the 12 questions no document answers**, in any condition, including when it was
handed one to three on-topic passages (0.30: all 12 questions got passages). The Stage 7 prompt's rule 4 ("An honest
'I don't have that in front of me' is always correct; a plausible guess is always wrong") is the likely reason. That
is evidence about this prompt and this model, not about models in general.

**3. The cost is real and it has a shape.** All six new wrong answers at 0.30 came from the same situation: Stage 5
returned three passages, **none of which held the answer in the prompt**, and the model built an answer from them
where it had declined before. 27 questions are in that situation at 0.30. Their answers there: 8 wrong (30%), 6
correct, 10 declined, 3 vague. The same 27 questions as shipped, with no passages: 3 wrong (11%), 21 declined, 3
vague. Six of the eight wrong answers are new. That is the failure this project recorded in FREEZE_LIST §10 —
misleading context, not a missing fact — reproduced at small scale. The six: `arch-cache-ttl` (answered that there is no TTL),
`arch-cloud-behind-local` (gave the Observer's locality rule as the reason), `arch-stale-lock` (a wrong staleness
rule), `fl-freeze-rule` (named three unrelated prohibitions), `migr-newest` (said the shortcut does not choose
automatically), `migr-total-checks` (said five defects failed). The one wrong answer that went away
(`vald-d06`) is itself a borderline call.

**4. A higher cut-off does not remove it.** Those six had top scores of 0.38 to 0.59 (`arch-stale-lock`: 0.59, 0.50,
0.49) — passages that looked relevant and were not. 0.45 still produced three new wrong answers. This is finding 2
of the retrieval report seen from the answer side: the score cannot tell the passage that answers from one about the
same subject.

**5. The 800-word cap hides retrieved answers.** At 0.30 the key phrase was retrieved but cut by Stage 7's 800-word
documents budget for 5 questions; the model answered 2 of them correctly from other text, 2 wrongly and declined 1.

## What this supports, and what it does not

- It does **not** support changing the cut-off on its own. By the rule I set, 0.30 trades 25 more correct answers for
  5 more wrong ones, which the rule counts as a failure. Whether that trade is acceptable is the owner's decision; the
  rule was mine, and strict on purpose.
- It points at two other levers, **neither tested here**: (a) the prompt tells the model how to treat facts about the
  user but nothing about documents, so a passage that does not state the answer is treated like one that does; (b) the
  800-word budget cuts a retrieved answer before the model reads it. Either can be run through this harness as a new
  condition, with a rule written down first. That is the next experiment, not done.

## Limits

- **One hand.** I wrote the questions, ran the check and graded it. Grading was blind to condition (the condition and
  the passages were not on the sheet and the key was not opened until every label was recorded), but an answer that
  says "according to the document" gives its condition away.
- **Nine borderline calls**, listed in `retrieval_e2e_grading_2026-10-08/make_grades.py` with a strict and a lenient
  reading. Under the strict reading 0.30 gains a net 21 correct and a net 7 wrong answers (against 0.60); under the
  lenient reading 24 and 3. The verdict does not move.
- **Temperature 0.** Chosen so the context is the only thing that differs; a user's model samples. It makes the
  comparison clean and is not what a user sees on a given day.
- **One corpus of technical Markdown, one 7B model, 66 questions.** 30% (8 of 27) is a rate from small numbers.
- **Largest prompt 2,210 tokens**, with no sign of the model's window cutting it (no round-number ceiling; 0 answers
  hit the 400-token limit).

---

# Appendix — generated tables (main grading)

Model qwen2.5:7b, snapshot `1577473`, temperature 0. Conditions: A_as_shipped = 0.6, B = 0.45, C = 0.3.

### The 54 answerable questions

| condition | cut-off | questions that got passages | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A_as_shipped | 0.6 | 3 | 1 | 41 | 4 | 8 |
| B | 0.45 | 20 | 11 | 30 | 7 | 6 |
| C | 0.3 | 47 | 26 | 15 | 9 | 4 |

### The 12 questions no document answers

| condition | cut-off | questions that got passages | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A_as_shipped | 0.6 | 0 | 0 | 12 | 0 | 0 |
| B | 0.45 | 2 | 0 | 12 | 0 | 0 |
| C | 0.3 | 12 | 0 | 12 | 0 | 0 |

### Paired against condition A_as_shipped (same question, only the passages differ)

| condition | answerable: more CORRECT / fewer CORRECT (sign test p) | answerable: WRONG rose / fell | unanswerable: WRONG rose / fell | unanswerable: DECLINES rose / fell |
|---|---|---|---|---|
| B | 10 / 0 (p = 0.00) | 3 / 0 | 0 / 0 | 0 / 0 |
| C | 25 / 0 (p = 0.00) | 6 / 1 | 0 / 0 | 0 / 0 |

### The pre-registered decision rule

- **B** (cut-off 0.45): (1) correct answers up by 10 (needs 8+, p < 0.05): met; (2) invented answers to unanswerable questions up by 0 (needs 2 or fewer): met; (3) wrong answers among the answerable up by 3 (needs 0 or fewer): NOT met. **NOT supported**
- **C** (cut-off 0.3): (1) correct answers up by 25 (needs 8+, p < 0.05): met; (2) invented answers to unanswerable questions up by 0 (needs 2 or fewer): met; (3) wrong answers among the answerable up by 5 (needs 0 or fewer): NOT met. **NOT supported**

### What the model was shown

Stage 7 caps the documents section at 800 words, so passages Stage 5 returns can be cut before the model
sees them. Split by what the PROMPT held, not what was retrieved:

| condition | answer in the prompt: CORRECT of | answer retrieved but cut by the 800-word cap: CORRECT of | passages without the answer: CORRECT / DECLINES / WRONG / VAGUE | no passages: CORRECT / DECLINES / WRONG / VAGUE |
|---|---|---|---|---|
| A_as_shipped | 1 of 2 | 0 of 0 | 0 / 0 / 1 / 0 | 0 / 41 / 3 / 7 |
| B | 9 of 9 | 1 of 1 | 1 / 3 / 6 / 0 | 0 / 27 / 1 / 6 |
| C | 20 of 20 | 2 of 5 | 4 / 9 / 6 / 3 | 0 / 5 / 1 / 1 |

### Checks

- distinct prompts run: 140; every status success: True
- the pipeline's own retrieval matched the plan on 140 of 140
- largest prompt Ollama counted: 2210 tokens (a prompt longer than the model's context window is cut without error; see the context length Ollama loaded the model with)
- answers that hit the 400-token limit: 0
