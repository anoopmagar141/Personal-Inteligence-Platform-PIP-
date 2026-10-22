# Chapter 4 files

- `chapter4_draft.md`: the draft of Chapter 4 (System Design), about 1,650 words of text plus Table 4.1 (17 use
  cases) and Figures 4.1-4.12 (the guide does not count tables and figures in the 10,000-word limit). Edit this one.
- `chapter4_draft.html`: the same draft laid out to the LUC guide, with each figure in place and its caption under
  it, for opening in Word. Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter4/chapter4_draft.md`
  The pictures come from `notes/report/diagrams/png/`, so keep the folders where they are, or Word shows empty
  boxes. In Word, check that each picture is saved inside the document (File > Info > Edit Links to Files >
  "Save picture in document"), not only linked.

Where the facts come from: the figures and their README in `notes/report/diagrams/`; the tables, keys and triggers
from backend/core/schema.sql and backend/memory/profile_store.py; the classes and imports from backend/; the
sign-in and chat steps from backend/api/server.py, backend/core/pipeline.py and session_key.py; the screens from
frontend/flutter/lib/ (home_shell.dart, providers_view.dart, profile_view.dart, reasoning_strip.dart) and its
tests (theme_test.dart for contrast, control_labels_test.dart for screen-reader names).

## Before you submit

1. Figures 4.13 (a chat in the dark theme) and 4.14 (the delete-profile dialog) are screenshots, taken on 22
   October 2026 in a throwaway copy (see `notes/report/screenshots/README.md`); the other screens are in 5.6.
2. If you change a diagram, re-run `notes/report/diagrams/make_diagrams.py` and `render.ps1`, then rebuild this
   HTML so the pictures and the text match.
3. Word count: Chapters 1-4 are now about 6,500 words, leaving about 3,500 for Chapters 5-7. If you need room,
   4.5 can lose about 200 words, because the figures show the same steps.
4. Figures go with the chapter; ask your supervisor whether the large ones (4.3, 4.7, 4.12) should be printed
   landscape or split.
