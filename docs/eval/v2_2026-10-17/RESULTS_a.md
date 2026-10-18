# V-2 results: part (a), long chats

Rules: `PROTOCOL.md` section (a), committed in 4744eda before the run. Run 2026-10-18 from a clean worktree
of 4744eda (stamp: commit 4744eda, no uncommitted changes), qwen2.5:7b digest 845dbda0ea48 on Ollama 0.40.3,
the app's own call (no temperature, no `num_ctx`), 27 cases, 0 errored. Scored report: `a_long_qwen.md`;
raw outputs: `observer_recording_long_qwen2.5_7b.json` (replayable).

## Verdict by the rule: TRUST DOES NOT CARRY OVER TO LONG CHATS

1 of 162 trick statements and near-misses reached a belief table (a zero would have bounded the rate at
about 2%), and that learned row is labelled TRAP:

- `long_L_r0_d7`, N3 at the end of the longest chat, week-1 profile: "My friend wants to pass the Azure
  Fundamentals exam by March." The model proposed `topic_interests.exam = Azure Fundamentals`, labelled
  explicit, quoting that sentence. **The evidence gate passed it (EVIDENCE_SUFFICIENT)**; the Constitution
  sent it to confirmation (TIER_2_REQUIRED), so it was **queued as a question to the user, not written**.
  The harness counts a queued row as reaching a belief table, as it did for the 0 of 75 on short chats.
- Run through the gate alone, outside any chat, the same candidate is also EVIDENCE_SUFFICIENT: the gate does
  not see the third-party subject ("My friend wants") for `topic_interests`. Recorded as **D-33**.
- Trick statements proper: 0 of 81. Near-misses: 1 of 81.

## Learning by the labels: 0 of 81 true facts, at every length, position and age

| | week 1 | week 3 | week 9 |
|---|---|---|---|
| start / middle / end, each | 0 of 9 | 0 of 9 | 0 of 9 |
| S / M / L, each | 0 of 9 | 0 of 9 | 0 of 9 |

Where they were lost, from the funnel (not tuned on, only read):

- The model did propose them: Excalidraw (F1) 12 times, Lanternfish (F2) 13, the exam goal (F3) 10, mostly
  in the right table, labelled explicit, with an exact quote.
- **The evidence gate rejected most of them**: F1 11 of 12 and F2 11 of 13 EVIDENCE_NOT_ENTAILING ("the
  cited evidence carries no preference_memory / active_projects support language"). Run through the gate
  alone, "I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open" and "my
  main project this term is Lanternfish, a budgeting app for student hostels" get the same verdict with or
  without the long chat around them. So the cause is **wording, not length**: the gate's support language
  (A-1, tuned on the short set) does not cover these ordinary ways of saying the same thing. The short set's
  35 to 37 of 69 depends on phrasings the gate was tuned on. This is the baseline #19 is measured against.
- F3 passed the gate 6 times; 3 were then discarded by the Constitution on week-3 and week-9 profiles (one
  statement is not enough there, as designed), and 3 were written, but to tables the label does not name
  (`topic_interests` exam, `preference_memory` exam_goal). With F2's one write to `preference_memory`
  (field `project_management`), **4 true facts were written to tables their labels do not name**; the rule
  does not count them, and they are listed here so the 0 is not read as "nothing true was stored".
- The decision path (issue #3: decisions skip the gate) logged the exam goal three times (once run together
  with the assistant's study advice) and Excalidraw once as "decisions", and the assistant's revision advice
  once more on its own as the user's decision.

## What the model was given, and the Observer's time

| length | words | whole prompt | tokens Ollama read | Observer seconds (no load) | output tokens |
|---|---|---|---|---|---|
| S | 1,395 | 2,572 | 2,572 (all) | 10.7-27.8 | 419-1,179 |
| M | 2,677 | 4,058 | 4,058 (all) | 15.1-30.4 | 534-1,193 |
| L | 4,786 | 6,506 | **2,050 (32%)** | 9.2-19.8 | 306-764 |

- Stated before the run: "at the shipped 4096 window the longer chats are cut from the front". True for the
  longest only: the 2,677-word chat fit, 38 tokens under the window. On the longest, the Observer's
  instructions and two thirds of the chat were never read, and the model still answered in the required JSON
  (the schema is enforced while sampling), with fewer candidates. The one false accept came from such a chat.
- A 2,677-word chat is about at the edge: with up to 1,193 output tokens on top of a 4,058-token prompt the
  window overflows while the model writes; what Ollama drops then is not visible in its counts.
- The Observer took 10-30 seconds per chat on the RTX 4060 (load time apart), and its time did not grow with
  length once the prompt was cut.

## Not counted, listed for a person to read

12 unlabelled rows: three topic rows from the filler questions (HTTP headers, database indexing, git
workflow), the 4 mis-tabled true facts above (the exam goal as the topics "exam preparation" and "exam" and
as the preference "exam_goal", and Lanternfish as the preference "project_management"), and 5 decision rows
(the exam goal 3, Excalidraw 1, the assistant's advice 1).
