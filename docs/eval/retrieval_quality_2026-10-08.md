# Retrieval quality — first measurement with the real embedding model (2026-10-08)

**Report only. Nothing in the pipeline was changed.** Raw results: `retrieval_results_2026-10-08_real.json`
(real model) and `retrieval_results_2026-10-08_shim.json` (the hashed bag-of-words stand-in, for comparison).
Questions and key phrases: `retrieval_labels_2026-10-08.json`, committed in `6c1720e` before the first run.
Tool: `scripts/eval_retrieval.py`.

## What was measured

Whether PIP's document search returns the passage that answers a question.

- **Model:** the real `all-MiniLM-L6-v2`, on CPU. This was not possible before the owner turned Smart App
  Control off (FREEZE_LIST §7.26); the validation pass of 2026-10-01 correctly claimed no retrieval result
  because its embedder was the stand-in.
- **Code under test:** the pipeline's own `vector_store.ingest_document` and `vector_store.query`, on a
  temporary index and a throwaway in-memory database. No real profile or key was touched.
- **Corpus:** seven of the project's own documents as of commit `1577473` (about 40,800 words, 93 chunks
  at the current 500-word setting), read with `git show` so a later edit cannot move the result.
- **Questions:** 54 with a known answer, 14 plainly off-topic, 4 about PIP but answered nowhere.
- **A question counts as answered** when a returned passage contains a short key phrase that occurs in the
  stated source document. This is a lexical test of a semantic system, so it is a floor (see finding 6).
- **Searched with** the first 12 words of the question, as `stage_01._extract_retrieval_hint` does; the
  full question was run as well.

Reproduce:

```
python scripts/eval_retrieval.py run --labels docs/eval/retrieval_labels_2026-10-08.json --out results.json
python scripts/eval_retrieval.py report --results results.json
python scripts/eval_retrieval.py run ... --shim      # the stand-in
```

## Findings

**1. As shipped, the right passage comes back for 2 of 54 questions (4%).** The ranking itself puts it in the
top 3 for 25 of 54 (46%) and in the top 10 for 34 (63%). What removes the rest is the 0.6 cut-off, not the
ranking: the passage that holds the answer scores a median **0.38** (middle half 0.32 to 0.46, highest 0.67),
so 0.6 sits above almost all of them. In the app this reads "nothing close enough" on the "Searching your
documents" line (`pipeline.py:410`). The spot check in §7.26 scored a matching passage at 0.73 and a reworded
question at 0.46; this measurement is mostly the second case.

**2. The score separates "about PIP" from "not about PIP", and nothing finer.** The best score for an
off-topic question was 0.05 to 0.19 (median 0.11); no off-topic question came back at any cut-off of 0.20 or
higher. But the passages that answer score a median 0.38, and so do the best passages returned for questions
that *missed* (0.38). A cut-off can keep off-topic questions out; it cannot pick the right passage among
passages about the same subject. At cut-offs from 0.20 to 0.30 the answered count stays at 25 of 54, but only
**18% to 23% of the passages handed to the model hold the answer** (at 0.6, 2 of 3 do, for just 2 questions).
That cost is not free here: the project's own record (FREEZE_LIST §10, "Fine-tuning rejected") is that
misleading context, not a missing fact, is what made the model fabricate.

**3. At 500 words the model cannot see most of a chunk.** On these documents the median 500-word chunk is
**855 tokens** (about 1.7 tokens per word of technical Markdown) and the model embeds only the first 254, so
**71% of the text in a chunk is not part of what its embedding was made from**. The comment in
`vector_store.py` says "~256"; on this kind of text that is about 150 words, not 256. Where the answer sits
matters: when it starts inside the readable part, the right passage is in the top 3 for **75% (12 of 16)**;
when it starts beyond it, **34% (13 of 38)**. 38 of the 54 answers are beyond it. At 300 words there is no such
gap (57% against 58%), so truncation does not explain everything; the numbers are small.

**4. Smaller chunks: one candidate, no established gain.** 300-word chunks did best (57% in the top 3 against
46%; MRR 0.51 against 0.41), but on the same 54 questions that is 12 better against 6 worse (sign test
p = 0.24), which cannot be told from luck. 200, 150 and 100 words were no better than 500 (6/7, 10/10, 11/15
better/worse). The data do not support "make chunks smaller"; they support testing 300 on more questions.

