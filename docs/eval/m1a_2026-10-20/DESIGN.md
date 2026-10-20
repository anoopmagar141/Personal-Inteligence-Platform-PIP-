# M-1(a): does a quote the gate accepts really support its claim? (design note, for the owner's approval)

BLUEPRINT card M-1, part (a); Promise 4. Written 2026-10-20, before anything is built or graded. Nothing runs until the
owner approves this page; then it is committed, and only then is the sheet made and graded.

## The question

Promise 4 says stored memory is supported by the user's words. Its honest wording still says: "Whether a genuine
quote actually supports the claim drawn from it has not been separately measured." The gate's own corpus has 0 false
accepts, but those cases were written to test it. This measures the real model's candidates instead.

Two numbers: of the quotes the gate ACCEPTS, how many really support their claim (false accepts are the dangerous
error); of the quotes it REJECTS for support, how many did support it (false rejects, the cost of the strictness).

## The items

- From the V-2 recordings (qwen2.5:7b short 3 x 37, llama3.1:8b short 3 x 37, qwen long 27), replayed through today's
  code (456dd9d), no model call. Memory candidates only (decisions were read one by one in G-4, §7.60).
- Only candidates whose quote is genuinely the user's: the gate said SUFFICIENT, NOT_ENTAILING or CONTRADICTORY.
  A quote the user never said (not found, the assistant's words, too short) has nothing to support.
- One item per distinct chat + claim (the same quote repeated across runs is graded once): about 54 accepted and 158
  rejected. ALL accepted items are graded; the same number of rejected items are drawn by a seeded sampler (seed
  20261020). About 108 items.

## Blind grading

- Each item shows only: the claim in plain words ("PIP would remember: preferred tool = Excalidraw"), the quote, the
  user's whole message it came from, and the assistant's message just before it. Hidden: the gate's verdict, the
  Constitution's, the model, the run. Items shuffled by the same seed.
- One answer per item: SUPPORTS (the user's own words say this about themselves), DOES NOT, or UNCLEAR. Strict reading:
  UNCLEAR counts as DOES NOT; lenient: as SUPPORTS.
- The sheet and its hidden key are written first; the key's SHA-256 is committed before grading starts.
- The grader must never have seen the verdicts. I have (this session ran the replays), so it cannot be me.

## The rule, fixed now

- Report: accepted items graded DOES NOT (false accepts), with a 95% bound; rejected items graded SUPPORTS (false
  rejects), with a 95% bound; both readings.
- Verdict on Promise 4's wording: HOLDS if 0 accepted items are DOES NOT on the strict reading; MOSTLY HOLDS if 1-3
  (each listed in the record); DOES NOT HOLD if 4 or more. The false-reject rate is reported, not judged.
- Promise 4's text is updated with the result either way.

## Limits, stated in advance

One author's made-up chats; one grader; English only; the qwen and llama recordings only.

## The one decision: who grades

**Decided by the owner, 2026-10-20: A.** The design above approved as written.

- A (my default): a fresh Claude session that has never seen the verdicts grades all items blind; I build the sheet
  and score the answers. About an hour, no work for the owner.
- B: the owner grades (most independent; about 1.5-2 hours for 108 items).
- C: A, plus the owner grades 20 items drawn by the seed, to check that the two agree.
