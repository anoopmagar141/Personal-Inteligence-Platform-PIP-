# The check on the owner's own document — results (2026-10-08)

The document is the owner's project synopsis (2,993 words, about 7 chunks at the current 500/50 chunking), kept in
a local folder that git ignores because the questions and keys quote it. What is committed is this report (counts
and question identifiers, no text from the document) and `own_docs_manifest_2026-10-08.json`, the SHA-256 of the
document, the 32 questions (26 answerable, 22 of them drawn by a seeded sentence sampler and 4 hand-picked from the
tables, plus 6 it does not answer) and the protocol, committed (`90d2607`) before the first run. The protocol is the
lever protocol (`a1e5f97`) unchanged. Tools: `scripts/eval_retrieval.py` and `scripts/eval_retrieval_levers.py --own`.

PIP itself does not accept a `.docx` (its supported types are `.pdf .md .txt .py .json .html`), so to put this
synopsis into PIP it would be saved as PDF or text; the check used its extracted text, as "save as text" gives.

## 1. The search step (no model involved)

| | 500-word chunks, searched with the first 12 words |
|---|---|
| right passage in the top 3 | 17 of 26 (65%) — with only 7 chunks, chance would be about 43% |
| found at the shipped cut-off, 0.60 | **0 of 26** |
| found at 0.30 | 7 (27%) |
| found at 0.20 | 13 (50%) |
| found at 0.15 | 15 (58%) |
| median score of the passage that answers | **0.26** (on PIP's technical notes: 0.38) |
| best score for the 14 unrelated questions | 0.15 at most |

The same picture as on PIP's own notes, stronger: plain prose scores lower against a question than dense technical
text, so a 0.60 cut-off lets nothing through and even 0.30 misses most answers. A cut-off near 0.15 to 0.20 would
keep the unrelated questions out and reach 13 to 15 of the 26. The 256-token blind spot is here too: when the answer
starts in the part of a 500-word passage the model embeds, the right passage is in the top 3 for 14 of 14 questions;
when it starts beyond it, for 3 of 12.

## 2. The answers (A shipped, C 0.30, D + document rule, E + 1800-word budget, F both)

**Verdict by the rule fixed in advance: INCONCLUSIVE for every lever.** The validity guard was not met: plain 0.30
did not reproduce the wrong-answer problem on this document (1 wrong, against 3 under the shipped setting), so this
set could not have shown a lever fixing it.

| 26 answerable | A: shipped | C: 0.30 | D: C + rule | E: C + budget | F: both |
|---|---|---|---|---|---|
| questions that got any passage | 0 | 15 | 15 | 15 | 15 |
| CORRECT | 1 | **8** | 8 | 8 | 8 |
| DECLINES | 17 | 9 | 10 | 9 | 11 |
| WRONG | 3 | 1 | 2 | 1 | 1 |
| VAGUE | 5 | 8 | 6 | 8 | 6 |
| invented, of 6 unanswerable | 0 | 0 | 0 | 0 | 0 |

What it shows, read plainly rather than through the rule:

- **Lowering the cut-off helped here and cost nothing.** Correct answers went from 1 to 8 (8 up, 1 down; p = 0.039)
  and wrong answers did not rise (3 to 1). When the answer was in the prompt the model was right 7 of 7.
- **It is limited by what search finds, not by the model.** 11 of the 26 questions got no passage at all even at 0.30.
  That matches the search step: the passage that answers scored under 0.30 for most of them.
- **The levers made no difference** (8 correct under C, D, E and F alike). With one wrong answer to fix, there was
  nothing for a prompt rule to remove.
- **As shipped, the model fabricated for 3 of 26** with no passages, answering from nothing; at 0.30 it did for 1.
- Eight answers at 0.30 were **vague**: general, true-sounding and not the document's own point (what "the memory
  component provides", what "phase one includes"). That is a failure the correct/wrong split does not capture.

## What this does not show

- **One document of 7 chunks.** Retrieval has little to choose between; a library of documents is harder.
- **The cut-off tested was 0.30**, fixed in advance. The search step says a lower one finds more; whether 0.15 or
  0.20 helps the answers, or lets in the wrong-answer problem seen on the technical notes, needs its own protocol.
- **One hand** wrote, ran and graded this. Nine borderline calls are in the local grading folder with a strict and a
  lenient reading; the verdict (inconclusive) does not move.
- **A document about PIP.** The questions name PIP and the document is its own synopsis; the model has never seen it,
  but a document on an unrelated subject would test invention harder.

---

# Appendix A — the search step, full tables

(see `own_docs_retrieval_2026-10-08.md`)

# Appendix B — the answers, generated tables

(The generator's wording says "held-out set" in the decision-rule and "changed grade" headings; in this report the set is
the owner's document. "Questions that got any passage" counts questions for which Stage 5 returned at least one passage.)

Model qwen2.5:7b, num_ctx 8192, temperature 0, snapshot `local`. Conditions: A = {'similarity_threshold': 0.6, 'note': 'as shipped'}; C = {'similarity_threshold': 0.3, 'note': "the previous run's best cut-off, no lever; the baseline for the levers"}; D = {'similarity_threshold': 0.3, 'document_rule': True}; E = {'similarity_threshold': 0.3, 'rag_chunks_tokens': 1800}; F = {'similarity_threshold': 0.3, 'document_rule': True, 'rag_chunks_tokens': 1800}.

### The owner's own document (the verdict is drawn from this)

**answerable, 26 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A | 0 | 0 | 1 | 17 | 3 | 5 |
| C | 15 | 399 | 8 | 9 | 1 | 8 |
| D | 15 | 399 | 8 | 10 | 2 | 6 |
| E | 15 | 567 | 8 | 9 | 1 | 8 |
| F | 15 | 567 | 8 | 11 | 1 | 6 |

**no document answers it, 6 questions**

| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |
|---|---|---|---|---|---|---|
| A | 0 | 0 | 0 | 6 | 0 | 0 |
| C | 2 | 220 | 0 | 6 | 0 | 0 |
| D | 2 | 220 | 0 | 6 | 0 | 0 |
| E | 2 | 338 | 0 | 6 | 0 | 0 |
| F | 2 | 338 | 0 | 6 | 0 | 0 |

### Decision rule (held-out set, relative to A)

Validity guard: WRONG under C = 1, under A = 3; the problem is reproduced when C exceeds A by 2 or more: **NO - every verdict is INCONCLUSIVE**.

- **D**: (1) CORRECT 1 -> 8, 8 up / 1 down, p = 0.039, needs net 6+ and p < 0.05: met; (2) WRONG 3 -> 2 (must not rise): met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 8 against C's 8 (at most 3 lower): met. **INCONCLUSIVE** (strict reading: INCONCLUSIVE; lenient reading: INCONCLUSIVE)
- **E**: (1) CORRECT 1 -> 8, 8 up / 1 down, p = 0.039, needs net 6+ and p < 0.05: met; (2) WRONG 3 -> 1 (must not rise): met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 8 against C's 8 (at most 3 lower): met. **INCONCLUSIVE** (strict reading: INCONCLUSIVE; lenient reading: INCONCLUSIVE)
- **F**: (1) CORRECT 1 -> 8, 8 up / 1 down, p = 0.039, needs net 6+ and p < 0.05: met; (2) WRONG 3 -> 1 (must not rise): met; (3) invented on the unanswerable 0 -> 0 (rise of at most 1): met; (4) CORRECT 8 against C's 8 (at most 3 lower): met. **INCONCLUSIVE** (strict reading: INCONCLUSIVE; lenient reading: INCONCLUSIVE)

### Held-out answers that changed grade relative to C

- D: own-01: VAGUE -> DECLINES; own-17: VAGUE -> WRONG
- E: none
- F: own-01: VAGUE -> DECLINES; own-22: VAGUE -> DECLINES

### What the model was shown (held-out, answerable)

| condition | answer in the prompt: CORRECT of | answer retrieved but cut: CORRECT of | passages without the answer: CORRECT / DECLINES / WRONG / VAGUE | no passages: CORRECT / DECLINES / WRONG / VAGUE |
|---|---|---|---|---|
| A | 0 of 0 | 0 of 0 | 0 / 0 / 0 / 0 | 1 / 17 / 3 / 5 |
| C | 7 of 7 | 0 of 0 | 1 / 1 / 0 / 6 | 0 / 8 / 1 / 2 |
| D | 7 of 7 | 0 of 0 | 1 / 1 / 1 / 5 | 0 / 9 / 1 / 1 |
| E | 7 of 7 | 0 of 0 | 1 / 1 / 0 / 6 | 0 / 8 / 1 / 2 |
| F | 7 of 7 | 0 of 0 | 1 / 2 / 0 / 5 | 0 / 9 / 1 / 1 |

### Checks

- distinct prompts run: 101; every status success: True
- largest prompt Ollama counted: 2555 tokens (num_ctx 8192)
- answers that hit the 400-token limit: 1
