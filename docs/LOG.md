# Log

<!-- Newest first. Prepend new entries directly under the format line. -->

Format:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

- [2026-10-01] claude · Made first-password setup and change-password refuse a password under the backend's 8-character minimum before the round trip, through one kMinPasswordLength (counted in code points, as Python's len() does) that restore now shares and a test holds to the backend's own numbers · why: only restore checked locally, so the other two paid a key derivation or a full re-encryption to be told · files: frontend/flutter/lib/api_client.dart, frontend/flutter/lib/screens/sign_in_screen.dart, frontend/flutter/lib/screens/profile_view.dart, frontend/flutter/lib/screens/backup_view.dart, frontend/flutter/test/password_rule_test.dart, frontend/flutter/test/sign_in_screen_test.dart, frontend/flutter/test/profile_management_test.dart, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-10-01] claude · Gave the Windows window a minimum client size of 800x640 logical (WM_GETMINMAXINFO, DPI-scaled, clamped to the work area), defined once in flutter_window.h and read from there by a layout test of every tab; tool/check_min_window.py confirms the release build holds it · why: the window could be dragged to a sliver and the sidebar and four screens overflowed below 800x615 · files: frontend/flutter/windows/runner/flutter_window.h, frontend/flutter/windows/runner/flutter_window.cpp, frontend/flutter/test/minimum_window_test.dart, frontend/flutter/tool/check_min_window.py, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-10-01] claude · Gave every icon-only control a name a screen reader can read (send/stop, delete conversation, sidebar toggle, collapsed sidebar items) and narrowed the collapsed sidebar header's padding, which clipped the toggle by 2px · why: the audit found no Semantics in lib/ and 13 tappables announced only as 'button' · files: frontend/flutter/lib/home_shell.dart, frontend/flutter/lib/screens/chat_view.dart, frontend/flutter/test/control_labels_test.dart, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-10-01] claude · Raised every text colour to WCAG AA (4.5:1) on every surface in both palettes and on the sign-in stage: light muted #5A5F6E, light faint #676C7C, dark faint #858A9A, sign-in faint #7B8195; theme_test now holds faint to the body-text bar and covers surfaceRaised and the gateway palette · why: faint was 2.86-3.87:1 on 11-13px text, passing a 3:1 large-text bar it was never eligible for · files: frontend/flutter/lib/theme.dart, frontend/flutter/lib/widgets/gateway_flow.dart, frontend/flutter/test/theme_test.dart, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-10-01] claude · Audited the Flutter client against the applicable half of a web launch checklist, read-only, no code changed: textFaint fails WCAG AA in both themes (2.86-3.82:1, ~59 uses) and kGatewayTextFaint on the sign-in fields (3.23-3.87:1); no Semantics anywhere, send/stop, delete-chat, sidebar toggle and collapsed nav items are unlabelled icons; client password checks skip the backend's 8-char minimum on setup and change-password; outbound traffic is loopback or HTTPS, and no route stores a remote provider endpoint yet; no minimum window size, and a temporary Segoe-UI widget probe (deleted) found the sidebar overflowing at 800x600 and four screens overflowing at 640x480 and below; startup could not be timed because Windows Application Control blocks torch's DLL in this shell · why: the owner asked for the audit before any authorized fixes · files: docs/LOG.md

- [2026-09-28] claude · Checked the agent-context layer against the code and corrected the drift: a renamed widget (thinking_orb → thinking_mark), six stale line citations, stale test/fixture counts, a deleted file still listed as tracked, the claim that only backend/memory imports the DB drivers (backend/core/restore.py does too), and the Ollama 'client' that is really urllib over HTTP with the `ollama` package unimported · why: the docs are read as ground truth before every task · files: AGENTS.md, docs/ARCHITECTURE.md, docs/CONVENTIONS.md, docs/LOG.md

