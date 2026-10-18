# V-2 part (a): long chats on today's code

Run stamp: 2026-10-18T04:34:18+00:00
- commit 4744edaf2489d11be4bd24164afa45df61a9da9a, uncommitted changes to tracked files: no
- Constitution version 1.0, sha256 3908bd8df7125990198086b6b0d9c09dc47d38c7ddcb383b28b31184a8328733
- model qwen2.5:7b, digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e; Ollama 0.40.3
- options sent: temperature=not sent, num_ctx=not sent
- transcript_token_cap: 8000
- prompt_hash: "9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139"
- wall_clock_seconds: [635.6]
- validity_condition: "Valid for gate-only comparisons; any change to the Observer prompt, the extraction schema, the model or grounding voids it."
- count_prompt_tokens_num_ctx: 16384

27 case runs, 0 errored.

## True facts learned (written or asked), by position and profile age

| position | week 1 | week 3 | week 9 |
|---|---|---|---|
| start | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| middle | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| end | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| all | 0/27 (0 written) | 0/27 (0 written) | 0/27 (0 written) |

By chat length:

| length | week 1 | week 3 | week 9 |
|---|---|---|---|
| S | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| M | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| L | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |

## Trick statements and near-misses reaching a belief table

| kind | start | middle | end | all |
|---|---|---|---|---|
| trap | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/81 (at most about 4%) |
| near_miss | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 1/27 (4%) | 1/81 (1%) |

All together: 1/162 (1%).
- HIT long_L_r0_d7: N3 (near_miss, end)

Learned rows: TRUE 0, TRAP 1, UNLABELLED 12; precision TRUE/(TRUE+TRAP) 0/1.

Unlabelled rows (from the filler or a mislabel; listed for a person to read, not judged here):

- long_S_r0_d63: written decision_log: 1 pass the aws solutions architect associate exam by march 0.7 active 2026-10-18t04:35:43z
- long_S_r1_d7: written topic_interests: 2 http headers 1 2026-10-18t04:36:09z active
- long_S_r1_d7: written topic_interests: 1 database indexing 1 2026-10-18t04:36:09z active
- long_S_r1_d7: written topic_interests: 4 exam preparation 1 2026-10-18t04:36:09z active
- long_S_r1_d7: written topic_interests: 3 git workflow 1 2026-10-18t04:36:09z active
- long_S_r1_d7: written decision_log: 1 to pass the aws solutions architect associate exam by march, the user should follow a sp
- long_S_r1_d21: written decision_log: 1 a sensible way to space out revision is short sessions several times a week, a practice 
- long_S_r1_d63: written decision_log: 1 use excalidraw for all diagrams due to personal preference and efficiency. 0.7 active 20
- long_S_r2_d7: written decision_log: 1 pass aws solutions architect associate exam by march 1.0 active 2026-10-18t04:37:40z
- long_M_r1_d7: written preference_memory: 1 exam_goal aws solutions architect associate exam by march 1 explicit 0 0.18 active
- long_M_r2_d7: written preference_memory: 1 project_management lanternfish, a budgeting app for student hostels 1 explicit 0 0.18 ac
- long_L_r0_d7: written topic_interests: 1 exam 1 2026-10-18t04:43:16z active

## What the model was given, and time per chat

| length | words in chat | prompt tokens (whole) | tokens Ollama read | share read | Observer seconds (no load) | output tokens |
|---|---|---|---|---|---|---|
| S | 1395 | 2572 | 2572-2572 | 100% - 100% | 10.7-27.8 | 419-1179 |
| M | 2677 | 4058 | 4058-4058 | 100% - 100% | 15.1-30.4 | 534-1193 |
| L | 4786 | 6506 | 2050-2050 | 32% - 32% | 9.2-19.8 | 306-764 |

## Verdict (rule fixed in PROTOCOL.md section (a) before the run)

TRUST DOES NOT CARRY OVER TO LONG CHATS: 1 trick statements or near-misses reached a belief table and 1 learned rows are TRAP.
Learning is reported, not judged: it is the baseline for W-1 (the window) and #19 (learning).