**5. The 12-word trim cost nothing here.** 14 of the 54 questions are longer than 12 words; the top-3 rate on
those is 50% with the full question and 50% with the trimmed one.

**6. The key-phrase test does not look like it hides much.** The right *document* is in the top 3 for 74%,
against 46% for the right *passage*, so about 15 questions are found in the right file but not the right
place. I read the returned passages for 8 of those 15 (every second one): none stated the answer in other
words. The check shows each passage's two best-matching sentences, so an answer buried elsewhere in a long
passage could have been missed.

**7. `skip_rag` is not a factor.** An early draft of this tool counted how many questions Stage 1's `skip_rag`
would keep from searching (47 of 54 were classed `general_knowledge`). That framing was wrong and was removed
before any result was recorded: `pipeline.py:388` runs Stage 5 on every turn (ADR-002), and `stage_02` accepts
`skip_rag` without using it. Stage 1 computes it and nothing reads it.

**8. Repeats.** Across three real-model runs the 500-, 300- and 200-word results were identical; the 150- and
100-word results moved by at most one question between runs. The search index is approximate, which would
explain it; the cause was not investigated. One question is 1.9 points, smaller than every difference relied
on above except finding 4, which is already marked as undecided. The committed results are the third run.

**9. Against the stand-in.** With the stand-in the right passage is in the top 3 for 26% (against 46%), and
the best off-topic score reaches **0.58** (median 0.38), so it cannot tell an off-topic question from an
on-topic one at all; the real model never exceeds 0.19. At 0.6 both return almost nothing, which is how this
stayed invisible. Results from the stand-in cannot be carried over in either direction.

## What this does not show

- **One kind of document.** Dense technical Markdown, heavy in identifiers and file names. The owner's own
  notes and papers are probably prose, and may score very differently. The cut-off values above should not be
  read as values for them.
- **Easy off-topic questions.** The 14 are cookies, football, Everest. A question that is general but close
  to a document's vocabulary ("how does SQLite journaling work?") is the hard case and was not tested; the
  0% false positives from 0.20 is the optimistic reading.
- **Questions written by the same hand that read the documents**, and only 54 of them. They paraphrase the
  source, but a real user will not paraphrase the way I did.
- **Retrieval only.** Whether the model answers better or worse with the extra passages was not measured.
- **One embedder, one machine.** Timing is incidental (median query 13 to 20 ms).

## What follows — none of it done, none of it authorised

Under the freeze, changing the threshold or the chunking changes what the model is told, so each needs the
owner's go-ahead and its own evidence. In order of what this report supports:

1. **Threshold.** A cut-off around 0.25 to 0.30 would return the answer for 46% of these questions instead of
   4%, and nothing for off-topic ones, but would hand the model about two passages per question of which
   roughly one in five holds the answer. Before changing it: a second corpus (the owner's real documents,
   with new labelled questions and some hard off-topic ones), and an end-to-end check that the model does not
   fabricate more with the extra passages.
2. **Chunking.** The 256-token blind spot is real and larger than the code comment says. A chunker that cuts
   by tokens (at most 254), or 300-word chunks, would remove most of it; only the second was measured, and
   not conclusively.
3. **The comment in `vector_store.py`** says "~256 tokens" for a 500-word chunk. On these documents a 500-word
   chunk is about 855 tokens. Correcting a comment is not a behaviour change, but it was not done here.

---

# Appendix A — full tables, real model (`all-MiniLM-L6-v2`)

Corpus snapshot `1577473`. Search depth 10 for ranking; production top_k 3.

### 1. Chunk sizes

| chunk words (overlap) | chunks | ingest | median query |
|---|---|---|---|
| 500 (50) | 93 | 2.2 s | 13.0 ms |
| 300 (30) | 155 | 3.0 s | 19.5 ms |
| 200 (20) | 231 | 4.5 s | 13.0 ms |
| 150 (15) | 309 | 6.4 s | 13.0 ms |
| 100 (10) | 459 | 7.6 s | 20.0 ms |

### 2a. Ranking by chunk size (500 words is the current setting), searching with the full question

| chunking | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|---|
| 500 (current) | 35% | 46% | 50% | 63% | 0.42 |
| 300 | 39% | 63% | 70% | 78% | 0.53 |
| 200 | 26% | 46% | 59% | 69% | 0.39 |
| 150 | 33% | 46% | 59% | 72% | 0.43 |
| 100 | 26% | 41% | 52% | 72% | 0.38 |

