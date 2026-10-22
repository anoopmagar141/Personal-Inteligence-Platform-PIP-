# Chapter 3 files

- `chapter3_draft.md`: the draft of Chapter 3 (Methodology), about 1,080 words of text plus five tables (the
  guide does not count tables in the 10,000-word limit). Edit this one.
- `chapter3_draft.html`: the same draft laid out to the LUC guide, for opening in Word. Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter3/chapter3_draft.md`
- Figure 3.1 (system architecture) is `notes/report/diagrams/png/fig3-1_system_architecture.png`; the HTML shows
  it in place in 3.5.

Where the facts come from: the phases and dates from the git history; the method from docs/FREEZE_LIST.md §1-§5;
the requirements from backend/api/server.py's routes and the app's screens; the versions from the project's
virtual environment, pubspec.yaml and `flutter --version` (22 October 2026); the GPU figures from Ollama's
/api/ps and FREEZE_LIST §7.56; the architecture from docs/ARCHITECTURE.md.

## Before you submit

1. One honest gap is written into FR-09 and 3.5: the backend can use a cloud model with consent, but this
   version of the app has no screen for adding one (the endpoint route was never merged). Keep that wording, or
   add the screen before you submit.
2. If you upgrade a package or Ollama, update Table 3.4, and re-run the speed measurement so Chapter 6 matches.
3. The commit count (329, at ccf9d0b) and the test counts (1,914 backend at b7759c3, 372 Flutter) are as of 22
   October 2026; update
   them at the end.
4. Ask your supervisor whether the phase table (3.1) should become a Gantt chart; the dates are all here.
