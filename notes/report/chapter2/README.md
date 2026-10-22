# Chapter 2 files

- `chapter2_draft.md`: the draft of Chapter 2 (Literature Review), about 2,160 words. Edit this one.
- `chapter2_draft.html`: the same draft laid out to the LUC guide (Times New Roman 12, double spacing, title
  rules), for opening in Word. Rebuild it after editing the Markdown:
  `.venv/Scripts/python.exe -I notes/report/make_chapter_html.py notes/report/chapter2/chapter2_draft.md`
- `references.html`: the APA 6 reference list for the chapter. `sources.md`: each source, how it was checked,
  and how it fits PIP.

## Before you submit

1. Read each source's abstract and conclusion, and check that the draft describes it fairly. Every number in
   the draft (65 hours to 5 seconds, 99% at half the size, 25 agents, 18 trillion tokens, one million examples)
   is from the source's own abstract.
2. Check the research-gap sentence in 2.4 against each of the four memory papers. It says none of them is
   described as checking the user's own words with a fixed rule, asking before sensitive facts are stored, or
   keeping a record of each decision. If a paper does one of these, soften the sentence.
3. Delete the two grey [Check: ...] notes once you have dealt with them.
4. Ask your supervisor whether to add a local law to 2.2.4 (Nepal's Privacy Act, 2075 (2018), is in
   sources.md, checked on the Asian Development Bank's law database).
5. The whole report should stay under 10,000 words; this chapter uses about a fifth. Trim 2.2.2 or 2.2.5 first
   if you need room.
6. The merged reference list for the whole report is `notes/report/references/references.html` (built and
   checked against all seven chapters by `make_reference_list.py`). Use that one at the end of the report, not
   this chapter's `references.html`.