### 2b. Ranking by chunk size (500 words is the current setting), searching with the first 12 words (what the pipeline really searches with)

| chunking | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|---|
| 500 (current) | 33% | 46% | 50% | 63% | 0.41 |
| 300 | 39% | 57% | 70% | 76% | 0.51 |
| 200 | 28% | 44% | 57% | 67% | 0.39 |
| 150 | 33% | 46% | 54% | 70% | 0.42 |
| 100 | 28% | 39% | 54% | 69% | 0.38 |

### 2c. Checks on the measurement itself

A hit needs the key phrase inside ONE returned chunk, which can make a score look worse than the
search really is (a small chunk can cut the phrase in two; a passage can state the answer in other
words), and a difference between two chunk sizes can be luck on 54 questions. Each is counted here
instead of being left to be guessed at.

| chunking | key split across two chunks (unwinnable) | right DOCUMENT in top 3 | right CHUNK (key) in top 3 | better than 500 / worse than 500 (key, top 3; sign test p) |
|---|---|---|---|---|
| 500 | 0 | 74% | 46% | - |
| 300 | 0 | 70% | 57% | 12 / 6 (p = 0.24) |
| 200 | 0 | 63% | 44% | 6 / 7 (p = 1.00) |
| 150 | 0 | 74% | 46% | 10 / 10 (p = 1.00) |
| 100 | 0 | 69% | 39% | 11 / 15 (p = 0.56) |

The right-document column is the generous reading (the passage may be elsewhere in the right file); the
key column is the strict one. The truth about usefulness lies between them. The last column is a paired
comparison on the same 54 questions: with 54 questions one question is 1.9 percentage points, and a
difference only means something if the 'better' count clearly exceeds the 'worse' count.

### 3. By kind of question (current chunking, 12-word search)

| kind | questions | hit@3 | hit@10 |
|---|---|---|---|
| fact | 23 | 48% | 70% |
| number | 12 | 50% | 50% |
| procedure | 3 | 33% | 67% |
| why | 16 | 44% | 62% |

| source document | questions | hit@3 |
|---|---|---|
| AGENTS.md | 4 | 25% |
| docs/ARCHITECTURE.md | 12 | 42% |
| docs/CONVENTIONS.md | 9 | 33% |
| docs/FREEZE_LIST.md | 10 | 60% |
| docs/eval/migration_rerun_2026-10-03.md | 8 | 62% |
| docs/eval/observer_end_to_end_2026-09-28.md | 5 | 80% |
| docs/eval/reliability_validation_2026-10-01.md | 6 | 17% |

### 4. Does the 12-word trim cost anything?

14 of 54 questions are longer than 12 words.
- raw: hit@3 on those questions = 50%
- hint12: hit@3 on those questions = 50%

### 5. The threshold (production top_k = 3, current chunking, 12-word search)

What each cut-off would do. 'answered' = a returned chunk holds the answer. 'off-topic returned' = an off-topic question still got something back.

'passages that hold the answer' counts every returned passage, so it is what the model is actually handed:
the rest is context that does not answer the question (this project's own record, FREEZE_LIST section 10,
'Fine-tuning rejected', is that misleading context - not a missing fact - made the model fabricate).

| threshold | answered | chunks returned per question | passages that hold the answer | off-topic returned | near-topic returned |
|---|---|---|---|---|---|
| 0.00 | 46% (25 of 54) | 3.0 | 17% | 100% | 100% |
| 0.05 | 46% (25 of 54) | 3.0 | 17% | 100% | 100% |
| 0.10 | 46% (25 of 54) | 3.0 | 17% | 86% | 100% |
| 0.15 | 46% (25 of 54) | 3.0 | 17% | 21% | 100% |
| 0.20 | 46% (25 of 54) | 2.9 | 18% | 0% | 100% |
| 0.25 | 46% (25 of 54) | 2.7 | 19% | 0% | 75% |
| 0.30 | 46% (25 of 54) | 2.2 | 23% | 0% | 75% |
| 0.35 | 35% (19 of 54) | 1.5 | 25% | 0% | 75% |
| 0.40 | 24% (13 of 54) | 0.9 | 27% | 0% | 25% |
| 0.45 | 19% (10 of 54) | 0.6 | 33% | 0% | 25% |
| 0.50 | 7% (4 of 54) | 0.3 | 29% | 0% | 0% |
| 0.55 | 6% (3 of 54) | 0.1 | 43% | 0% | 0% |
| 0.60  <- current | 4% (2 of 54) | 0.1 | 67% | 0% | 0% |
| 0.65 | 2% (1 of 54) | 0.0 | 100% | 0% | 0% |
| 0.70 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.75 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.80 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.85 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.90 | 0% (0 of 54) | 0.0 | - | 0% | 0% |