- [2026-09-28] claude · Ran the end-to-end Observer measurement (37 conversations, 3 runs, qwen2.5:7b) and recorded it in FREEZE_LIST §7.14 with the raw report in docs/eval/: memory precision 88-90% (the one false memory is sarcasm, every run), recall 30-39% (lost mostly at the evidence gate), and decisions auto-logged with overstatements · why: the thesis had only been measured at the gate · files: docs/eval/observer_end_to_end_2026-09-28.md, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Added a labelled conversation set and an end-to-end Observer measurement script (real local model through grounding, the evidence gate, the Constitution and Stage 13), committed before the first full run so the labels cannot be tuned to results · why: the council found the thesis measured only at the gate, never end to end · files: backend/tests/observer_cases.py, scripts/eval_observer_end_to_end.py, docs/LOG.md

- [2026-09-28] claude · Added end-to-end tests for Promises 1-3 through the real session-end path and recorded them in FREEZE_LIST §7.13: all three hold, each break-it seen failing, plus two findings (decision candidates bypass the evidence gate; immutable field names can be shadowed in preference_memory) · why: the graded governance layer had no tests for its own promises · files: backend/tests/test_observer_governance.py, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Brought the FREEZE_LIST §8.2 status table up to date with the fixes and wording that landed after each track reported, and marked Track 1 finding 3 resolved · why: the table still listed the Promise 5 wording as open and did not say 2, 4a or 4b had been fixed · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Applied the decided promise wording: Promise 5 names both locality records and the queue-until-later-start behaviour, Promise 7 gets its final key clause and states the unencrypted upload copy as a limitation, Promises 8 (profile isolation) and 9 (current record) are adopted, and AGENTS.md's Current focus no longer ties the freeze to the tracks being classified · why: owner decision on §7.7 item 5 · files: docs/FREEZE_LIST.md, AGENTS.md, docs/LOG.md

- [2026-09-28] claude · Recorded the lock identity fix in FREEZE_LIST §7.12, including the two decisions taken during it (the launcher asks holder() through Python; every int() parser moved with the format) · why: the freeze doc is the canonical record of what is enforced · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Made the instance lock record the holder's creation time beside its PID and made every gate (backend, launcher, restore, merge, demo seed) ask instance_lock.holder(), so a reused PID no longer reads as PIP running · why: a lock naming a live non-PIP process blocked all of them (FREEZE_LIST §7.4) · files: backend/core/instance_lock.py, scripts/launch_pip.ps1, scripts/restore_backup.py, scripts/merge_projects.py, scripts/seed_demo_conversation.py, backend/tests/test_lock_identity.py, backend/tests/test_instance_lock.py, backend/tests/test_api_server.py, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-28] claude · Recorded the lost-learning fix in FREEZE_LIST §7.11, marked §7.2 finding 1 fixed, and corrected the doc's status line, which still said no production code had changed under the freeze · why: claims match mechanisms (§2.3) · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Made the startup drain keep a session the Observer refused for want of a local provider queued for a later start, instead of filing it as terminally failed · why: Promise 5's queue-for-next-launch held for one launch only, so such a session was never learned from (FREEZE_LIST §7.2 finding 1) · files: backend/core/session_lifecycle.py, backend/stages/stage_11_observer.py, backend/tests/test_observer_provider_authorization.py, docs/LOG.md

- [2026-09-28] claude · Recorded the answers-about-the-user fixes in FREEZE_LIST §7.10: three promises with tests seen failing first, a corrected cache test that had passed on the unfixed code, and what stays open · why: the freeze doc is the canonical record of what is enforced · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-28] claude · Keyed the response cache on a record version that database triggers bump on any write to a table the context draws from, so a cached answer is never served after a document, decision or profile change · why: an answer cached with no context was replayed after matching context existed (FREEZE_LIST §7.6) · files: backend/core/schema.sql, backend/memory/profile_store.py, backend/core/response_cache.py, backend/core/pipeline.py, backend/tests/test_answers_about_the_user.py, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-28] claude · Stopped the prompt presenting what Stage 4 looked up as the user's whole record: the header now says each section is complete and names the sections not looked up, and rule 4 says 'not in front of you' instead of 'not recorded' · why: a fact in a section the category never fetched was to be reported as not recorded (FREEZE_LIST §7.5) · files: backend/stages/stage_07_context_assembly.py, backend/tests/test_answers_about_the_user.py, backend/tests/test_stage_07_context_assembly.py, docs/LOG.md

