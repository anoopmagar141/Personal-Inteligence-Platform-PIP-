# Chapter 1 files

- `chapter1_draft.md`: the draft of Chapter 1 (Introduction), about 1,620 words. Edit this one.
- `chapter1_draft.html`: the same draft laid out to the LUC guide, for opening in Word. Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter1/chapter1_draft.md`

Every fact about PIP in the draft comes from the project's own records: the nine promises and their evidence
in docs/FREEZE_LIST.md (§4, §7.63, §7.68, §7.70, §7.74, §8.2), docs/ARCHITECTURE.md, AGENTS.md, and the speed
measurement in notes/report/chapter6. The sources it cites are in notes/report/chapter2/references.html.

## Before you submit

1. Check the objectives with your supervisor. The six specific objectives are the project's nine promises,
   grouped; Chapter 6 should show a result for each one.
2. If your numbers change before submission (a new run, a fixed defect), update 1.5 and 1.6 too: they quote
   the time to the first word (4.5 s to 0.4 s), 0 of 81, 0 of 162, 8 of 58 and 2 of 54.
3. Limitation 8 names two open defects: D-41 and D-51 (partly fixed in ff916d7: told that nothing is saved during a
   chat, the model's claims to have saved a stated fact fell from 9 to 5 of 24 in a test, not to 0; FREEZE_LIST
   §7.76). Remove a defect from it if it is fixed before you submit.
4. Word count: Chapters 1 and 2 together are about 3,800 words of the 10,000-word limit. Chapter 1 can lose
   about 300 words from 1.4 (the feature list) if you need room.
