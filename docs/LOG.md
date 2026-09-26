# Log

<!-- Newest first. Prepend new entries directly under the format line. -->

Format:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

- [2026-09-26] claude · Recorded the Track 2 PIP_DB_KEY report in FREEZE_LIST §7.3: the main-DB env read is redundant, the vector_store read is load-bearing and fails open (chunks written after sign-out land in plaintext), and nvidia-smi inherits the key · why: Promise 7's final clause depended on it, and the pre-accepted outcome predicted the opposite · files: docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-26] claude · Added the Track 1 Observer/provider-authorization tests and recorded the Track 1 report in FREEZE_LIST §7.2: the locality gate holds on the real path, and a manual break-it confirmed the test catches its removal · why: Promise 5 was claimed but had no outcome test on the real path · files: backend/tests/test_observer_provider_authorization.py, docs/FREEZE_LIST.md, docs/LOG.md

- [2026-09-26] claude · Adopted the reliability freeze: added docs/FREEZE_LIST.md, pointed AGENTS.md Current focus at it, and archived the five oldest log entries · why: governance promises were claimed but unmeasured, and AGENTS.md still pointed agents at packaging · files: docs/FREEZE_LIST.md, AGENTS.md, docs/LOG.md

- [2026-09-19] antigravity · Cleared stale lock before backend startup and made Ollama optional when other endpoints are configured · why: a dead previous session caused silent backend crashes and hardcoding Ollama meant an unnecessary timeout penalty for users with alternative API providers · files: scripts/launch_pip.ps1, backend/core/pipeline.py, backend/api/server.py

- [2026-09-19] codex · Documented normal and developer launch commands and their locked sign-in behavior · why: the Flutter README was a stock template and did not explain the two supported launch paths · files: frontend/flutter/README.md, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-19] codex · Made the development launcher profile-neutral and selected its initial profile from the sign-in screen · why: neither a password nor a profile belongs in the terminal before PIP opens · files: scripts/run_dev.ps1, scripts/_profiles.ps1, scripts/launch_pip.ps1, frontend/flutter/lib/screens/sign_in_screen.dart, frontend/flutter/test/sign_in_screen_test.dart, docs/LOG.md

- [2026-09-18] codex · Simplified onboarding and sourced timezone from the local system automatically · why: timezone and current-project prompts added unnecessary first-run form fields · files: frontend/flutter/lib/onboarding_screen.dart, frontend/flutter/test/onboarding_screen_test.dart, docs/LOG.md

- [2026-09-18] codex · Removed the empty Default profile from new-account and first-run flows · why: a placeholder account was displayed beside the profile the user just created · files: backend/core/profiles.py, backend/api/server.py, backend/tests/test_profiles.py, backend/tests/test_profile_management.py, frontend/flutter/lib/screens/sign_in_screen.dart, frontend/flutter/test/sign_in_screen_test.dart, docs/ARCHITECTURE.md, docs/LOG.md

- [2026-09-14] codex · Aligned the first-run backup picker with the project's desktop file-picker API · why: it exposes the singular static picker used by BackupView · files: frontend/flutter/lib/screens/sign_in_screen.dart, docs/LOG.md

- [2026-09-14] codex · Added an explicit first-run Create/Import gateway before password setup · why: a synthetic empty default profile is not a user-facing account flow · files: frontend/flutter/lib/screens/sign_in_screen.dart, frontend/flutter/test/sign_in_screen_test.dart, docs/LOG.md

- [2026-09-12] codex · Rebuilt PIP-Setup.exe and completed an isolated install, runtime-load, and uninstall smoke test · why: the prior installer predated the app-local Visual C++ runtime commit and its recorded hash no longer matched · files: dist/PIP-Setup.exe, docs/LOG.md

- [2026-09-10] claude · Shipped MSVCP140/VCRUNTIME140/VCRUNTIME140_1 in the payload's app\ folder and made the payload gate require them · why: the Flutter exe imports them, a clean Windows install has none, and this build machine's System32 hid that from every test · files: scripts/build_portable.ps1, scripts/build_installer.ps1, docs/ARCHITECTURE.md

- [2026-09-10] claude · Replaced the iris artwork with the six-node mark, rendered it to both .ico files, the wizard panel and a light/dark pair of app assets, and rebuilt the installer from it · why: the mark PIP ships under changed, and one script owning every raster is what stops the window icon, the installer and the picture inside the app drifting apart · files: installer/pip-mark.svg, installer/pip-iris-blue.svg (deleted), scripts/make_icons.py, installer/PIP.iss, frontend/flutter/lib/logo.dart, frontend/flutter/pubspec.yaml, frontend/flutter/assets/*, frontend/flutter/windows/runner/resources/app_icon.ico

- [2026-09-10] claude · Rebuilt dist/PIP-Setup.exe from this code (twice: the first predated the Backup-tab refresh fix found by running it) · why: the shipped installer predated the in-app restore and the thinking mark; final sha256 69F2791DC58E76873103424E0C2E795770FB0E644154DF7E05583A19F220BFCD, app.so 842E8D94 verified identical in build tree and payload · files: dist/PIP-Setup.exe (gitignored artefact; recorded here for provenance)

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

## Archive

- 2026-09-08 (claude, 4 entries): built the agent-context layer (AGENTS.md, CLAUDE.md, GEMINI.md, ARCHITECTURE/CONVENTIONS/LOG docs, Copilot and Cursor pointers), added a pre-commit check for the AGENTS.md 80-line cap, and added the evidence gate between Observer extraction and Stage 12 after a genuine quote ("comparing FastAPI and Flask") wrote preferred_tools=Flask.
- 2026-09-09 (claude): added in-app profile creation, rename, password change and permanent deletion plus an opt-in sign-in picture, because profiles previously needed a script and a password change orphaned the ChromaDB index.
- 2026-09-09 (claude): gave vector_store one resolved_chroma_path() so test runs stopped renaming the developer's real data/chroma, and made set_db_password.py carry the ChromaDB index to the new key (encrypting a plaintext index on first encryption).
