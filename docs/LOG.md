# Log

<!-- Newest first. Prepend new entries directly under the format line. -->

Format:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

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
