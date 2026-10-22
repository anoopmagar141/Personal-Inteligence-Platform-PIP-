# Chapter 6 files

- `chapter6_draft.md`: the draft of Chapter 6 (Testing and Result Analysis), about 1,370 words of text plus three
  tables. Edit this one.
- `chapter6_draft.html`: the same draft laid out to the LUC guide, with all three tables in place, for opening in
  Word. Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter6/chapter6_draft.md`
- Table 6.1 (30 test cases) is built by `make_table.py`, and Table 6.2 (answer speed) by `make_speed_table.py`
  from `results/`. The chapter page includes them whole, so if you change one, run its script first, then rebuild
  the chapter. Table 6.3 (accuracy) is written in the draft itself.

Where the numbers come from (all in docs/FREEZE_LIST.md): the method §1-§5; the suites §7.74 (1,889 backend,
22 Oct) and §7.75 (372 Flutter); the validation pass §7.16; the migration re-run §7.24 and its fixes §7.26; the hard
stop §7.31; the real-window check §7.71 and D-47 §7.73; short chats §7.14, §7.37, §7.55, §7.64, §7.70; long chats
§7.70; the blind check §7.63, with D-40 and D-42 fixed in §7.67 and D-41 kept open in §7.72; document search §7.27,
§7.28, §7.68; the greeting §7.66; speed §7.74 and `results/`. The gate's 1-in-15 held-out cost is in
docs/ARCHITECTURE.md ("The evidence gate is an allowlist").

## Before you submit

1. Read Table 6.3 against Chapter 1 (1.5 and 1.6): both quote 0 of 81, 0 of 162, 8 of 58 and 2 of 54. If a number
   changes, change both.
2. The blind check had one grader, a separate AI session. Say so if your examiner asks; your supervisor may want you
   to grade a sample yourself.
3. If you run the suites again before submitting, update the counts in 6.5 and in Table 6.1's note
   (`make_table.py`), and in Chapter 3.
4. Word count: Chapters 1-6 are now about 9,450 words, which leaves about 550 for Chapter 7. Trim earlier
   chapters if Chapter 7 needs more (see the Chapter 5 README for where).
