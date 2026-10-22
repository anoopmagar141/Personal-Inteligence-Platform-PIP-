# PIP final year report: what we have, what is missing

Made 2026-10-21 from the repo at commit 1902c5e. It follows your college's 7-chapter outline
(the scanned 3 pages). Each section says:

- **Status:** READY (material exists, you only need to write it as report text),
  PARTLY (some material, a gap to fill), or MISSING (nothing in the repo yet).
- **Have:** where the material is.
- **Missing:** what you still need to make or write.

Remember the limit: about 10,000 words, 50-100 pages. PIP has far more material than that,
so most of the work is choosing and cutting, not finding.

---

## Short answer

| Chapter | Status | Biggest gap |
|---|---|---|
| 1 Introduction | DRAFTED (2026-10-22) | Draft in notes/report/chapter1/ (about 1,620 words); check the objectives with your supervisor |
| 2 Literature review | DRAFTED (2026-10-22) | Draft in notes/report/chapter2/ (about 2,160 words); read the sources and edit |
| 3 Methodology | DRAFTED (2026-10-22) | Draft in notes/report/chapter3/ (1,080 words + 5 tables) |
| 4 System design | DRAFTED (2026-10-22) | Draft in notes/report/chapter4/ (about 1,670 words + Table 4.1 + Figures 4.1-4.14, two of them screenshots) |
| 5 Implementation | DRAFTED (2026-10-22) | Draft in notes/report/chapter5/ (about 1,560 words + 2 tables, 4 listings, 3 algorithms, 11 screenshots) |
| 6 Testing and results | DRAFTED (2026-10-22) | Draft in notes/report/chapter6/ (about 1,370 words + Tables 6.1-6.3); about 550 words left for Chapter 7 |
| 7 Conclusion | DRAFTED (2026-10-22) | Draft in notes/report/chapter7/ (about 460 words + Table 7.1); all 7 chapters about 9,910 words |

Strongest chapters: 3, 5, 6, 7. Weakest: 2 (literature) and 4 (diagrams), then screenshots.

---

## Front pages

| Item | Status | Note |
|---|---|---|
| Outer and inner title page | MISSING | Name, student ID, programme, faculty, month/year |
| Recommendation, Certification | MISSING | Get them from the resource center |
| Declaration of Authenticity | MISSING | Signed and dated |
| Acknowledgements | DRAFTED (2026-10-22) | notes/report/front/; fill in the grey notes (names, programme, AI-use statement if required) |
| Table of contents, lists of figures/tables, abbreviations | PARTLY | Abbreviations DRAFTED 2026-10-22 (31, from the chapters, notes/report/front/); contents and lists: make in Word at the end |
| Executive Summary (150-250 words) | DRAFTED (2026-10-22) | 249 words, notes/report/front/; ask about a Malay version and keywords |

---

## Chapter 1: Introduction

**1.1 Background of the study** - DRAFTED 2026-10-22 (`notes/report/chapter1/chapter1_draft.md`)
- Have: what PIP is, in `AGENTS.md` (first paragraph): a local-first desktop assistant that runs its
  own model, keeps chat, memory, documents and decisions in an encrypted database on your machine,
  and controls what it learns about you through a rule-based "Constitution".
- Missing: a written background about AI assistants that remember users, and the privacy problem
  when that memory lives in the cloud. Needs 3-5 citations (from Chapter 2).

**1.2 Problem statement** - DRAFTED
- Have: two raw points. `docs/FREEZE_LIST.md` §1: the costly bugs "failed silently" (for example,
  encryption that was built but never given a key). §9.1: the part that learns about the user was
  "claimed but unmeasured".
- Missing: one clear paragraph. Suggested shape: (1) assistants that learn about you send your
  data away, (2) they can learn wrong things about you, (3) you cannot see or check why they
  believe something about you.

**1.3 Objectives (general and specific)** - DRAFTED (one general, six specific)
- Have: the nine promises in `docs/FREEZE_LIST.md` §4. Each can become one specific objective:
  1. The Observer writes memory only through the checks.
  2. It cannot change your name, language or timezone.
  3. Some fields need your confirmation first.
  4. A stored memory is supported by your own words.
  5. The Observer runs only on a local model.
  6. Nothing leaves the machine without your recorded consent.
  7. Data is encrypted at rest.
  8. One profile cannot see another profile's data.
  9. Answers about you use your current record.
