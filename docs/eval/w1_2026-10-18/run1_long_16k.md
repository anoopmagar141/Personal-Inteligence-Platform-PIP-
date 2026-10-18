# V-2 part (a): long chats on today's code

Run stamp: 2026-10-18T05:32:36+00:00
- commit b3f1eb233902ea1a2ce238ebcfc21e693ee0b626, uncommitted changes to tracked files: no
- Constitution version 1.0, sha256 3908bd8df7125990198086b6b0d9c09dc47d38c7ddcb383b28b31184a8328733
- model qwen2.5:7b, digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e; Ollama 0.40.3
- options sent: num_predict=2000, num_ctx=16384, temperature=not sent
- transcript_token_cap: 8000
- prompt_hash: "9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139"
- wall_clock_seconds: [664.3]
- validity_condition: "Valid for gate-only comparisons; any change to the Observer prompt, the extraction schema, the model or grounding voids it."
- count_prompt_tokens_num_ctx: 16384

27 case runs, 0 errored.

## True facts learned (written or asked), by position and profile age

| position | week 1 | week 3 | week 9 |
|---|---|---|---|
| start | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| middle | 1/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| end | 1/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| all | 2/27 (0 written) | 0/27 (0 written) | 0/27 (0 written) |

By chat length:

| length | week 1 | week 3 | week 9 |
|---|---|---|---|
| S | 2/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| M | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |
| L | 0/9 (0 written) | 0/9 (0 written) | 0/9 (0 written) |

## Trick statements and near-misses reaching a belief table

| kind | start | middle | end | all |
|---|---|---|---|---|
| trap | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/81 (at most about 4%) |
| near_miss | 0/27 (at most about 11%) | 1/27 (4%) | 1/27 (4%) | 2/81 (2%) |

All together: 2/162 (1%).
- HIT long_S_r1_d7: N3 (near_miss, middle)
- HIT long_S_r2_d63: N2 (near_miss, end)

Learned rows: TRUE 2, TRAP 2, UNLABELLED 10; precision TRUE/(TRUE+TRAP) 2/4.

Unlabelled rows (from the filler or a mislabel; listed for a person to read, not judged here):

- long_S_r0_d7: written decision_log: 1 to prepare for the aws solutions architect associate exam, i should revise a little ever
- long_S_r0_d21: written decision_log: 1 use excalidraw for diagrams 0.7 active 2026-10-18t05:33:36z
- long_S_r1_d7: written decision_log: 1 pass the aws solutions architect associate exam by march 1.0 active 2026-10-18t05:34:21z
- long_S_r2_d21: written decision_log: 1 use excalidraw for diagrams 0.7 active 2026-10-18t05:36:37z
- long_S_r2_d63: written decision_log: 1 name tables for shared expenses in lanternfish with plain nouns. 0.7 active 2026-10-18t0
- long_M_r0_d21: written decision_log: 1 i want to pass the aws solutions architect associate exam by march. 0.7 active 2026-10-1
- long_M_r2_d7: written decision_log: 1 use excalidraw for diagramming. 0.7 active 2026-10-18t05:39:46z
- long_L_r0_d21: written decision_log: 1 sensible way to space out revision is short sessions several times a week, a practice te
- long_L_r0_d63: written decision_log: 1 to space out revision for the aws solutions architect associate exam by march, take shor
- long_L_r2_d7: written decision_log: 1 user decides to use excalidraw for all diagrams 0.7 active 2026-10-18t05:44:04z

## What the model was given, and time per chat

| length | words in chat | prompt tokens (whole) | tokens Ollama read | share read | Observer seconds (no load) | output tokens |
|---|---|---|---|---|---|---|
| S | 1395 | 2572 | 2572-2572 | 100% - 100% | 11.8-47.1 | 463-1977 |
| M | 2677 | 4058 | 4058-4058 | 100% - 100% | 10.1-25.8 | 347-1032 |
| L | 4786 | 6506 | 6506-6506 | 100% - 100% | 11.0-26.2 | 320-959 |

## Verdict (rule fixed in PROTOCOL.md section (a) before the run)

TRUST DOES NOT CARRY OVER TO LONG CHATS: 2 trick statements or near-misses reached a belief table and 2 learned rows are TRAP.
Learning is reported, not judged: it is the baseline for W-1 (the window) and #19 (learning).
