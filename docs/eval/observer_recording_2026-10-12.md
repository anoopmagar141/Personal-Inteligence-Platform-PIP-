# Observer raw recording and unchanged-gate replay

Run date: 2026-10-12  
Code commit: `8bab19f`  
Model: `qwen2.5:7b` (`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`)  
Prompt hash: `9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139`

The recording contains all 37 labelled cases in each of three runs (111 case runs total), with no case errors and no missing raw responses. The raw file records the prompt hash, model digest, code commit and transcript token cap. Ollama's runtime context size is not configured or reported by PIP, so the stamp leaves it unknown.

| Run | Candidates | Survived grounding | Learned rows | TRUE / UNLABELLED / TRAP | Precision | Stated facts learned | Traps reaching belief table |
|---|---:|---:|---:|---|---:|---:|---:|
| 1 | 37 | 36 | 10 | 8 / 1 / 1 | 8/9 (89%) | 8/23 (35%) | 1/25 (4%) |
| 2 | 35 | 35 | 13 | 9 / 3 / 1 | 9/10 (90%) | 8/23 (35%) | 1/25 (4%) |
| 3 | 33 | 33 | 15 | 10 / 4 / 1 | 10/11 (91%) | 9/23 (39%) | 1/25 (4%) |
| Pooled | 105 | 104 | 38 | 27 / 8 / 3 | 27/30 (90%) | 25/69 (36%) | 3/75 (4%) |

The saved responses were replayed through the unchanged pipeline. The replay's complete per-case report matches the live report pasted by the owner for all funnel, learning, fact and trap results. Only elapsed-time values differ: replay does not call the model. The replay report is in `observer_raw_replay_2026-10-12.md`.

Recorded model-call time sums to 609.8 seconds across all cases. The stamp-to-record-file interval was 616.4 seconds (about 10 minutes 16 seconds), an approximate full-run wall-clock measure. This was much shorter than the four-hour estimate. No Observer prompt, evidence gate, Constitution or stages were changed as part of this measurement.

Files: `observer_raw_recording_2026-10-12.json` (raw outputs and stamp), `observer_raw_replay_2026-10-12.md` (all replay case details).