- Missing: a one-sentence general objective. Suggestion: "Build a local-first personal assistant
  that learns about its user only through an auditable rule-based gate, and measure how well
  that gate works."

**1.4 Scope of the study** - DRAFTED
- Have, spread around the docs: Windows desktop only; one machine; local Ollama with qwen2.5:7b;
  tested on an 8 GB GPU; English chats; Flutter app; optional cloud model only with consent.
- Missing: one short list, plus what is out of scope (mobile, sync between devices, a server
  with many users, document search quality).

**1.5 Significance of the study** - DRAFTED
- Write from the contribution statement the owner confirmed (BLUEPRINT DEC-5): "an auditable
  enforcement mechanism", meaning every learning decision leaves a record (`governance_audit_log`).

**1.6 Limitations** - DRAFTED (eight, each with its number)
- `docs/FREEZE_LIST.md` §7.68 (document search finds the answer for 2 of 54 questions),
  §7.70 (long chats learn 0 of 81 true facts), and the "Limitation" lines under each promise in §4
  (for example: locality is reported by whoever set up the model, not checked by PIP; one backend
  process serves every profile).

**1.7 Organization of the report** - DRAFTED

---

## Chapter 2: Literature review

Sources: FOUND AND CHECKED (2026-10-22). Text: DRAFTED 2026-10-22 in `notes/report/chapter2/chapter2_draft.md`
(and `.html` for Word; about 2,160 words; checklist in that folder's README) for you to edit.
`notes/report/chapter2/sources.md` (each source: APA 6 reference, how it was checked, what it is,
how it fits PIP, grouped by sub-section, plus a draft of the research gap) and
`notes/report/chapter2/references.html` (the reference list, alphabetical, hanging indent, for Word).
15 core sources, each checked against its own record (Crossref DOI, arXiv, NeurIPS BibTeX, ACL
Anthology, NIST, EUR-Lex), and 2 optional: the Nepal Privacy Act 2018 (checked on ADB's law
database) and Cavoukian's Privacy by Design (NOT verified: ipc.on.ca refused access; check its dates
yourself before citing).

**2.1 Introduction** - DRAFTED

**2.2 Review of related works** - DRAFTED (with Table 2.1)
- 2.2.1 Memory for LLM assistants: Packer et al. 2023 (MemGPT), Park et al. 2023 (Generative
  Agents), Zhong et al. 2024 (MemoryBank), Chhikara et al. 2025 (Mem0), Zhang et al. 2024 (survey).
- 2.2.2 Retrieval and embeddings: Lewis et al. 2020 (RAG), Reimers & Gurevych 2019 (SBERT),
  Wang et al. 2020 (MiniLM), Liu et al. 2024 (Lost in the middle).