### 6. How well the scores separate right from wrong

- similarity of the chunk that holds the answer: min 0.20 | p25 0.32 | median 0.38 | p75 0.46 | max 0.67
- best similarity for an OFF-TOPIC question: min 0.05 | p25 0.10 | median 0.11 | p75 0.13 | max 0.19
- best similarity for a NEAR-TOPIC question: min 0.25 | p25 0.37 | median 0.38 | p75 0.47 | max 0.47
- best similarity for answerable questions that were NOT found in the top 3: min 0.20 | p25 0.31 | median 0.38 | p75 0.46 | max 0.63

### 7. The 256-token blind spot (answer position inside its chunk)

The model reads 256 tokens of a chunk (254 of them text). Counted with the model's own tokenizer:

| chunking | median chunk length (tokens) | share of all chunk text the model cannot see | answer starts inside the readable part: hit@3 | answer starts beyond it: hit@3 |
|---|---|---|---|---|
| 500 | 855 | 71% | 75% of 16 | 34% of 38 |
| 300 | 514 | 52% | 57% of 28 | 58% of 26 |
| 200 | 341 | 29% | 42% of 36 | 50% of 18 |
| 150 | 257 | 9% | 47% of 45 | 44% of 9 |
| 100 | 170 | 1% | 40% of 52 | 0% of 2 |

**500-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 9 | 78% |
| 100-200 | 16 | 56% |
| 200-300 | 10 | 40% |
| 300+ | 19 | 26% |

**300-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 20 | 60% |
| 100-200 | 18 | 50% |
| 200-300 | 16 | 62% |
| 300+ | 0 | - |

**200-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 25 | 48% |
| 100-200 | 29 | 41% |
| 200-300 | 0 | - |
| 300+ | 0 | - |

### 8. Misses (current chunking, 12-word search): answerable but not in the top 3
- `arch-stale-lock` first hit rank None; best chunk 0.5875 from docs/FREEZE_LIST.md
- `arch-session-end` first hit rank None; best chunk 0.4649 from docs/FREEZE_LIST.md
- `arch-gate-before-reinforce` first hit rank None; best chunk 0.3385 from docs/eval/migration_rerun_2026-10-03.md
- `arch-one-thread` first hit rank 8; best chunk 0.3897 from docs/ARCHITECTURE.md
- `arch-cache-ttl` first hit rank None; best chunk 0.3809 from docs/FREEZE_LIST.md
- `arch-cloud-behind-local` first hit rank None; best chunk 0.3913 from docs/FREEZE_LIST.md
- `arch-401-423` first hit rank 9; best chunk 0.2413 from docs/eval/migration_rerun_2026-10-03.md
- `conv-null-loading` first hit rank None; best chunk 0.4202 from docs/eval/migration_rerun_2026-10-03.md
- `conv-agents-cap` first hit rank None; best chunk 0.4782 from AGENTS.md
- `conv-dead-config` first hit rank 9; best chunk 0.2921 from docs/CONVENTIONS.md
- `conv-kdf` first hit rank None; best chunk 0.2448 from docs/FREEZE_LIST.md
- `conv-conn-fixture` first hit rank None; best chunk 0.3991 from docs/FREEZE_LIST.md
- `conv-comments` first hit rank None; best chunk 0.198 from AGENTS.md
- `agents-db` first hit rank None; best chunk 0.2438 from docs/eval/observer_end_to_end_2026-09-28.md
- `agents-grpc` first hit rank None; best chunk 0.2866 from docs/ARCHITECTURE.md
- `agents-focus` first hit rank 5; best chunk 0.3217 from docs/FREEZE_LIST.md
- `migr-total-checks` first hit rank None; best chunk 0.4579 from docs/eval/migration_rerun_2026-10-03.md
- `migr-d19` first hit rank 6; best chunk 0.6323 from docs/FREEZE_LIST.md
- `migr-oem` first hit rank 6; best chunk 0.2781 from docs/FREEZE_LIST.md
- `obsv-sarcasm` first hit rank None; best chunk 0.327 from docs/FREEZE_LIST.md
- `vald-gpu` first hit rank None; best chunk 0.3458 from docs/eval/reliability_validation_2026-10-01.md
- `vald-critical` first hit rank None; best chunk 0.5361 from docs/eval/migration_rerun_2026-10-03.md
- `vald-retrieval-invalid` first hit rank None; best chunk 0.3479 from docs/eval/observer_end_to_end_2026-09-28.md
- `vald-tracked` first hit rank None; best chunk 0.4178 from docs/eval/migration_rerun_2026-10-03.md
- `vald-d06` first hit rank None; best chunk 0.5099 from docs/eval/reliability_validation_2026-10-01.md
- `fl-break-it` first hit rank 4; best chunk 0.3664 from docs/FREEZE_LIST.md
- `fl-finetune` first hit rank 10; best chunk 0.3079 from docs/FREEZE_LIST.md
- `fl-salt` first hit rank None; best chunk 0.4811 from docs/FREEZE_LIST.md
- `fl-ollama-down` first hit rank 6; best chunk 0.5124 from docs/FREEZE_LIST.md