- [2026-09-28] claude · Made Stage 4 look up identity and active projects for every question category, with a prompt-level test over the 14 Track 4a questions · why: 10 of 14 ordinary ways of asking about your own work reached the model without the project (FREEZE_LIST §7.5) · files: backend/stages/stage_04_memory_lookup.py, backend/tests/test_answers_about_the_user.py, backend/tests/test_stage_04_memory_lookup.py, docs/LOG.md

- [2026-09-28] claude · Recorded the profile boundary fixes in FREEZE_LIST §7.9: four promises, each with an end-to-end test seen failing first, and what they deliberately leave open (plaintext already on disk, same-profile cache staleness, the upload route holding the event loop) · why: the freeze doc is the canonical record of what is enforced · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-27] claude · Made a sign-in queue its own catch-up behind one still running from the previous session instead of skipping it, and documented the sign-out boundary in ARCHITECTURE.md · why: signing out and into another profile during a catch-up left the new session with no recovery, drain or index repair at all · files: backend/api/server.py, backend/tests/test_profile_boundary.py, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-27] claude · Made uploads and the ingestion sandbox follow the active profile's documents folder, and had the sign-in catch-up copy a profile's documents out of the old shared folder into its own and re-index them · why: every profile's uploads landed in one shared plaintext folder that any profile's ingest accepted (FREEZE_LIST §7.8) · files: backend/memory/vector_store.py, backend/api/server.py, backend/tests/test_profile_boundary.py, backend/tests/test_api_server.py, backend/tests/test_pipeline.py, backend/tests/test_set_db_password.py, backend/tests/test_stage_05_rag_retrieval.py, backend/tests/test_vector_store.py, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-27] claude · Made vector_store refuse to read or write the index when the active profile has a password but no key is held, instead of falling back to plaintext · why: an ingest in flight at sign-out stored its chunk text and path in plaintext, and it survived the next sign-in's rebuild (FREEZE_LIST §7.8) · files: backend/memory/vector_store.py, backend/tests/test_profile_boundary.py, docs/LOG.md

- [2026-09-27] claude · Made sign-out empty the response cache, so the next profile to sign in is no longer served the previous one's answers, with an end-to-end test through the real auth and chat routes · why: measured in FREEZE_LIST §7.8, a second profile received an answer built from the first profile's documents with its own model never called · files: backend/core/session_key.py, backend/core/response_cache.py, backend/tests/test_profile_boundary.py, docs/LOG.md

- [2026-09-27] claude · Ran the end-to-end profile boundary test through the real routes and recorded it in FREEZE_LIST §7.8: profile B was served profile A's document-based answer, an ingest in flight at sign-out stored plaintext that survived A's next sign-in, and uploads go to one shared plaintext folder rather than the profile's own · why: §7.7 named it the single test that could confirm or refute Pattern 1 · files: docs/FREEZE_LIST.md, docs/LOG.md

## Archive