- 2.2.3 Trust and safety: Ji et al. 2023 (hallucination), Bai et al. 2022 (Constitutional AI;
  explain PIP's Constitution is a rule file checked by code, not training), Greshake et al. 2023
  (indirect prompt injection).
- 2.2.4 Privacy and security: Turan et al. 2010 (NIST SP 800-132, PBKDF2), GDPR 2016 Art. 25.
- 2.2.5 The model: Qwen Team 2024 (Qwen2.5).

**2.3 Theoretical framework** - DRAFTED (RAG; grounding vs. support; data protection by design)
- Have: the ideas PIP is built on, in `docs/FREEZE_LIST.md` §1-§5 (fail closed, evidence
  hierarchy, "a guard nobody has watched fail is not a guard") and `docs/ARCHITECTURE.md`
  (grounding vs. support: a quote being said is not the same as it supporting the claim).
- Link them to the sources: Ji et al. 2023 (grounding vs. support), GDPR Art. 25 (by design and by
  default), Turan et al. 2010 (key derivation), Lewis et al. 2020 (retrieval).

**2.4 Research gap** - DRAFTED
- A draft paragraph is at the end of `notes/report/chapter2/sources.md`: the memory systems let
  the model decide what to remember; none checks the user's words with a fixed rule, asks before
  sensitive writes, or keeps an append-only record of each decision. Check it against each paper
  as you read it.

**2.5 Summary** - DRAFTED

---

## Chapter 3: Methodology

**3.1 Research/Development method** - DRAFTED 2026-10-22 (with Table 3.1, phases)
- `docs/FREEZE_LIST.md` §2: decide before building (write the promise, name the mechanism, name
  what "broken" looks like), test first, break the guard once by hand to prove the test catches
  it, smallest change, one commit per promise.
- Timeline from git (318 commits): started 2026-07-03; Phase 1 "Constitutional Core" 2026-07-04;
  Phase 6 RAG 2026-08-16; Phases 7-8 Observer, 14-stage pipeline, WebSocket and Flutter client
  2026-08-17/18; reliability freeze and evidence tracks from 2026-09-26; thesis measurements
  October. Good for a Gantt chart (MISSING: the chart itself).

**3.2 System Requirement Specification** - DRAFTED (Table 3.2: FR-01..FR-12; Table 3.3: NFRs)
- Functional: have the features, missing a numbered list (FR-01, FR-02 ...). Features: sign in to a
  password-protected profile; chat with streamed answers; memory of the user (skills, preferences,
  goals, projects); a review queue to confirm or reject what PIP learned; decisions; projects;
  documents with search; web search only after a click; choose a local or cloud model with
  consent; backup, restore and first-run import; a per-chat "where we left off" record; a trace
  view of the pipeline.
- Non-functional: READY. The nine promises (privacy, security, correctness) plus: answers stream
  token by token, a chat turn always ends with done or error, the 16k window fits on an 8 GB GPU.

**3.3 Tools and technologies used** - DRAFTED (Table 3.4, exact versions)
- `AGENTS.md` "Stack": Python, FastAPI, uvicorn; Flutter (Dart) for Windows; SQLite with SQLCipher;
  ChromaDB; Ollama with qwen2.5:7b; all-MiniLM-L6-v2 embeddings; DuckDuckGo search (ddgs);
  PBKDF2-HMAC-SHA512 with 256,000 iterations; pytest; Inno Setup installer; Git.

**3.4 Feasibility study** - DRAFTED (Table 3.5)
- Technical: runs on a normal PC; 6.6-6.8 GB of an 8 GB GPU in use (§7.56).
- Economic: every tool is free or open source; no cloud bill.
- Operational: Windows installer that needs no admin rights (`ARCHITECTURE.md`).
- Missing: write these three as a section, maybe as a table.

**3.5 System architecture** - DRAFTED (text for Figure 3.1)
- Have: `docs/ARCHITECTURE.md` "Layers" (transport, orchestration, persistence, providers) and
  "Data flow" (the 14 stages).
- Drawn 2026-10-21: Figure 3.1 in `notes/report/diagrams/png/`.

---

## Chapter 4: System design

Drawn 2026-10-21/22 in `notes/report/diagrams/` (captions and sources in its README): Figures 4.1-4.12.
Text drafted 2026-10-22 in `notes/report/chapter4/` (4.1-4.6, Table 4.1 of 17 use cases, the figures
placed in the HTML). Still missing: the UI/UX screenshots (4.6).

**4.1 Use case diagram and description** - DRAFTED (Figure 4.1, Table 4.1)
- Actors: User, local model (Ollama), cloud model (optional), web search.
- Use cases: create profile and sign in, chat, review what PIP learned, manage projects,
  decisions, documents, providers and consent, backup and restore.

**4.2 DFD (Level 0, 1, 2)** - DRAWN (Figures 4.2-4.5)
- Level 0: User <-> PIP <-> local model / web search / cloud model.
- Level 1: chat path, REST path, session-end path (`ARCHITECTURE.md` "Data flow").
- Level 2: the 14 stages of one message, and the session-end learning path
  (Observer -> evidence gate -> Constitution -> write / ask / reject).

**4.3 ER diagram and database schema** - DRAWN (Figures 4.6-4.7)
- `backend/core/schema.sql` has 33 tables. Draw only the main ones: identity, conversations,
  messages, chat_records, skill_memory, preference_memory, goal_memory, active_projects,
  decision_log, memory_candidates_pending, documents, provider_consent, governance_audit_log,
  trace_log.

**4.4 Class diagram** - DRAWN 2026-10-22 (Figure 4.8 package diagram from the real imports;
  Figure 4.9 class diagram of every class in backend/)
- Say in one sentence why there are few classes: PIP is mostly module-level functions (one run()
  per stage, store functions taking the connection first).

**4.5 Sequence / activity diagrams** - DRAWN (Figures 4.10-4.12; renumbered 2026-10-22)
- Sequence: one chat message (app -> WebSocket -> pipeline -> model -> tokens back).
- Sequence: sign in (password -> key -> database opens).
- Activity: a memory candidate going through the two gates.

**4.6 UI/UX design** - DRAFTED (five design rules; Figures 4.13-4.14 screenshots, 2026-10-22)
- 12 screens in `frontend/flutter/lib/screens/` (sign in, chat, profile, projects, decisions,
  documents, review, providers, model setup, model browser, backup, trace), plus onboarding and
  the chat record dialog. Need screenshots or wireframes.

---

## Chapter 5: System implementation

Text drafted 2026-10-22 in `notes/report/chapter5/`: 5.1-5.5 written (Table 5.1 modules with line counts, Table
5.2 security measures, Listings 5.1-5.4 from the real code, Algorithms 5.1-5.3 pseudocode); 5.6 has 11 screenshot
placeholders that turn into pictures once saved in `notes/report/screenshots/`.

**5.1 Module description** - DRAFTED
- `AGENTS.md` "Where things are" and `docs/ARCHITECTURE.md`.

**5.2 Frontend implementation** - DRAFTED
- Have: the Flutter app (plain setState, `api_client.dart` for REST, `ws_chat_client.dart` for chat).
- Missing: a short write-up of the main screens.

**5.3 Backend implementation** - DRAFTED (with 5.3.2 security)
- FastAPI with 68 REST routes, one WebSocket `/ws/chat`, the 14 stages in `backend/stages/`, the
  orchestrator `backend/core/pipeline.py`, middleware order (`ARCHITECTURE.md`).

**5.4 Database implementation** - DRAFTED
- SQLCipher (encrypted SQLite), raw SQL, 33 tables; ChromaDB for vectors, chunk text encrypted;
  append-only audit table (triggers block UPDATE and DELETE).

**5.5 Algorithms used** - DRAFTED (pseudocode for the pipeline, evidence gate, Constitution)
- The 14-stage message pipeline.
- The evidence gate: accepts a memory only when your own words carry a known support phrase;
  unknown wording is rejected (an "allowlist").
- The Constitution's thresholds (how many chats before a fact is trusted).
- Password to key: PBKDF2-HMAC-SHA512, 256,000 iterations.
- Answer cache key: profile session, model, day and a record version, so an old answer is never
  served after your data changes.
- Document search: embedding and a similarity cut-off of 0.60.
- Audit row: HMAC fingerprint, never the text.

**5.6 Screenshots of system features** - DONE 2026-10-22 (11 screenshots from a throwaway copy, made-up profile; notes/report/screenshots/)
- None in the repo (only the logo). The V-1 real-window check was done on 2026-10-21 (§7.71) in a
  throwaway copy, but it kept no screenshots for the report. Run the app once and capture each screen;
  that covers 4.6 and 5.6.

---

## Chapter 6: Testing and result analysis

This is PIP's strongest chapter. Text drafted 2026-10-22 in `notes/report/chapter6/`: 6.1-6.6 written,
Table 6.1 (30 test cases) and Table 6.2 (speed) placed whole, Table 6.3 (accuracy) new.

**6.1 Test plan** - DRAFTED
- `docs/FREEZE_LIST.md` §2 (method), §5 (evidence hierarchy), §4 (one test per promise, each
  seen failing on purpose first).

**6.2 Test cases (table format)** - READY (2026-10-21)
- Table 6.1 in `notes/report/chapter6/` (HTML for Word, Markdown copy, and `make_table.py` that writes
  both): 30 real tests (8 unit, 19 integration, 3 Flutter UI), covering all nine promises and the main
  fixes. All re-run on 2026-10-21: 27 backend tests from a clean export of 6a51798 (47 cases, 47 passed)
  and 3 Flutter tests (3 passed).

**6.3 Unit testing** - DRAFTED
- pytest, one file per module (`backend/tests/`); Flutter widget tests.

**6.4 Integration testing** - DRAFTED
- Tests through the real routes and real pipeline: profile boundary, consent before sending,
  Observer governance. The migration re-run: 307 checks through the real export and restore
  scripts (§7.24).

**6.5 System testing** - DRAFTED
- Product-wide validation pass (§7.16, `docs/eval/reliability_validation_2026-10-01.md`).
- Last full backend run: 1,881 passed, 0 failed (§7.72). Flutter: 352 passed (§7.69).
- V-1, the real app window (§7.71, 2026-10-21): first-run import, the web-search button, the record
  dialog and the turn end worked; a backend restart set off a reconnect storm in the app (D-47, open).

**6.6 Performance evaluation** - DRAFTED (6.6.1 speed, Table 6.2; 6.6.2 accuracy, Table 6.3)
- Accuracy results (READY, the core of the thesis):
  - Learning on 37 short chats: 88-90% of learned memories true (§7.14).
  - After the gate change: 0 of 75 trick statements learned; 36 of 36 learned rows true;
    35-49 of 69 true facts learned on short chats (§7.37, §7.55, §7.64, summed up in §7.70).
  - Long chats: 0 of 162 tricks written, but 0 of 81 true facts learned (§7.70, a limitation).
  - Blind check of the gate: 8 of 58 accepted quotes did not support their claim, 14%
    (§7.63). The next check (the Constitution) asked you about 4, threw away 3 and stored 1.
  - Document search: right passage found for 2 of 54 questions (§7.27, a limitation).
  - New-user greeting: 0 of 104 "no record" replies (§7.66).
- Speed: READY (2026-10-22). Table 6.2 in `notes/report/chapter6/` (HTML + Markdown, built by
  `make_speed_table.py` from `results/`; measured by `measure_speed.py`, 0 of 56 runs failed), before
  and after the D-50 fix: the first word took a median 4.48 s before (PIP called Ollama at "localhost",
  which resolves to IPv6 ::1 first, so each request waited 2.04 s, twice per message) and 0.36 s after
  (127.0.0.1). Writing speed about 46 tokens/s; cold start 9.0 s -> 5.0 s to the first word (model load
  4.3 s); a cached answer 0.01 s. Other numbers: one learning pass takes about 130 s; restart after a hard
  stop 1.8 s (§7.31); the key takes about 0.25 s to derive.
- Good material for 6.6 and 7.2: the measurement found a real defect (D-50, FREEZE_LIST §7.74), the fix
  was tested first, and the table shows the before/after.

---

## Chapter 7: Conclusion and recommendations

Text drafted 2026-10-22 in `notes/report/chapter7/`: 7.1-7.4 written, Table 7.1 gives each promise's status.

**7.1 Summary** - DRAFTED

**7.2 Conclusion** - DRAFTED (Table 7.1)
- Which promises hold (`docs/FREEZE_LIST.md` §4 and §8.2), and what the numbers mean.

**7.3 Limitations** - DRAFTED (points back to 1.6)
- §7.68 document search, §7.70 long chats, M-1(a)'s 14%, open defects (D-41 and D-47 on
  2026-10-21; D-46, D-30, D-29 were fixed that day; re-check `docs/FREEZE_LIST.md` §8.2 when you write),
  locality taken on trust, one process for all profiles, uploaded files kept unencrypted on disk.