---

# Appendix B — the same measurement with the stand-in embedder (hashed bag-of-words)

For comparison only (finding 9). The token-level section is empty because the stand-in has no tokenizer.
Corpus snapshot `1577473`. Search depth 10 for ranking; production top_k 3.

### 1. Chunk sizes

| chunk words (overlap) | chunks | ingest | median query |
|---|---|---|---|
| 500 (50) | 93 | 0.6 s | 2.0 ms |
| 300 (30) | 155 | 0.4 s | 1.7 ms |
| 200 (20) | 231 | 0.4 s | 1.0 ms |
| 150 (15) | 309 | 0.5 s | 1.9 ms |
| 100 (10) | 459 | 0.5 s | 2.0 ms |

### 2a. Ranking by chunk size (500 words is the current setting), searching with the full question

| chunking | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|---|
| 500 (current) | 9% | 28% | 35% | 54% | 0.22 |
| 300 | 11% | 30% | 37% | 46% | 0.22 |
| 200 | 6% | 24% | 26% | 37% | 0.15 |
| 150 | 7% | 22% | 33% | 37% | 0.17 |
| 100 | 11% | 17% | 24% | 35% | 0.17 |

### 2b. Ranking by chunk size (500 words is the current setting), searching with the first 12 words (what the pipeline really searches with)

| chunking | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|---|
| 500 (current) | 9% | 26% | 30% | 54% | 0.21 |
| 300 | 11% | 28% | 37% | 48% | 0.22 |
| 200 | 4% | 24% | 24% | 37% | 0.14 |
| 150 | 11% | 26% | 35% | 39% | 0.20 |
| 100 | 11% | 22% | 24% | 31% | 0.18 |

### 2c. Checks on the measurement itself

A hit needs the key phrase inside ONE returned chunk, which can make a score look worse than the
search really is (a small chunk can cut the phrase in two; a passage can state the answer in other
words), and a difference between two chunk sizes can be luck on 54 questions. Each is counted here
instead of being left to be guessed at.

| chunking | key split across two chunks (unwinnable) | right DOCUMENT in top 3 | right CHUNK (key) in top 3 | better than 500 / worse than 500 (key, top 3; sign test p) |
|---|---|---|---|---|
| 500 | 0 | 54% | 26% | - |
| 300 | 0 | 56% | 28% | 6 / 5 (p = 1.00) |
| 200 | 0 | 52% | 24% | 6 / 7 (p = 1.00) |
| 150 | 0 | 48% | 26% | 7 / 7 (p = 1.00) |
| 100 | 0 | 54% | 22% | 7 / 9 (p = 0.80) |

The right-document column is the generous reading (the passage may be elsewhere in the right file); the
key column is the strict one. The truth about usefulness lies between them. The last column is a paired
comparison on the same 54 questions: with 54 questions one question is 1.9 percentage points, and a
difference only means something if the 'better' count clearly exceeds the 'worse' count.

### 3. By kind of question (current chunking, 12-word search)

