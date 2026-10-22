# Front pages

- `front_matter_draft.md`: the executive summary (249 words), the acknowledgements and the list of abbreviations
  (31 entries, every abbreviation the seven chapters use). Edit this one.
- `front_matter_draft.html`: the same, laid out to the LUC guide for Word, each title starting a new page.
  Rebuild it after editing:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/front/front_matter_draft.md`

The summary's numbers are the report's own: 1,889 and 372 tests (Chapter 6), 237 trick statements (75 short + 162
long), 0 of 81, 8 of 58 (Table 6.3), 4.48 s to 0.36 s (Table 6.2). The abbreviations were collected from the seven
chapter drafts, outside code listings, on 22 October 2026.

## Before you submit

1. Deal with the grey [Check: ...] notes: the supervisor's name and title, your programme and faculty, the names
   you want to thank, and whether a Malay abstract and keywords are needed.
2. Ask your supervisor whether you must state how AI tools were used in the project and the report. If so, add one
   honest sentence; the note in the acknowledgements marks the place.
3. Still to make in Word, not here: the outer and inner title pages, the recommendation and certification pages
   (from the resource centre), the declaration of authenticity, the table of contents, and the lists of tables and
   figures (Word builds these from the captions).
4. If a chapter adds a new abbreviation, add it to the list (it is in alphabetical order).
5. The executive summary does not count towards the 10,000 words of the chapters, but check with your supervisor.
