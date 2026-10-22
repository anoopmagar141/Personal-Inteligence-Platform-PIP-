# References

- `references.html`: the report's one reference list, APA 6th edition, alphabetical, hanging indent, double spaced,
  for the end of the report. `references.md` is the same as text, with a hidden note of which chapters cite each.
- `make_reference_list.py` builds both from the 15 checked sources in `chapter2/make_references.py`, and checks the
  seven chapter drafts both ways: every in-text citation must have a reference, and every reference must be cited.
  It stops with a list of problems if either fails. Run it again after editing any chapter:
  `.venv/Scripts/python.exe -I notes/report/references/make_reference_list.py`

Result on 22 October 2026: 15 references, all cited (Chapter 1 cites 6 of them, Chapter 2 all 15; Chapters 3-7
cite none). Two optional sources are left out because no chapter cites them: Nepal's Privacy Act (named only in a
grey note in 2.2.4) and Cavoukian (2009, not verified). If you cite either, the script adds it.

While checking, one citation was corrected in Chapter 1: APA 6 puts a comma before "and" in a list of three or more
authors, so "Chhikara, Khant, Aryan, Singh, and Yadav (2025)".

## Before you submit

1. Chapter 2's own `references.html` was a draft for that chapter only; use this list instead, once, at the end of
   the report.
2. If you add a source, add it to `SOURCES` in `chapter2/make_references.py` (with how you checked it) and the name
   it is cited by to `NAMES` in `make_reference_list.py`, then run the script.