| kind | questions | hit@3 | hit@10 |
|---|---|---|---|
| fact | 23 | 26% | 39% |
| number | 12 | 33% | 50% |
| procedure | 3 | 33% | 100% |
| why | 16 | 19% | 69% |

| source document | questions | hit@3 |
|---|---|---|
| AGENTS.md | 4 | 0% |
| docs/ARCHITECTURE.md | 12 | 8% |
| docs/CONVENTIONS.md | 9 | 33% |
| docs/FREEZE_LIST.md | 10 | 30% |
| docs/eval/migration_rerun_2026-10-03.md | 8 | 75% |
| docs/eval/observer_end_to_end_2026-09-28.md | 5 | 20% |
| docs/eval/reliability_validation_2026-10-01.md | 6 | 0% |

### 4. Does the 12-word trim cost anything?

14 of 54 questions are longer than 12 words.
- raw: hit@3 on those questions = 50%
- hint12: hit@3 on those questions = 43%

### 5. The threshold (production top_k = 3, current chunking, 12-word search)

What each cut-off would do. 'answered' = a returned chunk holds the answer. 'off-topic returned' = an off-topic question still got something back.

'passages that hold the answer' counts every returned passage, so it is what the model is actually handed:
the rest is context that does not answer the question (this project's own record, FREEZE_LIST section 10,
'Fine-tuning rejected', is that misleading context - not a missing fact - made the model fabricate).

| threshold | answered | chunks returned per question | passages that hold the answer | off-topic returned | near-topic returned |
|---|---|---|---|---|---|
| 0.00 | 26% (14 of 54) | 3.0 | 9% | 100% | 100% |
| 0.05 | 26% (14 of 54) | 3.0 | 9% | 100% | 100% |
| 0.10 | 26% (14 of 54) | 3.0 | 9% | 100% | 100% |
| 0.15 | 26% (14 of 54) | 3.0 | 9% | 93% | 100% |
| 0.20 | 26% (14 of 54) | 2.9 | 9% | 86% | 100% |
| 0.25 | 22% (12 of 54) | 2.7 | 8% | 79% | 75% |
| 0.30 | 20% (11 of 54) | 2.5 | 8% | 64% | 75% |
| 0.35 | 15% (8 of 54) | 2.2 | 7% | 57% | 75% |
| 0.40 | 9% (5 of 54) | 1.5 | 6% | 43% | 25% |
| 0.45 | 9% (5 of 54) | 1.1 | 8% | 36% | 25% |
| 0.50 | 6% (3 of 54) | 0.8 | 7% | 21% | 0% |
| 0.55 | 4% (2 of 54) | 0.4 | 11% | 7% | 0% |
| 0.60  <- current | 2% (1 of 54) | 0.1 | 25% | 0% | 0% |
| 0.65 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.70 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.75 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.80 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.85 | 0% (0 of 54) | 0.0 | - | 0% | 0% |
| 0.90 | 0% (0 of 54) | 0.0 | - | 0% | 0% |

### 6. How well the scores separate right from wrong

- similarity of the chunk that holds the answer: min 0.19 | p25 0.31 | median 0.37 | p75 0.42 | max 0.65
- best similarity for an OFF-TOPIC question: min 0.14 | p25 0.28 | median 0.38 | p75 0.47 | max 0.58
- best similarity for a NEAR-TOPIC question: min 0.23 | p25 0.36 | median 0.38 | p75 0.47 | max 0.47
- best similarity for answerable questions that were NOT found in the top 3: min 0.15 | p25 0.37 | median 0.43 | p75 0.51 | max 0.63

### 7. The 256-token blind spot (answer position inside its chunk)

(no tokenizer for this embedder, so the token-level test is not available; word positions only)

**500-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 9 | 11% |
| 100-200 | 16 | 25% |
| 200-300 | 10 | 40% |
| 300+ | 19 | 26% |

**300-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 20 | 30% |
| 100-200 | 18 | 17% |
| 200-300 | 16 | 38% |
| 300+ | 0 | - |

**200-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):

| answer starts at word | questions | hit@3 |
|---|---|---|
| 0-100 | 25 | 16% |
| 100-200 | 29 | 31% |
| 200-300 | 0 | - |
| 300+ | 0 | - |