**7.4 Future enhancements** - DRAFTED (only recorded future work, privacy first)
- `docs/BLUEPRINT.md`: smaller document chunks and a re-measured cut-off; better learning from
  long chats; context window above 16k; the items cut below the line (#15-#18).

---

## References and appendices

- References (APA): DONE 2026-10-22, one merged list in `notes/report/references/` (15 sources, checked both ways against all seven chapters by `make_reference_list.py`).
- Appendices: READY material. Pick: the Constitution file (`backend/core/constitutional.json`),
  the schema, a few eval result tables from `docs/eval/`, an installation guide.

---

## What to make, in order

1. Literature: DONE 2026-10-22, 15 sources checked and Chapter 2 drafted; read the sources and edit the draft.
2. Diagrams: DONE 2026-10-22, all 13 figures (`notes/report/diagrams/`).
3. Screenshots: DONE 2026-10-22, 13 pictures in `notes/report/screenshots/` (README says how).
4. Test-case table: DONE 2026-10-21 (Table 6.1, `notes/report/chapter6/`).
5. Small tables: feasibility, answer speed, Gantt chart.
6. Then write, chapter by chapter, keeping to about 10,000 words.

Note: the code cites a master specification ("Part N.N", "ADR-0NN") that is not in the repo.
If you still have it, it probably has more material for 1.2, 3.2 and 4.
