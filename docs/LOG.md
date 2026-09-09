# Log

<!-- Newest first. Prepend new entries directly under the format line. -->

Format:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

- [2026-09-10] claude · Replaced the iris artwork with the six-node mark, rendered it to both .ico files, the wizard panel and a light/dark pair of app assets, and rebuilt the installer from it · why: the mark PIP ships under changed, and one script owning every raster is what stops the window icon, the installer and the picture inside the app drifting apart · files: installer/pip-mark.svg, installer/pip-iris-blue.svg (deleted), scripts/make_icons.py, installer/PIP.iss, frontend/flutter/lib/logo.dart, frontend/flutter/pubspec.yaml, frontend/flutter/assets/*, frontend/flutter/windows/runner/resources/app_icon.ico

- [2026-09-10] claude · Rebuilt dist/PIP-Setup.exe from this code, sha256 27E64DF5DCF70EA9F3F27E7EDACAD5C63CFA890FC8B4577546A036062176ABB6 · why: the shipped installer predated the in-app restore and the thinking mark; app.so 3ED198E1 verified identical in build tree, payload and installer · files: dist/PIP-Setup.exe (gitignored artefact; recorded here for provenance)

- [2026-09-10] claude · Added an in-app .pipbak restore: the conversion runs while the app is open, the swap is staged for the next start · why: backup_view.dart said a restore button could not exist, which was true of the swap and not of the conversion - and deferring the whole thing would have meant writing two passwords to disk · files: backend/core/restore.py, backend/api/server.py, backend/tests/test_restore_in_app.py, frontend/flutter/lib/api_client.dart, frontend/flutter/lib/screens/backup_view.dart, frontend/flutter/lib/home_shell.dart, frontend/flutter/test/backup_view_test.dart, docs/ARCHITECTURE.md

- [2026-09-10] claude · Replaced the thinking orb's dot cloud with the PIP mark turning · why: the dots were a port of somebody else's idea and read as a second application beside the six-node mark; the states and the backend's own labels are unchanged · files: frontend/flutter/lib/widgets/thinking_mark.dart, frontend/flutter/lib/widgets/reasoning_strip.dart, frontend/flutter/test/reasoning_strip_test.dart

- [2026-09-09] claude · Added a 300s per-test timeout to pytest.ini (thread method) and pytest-timeout to requirements · why: a run of the suite hung silently for 20 minutes with no output to diagnose it by; the ceiling caught the next occurrence and named it - test_ws_chat.py's accumulates_conversation_history_across_turns, blocked in receive_json with every executor thread and the event loop idle · files: pytest.ini, requirements.txt

- [2026-09-09] claude · Wrote the hook-install requirement into docs/CONVENTIONS.md and installed the hooks on this machine · why: core.hooksPath is per-clone and cannot be committed, so the repo carried the cap rule and a LOG entry saying the check was added while no hook was installed to run it · files: docs/CONVENTIONS.md

- [2026-09-09] claude · Rebuilt dist/PIP-Setup.exe from a clean flutter build and verified it: 31,615/31,615 files byte-identical to the payload, sha256 7CE29ABA6F129C21886B473F82C9097CA1BA471862AB4363F9CA6C7AE20D3254 · why: the 76 MB installer in dist/ predated its own payload by 22 minutes and carried an empty version resource, so it was untrusted and replaced rather than explained · files: dist/PIP-Setup.exe (gitignored artefact; recorded here for provenance)

- [2026-09-09] claude · Made scripts/build_installer.ps1 refuse to compile an incomplete, dirty or stale payload, and fail a suspiciously small installer · why: a 76 MB PIP-Setup.exe had been produced from a payload that had not finished assembling, and nothing in the pipeline could tell that from a success · files: scripts/build_installer.ps1

- [2026-09-09] claude · Corrected the packaging path drift in AGENTS.md and installer/PIP.iss and recorded the MAX_PATH reason in ARCHITECTURE.md · why: both said the payload is built at dist/PIP while build_installer.ps1 stages it at <drive>\pip-build\PIP · files: AGENTS.md, installer/PIP.iss, docs/ARCHITECTURE.md

- [2026-09-09] claude · Gave the active-model dropdown isExpanded, and covered the providers screen at widths either side of its 720px cap · why: below 720 the dropdown sized itself to its widest model name and the field clamped it, filling the console with one RenderFlex overflow per pulled model · files: frontend/flutter/lib/screens/providers_view.dart, frontend/flutter/test/providers_view_test.dart

- [2026-09-09] claude · Put the PIP mark on the assistant's chat avatar in place of the letter P, and gave PipLogo an optional fallback · why: the avatar answers who said a turn, and a letter was standing in for a mark the app already has · files: frontend/flutter/lib/logo.dart, frontend/flutter/lib/screens/chat_view.dart

- [2026-09-09] claude · Added Cancel to a running model download and Delete to a pulled model · why: a 4GB pull could only be waited out, and models could be added but never removed, so a machine that compared four of them had spent twenty gigabytes with no way back · files: backend/providers/ollama_provider.py, backend/api/server.py, backend/tests/test_llm_catalog.py, frontend/flutter/lib/api_client.dart, frontend/flutter/lib/screens/model_browser.dart, frontend/flutter/test/model_browser_test.dart

- [2026-09-09] claude · Made a profile delete that cannot finish now record itself and complete at the next start · why: deleting a profile that had been chatted in failed with WinError 32, because a chat connection's close is abandoned by design and leaves pip.db open for the life of the process · files: backend/core/profiles.py, backend/api/server.py, frontend/flutter/lib/screens/profile_view.dart, backend/tests/test_profile_management.py, frontend/flutter/test/profile_management_test.dart, docs/ARCHITECTURE.md

- [2026-09-09] claude · Made scripts/set_db_password.py carry the ChromaDB index over to the new key, and taught vector_store.reencrypt to encrypt a plaintext index on a first encryption · why: the script rekeyed only SQLite, so the index went dark while the Documents screen kept reporting it, and a first encryption left every document's text readable on disk in chroma/ · files: scripts/set_db_password.py, backend/memory/vector_store.py, backend/tests/test_set_db_password.py, backend/tests/test_vector_store.py, backend/core/session_key.py, docs/ARCHITECTURE.md

- [2026-09-09] claude · Gave vector_store one resolved_chroma_path() and pointed restore_backup.py's rebuild at it · why: it read the CHROMA_DB_PATH module constant, so every full-suite run renamed the developer's real data/chroma to chroma.superseded-<stamp> from tests that never touched Chroma · files: backend/memory/vector_store.py, scripts/restore_backup.py, backend/tests/test_restore_backup.py

- [2026-09-09] claude · Added profile creation, rename, password change and permanent deletion from inside the app, plus an opt-in unencrypted sign-in picture · why: profiles could only be added by running a Python script and could not be deleted at all, and a password change silently orphaned the ChromaDB index · files: backend/core/profiles.py, backend/core/session_key.py, backend/core/db_key.py, backend/memory/vector_store.py, backend/api/server.py, backend/tests/test_profile_management.py, backend/tests/test_vector_store.py, frontend/flutter/lib/api_client.dart, frontend/flutter/lib/home_shell.dart, frontend/flutter/lib/screens/sign_in_screen.dart, frontend/flutter/lib/screens/profile_view.dart, frontend/flutter/test/profile_management_test.dart, frontend/flutter/test/profile_view_test.dart, docs/ARCHITECTURE.md

- [2026-09-08] claude · Added the evidence gate between Observer extraction and Stage 12, so a genuine quote can no longer carry an inference the user never made · why: grounding proved the words existed and the constitution checked policy, but nothing compared the evidence to the claim, so "I've been comparing FastAPI and Flask" wrote preferred_tools=Flask · files: backend/core/evidence_gate.py, backend/stages/stage_11_observer.py, backend/stages/stage_13_profile_update.py, backend/core/session_lifecycle.py, backend/tests/evidence_cases.py, backend/tests/test_evidence_gate.py, backend/tests/test_evidence_inference.py, backend/tests/test_venv_guard.py, scripts/eval_evidence_gate.py, docs/ARCHITECTURE.md

- [2026-09-08] claude · Added an AGENTS.md 80-line cap check to the pre-commit hook and documented it, plus the trailing-newline rule, in CONVENTIONS.md · why: the cap only existed in conversation, and an agent verifying against remembered counts reported all six docs as broken · files: scripts/pre-commit, docs/CONVENTIONS.md

- [2026-09-08] claude · Added Copilot and Cursor pointer files and listed them in the AGENTS.md folder map · why: both tools read only their own filename and would never reach AGENTS.md on their own · files: .github/copilot-instructions.md, .cursor/rules/project-context.mdc, AGENTS.md

- [2026-09-08] claude · Added the agent-context layer: AGENTS.md, CLAUDE.md, GEMINI.md, docs/ARCHITECTURE.md, docs/CONVENTIONS.md, docs/LOG.md · why: the repo's only written context was a single 766-line status doc with no rules for agents and no conventions reference · files: AGENTS.md, CLAUDE.md, GEMINI.md, docs/ARCHITECTURE.md, docs/CONVENTIONS.md, docs/LOG.md

## Archive