### 8. Misses (current chunking, 12-word search): answerable but not in the top 3
- `arch-hook-scope` first hit rank None; best chunk 0.3717 from docs/ARCHITECTURE.md
- `arch-stale-lock` first hit rank None; best chunk 0.5704 from docs/FREEZE_LIST.md
- `arch-lock-gate-order` first hit rank None; best chunk 0.505 from docs/FREEZE_LIST.md
- `arch-session-end` first hit rank 10; best chunk 0.4146 from docs/FREEZE_LIST.md
- `arch-gate-before-reinforce` first hit rank 4; best chunk 0.3883 from docs/FREEZE_LIST.md
- `arch-one-thread` first hit rank 10; best chunk 0.2438 from docs/FREEZE_LIST.md
- `arch-cache-ttl` first hit rank None; best chunk 0.4068 from docs/FREEZE_LIST.md
- `arch-cloud-behind-local` first hit rank 10; best chunk 0.4328 from docs/FREEZE_LIST.md
- `arch-gate-cost` first hit rank None; best chunk 0.5027 from docs/FREEZE_LIST.md
- `arch-role-headers` first hit rank 10; best chunk 0.2849 from docs/eval/reliability_validation_2026-10-01.md
- `arch-401-423` first hit rank 6; best chunk 0.5497 from docs/FREEZE_LIST.md
- `conv-no-pydantic` first hit rank None; best chunk 0.3585 from docs/eval/migration_rerun_2026-10-03.md
- `conv-null-loading` first hit rank None; best chunk 0.3659 from docs/FREEZE_LIST.md
- `conv-agents-cap` first hit rank None; best chunk 0.4906 from docs/FREEZE_LIST.md
- `conv-hooks-clone` first hit rank None; best chunk 0.5522 from docs/FREEZE_LIST.md
- `conv-kdf` first hit rank 10; best chunk 0.4223 from docs/FREEZE_LIST.md
- `conv-comments` first hit rank 9; best chunk 0.4879 from docs/FREEZE_LIST.md
- `agents-db` first hit rank None; best chunk 0.3935 from docs/eval/migration_rerun_2026-10-03.md
- `agents-grpc` first hit rank None; best chunk 0.345 from docs/FREEZE_LIST.md
- `agents-focus` first hit rank None; best chunk 0.5339 from docs/eval/migration_rerun_2026-10-03.md
- `agents-log-order` first hit rank 4; best chunk 0.4054 from docs/FREEZE_LIST.md
- `migr-d19` first hit rank 7; best chunk 0.227 from docs/eval/migration_rerun_2026-10-03.md
- `migr-oem` first hit rank 10; best chunk 0.3456 from docs/FREEZE_LIST.md
- `obsv-precision` first hit rank None; best chunk 0.4449 from docs/FREEZE_LIST.md
- `obsv-model` first hit rank None; best chunk 0.5678 from docs/FREEZE_LIST.md
- `obsv-cases` first hit rank None; best chunk 0.4358 from docs/FREEZE_LIST.md
- `obsv-sarcasm` first hit rank None; best chunk 0.3503 from docs/FREEZE_LIST.md
- `vald-rest` first hit rank 8; best chunk 0.2548 from docs/FREEZE_LIST.md
- `vald-gpu` first hit rank None; best chunk 0.5727 from docs/FREEZE_LIST.md
- `vald-critical` first hit rank None; best chunk 0.5114 from docs/FREEZE_LIST.md
- `vald-retrieval-invalid` first hit rank None; best chunk 0.374 from docs/FREEZE_LIST.md
- `vald-tracked` first hit rank None; best chunk 0.5217 from docs/FREEZE_LIST.md
- `vald-d06` first hit rank 6; best chunk 0.4895 from docs/ARCHITECTURE.md
- `fl-principle` first hit rank None; best chunk 0.6259 from docs/FREEZE_LIST.md
- `fl-finetune` first hit rank 7; best chunk 0.4338 from docs/FREEZE_LIST.md
- `fl-audit-spec` first hit rank None; best chunk 0.5112 from docs/eval/migration_rerun_2026-10-03.md
- `fl-salt` first hit rank 7; best chunk 0.4566 from docs/FREEZE_LIST.md
- `fl-ollama-down` first hit rank None; best chunk 0.4128 from docs/FREEZE_LIST.md
- `fl-stage12` first hit rank None; best chunk 0.1545 from docs/FREEZE_LIST.md
- `fl-promise1` first hit rank None; best chunk 0.5701 from docs/FREEZE_LIST.md
