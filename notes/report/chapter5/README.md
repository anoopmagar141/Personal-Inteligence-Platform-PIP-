# Chapter 5 files

- `chapter5_draft.md`: the draft of Chapter 5 (System Implementation), about 1,540 words of text plus Tables
  5.1-5.2, Listings 5.1-5.4 (real code) and Algorithms 5.1-5.3 (pseudocode). Edit this one.
- `chapter5_draft.html`: the same draft laid out to the LUC guide, for opening in Word. Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter5/chapter5_draft.md`

Where the facts come from: line counts from `git ls-files` at commit ccf9d0b (22 October 2026, comments
included); the code in the listings copied from the files named at the top of each listing (every line was
checked to be in its file); the algorithms from pipeline.py, evidence_gate.py, constitution_enforcer.py,
stage_13_profile_update.py and constitutional.json; the settings from backend/config/settings.json; the security
measures from docs/ARCHITECTURE.md and the code it names; the kept limits from docs/FREEZE_LIST.md Promise 7.

## Before you submit

1. The 11 screenshots for 5.6 are taken (22 October 2026, a throwaway copy with a made-up profile; see
   `notes/report/screenshots/README.md`) and placed. To replace one, save the new picture under the same name in
   `notes/report/screenshots/` and rebuild the HTML.
2. Ask your supervisor whether code listings and pseudocode count towards the 10,000 words. The count above leaves
   them out, like tables and figures. If they count, move Listings 5.1-5.4 to an appendix.
3. Word count: Chapters 1-5 are now about 8,100 words, which leaves about 1,900 for Chapters 6 and 7. That is
   tight. Places to trim if needed: Chapter 2 sections 2.2.2 or 2.2.5 (about 300 words), Chapter 4 section 4.5
   (about 200), and in this chapter the frontend text in 5.2 (about 150).
4. The limits paragraph at the end of 5.3.2 must match Chapter 1's limitation 6. If either changes, change both.
5. If the code changes before you submit, re-check the listings against their files and update the commit and the
   line counts in 5.1.
