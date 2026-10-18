# V-2 part (a): long chats on today's code

Run stamp: 2026-10-18T10:30:47+00:00
- commit 69252d9b5303f81904d98b93caa296f6c4bdfc7a, uncommitted changes to tracked files: no
- Constitution version 1.1, sha256 75363e5af8e00985f27d4b0c161e505e8e2d293b86c59dc7908ef125de048d83
- model qwen2.5:7b, digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e; Ollama 0.40.3
- options sent: num_predict=2000, num_ctx=16384, temperature=0.0
- transcript_token_cap: 8000
- prompt_hash: "9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139"
- wall_clock_seconds: [725.1]
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
| near_miss | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/27 (at most about 11%) | 0/81 (at most about 4%) |

All together: 0/162 (at most about 2%).

Learned rows: TRUE 0, TRAP 0, UNLABELLED 0; precision TRUE/(TRUE+TRAP) 0/0.

## What the model was given, and time per chat

| length | words in chat | prompt tokens (whole) | tokens Ollama read | share read | Observer seconds (no load) | output tokens |
|---|---|---|---|---|---|---|
| S | 1395 | 2572 | 2572-2572 | 100% - 100% | 25.9-43.5 | 955-1622 |
| M | 2677 | 4058 | 4058-4058 | 100% - 100% | 12.8-15.6 | 404-506 |
| L | 4786 | 6506 | 6506-6506 | 100% - 100% | 13.8-17.8 | 375-522 |

## Verdict (rule fixed in PROTOCOL.md section (a) before the run)

TRUST HOLDS ON LONG CHATS: no trick statement or near-miss reached a belief table (0/162 (at most about 2%)) and no learned row is TRAP.
Learning is reported, not judged: it is the baseline for W-1 (the window) and #19 (learning).