- 2026-09-08 (claude, 4 entries): built the agent-context layer (AGENTS.md, CLAUDE.md, GEMINI.md, ARCHITECTURE/CONVENTIONS/LOG docs, Copilot and Cursor pointers), added a pre-commit check for the AGENTS.md 80-line cap, and added the evidence gate between Observer extraction and Stage 12 after a genuine quote ("comparing FastAPI and Flask") wrote preferred_tools=Flask.
- 2026-09-09 (claude): added in-app profile creation, rename, password change and permanent deletion plus an opt-in sign-in picture, because profiles previously needed a script and a password change orphaned the ChromaDB index.
- 2026-09-09 (claude): gave vector_store one resolved_chroma_path() so test runs stopped renaming the developer's real data/chroma, and made set_db_password.py carry the ChromaDB index to the new key (encrypting a plaintext index on first encryption).
- 2026-09-09 (claude): made a profile delete that cannot finish (WinError 32 from a still-open pip.db) record itself and complete at the next start.
- 2026-09-09 (claude): added Cancel to a running model download and Delete to a pulled model, so a pull no longer had to be waited out and models could be removed.
- 2026-09-09 (claude): put the PIP mark on the assistant's chat avatar in place of the letter P, with an optional fallback in PipLogo.
- 2026-09-09 (claude): gave the active-model dropdown isExpanded and covered the providers screen either side of its 720px cap, ending a RenderFlex overflow per pulled model.
- 2026-09-09 (claude): corrected the packaging path drift in AGENTS.md and installer/PIP.iss (payload staged at <drive>\pip-build\PIP, not dist/PIP) and recorded the MAX_PATH reason in ARCHITECTURE.md.
- 2026-09-09 (claude): made scripts/build_installer.ps1 refuse an incomplete, dirty or stale payload and fail a suspiciously small installer.
- 2026-09-09 (claude): rebuilt dist/PIP-Setup.exe from a clean flutter build and verified 31,615/31,615 files byte-identical to the payload (sha256 7CE29ABA…3254).
- 2026-09-09 (claude): wrote the hook-install requirement into docs/CONVENTIONS.md and installed the hooks on this machine, since core.hooksPath is per-clone.
- 2026-09-09 (claude): added a 300s per-test timeout (thread method) to pytest.ini, after a suite run hung silently for 20 minutes; it later named test_ws_chat's history test as the hang.
- 2026-09-10 (claude): replaced the thinking orb's dot cloud with the PIP mark turning; the states and the backend's labels were unchanged.
- 2026-09-10 (claude): added an in-app .pipbak restore - the conversion runs while the app is open, the file swap is staged for the next start.
- 2026-09-10 (claude): rebuilt dist/PIP-Setup.exe twice from this code (the first predated a Backup-tab refresh fix found by running it); final sha256 69F2791D…BFCD.
- 2026-09-10 (claude): replaced the iris artwork with the six-node mark across both .ico files, the installer wizard and the app assets, and rebuilt the installer from it.
- 2026-09-10 (claude): shipped MSVCP140/VCRUNTIME140/VCRUNTIME140_1 in the payload's app folder and made the payload gate require them, since a clean Windows install has none.
- 2026-09-12 (codex): rebuilt PIP-Setup.exe and completed an isolated install, runtime-load and uninstall smoke test.
- 2026-09-14 (codex): added an explicit first-run Create/Import gateway before password setup, replacing a synthetic empty default profile.
- 2026-09-14 (codex): aligned the first-run backup picker with the project's desktop file-picker API.
- 2026-09-18 (codex): removed the empty Default profile from new-account and first-run flows.
- 2026-09-18 (codex): simplified onboarding and sourced the timezone from the local system automatically.
- 2026-09-19 (codex): made the development launcher profile-neutral, with the initial profile chosen on the sign-in screen.
- 2026-09-19 (codex): documented the normal and developer launch commands and their locked sign-in behaviour.
- 2026-09-19 (antigravity): cleared a stale lock before backend startup and made Ollama optional when other endpoints are configured.
- 2026-09-26 (claude): adopted the reliability freeze - added docs/FREEZE_LIST.md and pointed AGENTS.md's Current focus at it.
- 2026-09-26 (claude): added the Track 1 Observer/provider-authorization tests and recorded in FREEZE_LIST §7.2 that the locality gate holds on the real path, with a manual break-it confirming the test catches its removal.
- 2026-09-26 (claude): recorded the Track 2 PIP_DB_KEY report in FREEZE_LIST §7.3 - the vector_store read is load-bearing and fails open, and nvidia-smi inherits the key.
- 2026-09-27 (claude): recorded the Track 3 PID-reuse lock report in FREEZE_LIST §7.4 - the lock stored a bare PID, so a reused PID blocked the app, the restore script and the launcher (fixed in §7.12).
- 2026-09-27 (claude): recorded the Track 4a Stage 1 routing report in FREEZE_LIST §7.5 - 10 of 14 identity/project questions reached the model without the seeded project, under a header claiming the complete record.
- 2026-09-27 (claude): recorded the Track 4b cache-safety report in FREEZE_LIST §7.6 - stale cached answers were replayed after a matching document or decision existed, and one profile's answer was served to another.
- 2026-09-27 (claude): wrote the cross-track synthesis in FREEZE_LIST §7.7 - five patterns confirmed by two or more reports (sign-out boundary missing in-memory work, duplicated rules, optional parts failing open, tests concealing defects, under-identifying keys).
