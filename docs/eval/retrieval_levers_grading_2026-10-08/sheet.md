# Grading sheet - levers

Label each answer: CORRECT, DECLINES, WRONG or VAGUE (definitions in docs/eval/retrieval_e2e_protocol_2026-10-08.json; a DECLINES that says the documents do not state the answer counts as DECLINES).
The condition and the retrieved passages are not shown.

## 1
Q: Which graphics card was in the machine used for the validation?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): (`VerifiedAndReputablePolicyState = 1`). - Python 3.12.10 (`.venv`), Flutter 3.44.2, Ollama 0.32.14 on an RTX 4060 Laptop GPU (8 GB). Live model `qwen2.5:7b`; `llama3.1:8b` and `phi3:mini` are also pulled.
ANSWER: I do not have information about the specific graphics card used for the validation in front of me. The document does not provide details about the hardware configuration of the machine used for this evaluation.

## 2
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: The pre-commit import guard enforces the rule that nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb`, or `ollama` directly. Specifically, it guards against direct imports in those two directories. Inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py` (which opens a `.pipbak` itself); `chromadb` only in `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. The `ollama` package is not imported even though it is listed in `requirements.txt`, as `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.

## 3
Q: Why was the export not re-run end to end from the Backup screen?
REFERENCE (from docs/FREEZE_LIST.md): - **The export itself was not re-run end to end from the Backup screen.** `export_backup.py` asks for both passwords through `getpass`, which reads the console, not a pipe. What stands in: - the launcher's choice, tested through the real wrapper;
ANSWER: The export was not re-run end to end from the Backup screen because the export process is triggered by specific conditions, such as the export starting while a writer is committing, or shortly after signing in or signing out. These conditions are not replicated when switching to the Backup tab without initiating a new chat session or performing actions that would trigger the Observer pass. Therefore, the export from the Backup tab does not always start under the same conditions as when it is initiated through other means, leading to the observed behavior.

## 4
Q: Why are the probe files named probe_*.py?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): None in `backend/tests/` (freeze). The probes are kept beside this report in `docs/eval/reliability_2026-10-01/`, named `probe_*.py` so a bare `pytest` does not collect them. Each failing probe is the regression test for its defect once a fix is authorized, in the §7.8 style.
ANSWER: I don't have any information about the naming convention for probe files in front of me. Could you provide more context or details about where you encountered these files?

## 5
Q: How does the count from wc -l compare with the line number an editor shows at the end of a file?
REFERENCE (from docs/CONVENTIONS.md): once the hooks are installed — see Hooks below) - **Every file ends with exactly one trailing newline and no blank line.** `wc -l` therefore reports one fewer than the line number an editor shows for the end of the file. That gap is not a defect and must not be closed by
ANSWER: I do not have that in front of me. The context provided does not contain information about how the count from `wc -l` compares with the line number an editor shows at the end of a file. However, generally, `wc -l` and most text editors display the number of lines in a file, so they should be consistent. If you have a specific file in mind, you could check by running `wc -l` in the terminal and comparing it to the line number shown by an editor.

## 6
Q: What happens when the original path is absent, the true cross-machine case?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): the Documents screen lists the document. - With the original path absent (the true cross-machine case), the write-back runs (existing `test_phase9_roundtrip`). Re-indexing in that case was not re-measured, because D-01 struck the attempt.
ANSWER: Based on the information provided, when the original path is absent, the result is **D-07**. This indicates that the index is rebuilt from the registry after restore in the absence of the original path.

## 7
Q: What fields does a LOG.md entry have?
REFERENCE (from AGENTS.md): Verbatim, one line per entry, newest first: - [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>
ANSWER: A LOG.md entry has the following fields:

- Date and time of the entry: `[YYYY-MM-DD]`
- Agent who made the entry: `<agent>`
- Description of what changed: `<what changed>`
- Reason for the change: `why: <one clause>`
- File paths affected: `files: <paths>`

These fields are formatted verbatim, one line per entry, with the newest entries first.

## 8
Q: How many REST method and path pairs refused bad credentials?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): PIP's security boundaries mostly hold when measured from outside. All 64 REST method+path pairs refuse bad credentials, every gated route refuses while locked, the WebSocket checks its token and origin, profiles stay
ANSWER: Every gated route refused bad credentials. Since the document states that "All 64 REST method+path pairs refuse bad credentials," there were 64 REST method and path pairs that refused bad credentials.

## 9
Q: Which exact version of the grpc package must be installed?
REFERENCE (from AGENTS.md): OpenAI-compatible provider for configured endpoints. - **Key packages:** backend — `fastapi`, `uvicorn`, `sqlcipher3`, `cryptography`, `chromadb`, `grpcio==1.83.1` (exact pin — see `requirements.txt`), `sentence-transformers`, `pypdf`, `ddgs` (`ollama`
ANSWER: I do not have that information in front of me. The user's projects and specific package versions are not recorded.

## 10
Q: What time-to-live does the cache give to general knowledge answers?
REFERENCE (from docs/ARCHITECTURE.md): Stages 3–9, not just the LLM call. TTLs are per intent category in `backend/config/settings.json`; `project_question` and `personal_question` are `0`, `general_knowledge` is 86400. The key also carries `profile_store.record_version()`, a counter that database triggers bump on
ANSWER: The cache gives a time-to-live (TTL) of 24 hours to general knowledge answers. This is based on the information provided in the document, where it states that "what am I working on?" is classified as `general_knowledge`, so after the "you have no project recorded" answer it would be cached and replayed for 24 hours.

## 11
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: The pip.lock file is treated as stale by the launcher when it detects a live process with a different PID. Specifically, the launcher uses the `_pid_is_running` function to check if the process with the PID stored in the pip.lock file is still running. If the process is running but has a different PID, the launcher considers the lock stale and will not proceed with operations that require the lock to be held by the expected process.

## 12
Q: What happens to the next sign-in's catch-up if one is still running?
REFERENCE (from docs/ARCHITECTURE.md): active profile has a salt but no key is held (`IndexLockedError`) instead of falling back to plaintext. And the next sign-in's catch-up is queued behind any still running rather than skipped. All three were measured through the real routes (FREEZE_LIST §7.8) and are pinned by
ANSWER: I do not have information about what happens to the next sign-in's catch-up if one is still running. The context provided does not contain details about catch-up processes or their interaction with sign-ins.

## 13
Q: Why did the harness fail to read paths with accented characters?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): by `export_pip.ps1` (§7.18's observation), not left unnamed; the check expects that; - a redirected PowerShell writes in the OEM code page, which the harness read as cp1252, so a path containing `ü` came back as nothing; the
ANSWER: I do not have any recorded information about why the harness failed to read paths with accented characters. Could you provide more details or context about this issue?

## 14
Q: Why does a newly added cloud endpoint sit behind the local model?
REFERENCE (from docs/ARCHITECTURE.md): `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint sits *behind* the local model and cannot silently start sending conversations off the machine. Ollama is dynamically skipped if it is unreachable and alternative endpoints exist, avoiding an unnecessary timeout penalty for every message, while
ANSWER: Based on the information provided, a newly added cloud endpoint is not automatically treated the same as a local endpoint. The system enforces specific conditions for a provider to be considered local, as detailed in Promise 5. Specifically, a provider is only considered local if both its own entry (`llm_endpoints.is_local`) and its consent entry (`provider_consent.is_cloud = 0`) are set to indicate local status. These statuses are attested by whoever configured the endpoint and are not inferred from the hostname.

Since a newly added cloud endpoint would not have both of these records set to indicate local status, it would not be treated as local by the system. Therefore, the Observer runs only against providers that meet these criteria, and a cloud endpoint would sit behind the local model until it is properly configured to be recognized as local.

## 15
Q: What recall did the observer reach in run two?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 9/10 (90%) - **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: The recall for run two was 9/23 (39%).

## 16
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: The backend talks to Ollama through the `ollama_provider.py` file, which implements the provider interface defined in `base_provider.py`. Even though the `ollama` package is not imported directly, the communication is handled via the HTTP API using `urllib`.

## 17
Q: Where does onboarding_screen.dart sit compared with sign_in_screen.dart?
REFERENCE (from docs/CONVENTIONS.md): `lib/screens/model_setup_screen.dart`), and no suffix at all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.
ANSWER: I do not have any specific information about the relative positions or files of `onboarding_screen.dart` and `sign_in_screen.dart` in the user's project or files. These are likely part of the application's user interface, but without more context about the project structure or the exact location of these files, I cannot provide a precise answer.

## 18
Q: What recall did the observer reach in run three?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 7, 'UNLABELLED': 4, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 7/8 (88%) - **recall** (stated facts learned): 7/23 (30%) - written 3, only queued for confirmation 4 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: The recall in run three was 7/23 (30%).

## 19
Q: How long may the AGENTS.md file be, and is that rule enforced?
REFERENCE (from docs/CONVENTIONS.md): ## Docs - **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.** It is loaded into an agent's context before every session, so its length is
ANSWER: The AGENTS.md file has a line count cap enforced by a pre-commit hook. According to `docs/CONVENTIONS.md`, every file ends with exactly one trailing newline and no blank line, and `wc -l` reports one fewer than the line number an editor shows for the end of the file. This gap is not a defect and must not be closed by deleting the final newline. The hook `scripts/pre-commit` rejects a staged `AGENTS.md` over the cap.

## 20
Q: Does PIP run on macOS?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP runs on macOS.

## 21
Q: What number of key derivation iterations is actually used in the code?
REFERENCE (from docs/CONVENTIONS.md): `DEFAULT_MODEL_NAME`), and the whole `performance_targets` and `database` blocks. `database.kdf_iterations` is duplicated as a constant in `backend/core/db_key.py:42` (`KDF_ITERATIONS = 256_000`), which is the value that is actually used.
ANSWER: I do not have that information in front of me. The number of key derivation iterations used in the code is not recorded in the context provided.

## 22
Q: After a new test passes, what must you do to be sure it proves anything?
REFERENCE (from docs/FREEZE_LIST.md): files. Not "the function returned REJECT". 3. **Break it once by hand.** Weaken the guard, confirm the test fails, restore the guard. A test never seen failing proves nothing. 4. **Make the smallest change that passes.** No cleanup riding along.
ANSWER: To be sure a new test proves anything, you must follow the steps outlined in §2.2: test first on the outcome, break it once, and commit one change per promise. This ensures that the test isolates the specific change and confirms its effect.

## 23
Q: What could an unisolated salt path in the tests have done to the real database?
REFERENCE (from docs/FREEZE_LIST.md): - **Tests never touch real data.** Every `PIP_*` path isolated in `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have made the real database permanently unopenable. - **Measure a flake before believing it.** Compare against a pinned
ANSWER: The context does not provide specific details on what an unisolated salt path in the tests could have done to the real database. The information given focuses on the testing framework and its behavior under different conditions, but it does not describe potential impacts on the real database. Therefore, I do not have that information in front of me.

## 24
Q: On how many of the in-app restores did D-01 hold?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at `9968e8c`; the inputs-and-delete control and two staging restores swapped out none, or an empty one). Each of those `pip.db-wal` files held
ANSWER: The documents provided do not contain specific information on how many in-app restores D-01 held. Therefore, I do not have that in front of me.

## 25
Q: Why was the export not re-run end to end from the Backup screen?
REFERENCE (from docs/FREEZE_LIST.md): - **The export itself was not re-run end to end from the Backup screen.** `export_backup.py` asks for both passwords through `getpass`, which reads the console, not a pipe. What stands in: - the launcher's choice, tested through the real wrapper;
ANSWER: The export was not re-run end to end from the Backup screen because the export process is triggered by specific actions that do not occur when switching to the Backup tab alone. According to the evidence, the export starts when the export command is issued, which can happen within a couple of minutes of a new chat, signing out, signing in, or while the app is in use after the console is waiting. The export does not automatically re-run from the Backup tab without these triggering actions.

## 26
Q: What did Yara's Backup screen show after she signed in, and with whose file name?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - Zed stages a restore and signs out. Yara signs in: the status route gives her `{"pending": true, "source": "export-1.pipbak", ...}`, which her Backup screen shows as "Ready to restore on the next start" for this profile (`backup_view.dart:514-555`), with Zed's file name. Her
ANSWER: After Yara signed in, her Backup screen showed "Ready to restore on the next start" for Zed's profile, with Zed's file name.

## 27
Q: What produced the one export failure on a machine with no chat on it?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): holds one `session_snapshot` row, about the conversation that came with the backup, stamped one second before the `.pipbak` was written: the sign-in catch-up was observing the restored conversation. - **How a person reaches it.** Switching to the Backup tab does not close
ANSWER: The one export failure on a machine with no chat on it occurred during the restoration of a backup using the shortcut. Specifically, the failure happened when the export started while the console was waiting, which is about ten minutes after the last message. This timing aligns with the Observer's session-end pass committing changes to the tables that differed, leading to the export failure.

## 28
Q: How many conversations can PIP store before it slows down?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on how many conversations PIP can store before it slows down. The documents provided do not contain details about PIP's storage limits or performance degradation thresholds.

## 29
Q: Does PIP support voice input?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 30
Q: What is the full name of the PIP project's owner?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 31
Q: What is the expected style for code comments in this project?
REFERENCE (from docs/CONVENTIONS.md): code**, whether it was found live or by inspection, what was tried first, and what limitation remains. This is the house style, not noise — terse code reads as out of place here. → `backend/core/pinned_executor.py` (45 lines of reasoning before the first import), `frontend/flutter/pubspec.yaml`
ANSWER: I do not have that in front of me.

## 32
Q: Where is the interpretation of the end-to-end observer results, including the hand review of the unlabelled rows?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): (the code's default, llama3.1:8b, was not available). Every case on a fresh profile in its first two weeks. Interpretation, including the hand review of the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->
ANSWER: I do not have that in front of me.

## 33
Q: What fields does a LOG.md entry have?
REFERENCE (from AGENTS.md): Verbatim, one line per entry, newest first: - [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>
ANSWER: A LOG.md entry has the following fields:

- Date: `[YYYY-MM-DD]`
- Agent: `<agent>`
- Action: `<what changed>`
- Reason: `why: <one clause>`
- File paths: `files: <paths>`

## 34
Q: What happens when the original path is absent, the true cross-machine case?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): the Documents screen lists the document. - With the original path absent (the true cross-machine case), the write-back runs (existing `test_phase9_roundtrip`). Re-indexing in that case was not re-measured, because D-01 struck the attempt.
ANSWER: Based on the document, when the original path is absent, the result is **D-07**. This means that the index rebuilt from the registry after restore does not hold when the original path does not exist.

## 35
Q: Why does a newly added cloud endpoint sit behind the local model?
REFERENCE (from docs/ARCHITECTURE.md): `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint sits *behind* the local model and cannot silently start sending conversations off the machine. Ollama is dynamically skipped if it is unreachable and alternative endpoints exist, avoiding an unnecessary timeout penalty for every message, while
ANSWER: The newly added cloud endpoint sits behind the local model because, according to the documentation, the Observer runs only against a provider recorded as local in both of its records: the endpoint's own entry (`llm_endpoints.is_local`) and its consent entry (`provider_consent.is_cloud = 0`). Both are attested by whoever configured the endpoint, never inferred from the hostname; PIP does not verify the machine boundary. Therefore, until the endpoint is explicitly marked as local, it is treated as if it were not authorized, and the session stays queued.

## 36
Q: What is the size limit for a single uploaded document?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 37
Q: What is the full name of the PIP project's owner?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 38
Q: Which web browser engine does the PIP desktop app embed?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information about the web browser engine embedded in the PIP desktop app in front of me.

## 39
Q: What is the difference between a 401 and a 423 response from the backend?
REFERENCE (from docs/ARCHITECTURE.md): convert it to `HTTPException(422)` so the client can show it. - **Two unlock states, two status codes.** 401 means the bearer token is wrong; 423 means the token is fine but no password has opened the database. `_UNLOCKED_PATHS` is the small set the sign-in screen itself needs, plus
ANSWER: The backend response codes 401 and 423 have different meanings:

- A 401 Unauthorized response indicates that the request requires user authentication. The client must authenticate to gain network access or to access the requested resource.

- A 423 Locked response is a more recent addition to the HTTP status codes and is used to indicate that the resource identified by the request is temporarily unavailable due to a temporary condition that is expected to be alleviated after some delay.

## 40
Q: How many lines of code does the PIP backend have in total?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 41
Q: Which pipeline threshold has never been measured?
REFERENCE (from docs/FREEZE_LIST.md): remains a separate capability experiment. - **Documented limitations kept visible:** Stage 12 threshold quality unmeasured; Stage 1 is regex under a 30 ms budget by design; `PIP_*` test isolation not exhaustively audited; decision history keeps only the
ANSWER: According to the document, Stage 12 threshold quality unmeasured is listed as a documented limitation. Therefore, Stage 12 threshold quality unmeasured has never been measured.

## 42
Q: Where does onboarding_screen.dart sit compared with sign_in_screen.dart?
REFERENCE (from docs/CONVENTIONS.md): `lib/screens/model_setup_screen.dart`), and no suffix at all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.
ANSWER: I don't have that in front of me. Onboarding_screen.dart and sign_in_screen.dart are likely part of a project's directory structure, but without the context of the project's file organization, I cannot determine their relative positions.

## 43
Q: What do drain, cancel and cancel_pending_restore_for touch?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): staging's files behind (`restore.py:154-158`, `197-201`). Nothing else looks for `restore-*.tmp.*` files: drain, cancel and `cancel_pending_restore_for` touch only what the current marker names. - **Reachable through the app (backend half measured; the screen half from
ANSWER: I do not have information on what drain, cancel, and cancel_pending_restore_for touch in the context provided about this user. These terms seem to be related to some process or function, but without more details, I cannot provide an accurate answer.

## 44
Q: How many people work on the PIP project?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me. The context provided does not include details about the number of people working on the PIP project.

## 45
Q: What names are used for a used catch variable in the Flutter code?
REFERENCE (from docs/CONVENTIONS.md): `{"detail": …}` envelope**; screens store `error.toString()` in a nullable `_error` field and render it. → `lib/api_client.dart:17` - **Inconsistent:** a used catch variable is named both `catch (error)` (`lib/screens/decisions_view.dart`) and `catch (e)`
ANSWER: I do not have information about specific names used for catch variables in the Flutter code from the provided documents. The documents focus on reliability testing, migration processes, and UI fixes, but do not contain details about the Flutter codebase or variable names.

## 46
Q: What does the log say on every sign-in when a document cannot be re-indexed?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): a path outside this profile's documents folder. - The failure is only collected into a return value; the log says "rebuilding" on every sign-in. The index stayed empty after 55 s, while the Documents screen lists the document.
ANSWER: I do not have that in front of me. The log entries for sign-in processes and document re-indexing are not detailed in the provided context.

## 47
Q: What is the critical defect found in restoring over a leftover wal file?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | ID | Severity | One line | |---|---|---| | D-01 | **Critical** | An in-app restore installed over a profile with a leftover `-wal` produces a profile that opens with neither the new nor the old password | | D-02 | **High** | On Windows with Smart App Control enforcing, the backend cannot start at all (unsigned torch DLL, imported eagerly) — confirmed on the staged installer payload |
ANSWER: The critical defect found in restoring over a leftover wal file is that the restored database may not open with the new password. Specifically, when a profile's database has uncheckpointed writes in `pip.db-wal`, and `restore.stage_restore()` and `restore.drain_pending_restore()` are run, the old `pip.db-wal` file is not properly handled. As a result, SQLite may replay the uncheckpointed writes onto the restored `pip.db` file, causing the restored database to open only with the old password and salt. This issue is classified as a critical defect (B missing state) and was corrected on 2026-10-02.

## 48
Q: How many tokens of conversation history does the model remember?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 49
Q: How long may the AGENTS.md file be, and is that rule enforced?
REFERENCE (from docs/CONVENTIONS.md): ## Docs - **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.** It is loaded into an agent's context before every session, so its length is
ANSWER: The AGENTS.md file has a line count cap enforced by a pre-commit hook. The exact cap is not specified in the documents, but the hook rejects staged changes to AGENTS.md if it exceeds the limit. To ensure compliance, you should verify the file's length using `wc -l` and ensure it does not exceed the cap before committing changes.

## 50
Q: Which entries in settings.json are never read by any code?
REFERENCE (from docs/CONVENTIONS.md): - **Paths are overridable by environment variable with a default**, so tests can isolate them. → `backend/api/server.py:60` (`PIP_DB_PATH`) - **Inconsistent / dead config:** `settings.json` contains keys nothing reads — `observer.model` (the model actually comes from
ANSWER: I do not have the contents of the user's settings.json file in front of me, so I cannot determine which entries are never read by any code.

## 51
Q: What is wrong with the Welcome back card at the default window size?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): statement. - **D-13:** at the default 1280×720 window, the "Welcome back" card puts Unlock below the fold (screenshot `ui_signin.png`). It scrolls, and Enter submits.
ANSWER: The "Welcome back" card at the default window size has the "Unlock" option positioned below the fold. This means that users cannot see the "Unlock" option without scrolling down, which might not be ideal for a welcoming and user-friendly interface.

## 52
Q: Which local model answered the chat turns during the journey?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): `restore_backup.py`, both with `--from --yes` and as the shortcut runs it (no arguments, typed `yes`); - **chat:** `/ws/chat` with a live local model (Ollama, `qwen2.5:7b`).
ANSWER: The local model used during the journey was `qwen2.5:7b`. This model was the one pulled on the machine for running the `scripts/eval_observer_end_to_end.py` script, which processed the chat turns through the real local model and `run_session_end()`.

## 53
Q: Why are the probe files named probe_*.py?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): None in `backend/tests/` (freeze). The probes are kept beside this report in `docs/eval/reliability_2026-10-01/`, named `probe_*.py` so a bare `pytest` does not collect them. Each failing probe is the regression test for its defect once a fix is authorized, in the §7.8 style.
ANSWER: The probe files are named `probe_*.py` so they are not collected by a bare `pytest` command. They are intended to be run as regression tests once a fix is authorized.

## 54
Q: What is the PIP project's budget?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information about the PIP project's budget in front of me.

## 55
Q: What does the backend/core folder hold?
REFERENCE (from AGENTS.md): - `backend/api/` — `server.py` only: `create_app()`, middleware, all routes. - `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace. - `backend/memory/` — one module per store, functions taking `conn` first.
ANSWER: The `backend/core` folder holds several key components of the backend architecture:

1. **Pipeline Management**: `pipeline.py` and related files manage the execution flow of different stages in the pipeline.
2. **Store Management**: Various store modules under `memory/` handle persistence, such as `profile_store.py` and `vector_store.py`.
3. **Provider Interfaces**: `base_provider.py` and implementations like `ollama_provider.py` and `openai_compatible_provider.py` define and implement the provider interfaces.

These components work together to manage the core logic and data storage of the application.

## 56
Q: What should the system do when Ollama is down?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.3 Standing rules - **Fail closed.** Unknown provider, missing key, Ollama down → refuse and queue. Never fall back to something less safe. - **One source of truth per rule.** A policy in both JSON and code means
ANSWER: The system should handle the case where Ollama is down by failing the cached-answer test, as mentioned in §7.17 of the documentation. No client code changes were made, so the Flutter suite was not re-run.

## 57
Q: What is the difference between a 401 and a 423 response from the backend?
REFERENCE (from docs/ARCHITECTURE.md): convert it to `HTTPException(422)` so the client can show it. - **Two unlock states, two status codes.** 401 means the bearer token is wrong; 423 means the token is fine but no password has opened the database. `_UNLOCKED_PATHS` is the small set the sign-in screen itself needs, plus
ANSWER: I don't have that in front of me. The differences between a 401 and a 423 response from the backend are not recorded in the context provided about this user.

## 58
Q: What is the first of the nine promises about?
REFERENCE (from docs/FREEZE_LIST.md): ## 4. The nine promises ### Promise 1 — Observer writes only through governance **Claim:** Observer candidates reach memory only via grounding → evidence
ANSWER: The first of the nine promises is about Observer writes only through governance. The claim is that Observer candidates reach memory only via grounding → evidence gate → Stage 12 → Stage 13. This promise must prove that there is no production path from Observer output to storage that skips governance.

## 59
Q: Why were no retrieval quality results claimed in the validation pass?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): embedder (`harness/pip_embed_shim.py`): a deterministic hashed bag-of-words, not all-MiniLM. **Any result about retrieval quality is invalid under it**, and none is claimed.
ANSWER: I do not have information about retrieval quality results in the provided documents. The documents focus on tests and controls related to consent and provider locality, but do not mention retrieval quality.

## 60
Q: Why does the evidence check run before reinforcement instead of after validation?
REFERENCE (from docs/ARCHITECTURE.md): `memory_observation_log` and that log is how a signal accrues the `evidence_count` that clears `week_3_4` and `month_2_plus` — gating after it would let an unsupported inference vote itself in by being repeated across three sessions. Its verdict is expressed as an ordinary `ValidationResult`
ANSWER: The evidence check runs before reinforcement because the purpose of the evidence check is to determine the validity and sufficiency of the evidence supporting a fact or decision. If the evidence is not sufficient or valid, the fact or decision should not proceed to the reinforcement phase, where it would be integrated into the model's knowledge base. Running the evidence check early ensures that only well-supported facts and decisions are reinforced, maintaining the integrity and reliability of the model's knowledge.

## 61
Q: Is there an Android version of PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on an Android version of PIP in front of me. The documents provided focus on the Flutter client for a Windows application and do not mention an Android version.

## 62
Q: What did the catch-up started by /auth/setup run into at sign-out?
REFERENCE (from docs/FREEZE_LIST.md): **The fourth promise was not in the authorized list.** It was found while fixing the second one. The catch-up started by `/auth/setup` was still running at sign-out, and it hit the new refusal, which was correct. But the next sign-in then skipped its own catch-up because one "was running".
ANSWER: The catch-up started by /auth/setup at sign-out ran into the issue that the connection, which was already open at the time of sign-out, could still answer questions from the user's profile's database. This means that while the connection could no longer exchange cached answers with other sessions due to the isolation mechanisms, it could still provide answers based on the cached data from the user's profile until the client dropped the connection.

## 63
Q: How many lines of code does the PIP backend have in total?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have the total line count of the PIP backend in front of me.

## 64
Q: What is the maximum length of a PIP password?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 65
Q: What happens to a conversation whose process was killed before the memory step ran?
REFERENCE (from docs/ARCHITECTURE.md): idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for a killed process, rebuilt at the next startup from `conversations` /`messages` where `observed_at IS NULL`. Catch-up drains in a background task, never inline before serving. Every sign-in gets its own: one still running from a previous
ANSWER: I do not have information on what happens to a conversation whose process was killed before the memory step ran. The context provided does not cover this specific scenario.

## 66
Q: What produced the one export failure on a machine with no chat on it?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): holds one `session_snapshot` row, about the conversation that came with the backup, stamped one second before the `.pipbak` was written: the sign-in catch-up was observing the restored conversation. - **How a person reaches it.** Switching to the Backup tab does not close
ANSWER: The one export failure on a machine with no chat on it was due to an installation just restored by the shortcut. The export failed with `{'session_snapshot': (0, 1)}`, indicating an issue with the `session_snapshot` row. This failure occurred because the export started while the Observer's session-end pass was committing changes, specifically the first `session_snapshot` row, which was about the conversation that came with the backup.

## 67
Q: What does the backend/core folder hold?
REFERENCE (from AGENTS.md): - `backend/api/` — `server.py` only: `create_app()`, middleware, all routes. - `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace. - `backend/memory/` — one module per store, functions taking `conn` first.
ANSWER: I do not have information about the contents of the backend/core folder for this user's projects, as no project details have been recorded.

## 68
Q: What did all the revisions of the audit specification produce?
REFERENCE (from docs/FREEZE_LIST.md): ### 9.2 Lessons 1. **Planning can become the sideways expansion it was meant to stop.** Ten revisions of the audit spec produced zero evidence; a small test would have produced some in an afternoon. Hence the two-revision cap.
ANSWER: The revisions of the audit specification produced zero evidence. Despite ten revisions, no repository evidence was generated.

## 69
Q: What fix was recommended for D-20 in _install?
REFERENCE (from docs/FREEZE_LIST.md): requires. Open the chosen file read-only. - **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/` aside with the database in `_install`, under the same stamp and undo list.
ANSWER: The fix for D-20 in _install involved not swapping `documents/` and `chroma/` directories during a restore over a profile with a same-named document. Instead, the backup's documents were written back to the restored profile, ensuring that the backup's text was retrieved and the replaced profile's same-named document was not overwritten.

## 70
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: The pre-commit import guard enforces the dependency rule on the `backend/stages/` and `backend/api/` directories. In practice, it guards against direct imports of `sqlite3`, `sqlcipher3`, `chromadb`, and `ollama` in those two directories. Imports in other parts of the `backend/` directory, such as `backend/memory/profile_store.py` and `backend/core/restore.py`, are not checked by this guard.

## 71
Q: What happens in D-20, a restore over a profile with a same-named document?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): 3. **D-20 (Medium, upper end):** a restore over a profile with a same-named document silently takes the wrong document and discards the backup's copy. 4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
ANSWER: In D-20, a restore over a profile that already holds a document of the same name with different bytes (for example, a common name like `notes.txt` or `resume.pdf` used on the new machine before restoring), the restore process will overwrite the existing document with the one from the backup. This results in the loss of the local changes made to the document on the new machine, as the backup's version is used instead.

## 72
Q: Which restore option is listed as unsupported for the desktop shortcut?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): - In-app export (by design, ADR-027). - Third-party/legacy import. - Restore into a named new profile from the desktop shortcut (it uses the Default slot).
ANSWER: The restore into a named new profile from the desktop shortcut is listed as unsupported. It uses the Default slot instead.

## 73
Q: On how many of the in-app restores did D-01 hold?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at `9968e8c`; the inputs-and-delete control and two staging restores swapped out none, or an empty one). Each of those `pip.db-wal` files held
ANSWER: I do not have information on how many in-app restores D-01 held. The context provided does not contain this specific detail.

## 74
Q: Which cloud storage service does PIP back up to automatically?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 75
Q: What precision did the observer reach in its first run?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - Stage 13: {'written': 3, 'rejected': 22, 'pending': 5} - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5
ANSWER: In the first run, the precision of the observer was 89%. This means out of the 9 rows that were stated facts (TRUE and TRAP), 8 were correctly identified as TRUE.

## 76
Q: Why does cloning the repository not install the git hooks automatically?
REFERENCE (from docs/CONVENTIONS.md): - **Cloning does not install the hooks; `scripts/install_hooks.ps1` does, once per clone.** Git will not run hooks straight from a clone — that is what stops a repository you cloned executing code on checkout — so this is a deliberate step, and until it is taken nothing enforces the ADR-025 import guard or the
ANSWER: Cloning the repository does not install the git hooks automatically because Git does not execute hooks directly from a clone. This design prevents a repository you cloned from running arbitrary code on checkout. The hooks must be installed manually using `scripts/install_hooks.ps1` after the repository is cloned. This ensures that the hooks are properly configured and enforced.

## 77
Q: Why does cloning the repository not install the git hooks automatically?
REFERENCE (from docs/CONVENTIONS.md): - **Cloning does not install the hooks; `scripts/install_hooks.ps1` does, once per clone.** Git will not run hooks straight from a clone — that is what stops a repository you cloned executing code on checkout — so this is a deliberate step, and until it is taken nothing enforces the ADR-025 import guard or the
ANSWER: Cloning the repository does not install the git hooks automatically because Git does not run hooks directly from a clone. This is a security measure to prevent repositories from executing arbitrary code upon checkout. The hooks must be installed manually using `scripts/install_hooks.ps1` after the repository is cloned. This ensures that the hooks are properly configured and enforced.

## 78
Q: How many false rejects did the evidence gate have on the held-out set?
REFERENCE (from docs/ARCHITECTURE.md): queue. The reverse arrangement would pay for the same coverage in false *accepts* — beliefs written into the profile that the user never expressed. Measured cost on a held-out set: 1 false reject in 15 supported statements, 0 false accepts. `scripts/eval_evidence_gate.py` prints the numbers.
ANSWER: The evidence gate had one held-out false reject, `held_accept_tool_habit`, as mentioned in the document.

## 79
Q: What is the critical defect found in restoring over a leftover wal file?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | ID | Severity | One line | |---|---|---| | D-01 | **Critical** | An in-app restore installed over a profile with a leftover `-wal` produces a profile that opens with neither the new nor the old password | | D-02 | **High** | On Windows with Smart App Control enforcing, the backend cannot start at all (unsigned torch DLL, imported eagerly) — confirmed on the staged installer payload |
ANSWER: The critical defect found in restoring over a leftover wal file is documented as D-01. When a profile's database has uncheckpointed writes in `pip.db-wal`, and `restore.stage_restore()` is run followed by `restore.drain_pending_restore()`, the restored `pip.db` is opened with the new key. However, the actual result is that the restored database opens only with the old password and old salt, as the old `pip.db-wal` stays and SQLite replays it onto the restored file. This leaves the profile unopenable with the new password.

## 80
Q: On how many of the in-app restores did D-01 hold?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at `9968e8c`; the inputs-and-delete control and two staging restores swapped out none, or an empty one). Each of those `pip.db-wal` files held
ANSWER: I do not have information on how many in-app restores D-01 held. The documents provided do not contain this specific detail.

## 81
Q: What does rule 4 of the prompt tell the model to answer?
REFERENCE (from docs/FREEZE_LIST.md): the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):` and then lists only the interaction style. Rule 4 of the same prompt tells the model to answer that it has nothing recorded. - The expected answer is therefore a confident *"you have no project
ANSWER: Rule 4 of the prompt tells the model to answer that it has no information about a fact if that fact is not in front of the model. Specifically, for questions about the user's goals, skills, preferences, preferred tools, topics they keep returning to, and documents they consult most, the model should state that it does not have that information in front of it and stop, without making guesses or providing plausible examples.

## 82
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: The lock-gate middleware is registered before the token authentication middleware so that it can sit inside the token middleware. This ensures that the lock-gate middleware only ever sees authenticated requests. The middleware order is deliberate and commented in `server.py`, where Starlette wraps in reverse registration order. This means that the lock-gate middleware, being registered earlier, will be applied before the token middleware, ensuring that unauthenticated requests are intercepted by the lock-gate middleware.

## 83
Q: What is the governing principle of the reliability plan?
REFERENCE (from docs/FREEZE_LIST.md): ## 1. Governing principle > **Constrain the mechanism; do not merely restate the intent.**
ANSWER: The governing principle of the reliability plan is to **constrain the mechanism; do not constrain the outcome**.

## 84
Q: Where is the interpretation of the end-to-end observer results, including the hand review of the unlabelled rows?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): (the code's default, llama3.1:8b, was not available). Every case on a fresh profile in its first two weeks. Interpretation, including the hand review of the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->
ANSWER: The interpretation, including the hand review of the unlabelled rows, is detailed in the document `docs/eval/observer_end_to_end_2026-09-28.md`. This document provides a comprehensive analysis of the results from running `scripts/eval_observer_end_to_end.py` with the model `qwen2.5:7b` on 37 labelled conversations.

## 85
Q: On how many of the in-app restores did D-01 hold?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at `9968e8c`; the inputs-and-delete control and two staging restores swapped out none, or an empty one). Each of those `pip.db-wal` files held
ANSWER: I do not have that information in front of me.

## 86
Q: What happens when the original path is absent, the true cross-machine case?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): the Documents screen lists the document. - With the original path absent (the true cross-machine case), the write-back runs (existing `test_phase9_roundtrip`). Re-indexing in that case was not re-measured, because D-01 struck the attempt.
ANSWER: Based on the document, when the original path is absent, the true cross-machine case, the result is **D-07**. This means that the index is rebuilt from the registry after restore, but this only holds when the original path exists. If the original path is absent, the behavior is not explicitly detailed in the provided records.

## 87
Q: What is the PIP project's budget?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 88
Q: How many hand-made mutations were caught for the read-only open?
REFERENCE (from docs/FREEZE_LIST.md): `test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run showed it (a folder named for the word asserted, an export test that failed
ANSWER: The document does not contain a specific number of hand-made mutations caught for the read-only open scenario. The relevant section does not detail the number of mutations performed or their outcomes.

## 89
Q: How many tokens of conversation history does the model remember?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information about how many tokens of conversation history the model remembers.

## 90
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: The frontend and backend design decisions include specific considerations that prevent the database work from being spread over several threads. The `pipeline.py` document explains that stages 3, 4, 5, and 6 run sequentially even though the specification describes them as running in parallel. This is due to the shared use of a single connection (`conn`) among these stages. If these stages were to run in parallel using `asyncio.gather` across executor threads, it could reintroduce the thread-affinity crash that the system aims to avoid.

To properly handle this, the design either needs a connection per stage or genuinely asynchronous database access, which is a more complex and potentially more resource-intensive solution. The current design prioritizes simplicity and reliability over parallelism in database operations.

## 91
Q: Does PIP support voice input?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether voice input is supported.

## 92
Q: What does _conn() raise for callers that are not routes when the database is locked?
REFERENCE (from docs/ARCHITECTURE.md): - **`_conn()` is a backstop, not the lock.** `LockGateMiddleware` refuses routes while locked; `_conn()` raises `LockedError` for the things that are not routes (background tasks, the WebSocket). Opening the DB with no key would silently create an empty unencrypted file beside the encrypted one, which is
ANSWER: I do not have that in front of me.

## 93
Q: What recall did the observer reach in run three?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 7, 'UNLABELLED': 4, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 7/8 (88%) - **recall** (stated facts learned): 7/23 (30%) - written 3, only queued for confirmation 4 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: I do not have that information in front of me.

## 94
Q: What did Yara's Backup screen show after she signed in, and with whose file name?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - Zed stages a restore and signs out. Yara signs in: the status route gives her `{"pending": true, "source": "export-1.pipbak", ...}`, which her Backup screen shows as "Ready to restore on the next start" for this profile (`backup_view.dart:514-555`), with Zed's file name. Her
ANSWER: After Yara signed in, the Backup screen showed "Ready to restore on the next start" for Zed's profile, with Zed's file name.

## 95
Q: What is the governing principle of the reliability plan?
REFERENCE (from docs/FREEZE_LIST.md): ## 1. Governing principle > **Constrain the mechanism; do not merely restate the intent.**
ANSWER: The governing principle of the reliability plan is to **constrain the mechanism; do not merely restate the intent**. The aim is to catch errors early, cheaply, and through a mechanism rather than by relying on someone remembering to look for them.

## 96
Q: How many backend test files have their own local conn fixture?
REFERENCE (from docs/CONVENTIONS.md): a visible omission. Adding a new `PIP_*` path override means adding it here. → `backend/tests/conftest.py:17` - **Inconsistent:** 16 of 67 backend test files define their own local `conn` fixture (`sqlite3.connect(tmp_path / "pip.db")` + `initialize_schema`) instead
ANSWER: I do not have any information on the number of backend test files that have their own local `conn` fixture. The context provided does not contain details about test fixtures used in the backend tests.

## 97
Q: Why was qwen used for the observer measurement and not the default model?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): <!-- Raw output of scripts/eval_observer_end_to_end.py --repeat 3, 2026-09-28. Labels: backend/tests/observer_cases.py as committed in 1256b51, before this run. Model: qwen2.5:7b through Ollama 0.32.14 - the only model pulled on the machine (the code's default, llama3.1:8b, was not available). Every case on a fresh
ANSWER: The observer measurement used `qwen2.5:7b` because it was the only model available on the machine at the time. The default model, `llama3.1:8b`, was not measured in this run.

## 98
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: The pip.lock file is treated as stale by the launcher when it cannot find a live process with the PID stored in the file. Specifically, the launcher uses the `_pid_is_running` function to check if the process with the stored PID is still alive. If the process is not running, the launcher considers the lock stale and proceeds with the appropriate actions, such as starting the PIP backend.

## 99
Q: What happens to the next sign-in's catch-up if one is still running?
REFERENCE (from docs/ARCHITECTURE.md): active profile has a salt but no key is held (`IndexLockedError`) instead of falling back to plaintext. And the next sign-in's catch-up is queued behind any still running rather than skipped. All three were measured through the real routes (FREEZE_LIST §7.8) and are pinned by
ANSWER: I do not have information about what happens to the next sign-in's catch-up if one is still running in the context provided. The details about catch-up processes and their interactions with sign-ins are not included in the records I have.

## 100
Q: Why was the export not re-run end to end from the Backup screen?
REFERENCE (from docs/FREEZE_LIST.md): - **The export itself was not re-run end to end from the Backup screen.** `export_backup.py` asks for both passwords through `getpass`, which reads the console, not a pipe. What stands in: - the launcher's choice, tested through the real wrapper;
ANSWER: The export was not re-run end to end from the Backup screen because the supported migration workflow failed. Specifically, the issue tracked as D-09 indicates that "Close PIP and open it again to finish" does not apply a restore; the launcher reuses the running backend, causing the swap to wait for an unclean exit, which feeds D-01. This means that the end-to-end re-run through the Backup screen was not met due to this unresolved issue.

## 101
Q: Which languages does the PIP interface support besides English?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on the languages supported by the PIP interface besides English.

## 102
Q: Why were no retrieval quality results claimed in the validation pass?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): embedder (`harness/pip_embed_shim.py`): a deterministic hashed bag-of-words, not all-MiniLM. **Any result about retrieval quality is invalid under it**, and none is claimed.
ANSWER: In the validation pass, the backend suite and every real backend process ran with a stand-in embedder, which was a hashed bag-of-words. This stand-in embedder did not claim any retrieval-quality results because it does not provide actual embedding-based retrieval capabilities. The backend processes relied on this stand-in embedder to avoid issues related to the torch library being unsigned and blocked by Smart App Control, but since it does not perform actual embedding computations, no retrieval quality could be claimed or tested.

## 103
Q: What do drain, cancel and cancel_pending_restore_for touch?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): staging's files behind (`restore.py:154-158`, `197-201`). Nothing else looks for `restore-*.tmp.*` files: drain, cancel and `cancel_pending_restore_for` touch only what the current marker names. - **Reachable through the app (backend half measured; the screen half from
ANSWER: `drain`, `cancel`, and `cancel_pending_restore_for` touch only the files named by the current marker's staging. Specifically, they do not look for or interact with `restore-*.tmp.*` files unless those files are explicitly named by the current staging process.

## 104
Q: What happens when the original path is absent, the true cross-machine case?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): the Documents screen lists the document. - With the original path absent (the true cross-machine case), the write-back runs (existing `test_phase9_roundtrip`). Re-indexing in that case was not re-measured, because D-01 struck the attempt.
ANSWER: Based on the information provided in the document, when the original path is absent, the result is **D-07**. This indicates that the index is rebuilt from the registry after restore in the absence of the original path.

## 105
Q: Where does onboarding_screen.dart sit compared with sign_in_screen.dart?
REFERENCE (from docs/CONVENTIONS.md): `lib/screens/model_setup_screen.dart`), and no suffix at all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.
ANSWER: I do not have any specific information about the relative positions or locations of `onboarding_screen.dart` and `sign_in_screen.dart` in the project structure. These files are likely part of the application's user interface, but without more context about the project's directory layout or the exact nature of these screens, I cannot provide a precise comparison of their positions.

## 106
Q: What is wrong with staged restore state being shared across profiles?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | D-21 | Medium (low end) | The desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used" | | D-17 | Low (upper) | An export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list | | D-19 | Low | Staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's: one profile can cancel another's restore, and an orphaned staged copy survives its profile's deletion |
ANSWER: The issue with shared staged restore state across profiles is that it can lead to unintended overwrites or installations of backups. Specifically, if a staged restore is pending for one profile and another profile is deleted, the staged restore for the first profile should not be affected. However, if the staged restore state is shared, it could result in the backup intended for one profile being installed into the newly created or restored profile, which was not the intended behavior. This could overwrite documents or settings that the user did not intend to replace, leading to data loss or misconfiguration. The current implementation ensures that the staged restore is canceled specifically for the profile being deleted, preventing this from happening.

## 107
Q: Were there uncommitted changes in the repository when the validation ran?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): ## 2. Revision and environment - Revision `f66a309` on `frontend_fix`, no tracked changes. - Windows 11 Home 10.0.26200, **Smart App Control on**
ANSWER: The documents do not state whether there were uncommitted changes in the repository when the validation ran.

## 108
Q: Does PIP run on macOS?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP runs on macOS. The documents provided do not mention macOS compatibility.

## 109
Q: How many hand-made mutations were caught for the read-only open?
REFERENCE (from docs/FREEZE_LIST.md): `test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run showed it (a folder named for the word asserted, an export test that failed
ANSWER: The document does not contain information on how many hand-made mutations were caught for the read-only open. I do not have that in front of me.

## 110
Q: Why does the evidence check run before reinforcement instead of after validation?
REFERENCE (from docs/ARCHITECTURE.md): `memory_observation_log` and that log is how a signal accrues the `evidence_count` that clears `week_3_4` and `month_2_plus` — gating after it would let an unsupported inference vote itself in by being repeated across three sessions. Its verdict is expressed as an ordinary `ValidationResult`
ANSWER: I do not have information about why the evidence check runs before reinforcement instead of after validation. The documents provided do not contain details about the sequence of checks or the rationale behind the order of operations in this context.

## 111
Q: How many lines of code does the PIP backend have in total?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have the total line count of the PIP backend in front of me. The provided documents do not include this metric.

## 112
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: The migration re-run made several checks, and the following defects were identified:

- D-18: Medium severity, an empty (0-byte) file is accepted as a backup.
- D-20: Medium (upper end) severity, an in-app restore over a profile that already has a document of the same name takes that file instead of the backup's.
- D-21: Medium (low end) severity, the desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used."
- D-17: Low (upper) severity, an export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list.
- D-19: Low severity, staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's.

In total, five defects were identified during the migration re-run.

## 113
Q: Which restore option is listed as unsupported for the desktop shortcut?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): - In-app export (by design, ADR-027). - Third-party/legacy import. - Restore into a named new profile from the desktop shortcut (it uses the Default slot).
ANSWER: The restore into a named new profile from the desktop shortcut is listed as an unsupported feature. It uses the Default slot.

## 114
Q: What fix was recommended for D-20 in _install?
REFERENCE (from docs/FREEZE_LIST.md): requires. Open the chosen file read-only. - **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/` aside with the database in `_install`, under the same stamp and undo list.
ANSWER: The fix for D-20 in _install involved not swapping `documents/` and `chroma/` directories during a restore over a profile with a same-named document. Instead, the backup's documents were written back to the restored database, ensuring the backup's copy is preserved.

## 115
Q: Which web browser engine does the PIP desktop app embed?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 116
Q: Which restore option is listed as unsupported for the desktop shortcut?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): - In-app export (by design, ADR-027). - Third-party/legacy import. - Restore into a named new profile from the desktop shortcut (it uses the Default slot).
ANSWER: The restore into a named new profile from the desktop shortcut is listed as unsupported. It uses the Default slot.

## 117
Q: What do drain, cancel and cancel_pending_restore_for touch?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): staging's files behind (`restore.py:154-158`, `197-201`). Nothing else looks for `restore-*.tmp.*` files: drain, cancel and `cancel_pending_restore_for` touch only what the current marker names. - **Reachable through the app (backend half measured; the screen half from
ANSWER: `drain`, `cancel`, and `cancel_pending_restore_for` touch the following files and directories:

- `restore-*.tmp.*` files in the profile's folder.
- `pending-restore.json` file, which is used to stage a restore.

These operations do not look for or touch any other files or directories related to staged restores.

## 118
Q: What fix was recommended for D-20 in _install?
REFERENCE (from docs/FREEZE_LIST.md): requires. Open the chosen file read-only. - **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/` aside with the database in `_install`, under the same stamp and undo list.
ANSWER: I do not have that in front of me.

## 119
Q: What is the size limit for a single uploaded document?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 120
Q: Does the backend use an ORM or Pydantic models for its rows?
REFERENCE (from docs/CONVENTIONS.md): - **Rows are returned as plain dicts, never row objects or model classes.** Return types are `dict[str, Any]` / `list[dict[str, Any]]`. There is no ORM and no Pydantic model anywhere in the backend. → `backend/memory/candidate_store.py:34`
ANSWER: The backend does not use an ORM or Pydantic models for its rows. Rows are returned as plain dicts, never row objects or model classes. The convention is documented in `backend/core/types.py`, and there is no ORM and no Pydantic model anywhere in the backend.

## 121
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: The migration re-run made several checks, and five new defects were identified that failed. These defects are listed as follows:

- D-18: Medium severity, an empty file is accepted as a backup.
- D-20: Medium (upper end) severity, an in-app restore overwrites an existing document.
- D-21: Medium (low end) severity, the desktop shortcut restores the older backup.
- D-17: Low (upper) severity, an export taken while the app is committing rows fails verification.
- D-19: Low severity, staged-restore state is not isolated per installation.

## 122
Q: What should the system do when Ollama is down?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.3 Standing rules - **Fail closed.** Unknown provider, missing key, Ollama down → refuse and queue. Never fall back to something less safe. - **One source of truth per rule.** A policy in both JSON and code means
ANSWER: Based on the information provided, when Ollama is down, the system should handle the situation as follows:

- The system will not serve cached answers after the cache is patched to fail after `done`.
- The backend tests and reliability validation confirm that the system handles Ollama being down as one of the failure scenarios.
- Specifically, the system should not retry mid-session if no provider passes, and the session stays queued until a provider that passes the authorization checks becomes available.
- The Observer runs only against providers recorded as local in both the endpoint's own entry and its consent entry, and it will not send requests to a loopback provider recorded as not local when Ollama is down.

In summary, when Ollama is down, the system should not attempt to use it and should wait for a valid provider to become available before proceeding with any operations that require Ollama.

## 123
Q: What fields does a LOG.md entry have?
REFERENCE (from AGENTS.md): Verbatim, one line per entry, newest first: - [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>
ANSWER: A LOG.md entry has the following fields:

- Date and time of the entry, formatted as `[YYYY-MM-DD]`.
- The agent who made the entry.
- A description of what changed.
- A clause explaining why the change was made.
- A list of file paths affected by the change.

## 124
Q: After a new test passes, what must you do to be sure it proves anything?
REFERENCE (from docs/FREEZE_LIST.md): files. Not "the function returned REJECT". 3. **Break it once by hand.** Weaken the guard, confirm the test fails, restore the guard. A test never seen failing proves nothing. 4. **Make the smallest change that passes.** No cleanup riding along.
ANSWER: To ensure a new test proves anything, you must follow these steps:

1. **Test First on the Outcome**: Run the test to see if the outcome matches the expected result. This initial test should be done in isolation to confirm the behavior under the specific conditions being tested.

2. **Break It Once**: Introduce a single, minimal change that should cause the test to fail. This change should be isolated and not affect other parts of the system. This step helps to isolate the issue and confirm that the test is sensitive to the change.

3. **One Commit per Promise**: Make a single commit that implements the change and runs the test. This ensures that the test result is directly attributable to the change made.

4. **Document the Mechanism**: Record how the test was designed and the specific change that was introduced. This documentation helps in understanding the test and its purpose.

5. **Run the Full Suite**: After the single commit, run the full suite of tests to ensure that the change did not introduce any regressions or unexpected side effects.

6. **Verify the Control**: Ensure that the control test (the test that should pass without the change) still passes. This step confirms that the change introduced is the only factor affecting the test outcome.

7. **Review and Confirm**: Review the results to confirm that the test outcome aligns with the expected behavior. If the test [CUT: answer longer than the sheet shows]

## 125
Q: What was added to each icon-only control to give it a name?
REFERENCE (from docs/FREEZE_LIST.md): - **Promise:** every control a screen reader can tap, on every tab, with the sidebar open or collapsed, has a name it can read. - **Mechanism:** a `Tooltip` on each icon-only control (send/stop, delete conversation, the sidebar toggle, and each sidebar item while
ANSWER: I do not have that information in front of me regarding this user.

## 126
Q: What colour is the Unlock button?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 127
Q: How many hand-made mutations were caught for the read-only open?
REFERENCE (from docs/FREEZE_LIST.md): `test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run showed it (a folder named for the word asserted, an export test that failed
ANSWER: The document does not specify how many hand-made mutations were caught for the read-only open. I do not have that information in front of me.

## 128
Q: What three things are forbidden until all the evidence tracks return?
REFERENCE (from docs/FREEZE_LIST.md): Until all five tracks return and are classified: **No feature work. No speculative cleanup. No fix without evidence.**
ANSWER: Until all five tracks return and are classified, the following are forbidden:

1. No feature work.
2. No speculative cleanup.
3. No fix without evidence.

## 129
Q: Why does format_transcript indent lines that start with a role name?
REFERENCE (from docs/ARCHITECTURE.md): `Assistant:`, because `EvidenceLedger` parses those headers back out to decide who said a quote. Without the escaping, an assistant reply containing a line `User: I prefer Flask` parses back as a genuine user turn. - **The trace logs message length, never message text.** The original reason
ANSWER: `format_transcript()` indents any content line beginning with `User:` or `Assistant:` because `EvidenceLedger` parses these headers back out to decide who said a quote. Without the indentation, an assistant reply containing a line like `User: I prefer Flask` would parse back as a genuine user turn.

## 130
Q: How many people use PIP today?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 131
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: I don't have information about this user's projects or their specific experience with websockets, so I'll provide a general explanation.

Websocket connections are typically designed to handle real-time data exchange between a client and a server. While it is possible to spread the database work over several threads, there are several considerations and potential challenges:

1. **Thread Safety**: Database operations, especially those involving transactions, must be thread-safe. If not managed properly, concurrent access from multiple threads can lead to data corruption or inconsistent states.

2. **Concurrency Control**: Implementing proper concurrency control mechanisms can be complex. This includes managing locks, ensuring atomic operations, and handling deadlocks.

3. **Performance**: While spreading work over threads can improve performance by utilizing multiple CPU cores, it also introduces overhead due to context switching and thread management.

4. **WebSocket Library Support**: Not all WebSocket libraries or frameworks support or are optimized for multi-threaded database operations. You may need to use specific libraries or frameworks that are designed to handle such scenarios.

5. **Scalability**: Depending on the application, spreading the workload might not always lead to better scalability. The benefits of multi-threading must be weighed against the complexity and  [CUT: answer longer than the sheet shows]

## 132
Q: Why are the probe files named probe_*.py?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): None in `backend/tests/` (freeze). The probes are kept beside this report in `docs/eval/reliability_2026-10-01/`, named `probe_*.py` so a bare `pytest` does not collect them. Each failing probe is the regression test for its defect once a fix is authorized, in the §7.8 style.
ANSWER: The probe files are named `probe_*.py` to indicate that they are test scripts specifically designed for running reliability and functionality tests. These names help in identifying and organizing the test scripts separately from other types of Python files in the project.

## 133
Q: What database technology stores the structured data?
REFERENCE (from AGENTS.md): State is plain `StatefulWidget` + `setState` — **no state-management package**. One app-wide `ValueNotifier` (`lib/profile_picture.dart`). - **DB:** SQLite via SQLCipher (`sqlcipher3`), schema in `backend/core/schema.sql`. Raw SQL, no ORM.
ANSWER: I don't have that in front of me.

## 134
Q: What recall did the observer reach in run two?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 9/10 (90%) - **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: The recall in run two was 9/23 (39%).

## 135
Q: What recall did the observer reach in run three?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 7, 'UNLABELLED': 4, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 7/8 (88%) - **recall** (stated facts learned): 7/23 (30%) - written 3, only queued for confirmation 4 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: In run three, the recall of the observer was 7/23 (30%) for stated facts learned.

## 136
Q: What is the first of the nine promises about?
REFERENCE (from docs/FREEZE_LIST.md): ## 4. The nine promises ### Promise 1 — Observer writes only through governance **Claim:** Observer candidates reach memory only via grounding → evidence
ANSWER: The first of the nine promises about is not explicitly stated in the provided documents. The documents detail a process for writing and enforcing promises but do not list out the nine specific promises. Therefore, I do not have that information in front of me.

## 137
Q: What precision did the observer reach in its first run?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - Stage 13: {'written': 3, 'rejected': 22, 'pending': 5} - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5
ANSWER: In the first run, the precision of the observer was 89%. This means out of the 9 rows that the model marked as TRUE or TRAP, 8 were correctly identified as TRUE.

## 138
Q: Which provider is always kept and always passes the Stage 8 gate?
REFERENCE (from docs/FREEZE_LIST.md): endpoint (Ollama down and the only endpoint unconsented, or every endpoint refused). Ollama alone is always kept and always passes the gate, and no route or script adds endpoints yet. It is the same state D-04 was in (§7.21).
ANSWER: Based on the information provided, Ollama is always kept and always passes the Stage 8 gate. The document states that Ollama is local by definition and does not require consent for provider interaction, as it is handled under the "Provider counts as local, needing no consent" scope.

## 139
Q: Was the exit criterion for the migration met?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and so does carrying on from the layout it creates. **The exit criterion is not met as worded** (§9). "Close PIP and open it again", the restart the app asks for, does not apply a restore (D-09, open),
ANSWER: The exit criterion for the migration was not met as worded. The summary in the document states: "The exit criterion is not met as worded. 'Close PIP and open it again', the restart the app asks for, does not apply a restore (D-09, open), and five new defects sit on the backup and restore path."

## 140
Q: What does rule 4 of the prompt tell the model to answer?
REFERENCE (from docs/FREEZE_LIST.md): the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):` and then lists only the interaction style. Rule 4 of the same prompt tells the model to answer that it has nothing recorded. - The expected answer is therefore a confident *"you have no project
ANSWER: Rule 4 of the prompt tells the model to answer normally and fully from its own knowledge when asked a general question, such as how something works, what a term means, or how to solve a problem. If the question is not about the user's records, the model should provide an answer based on its own information.

## 141
Q: How does the count from wc -l compare with the line number an editor shows at the end of a file?
REFERENCE (from docs/CONVENTIONS.md): once the hooks are installed — see Hooks below) - **Every file ends with exactly one trailing newline and no blank line.** `wc -l` therefore reports one fewer than the line number an editor shows for the end of the file. That gap is not a defect and must not be closed by
ANSWER: The `wc -l` command in a Unix-like environment counts the number of lines in a file, including any blank lines. An editor typically shows the line number of the current line or the total number of lines in the file, but this can vary depending on the editor settings and the specific editor being used.

If you run `wc -l` on a file, it will give you the total line count, which should match the line number shown by the editor if the editor is set to display the total number of lines. However, if the editor is set to show the line number of the current line, it will display a different number unless you are on the last line of the file.

To compare the two, you can use `wc -l` in a terminal and check the line number in your editor. If you are using a specific editor, let me know, and I can provide more detailed instructions.

## 142
Q: Under what condition does launch_pip.ps1 stop a running backend?
REFERENCE (from docs/ARCHITECTURE.md): `backend.api.server` (a bare port number is somebody else's program until proved otherwise) and stops it. `launch_pip.ps1` uses it only when `pending-restore.json` exists, so a staged restore is installed by a new backend's lifespan instead of waiting for a reboot; `restore_pip.ps1` offers it
ANSWER: I do not have information on the conditions under which launch_pip.ps1 stops a running backend. The context provided does not contain details about the script's behavior or the conditions that might cause it to stop a backend process.

## 143
Q: What did the catch-up started by /auth/setup run into at sign-out?
REFERENCE (from docs/FREEZE_LIST.md): **The fourth promise was not in the authorized list.** It was found while fixing the second one. The catch-up started by `/auth/setup` was still running at sign-out, and it hit the new refusal, which was correct. But the next sign-in then skipped its own catch-up because one "was running".
ANSWER: I do not have that in front of me.

## 144
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: The pip.lock file is treated as stale by the launcher when it detects a live process with the same PID but without the necessary process creation time to confirm it is the original PIP process. Specifically, the launcher uses the `_pid_is_running` function to check if a process with the PID stored in pip.lock is still alive. If the process is alive but lacks the creation time stored alongside the PID, the launcher considers the lock stale and allows the new PIP instance to proceed. This behavior was modified to avoid repeating the rule in PowerShell and to ensure consistency across all scripts parsing the lock file.

## 145
Q: How many false rejects did the evidence gate have on the held-out set?
REFERENCE (from docs/ARCHITECTURE.md): queue. The reverse arrangement would pay for the same coverage in false *accepts* — beliefs written into the profile that the user never expressed. Measured cost on a held-out set: 1 false reject in 15 supported statements, 0 false accepts. `scripts/eval_evidence_gate.py` prints the numbers.
ANSWER: The evidence gate had 1 false reject in 15 supported statements on the held-out set.

## 146
Q: How many tokens of conversation history does the model remember?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information about the number of tokens of conversation history the model remembers.

## 147
Q: What happens to the next sign-in's catch-up if one is still running?
REFERENCE (from docs/ARCHITECTURE.md): active profile has a salt but no key is held (`IndexLockedError`) instead of falling back to plaintext. And the next sign-in's catch-up is queued behind any still running rather than skipped. All three were measured through the real routes (FREEZE_LIST §7.8) and are pinned by
ANSWER: I do not have information about what happens to the next sign-in's catch-up if one is still running in the context provided. The documents focus on cache management and consent locality but do not detail the behavior of catch-up processes during sign-ins.

## 148
Q: Why did the harness fail to read paths with accented characters?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): by `export_pip.ps1` (§7.18's observation), not left unnamed; the check expects that; - a redirected PowerShell writes in the OEM code page, which the harness read as cp1252, so a path containing `ü` came back as nothing; the
ANSWER: I don't have that in front of me. The context provided does not contain information about why the harness failed to read paths with accented characters. Could you provide more details or context related to this issue?

## 149
Q: What happens in D-20, a restore over a profile with a same-named document?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): 3. **D-20 (Medium, upper end):** a restore over a profile with a same-named document silently takes the wrong document and discards the backup's copy. 4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
ANSWER: In D-20, a restore over a profile that already holds a document of the same name with different bytes (for example, a common name like `notes.txt` or `resume.pdf` used on the new machine before restoring), the restore process will overwrite the existing document with the one from the backup. This overwrite happens silently, meaning the user is not prompted for confirmation. The backup's copy of the document replaces the document in the restored profile, and the original document's bytes are destroyed in the restored database. This behavior is against an explicit promise made by the restore dialog, which states that the restore will replace the profile with what is in the backup, including documents.

## 150
Q: Does PIP run on macOS?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP runs on macOS. The context provided does not mention macOS compatibility or any specific requirements for operating systems.

## 151
Q: Which local model answered the chat turns during the journey?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): `restore_backup.py`, both with `--from --yes` and as the shortcut runs it (no arguments, typed `yes`); - **chat:** `/ws/chat` with a live local model (Ollama, `qwen2.5:7b`).
ANSWER: The local model used to answer the chat turns during the journey was `qwen2.5:7b`. This model was the one pulled on the machine for the evaluation, and it is mentioned specifically in the document.

## 152
Q: Why does a newly added cloud endpoint sit behind the local model?
REFERENCE (from docs/ARCHITECTURE.md): `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint sits *behind* the local model and cannot silently start sending conversations off the machine. Ollama is dynamically skipped if it is unreachable and alternative endpoints exist, avoiding an unnecessary timeout penalty for every message, while
ANSWER: Based on the information provided, a newly added cloud endpoint sits behind the local model because the system enforces strict consent and authorization checks. Specifically, the Observer runs only against a provider recorded as local in both its own entry (`llm_endpoints.is_local`) and its consent entry (`provider_consent.is_cloud = 0`). This means that for a cloud provider to be considered local and thus allowed to be observed, both conditions must be met. If these conditions are not satisfied, the session remains queued and is processed only when a local provider is available.

## 153
Q: What happens to a conversation whose process was killed before the memory step ran?
REFERENCE (from docs/ARCHITECTURE.md): idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for a killed process, rebuilt at the next startup from `conversations` /`messages` where `observed_at IS NULL`. Catch-up drains in a background task, never inline before serving. Every sign-in gets its own: one still running from a previous
ANSWER: I do not have that in front of me.

## 154
Q: Why are the probe files named probe_*.py?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): None in `backend/tests/` (freeze). The probes are kept beside this report in `docs/eval/reliability_2026-10-01/`, named `probe_*.py` so a bare `pytest` does not collect them. Each failing probe is the regression test for its defect once a fix is authorized, in the §7.8 style.
ANSWER: The probe files are named `probe_*.py` so that the suite does not collect them when running tests. Each failing probe serves as a regression test for its defect once a fix is authorized.

## 155
Q: Which cloud storage service does PIP back up to automatically?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have any information on which cloud storage service PIP back up to automatically. There are no records of a default or automatic cloud backup service in the provided context.

## 156
Q: What is wrong with staged restore state being shared across profiles?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | D-21 | Medium (low end) | The desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used" | | D-17 | Low (upper) | An export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list | | D-19 | Low | Staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's: one profile can cancel another's restore, and an orphaned staged copy survives its profile's deletion |
ANSWER: The issue with staged restore state being shared across profiles is that it could lead to the wrong backup being installed into a profile that is being deleted. Specifically, if a profile is deleted and a staged restore for another profile exists, the staged restore might be installed into the deleted profile's folder, leading to the old backup being installed over the new one's database. This would happen under a password that the new owner of the profile did not choose, potentially resulting in the loss of the new profile's data and the installation of outdated or irrelevant data.

## 157
Q: Why was fine tuning rejected as a way to stop the model fabricating?
REFERENCE (from docs/FREEZE_LIST.md): - **Fine-tuning rejected as a fabrication fix.** The bug was deterministic (misleading context); training teaches tendencies, and the only corpus was the contaminated history. A smaller stock Observer model
ANSWER: I do not have information about why fine tuning was rejected as a way to stop the model from fabricating in the provided context. The details given are about backend suite tests, model loading, and user interface interactions with the PIP application. There is no mention of fine tuning or its rejection in the recorded projects or documents.

## 158
Q: Why did the shortcut choose the first backup of the day over the second?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and restores it. The restored profile lacks the change. - **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last name in `sorted()`, and `-` sorts before `.`. The same rule picks any name sorting after `pip_backup_` over the dated files whatever their age, and
ANSWER: The shortcut does not inherently choose the first backup of the day over the second. According to the document, the shortcut with no `--from` parameter is designed to be used when `data/` contains two or more backups and the newest day has more than one backup. In such a case, the machine typically chooses the newest backup by modification time, with a numeric suffix to break ties, as the listing and the Backup screen already order them.

If there is a specific instance where the shortcut chose the first backup of the day, it would be due to the modification time of the files. The document does not indicate any preference for the first backup over the second; it simply states that the newest backup by modification time is selected.

## 159
Q: Is there an Android version of PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on an Android version of PIP in front of me. The documents mention a Flutter client for Windows, but there is no record of an Android version.

## 160
Q: Why are the probe files named probe_*.py?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): None in `backend/tests/` (freeze). The probes are kept beside this report in `docs/eval/reliability_2026-10-01/`, named `probe_*.py` so a bare `pytest` does not collect them. Each failing probe is the regression test for its defect once a fix is authorized, in the §7.8 style.
ANSWER: The probe files are named `probe_*.py` so they are not collected by the test suite when running `pytest`. This allows them to be used as regression tests for specific defects once a fix is authorized.

## 161
Q: What happens when the original path is absent, the true cross-machine case?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): the Documents screen lists the document. - With the original path absent (the true cross-machine case), the write-back runs (existing `test_phase9_roundtrip`). Re-indexing in that case was not re-measured, because D-01 struck the attempt.
ANSWER: I do not have that in front of me.

## 162
Q: Why was fine tuning rejected as a way to stop the model fabricating?
REFERENCE (from docs/FREEZE_LIST.md): - **Fine-tuning rejected as a fabrication fix.** The bug was deterministic (misleading context); training teaches tendencies, and the only corpus was the contaminated history. A smaller stock Observer model
ANSWER: I do not have information about why fine tuning was rejected as a way to stop the model from fabricating in the provided context. The document focuses on backend suite passes, model loading, and behavior of the Flutter client, but does not mention any discussions or decisions regarding fine tuning or model fabrication.

## 163
Q: In the Flutter screens how can you tell data has not been fetched yet?
REFERENCE (from docs/CONVENTIONS.md): → `lib/screens/decisions_view.dart` - **Data is fetched in `initState()` and stored in a nullable field; `null` means "not loaded yet", an empty list means "loaded, nothing there".** The build method branches on that. → `lib/screens/decisions_view.dart:53`
ANSWER: In the Flutter screens, data not being fetched yet can typically be indicated by several visual cues or placeholders. Here are some common ways to show that data is still being fetched:

1. **Loading Spinners or Spinners**: A circular progress indicator ( CircularProgressIndicator or LinearProgressIndicator) can be displayed to indicate that the data is being fetched.

2. **Placeholders**: Text or placeholder widgets can be shown where the data will eventually appear. For example, you might display "Loading..." or a more detailed placeholder like "No data available" until the actual data is fetched.

3. **Shimmer Effects**: Shimmer effects can be used to show a visual representation of the data that is yet to be fetched. This can give a sense of what the final UI will look like once the data is loaded.

4. **Progress Bars**: A progress bar can be used to show the progress of data fetching, especially if the process is expected to take some time.

5. **Empty States**: An empty state screen can be shown if no data is available. This can include a message like "No data available" along with an icon or a call to action.

6. **Toast Messages**: A toast message can be shown briefly to indicate that data is being fetched, though this is less common and usually used for other purposes.

To implement these in a Flutter screen, you would typically use a combination of `FutureBuilder`, `S [CUT: answer longer than the sheet shows]

## 164
Q: Under what condition does launch_pip.ps1 stop a running backend?
REFERENCE (from docs/ARCHITECTURE.md): `backend.api.server` (a bare port number is somebody else's program until proved otherwise) and stops it. `launch_pip.ps1` uses it only when `pending-restore.json` exists, so a staged restore is installed by a new backend's lifespan instead of waiting for a reboot; `restore_pip.ps1` offers it
ANSWER: `launch_pip.ps1` stops a running backend when `pending-restore.json` exists. The script uses `scripts/_backend.ps1` to find and stop the backend by the owner of the port and a command line naming `backend.api.server`. This stop is a hard one by design, and what it costs is already recovered at the next start.

## 165
Q: What three things are forbidden until all the evidence tracks return?
REFERENCE (from docs/FREEZE_LIST.md): Until all five tracks return and are classified: **No feature work. No speculative cleanup. No fix without evidence.**
ANSWER: Based on the information provided, there are no three specific things forbidden until all the evidence tracks return. The document outlines various evidence tracks and their methods but does not mention any prohibitions tied to the completion of these tracks. Therefore, I do not have that information in front of me.

## 166
Q: What does the backend/core folder hold?
REFERENCE (from AGENTS.md): - `backend/api/` — `server.py` only: `create_app()`, middleware, all routes. - `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace. - `backend/memory/` — one module per store, functions taking `conn` first.
ANSWER: The backend/core folder holds modules related to persistence. Specifically, it contains modules for different stores that interact with the database, using raw SQL. These modules are part of the third layer in the architecture described, which is the Persistence layer.

## 167
Q: What does the backend/core folder hold?
REFERENCE (from AGENTS.md): - `backend/api/` — `server.py` only: `create_app()`, middleware, all routes. - `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace. - `backend/memory/` — one module per store, functions taking `conn` first.
ANSWER: The backend/core folder holds the following components according to the architecture documentation:

- `pipeline.py` and `stages/`: These are part of the Orchestration layer, containing one `run()` per stage that the pipeline calls in order.
- `memory/`: This is part of the Persistence layer, containing modules for different stores with module-level functions and raw SQL against `schema.sql`.

## 168
Q: What does shared/ws_spec.py contain?
REFERENCE (from docs/ARCHITECTURE.md): `shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire events, imported by the stage that produces them, the pipeline that relays them, and the server that forwards them.
ANSWER: shared/ws_spec.py's header explicitly states that structured shapes are `TypedDict`, not Pydantic, and explains that introducing Pydantic in one file would be an inconsistency rather than an improvement.

## 169
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: The pre-commit import guard enforces the rule that nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb`, or `ollama` directly. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py` (which opens a `.pipbak` itself); `chromadb` only in `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly.

## 170
Q: What time-to-live does the cache give to general knowledge answers?
REFERENCE (from docs/ARCHITECTURE.md): Stages 3–9, not just the LLM call. TTLs are per intent category in `backend/config/settings.json`; `project_question` and `personal_question` are `0`, `general_knowledge` is 86400. The key also carries `profile_store.record_version()`, a counter that database triggers bump on
ANSWER: The documents you provided do not state a specific time-to-live for general knowledge answers. The cache behavior described is primarily in the context of document-based and decision-based answers, with no explicit mention of a time-to-live for general knowledge answers.

## 171
Q: What does shared/ws_spec.py contain?
REFERENCE (from docs/ARCHITECTURE.md): `shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire events, imported by the stage that produces them, the pipeline that relays them, and the server that forwards them.
ANSWER: I do not have information about the contents of shared/ws_spec.py in front of me. Could you provide more context or details about this file?

## 172
Q: What three things are forbidden until all the evidence tracks return?
REFERENCE (from docs/FREEZE_LIST.md): Until all five tracks return and are classified: **No feature work. No speculative cleanup. No fix without evidence.**
ANSWER: The documents do not specify three things that are forbidden until all the evidence tracks return. The evidence tracks are described, but their completion conditions and any associated prohibitions are not detailed in the provided information.

## 173
Q: What names are used for a used catch variable in the Flutter code?
REFERENCE (from docs/CONVENTIONS.md): `{"detail": …}` envelope**; screens store `error.toString()` in a nullable `_error` field and render it. → `lib/api_client.dart:17` - **Inconsistent:** a used catch variable is named both `catch (error)` (`lib/screens/decisions_view.dart`) and `catch (e)`
ANSWER: I do not have information about specific variable names used for catch variables in the Flutter code for this user. The Flutter codebase is not detailed in the provided context, and there are no records of such variable names.

## 174
Q: What was added to each icon-only control to give it a name?
REFERENCE (from docs/FREEZE_LIST.md): - **Promise:** every control a screen reader can tap, on every tab, with the sidebar open or collapsed, has a name it can read. - **Mechanism:** a `Tooltip` on each icon-only control (send/stop, delete conversation, the sidebar toggle, and each sidebar item while
ANSWER: I do not have that information in front of me regarding this user's projects or activities. Could you provide more context or details about the icons and controls you are referring to?

## 175
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: I do not have information about when the `pip.lock` file is treated as stale by the launcher in front of me. The context provided does not contain details about the criteria or timeline for considering a `pip.lock` file stale. Could you provide more context or specify which launcher you are referring to?

## 176
Q: What do drain, cancel and cancel_pending_restore_for touch?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): staging's files behind (`restore.py:154-158`, `197-201`). Nothing else looks for `restore-*.tmp.*` files: drain, cancel and `cancel_pending_restore_for` touch only what the current marker names. - **Reachable through the app (backend half measured; the screen half from
ANSWER: `drain`, `cancel`, and `cancel_pending_restore_for` touch the following files and directories:

- `restore-<stamp>.tmp.db` and its associated salt file in the profile's folder.
- Any temporary files or directories related to the pending restore process.

These actions are part of managing a staged restore that is pending for a profile. When a restore is canceled or drained, these files are targeted to ensure that any staged data is properly cleaned up.

## 177
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: The frontend has no logic, and `api_client.dart` turns a path plus payload into an HTTP call and the JSON back into a Dart value — no caching, no retries, no client-side validation. The websocket handling, `ws_chat_client.dart`, relays events and reconnects; it decides nothing. The database work for the websocket is managed by the backend, and there are specific design decisions in place to ensure thread safety and avoid reintroducing thread-affinity crashes.

The response cache sits between Stage 2 and Stage 7, so a hit skips Stages 3–9, not just the LLM call. This cache uses TTLs per intent category, and it carries a counter that bumps on any write to a table, ensuring that cached answers are invalidated when relevant data changes. However, the design decision to run Stages 3/4/5/6 sequentially, even though the spec describes them as parallel, is due to the need for a shared connection `conn` among these stages. `asyncio.gather` across executor threads would reintroduce the thread-affinity crash, necessitating a connection per stage or genuinely async DB access, which is a design decision rather than a mechanical follow-up.

Given these constraints, spreading the websocket's database work over several threads would likely reintroduce the thread-affinity crash, making it necessary to maintain the current design.

## 178
Q: Which web browser engine does the PIP desktop app embed?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on which web browser engine the PIP desktop app embeds. The documents provided do not mention the specific browser engine used by the desktop app.

## 179
Q: Which graphics card does PIP require?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on the specific graphics card requirements for PIP in front of me. The document mentions `ollama` as a declared dependency, but does not specify any graphics card requirements. If you need this information, you might want to check the project's documentation or setup instructions more thoroughly, or look for any mentions of system requirements.

## 180
Q: What happens in D-20, a restore over a profile with a same-named document?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): 3. **D-20 (Medium, upper end):** a restore over a profile with a same-named document silently takes the wrong document and discards the backup's copy. 4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
ANSWER: In D-20, a restore over a profile that already holds a document of the same name with different bytes, the system will overwrite the existing document with the one from the backup. This can lead to the loss of the local changes made to the document on the new machine before the restore. For example, if the document is named `notes.txt` and both the backup and the local profile contain a file with this name but different content, the content from the backup will replace the local content. This behavior is consistent regardless of whether the restore is performed through the in-app process or a fresh profile installation.

## 181
Q: What does the backend/core folder hold?
REFERENCE (from AGENTS.md): - `backend/api/` — `server.py` only: `create_app()`, middleware, all routes. - `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace. - `backend/memory/` — one module per store, functions taking `conn` first.
ANSWER: The `backend/core` folder in the architecture holds several key components of the backend system:

1. **Pipeline Management**: `pipeline.py` and related files manage the execution flow of various stages. Each stage has a `run()` method that is called in sequence.

2. **Store Management**: Subfolders like `memory` contain modules that handle persistence, such as `vector_store.py` and `profile_store.py`. These modules interact with the database to store and retrieve data.

3. **Middleware and Utilities**: Various utility functions and classes that are used across different parts of the backend, such as `LockGateMiddleware` which manages access to the database.

4. **Schema Definitions**: `schema.sql` defines the database schema used by the persistence layer.

This folder is part of the "Persistence" layer in the architecture, which is responsible for storing and retrieving data.

## 182
Q: What is the size limit for a single uploaded document?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me for this user.

## 183
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: The backend talks to Ollama through the `ollama_provider.py` file, which implements the provider interface defined in `base_provider.py`. Even though the `ollama` package is not imported directly, the communication happens via HTTP API requests using `urllib`. This setup ensures that the dependency rule is maintained, where nothing under `backend/stages/` or `backend/api/` imports `sqlite3`, `chromadb`, or `ollama` directly.

## 184
Q: What recall did the observer reach in run two?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 9/10 (90%) - **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: I do not have that information in front of me.

## 185
Q: What is the maximum number of documents a person can upload to PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 186
Q: What happens to the next sign-in's catch-up if one is still running?
REFERENCE (from docs/ARCHITECTURE.md): active profile has a salt but no key is held (`IndexLockedError`) instead of falling back to plaintext. And the next sign-in's catch-up is queued behind any still running rather than skipped. All three were measured through the real routes (FREEZE_LIST §7.8) and are pinned by
ANSWER: I do not have that in front of me.

## 187
Q: What does shared/ws_spec.py contain?
REFERENCE (from docs/ARCHITECTURE.md): `shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire events, imported by the stage that produces them, the pipeline that relays them, and the server that forwards them.
ANSWER: shared/ws_spec.py contains the header and documentation for the WebSocket specification used in the application. It explicitly states that structured shapes should be `TypedDict` and not Pydantic, and explains that introducing Pydantic in one file would be an inconsistency rather than an improvement.

## 188
Q: Which exact version of the grpc package must be installed?
REFERENCE (from AGENTS.md): OpenAI-compatible provider for configured endpoints. - **Key packages:** backend — `fastapi`, `uvicorn`, `sqlcipher3`, `cryptography`, `chromadb`, `grpcio==1.83.1` (exact pin — see `requirements.txt`), `sentence-transformers`, `pypdf`, `ddgs` (`ollama`
ANSWER: I do not have that information in front of me. The exact version of the grpc package that needs to be installed is not recorded in the context provided.

## 189
Q: In which order should entries be placed in the LOG file?
REFERENCE (from AGENTS.md): ## LOG.md entry format Verbatim, one line per entry, newest first:
ANSWER: Entries in the LOG file should be placed in chronological order, with the newest entries first.

## 190
Q: What does rule 4 of the prompt tell the model to answer?
REFERENCE (from docs/FREEZE_LIST.md): the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):` and then lists only the interaction style. Rule 4 of the same prompt tells the model to answer that it has nothing recorded. - The expected answer is therefore a confident *"you have no project
ANSWER: Rule 4 of the prompt tells the model to answer normally and fully from its own knowledge if a question is not about the user's records. If the context does not contain a fact about the user that was asked for, the model should say it does not have that in front of it and stop.

## 191
Q: What fields does a LOG.md entry have?
REFERENCE (from AGENTS.md): Verbatim, one line per entry, newest first: - [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>
ANSWER: A LOG.md entry typically has fields such as date, description of the activity or task, duration, and any notes or outcomes. However, without specific context about the user's LOG.md entries, I cannot provide a more detailed breakdown. Do you need information on a particular LOG.md entry or format?

## 192
Q: How many backend test files have their own local conn fixture?
REFERENCE (from docs/CONVENTIONS.md): a visible omission. Adding a new `PIP_*` path override means adding it here. → `backend/tests/conftest.py:17` - **Inconsistent:** 16 of 67 backend test files define their own local `conn` fixture (`sqlite3.connect(tmp_path / "pip.db")` + `initialize_schema`) instead
ANSWER: I do not have information on the number of backend test files that have their own local conn fixture. The documents provided do not contain this specific detail.

## 193
Q: Which graphics card does PIP require?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information about the specific graphics card required by PIP in front of me.

## 194
Q: Does PIP run on macOS?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP runs on macOS. The context provided does not mention macOS compatibility or any specific testing on that operating system.

## 195
Q: How many revisions of a plan are allowed before building a small version?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.4 Process - **Freeze features while promises are unverified.** - **Cap planning at two revisions.** If a spec needs a third, run a small version and let the result correct it (see §9, lesson 1).
ANSWER: According to the documents, a plan can be revised up to two times before a small version needs to be run to confirm the direction. If a third revision is needed, a small version should be created and run to correct the plan.

## 196
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: I don't have information about the specific projects or middleware configurations of this user in front of me. However, in general, lock-gate middleware is often registered before token middleware to ensure that access to resources is properly controlled. Lock-gate middleware can handle tasks like rate limiting, IP blocking, or other security measures that need to be applied before token validation. Once these initial checks are passed, the token middleware can then validate the user's authentication token to grant or deny access to the requested resource.

## 197
Q: What does shared/ws_spec.py contain?
REFERENCE (from docs/ARCHITECTURE.md): `shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire events, imported by the stage that produces them, the pipeline that relays them, and the server that forwards them.
ANSWER: I do not have information about the contents of `shared/ws_spec.py` in front of me. The document I have reviewed does not provide details about the specific content or structure of this file. It only mentions that the file's header explicitly states that structured shapes should be `TypedDict`, not Pydantic, and that introducing Pydantic in this file would be considered an inconsistency.

## 198
Q: What did the catch-up started by /auth/setup run into at sign-out?
REFERENCE (from docs/FREEZE_LIST.md): **The fourth promise was not in the authorized list.** It was found while fixing the second one. The catch-up started by `/auth/setup` was still running at sign-out, and it hit the new refusal, which was correct. But the next sign-in then skipped its own catch-up because one "was running".
ANSWER: The catch-up started by `/auth/setup` at sign-out did not run into any specific issues as documented in the provided context. The context focuses on the mechanisms and tests related to session boundaries and caching, but does not mention any particular problems or issues encountered during sign-out with the `/auth/setup` process. If there were any issues, they are not detailed in the given information.

## 199
Q: What does rule 4 of the prompt tell the model to answer?
REFERENCE (from docs/FREEZE_LIST.md): the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):` and then lists only the interaction style. Rule 4 of the same prompt tells the model to answer that it has nothing recorded. - The expected answer is therefore a confident *"you have no project
ANSWER: Rule 4 of the prompt tells the model to answer honestly if a fact about the user is not in front of it. Specifically, if the model does not have information about the user's goals, skills, preferences, preferred tools, topics they keep returning to, or documents they consult most, it should say it does not have that information in front of it and stop.

## 200
Q: What did Yara's Backup screen show after she signed in, and with whose file name?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - Zed stages a restore and signs out. Yara signs in: the status route gives her `{"pending": true, "source": "export-1.pipbak", ...}`, which her Backup screen shows as "Ready to restore on the next start" for this profile (`backup_view.dart:514-555`), with Zed's file name. Her
ANSWER: After Yara signed in, the Backup screen showed that there was a pending restore, specifically with Zed's file name. The status route gave her a response of `{"pending": true, "source": "export-1.pipbak", ...}`, which was displayed on her Backup screen as "Ready to restore on the next start" for this profile.

## 201
Q: What does _conn() raise for callers that are not routes when the database is locked?
REFERENCE (from docs/ARCHITECTURE.md): - **`_conn()` is a backstop, not the lock.** `LockGateMiddleware` refuses routes while locked; `_conn()` raises `LockedError` for the things that are not routes (background tasks, the WebSocket). Opening the DB with no key would silently create an empty unencrypted file beside the encrypted one, which is
ANSWER: I do not have information on what `_conn()` raises for callers that are not routes when the database is locked. The documents provided do not contain this specific detail.

## 202
Q: Which provider is always kept and always passes the Stage 8 gate?
REFERENCE (from docs/FREEZE_LIST.md): endpoint (Ollama down and the only endpoint unconsented, or every endpoint refused). Ollama alone is always kept and always passes the gate, and no route or script adds endpoints yet. It is the same state D-04 was in (§7.21).
ANSWER: I do not have that in front of me.

## 203
Q: What time-to-live does the cache give to general knowledge answers?
REFERENCE (from docs/ARCHITECTURE.md): Stages 3–9, not just the LLM call. TTLs are per intent category in `backend/config/settings.json`; `project_question` and `personal_question` are `0`, `general_knowledge` is 86400. The key also carries `profile_store.record_version()`, a counter that database triggers bump on
ANSWER: The cache does not give a specific time-to-live (TTL) for general knowledge answers. The relevant information provided does not mention any TTL for such answers. The TTL of 0 mentioned is for decision questions, not general knowledge answers. Therefore, I do not have that information in front of me.

## 204
Q: How much memory does the PIP backend use while it is idle?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on how much memory the PIP backend uses while it is idle. The documents provided do not contain details about the backend's memory usage during idle periods.

## 205
Q: How many hand-made mutations were caught for the read-only open?
REFERENCE (from docs/FREEZE_LIST.md): `test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run showed it (a folder named for the word asserted, an export test that failed
ANSWER: The documents do not say how many hand-made mutations were caught for the read-only open.

## 206
Q: Where is the interpretation of the end-to-end observer results, including the hand review of the unlabelled rows?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): (the code's default, llama3.1:8b, was not available). Every case on a fresh profile in its first two weeks. Interpretation, including the hand review of the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->
ANSWER: The interpretation, including the hand review of the unlabelled rows, is detailed in the document `docs/FREEZE_LIST.md §7.14`. Specifically, it is part of the section titled "End-to-end Observer measurement - model `qwen2.5:7b`" and covers the results of the three runs conducted on September 28, 2026.

## 207
Q: Which provider is always kept and always passes the Stage 8 gate?
REFERENCE (from docs/FREEZE_LIST.md): endpoint (Ollama down and the only endpoint unconsented, or every endpoint refused). Ollama alone is always kept and always passes the gate, and no route or script adds endpoints yet. It is the same state D-04 was in (§7.21).
ANSWER: Based on the information provided, Ollama is always kept and always passes the Stage 8 gate. The document states that Ollama is local by definition and does not require consent for provider interaction, which aligns with the Stage 8 enforcement boundary.

## 208
Q: Where does onboarding_screen.dart sit compared with sign_in_screen.dart?
REFERENCE (from docs/CONVENTIONS.md): `lib/screens/model_setup_screen.dart`), and no suffix at all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.
ANSWER: I do not have information about the specific placement or relationship between `onboarding_screen.dart` and `sign_in_screen.dart` in the Flutter project. These files are not mentioned in the provided documents, and I do not have a complete picture of the project's structure. If these screens are part of the project, they would typically be located in the `frontend/flutter/lib` directory, but their exact location and how they relate to each other would depend on the project's design and implementation.

## 209
Q: Why did the shortcut choose the first backup of the day over the second?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and restores it. The restored profile lacks the change. - **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last name in `sorted()`, and `-` sorts before `.`. The same rule picks any name sorting after `pip_backup_` over the dated files whatever their age, and
ANSWER: The shortcut does not inherently choose the first backup of the day over the second. According to the document, the shortcut with no `--from` parameter is designed to be used when `data/` contains two or more backups and the newest day has more than one backup. In such a case, the typical behavior is to use the machine that wrote the backups, such as after a lost live password, where the in-app restore is not available. However, the document does not specify a preference for the first backup over the second. Instead, it implies that the user or the system should be able to choose the correct backup, as the newer `.pipbak` file is kept, and the replaced database is retained as `.superseded-<stamp>`.

If there is a specific behavior or rule that dictates choosing the first backup over the second, it is not mentioned in the provided documents. Therefore, based on the information available, there is no indication that the shortcut inherently chooses the first backup of the day over the second.

## 210
Q: In which order should entries be placed in the LOG file?
REFERENCE (from AGENTS.md): ## LOG.md entry format Verbatim, one line per entry, newest first:
ANSWER: Entries in the LOG file should be placed in chronological order, with the newest entries at the top. The main list should keep the newest 25 entries, and older entries should be rolled into an `## Archive` section as summaries of 3-4 lines each.

## 211
Q: What happens in D-20, a restore over a profile with a same-named document?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): 3. **D-20 (Medium, upper end):** a restore over a profile with a same-named document silently takes the wrong document and discards the backup's copy. 4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
ANSWER: In D-20, a restore over a profile that already holds a document of the same name with different bytes, the document in the restored profile will have the wrong content. Specifically, the document's bytes from the backup will overwrite the existing document in the profile, even if the names are the same but the content differs. This results in the user losing the changes made to the document on the new machine before restoring, as the backup's version is used instead.

## 212
Q: Where do the rules in the conventions document come from?
REFERENCE (from docs/CONVENTIONS.md): # Conventions Every rule below is derived from code in this repo, with one example file per rule. Where a convention is applied inconsistently, both forms are named rather
ANSWER: The rules in the conventions document are based on the guidelines provided to ensure accurate and respectful handling of the user's personal information and preferences. These rules are designed to protect the user's privacy and ensure that interactions are helpful and appropriate.

## 213
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: The backend talks to Ollama through `urllib` in `backend/providers/ollama_provider.py`. Even though the `ollama` package is listed in `requirements.txt`, it is not imported directly. Instead, `ollama_provider.py` uses `urllib` to communicate with Ollama's HTTP API.

## 214
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: The frontend has no logic, and `api_client.dart` turns a path plus payload into an HTTP call and the JSON back into a Dart value—no caching, no retries, no client-side validation. The websocket handling, `ws_chat_client.dart`, relays events and reconnects; it decides nothing. Therefore, the websocket's database work cannot be spread over several threads as the frontend does not contain any logic to manage such operations. The decision to avoid spreading database work over threads is documented in the code as a design choice to prevent reintroducing thread-affinity crashes.

## 215
Q: Where do the rules in the conventions document come from?
REFERENCE (from docs/CONVENTIONS.md): # Conventions Every rule below is derived from code in this repo, with one example file per rule. Where a convention is applied inconsistently, both forms are named rather
ANSWER: The rules in the conventions document come from code in this repo, with one example file per rule.

## 216
Q: How many tokens of conversation history does the model remember?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 217
Q: How many conversations can PIP store before it slows down?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 218
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: The lock-gate middleware is registered before the token authentication middleware so that it sits inside it and only ever sees authenticated requests. This ensures that the lock-gate middleware can enforce its rules on top of the authentication layer, meaning it only processes requests that have already passed the token validation.

## 219
Q: What do drain, cancel and cancel_pending_restore_for touch?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): staging's files behind (`restore.py:154-158`, `197-201`). Nothing else looks for `restore-*.tmp.*` files: drain, cancel and `cancel_pending_restore_for` touch only what the current marker names. - **Reachable through the app (backend half measured; the screen half from
ANSWER: `drain`, `cancel`, and `cancel_pending_restore_for` touch only what the current marker names. Specifically, they do not search for `restore-*.tmp.*` files; they only interact with the files and markers that are currently staged for a restore.

## 220
Q: What names are used for a used catch variable in the Flutter code?
REFERENCE (from docs/CONVENTIONS.md): `{"detail": …}` envelope**; screens store `error.toString()` in a nullable `_error` field and render it. → `lib/api_client.dart:17` - **Inconsistent:** a used catch variable is named both `catch (error)` (`lib/screens/decisions_view.dart`) and `catch (e)`
ANSWER: I do not have any specific information about names used for catch variables in the Flutter code for this user. The documents provided do not contain details about the implementation of error handling or catch variables in the Flutter part of the application. If such information exists, it would be in the Flutter codebase, which is not referenced in the provided documents.

## 221
Q: In the end-to-end profile boundary test, what stood in for the model provider?
REFERENCE (from docs/FREEZE_LIST.md): **Patched, and why:** - the model provider, replaced by a recorder, so we see exactly what the model would be sent;
ANSWER: In the end-to-end profile boundary test, the model provider was replaced by a recorder. This change allowed the test to see exactly what the model would be sent.

## 222
Q: Which test case got a sarcastic remark stored as a real preference?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): | retract_deadline | retraction | written decision_log: 1 to ship the beta in may. 0.7 active 2026-09-28t05:57:08z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending | | trap_sarcasm_css | sarcasm | - | - | 0/1 | - | | trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected | | trap_assistant_suggests_zig | assist
ANSWER: The documents do not state which test case got a sarcastic remark stored as a real preference.

## 223
Q: What does _conn() raise for callers that are not routes when the database is locked?
REFERENCE (from docs/ARCHITECTURE.md): - **`_conn()` is a backstop, not the lock.** `LockGateMiddleware` refuses routes while locked; `_conn()` raises `LockedError` for the things that are not routes (background tasks, the WebSocket). Opening the DB with no key would silently create an empty unencrypted file beside the encrypted one, which is
ANSWER: I do not have that in front of me. The context provided does not contain information about the user's projects or any specific codebase or framework they are working with. To answer your question, I would need more details about the context in which _conn() is used and the framework or library it is part of. Could you provide more information about the codebase or the framework you are referring to?

## 224
Q: Where is the interpretation of the end-to-end observer results, including the hand review of the unlabelled rows?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): (the code's default, llama3.1:8b, was not available). Every case on a fresh profile in its first two weeks. Interpretation, including the hand review of the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->
ANSWER: The interpretation, including the hand review of the unlabelled rows, is detailed in the document `docs/eval/observer_end_to_end_2026-09-28.md`. Specifically, it is found in the section of the document that follows the raw output of the `scripts/eval_observer_end_to_end.py` script. This section provides an analysis of the precision and recall metrics, as well as the hand review of the unlabelled rows.

## 225
Q: On how many of the in-app restores did D-01 hold?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - **D-01, on every in-app restore that had a WAL to swap** (10 of 13 at `9968e8c`; the inputs-and-delete control and two staging restores swapped out none, or an empty one). Each of those `pip.db-wal` files held
ANSWER: I do not have information on how many in-app restores D-01 held. The context provided does not contain data regarding the specific occurrences or outcomes of in-app restores related to D-01.

## 226
Q: What does rule 4 of the prompt tell the model to answer?
REFERENCE (from docs/FREEZE_LIST.md): the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):` and then lists only the interaction style. Rule 4 of the same prompt tells the model to answer that it has nothing recorded. - The expected answer is therefore a confident *"you have no project
ANSWER: Rule 4 of the prompt tells the model to answer normally and fully from its own knowledge if the question is not about the user's records. If the question asks for a fact that was not recorded about the user, the model should say it does not have that in front of it and stop.

## 227
Q: Why was the export not re-run end to end from the Backup screen?
REFERENCE (from docs/FREEZE_LIST.md): - **The export itself was not re-run end to end from the Backup screen.** `export_backup.py` asks for both passwords through `getpass`, which reads the console, not a pipe. What stands in: - the launcher's choice, tested through the real wrapper;
ANSWER: The export was not re-run end to end from the Backup screen because the supported migration workflow failed. Specifically, the issue is tracked under D-09, which states that "Close PIP and open it again to finish" does not apply a restore: the launcher reuses the running backend, so the swap waits for an unclean exit, which feeds D-01. This means that the end-to-end re-run through the Backup screen was not met as worded.

## 228
Q: What did all the revisions of the audit specification produce?
REFERENCE (from docs/FREEZE_LIST.md): ### 9.2 Lessons 1. **Planning can become the sideways expansion it was meant to stop.** Ten revisions of the audit spec produced zero evidence; a small test would have produced some in an afternoon. Hence the two-revision cap.
ANSWER: The revisions of the audit specification produced zero evidence. Specifically, the documents state that a small test would have produced some evidence in an afternoon, but ten revisions resulted in no repository evidence.

## 229
Q: What colour is the Unlock button?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I don't have that in front of me.

## 230
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: The lock-gate middleware is registered before the token authentication middleware so that it only ever sees authenticated requests. This order ensures that the lock-gate middleware can enforce its rules based on the assumption that the request has already passed through the token authentication middleware, which verifies the user's authentication status.

## 231
Q: What is wrong with the Welcome back card at the default window size?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): statement. - **D-13:** at the default 1280×720 window, the "Welcome back" card puts Unlock below the fold (screenshot `ui_signin.png`). It scrolls, and Enter submits.
ANSWER: The "Welcome back" card at the default window size has the "Unlock" button positioned below the fold. This means that the button is not visible without scrolling, which could potentially lead to a less intuitive user experience.

## 232
Q: Where do the rules in the conventions document come from?
REFERENCE (from docs/CONVENTIONS.md): # Conventions Every rule below is derived from code in this repo, with one example file per rule. Where a convention is applied inconsistently, both forms are named rather
ANSWER: The rules in the conventions document are derived from the code in this repository. Each rule is based on the consistent practices observed across the files, with examples provided for clarity.

## 233
Q: How many hand-made mutations were caught for the read-only open?
REFERENCE (from docs/FREEZE_LIST.md): `test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run showed it (a folder named for the word asserted, an export test that failed
ANSWER: I do not have that in front of me.

## 234
Q: Which test case got a sarcastic remark stored as a real preference?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): | retract_deadline | retraction | written decision_log: 1 to ship the beta in may. 0.7 active 2026-09-28t05:57:08z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending | | trap_sarcasm_css | sarcasm | - | - | 0/1 | - | | trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected | | trap_assistant_suggests_zig | assist
ANSWER: I do not have that in front of me. The context provided does not contain any specific instances of sarcastic remarks being stored as real preferences. The document mentions that the model identifies sarcasm, but it does not provide examples of this occurrence.

## 235
Q: What does _conn() raise for callers that are not routes when the database is locked?
REFERENCE (from docs/ARCHITECTURE.md): - **`_conn()` is a backstop, not the lock.** `LockGateMiddleware` refuses routes while locked; `_conn()` raises `LockedError` for the things that are not routes (background tasks, the WebSocket). Opening the DB with no key would silently create an empty unencrypted file beside the encrypted one, which is
ANSWER: I do not have information on what _conn() raises for callers that are not routes when the database is locked. The conventions document does not provide this specific detail. You may need to refer to the actual implementation of `_conn()` in `backend/api/server.py` or related files to find the answer.

## 236
Q: Under what condition does launch_pip.ps1 stop a running backend?
REFERENCE (from docs/ARCHITECTURE.md): `backend.api.server` (a bare port number is somebody else's program until proved otherwise) and stops it. `launch_pip.ps1` uses it only when `pending-restore.json` exists, so a staged restore is installed by a new backend's lifespan instead of waiting for a reboot; `restore_pip.ps1` offers it
ANSWER: `launch_pip.ps1` stops a running backend when `pending-restore.json` exists. This condition triggers the installation of a staged restore by a new backend's lifespan instead of waiting for a reboot.

## 237
Q: What happens to the file on disk when a document is deleted?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | D-04 | **High (latent)** | Consent fails open for an endpoint re-saved from local to remote, or registered under the id `ollama`: the full prompt is sent with no consent | | D-05 | Medium | After any restart, until a profile is chosen, the backend serves the unencrypted default slot: a request creates a plaintext `data/pip.db`, and chat typed then is stored in plaintext | | D-06 | Medium | Deleting a document leaves its plaintext file on disk and its content in the database (and so in every later backup) | | D-07 | Medium | A restored document whose original path exists on the target machine is never re-indexed; retrieval is silently empty |
ANSWER: When a document is deleted in PIP, the file on disk is not immediately removed. Instead, the system marks the document as deleted in the database, and the file remains in the `documents/` folder. The user can still access the file through the file system until they choose to delete it permanently. Once the user confirms the deletion, the file is then removed from the `documents/` folder.

## 238
Q: What did the catch-up started by /auth/setup run into at sign-out?
REFERENCE (from docs/FREEZE_LIST.md): **The fourth promise was not in the authorized list.** It was found while fixing the second one. The catch-up started by `/auth/setup` was still running at sign-out, and it hit the new refusal, which was correct. But the next sign-in then skipped its own catch-up because one "was running".
ANSWER: I do not have information about what the catch-up started by /auth/setup ran into at sign-out. The documents provided do not contain details about specific issues or outcomes related to the /auth/setup endpoint during sign-out processes.

## 239
Q: Which restore option is listed as unsupported for the desktop shortcut?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): - In-app export (by design, ADR-027). - Third-party/legacy import. - Restore into a named new profile from the desktop shortcut (it uses the Default slot).
ANSWER: I do not have that in front of me.

## 240
Q: What happens to the next sign-in's catch-up if one is still running?
REFERENCE (from docs/ARCHITECTURE.md): active profile has a salt but no key is held (`IndexLockedError`) instead of falling back to plaintext. And the next sign-in's catch-up is queued behind any still running rather than skipped. All three were measured through the real routes (FREEZE_LIST §7.8) and are pinned by
ANSWER: The documents you provided do not state what happens to the next sign-in's catch-up if one is still running.

## 241
Q: What is the PIP project's budget?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have any information about the PIP project's budget in front of me.

## 242
Q: What did Yara's Backup screen show after she signed in, and with whose file name?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): - Zed stages a restore and signs out. Yara signs in: the status route gives her `{"pending": true, "source": "export-1.pipbak", ...}`, which her Backup screen shows as "Ready to restore on the next start" for this profile (`backup_view.dart:514-555`), with Zed's file name. Her
ANSWER: I do not have that information in front of me.

## 243
Q: What is wrong with the Welcome back card at the default window size?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): statement. - **D-13:** at the default 1280×720 window, the "Welcome back" card puts Unlock below the fold (screenshot `ui_signin.png`). It scrolls, and Enter submits.
ANSWER: I do not have information about the Welcome back card at the default window size in front of me. Could you provide more details or describe the issue you are encountering?

## 244
Q: What could an unisolated salt path in the tests have done to the real database?
REFERENCE (from docs/FREEZE_LIST.md): - **Tests never touch real data.** Every `PIP_*` path isolated in `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have made the real database permanently unopenable. - **Measure a flake before believing it.** Compare against a pinned
ANSWER: The context does not provide specific details on what an unisolated salt path in the tests could have done to the real database. The information given focuses on the testing setup and outcomes, particularly how the tests are structured to handle different scenarios with the export launcher and the export backup process. Without additional details about potential impacts or outcomes, I cannot provide a specific answer.

## 245
Q: What does the log say on every sign-in when a document cannot be re-indexed?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): a path outside this profile's documents folder. - The failure is only collected into a return value; the log says "rebuilding" on every sign-in. The index stayed empty after 55 s, while the Documents screen lists the document.
ANSWER: I do not have that in front of me.

## 246
Q: In the end-to-end profile boundary test, what stood in for the model provider?
REFERENCE (from docs/FREEZE_LIST.md): **Patched, and why:** - the model provider, replaced by a recorder, so we see exactly what the model would be sent;
ANSWER: I do not have that in front of me.

## 247
Q: What did the catch-up started by /auth/setup run into at sign-out?
REFERENCE (from docs/FREEZE_LIST.md): **The fourth promise was not in the authorized list.** It was found while fixing the second one. The catch-up started by `/auth/setup` was still running at sign-out, and it hit the new refusal, which was correct. But the next sign-in then skipped its own catch-up because one "was running".
ANSWER: The catch-up started by `/auth/setup` at sign-out ran into the issue that the connection, which was already open at the time of sign-out, could still answer questions from the user's profile's database, even though it could no longer exchange cached answers with other sessions through the cache. This is documented under the limitations of Promise 8, as noted in the evidence hierarchy and the Consent locality fix, D-04.

## 248
Q: What happens to the file on disk when a document is deleted?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | D-04 | **High (latent)** | Consent fails open for an endpoint re-saved from local to remote, or registered under the id `ollama`: the full prompt is sent with no consent | | D-05 | Medium | After any restart, until a profile is chosen, the backend serves the unencrypted default slot: a request creates a plaintext `data/pip.db`, and chat typed then is stored in plaintext | | D-06 | Medium | Deleting a document leaves its plaintext file on disk and its content in the database (and so in every later backup) | | D-07 | Medium | A restored document whose original path exists on the target machine is never re-indexed; retrieval is silently empty |
ANSWER: I do not have information on what happens to the file on disk when a document is deleted in this user's setup. The documents and records I have do not specify the behavior of file deletion on disk.

## 249
Q: Where does onboarding_screen.dart sit compared with sign_in_screen.dart?
REFERENCE (from docs/CONVENTIONS.md): `lib/screens/model_setup_screen.dart`), and no suffix at all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.
ANSWER: I do not have information about the specific placement or relationship between `onboarding_screen.dart` and `sign_in_screen.dart` in the Flutter project. These files are part of the frontend Flutter application, but I do not have details on their hierarchy or how they interact within the application's structure. If you need this information, you might want to check the project's directory structure or the relevant documentation.

## 250
Q: What fix was recommended for D-20 in _install?
REFERENCE (from docs/FREEZE_LIST.md): requires. Open the chosen file read-only. - **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/` aside with the database in `_install`, under the same stamp and undo list.
ANSWER: The fix for D-20 in _install involved not swapping `documents/` and `chroma/` directories during a restore over a profile with a same-named document. Instead, `materialise_documents` should repoint a record to the backup's file rather than writing the backup's bytes, as the backup's text might be newer than the backup's. This ensures that the backup's document is used, and the replaced profile's same-named document is not overwritten by the restore process.

## 251
Q: In the Flutter screens how can you tell data has not been fetched yet?
REFERENCE (from docs/CONVENTIONS.md): → `lib/screens/decisions_view.dart` - **Data is fetched in `initState()` and stored in a nullable field; `null` means "not loaded yet", an empty list means "loaded, nothing there".** The build method branches on that. → `lib/screens/decisions_view.dart:53`
ANSWER: I do not have information about specific UI elements or states in the Flutter screens from the provided context. The documents focus on the backend and some general stack details but do not detail the UI or how data fetching is indicated on the Flutter screens. Could you provide more context or details about the screens you are referring to?

## 252
Q: What names are used for a used catch variable in the Flutter code?
REFERENCE (from docs/CONVENTIONS.md): `{"detail": …}` envelope**; screens store `error.toString()` in a nullable `_error` field and render it. → `lib/api_client.dart:17` - **Inconsistent:** a used catch variable is named both `catch (error)` (`lib/screens/decisions_view.dart`) and `catch (e)`
ANSWER: I don't have that in front of me.

## 253
Q: Why was the export not re-run end to end from the Backup screen?
REFERENCE (from docs/FREEZE_LIST.md): - **The export itself was not re-run end to end from the Backup screen.** `export_backup.py` asks for both passwords through `getpass`, which reads the console, not a pipe. What stands in: - the launcher's choice, tested through the real wrapper;
ANSWER: I don't have that in front of me. Could you provide more details about the situation? When did you attempt to re-run the export, and what happened exactly?

## 254
Q: In the end-to-end profile boundary test, what stood in for the model provider?
REFERENCE (from docs/FREEZE_LIST.md): **Patched, and why:** - the model provider, replaced by a recorder, so we see exactly what the model would be sent;
ANSWER: In the end-to-end profile boundary test, the model provider was replaced by a recorder. This allowed the test to see exactly what the model would be sent.

## 255
Q: Which restore option is listed as unsupported for the desktop shortcut?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): - In-app export (by design, ADR-027). - Third-party/legacy import. - Restore into a named new profile from the desktop shortcut (it uses the Default slot).
ANSWER: The restore option that is listed as unsupported for the desktop shortcut is the "Restore into a named new profile from the desktop shortcut (it uses the Default slot)."

## 256
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: I do not have information about which folders the pre-commit import guard checks. The pre-commit import guard is related to code formatting and linting, but without specific details about the user's setup or the context of their use, I cannot provide accurate information.

## 257
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: The migration re-run made checks for five new defects, and all of them failed. These defects are listed as follows:

- D-18: Medium severity, an empty file is accepted as a backup.
- D-20: Medium (upper end) severity, an in-app restore overwrites an existing document.
- D-21: Medium (low end) severity, the desktop shortcut restores the older backup.
- D-17: Low (upper) severity, an export taken while the app is committing rows fails verification.
- D-19: Low severity, staged-restore state is not isolated per installation.

Each of these defects failed the checks during the re-run.

## 258
Q: How many conversations can PIP store before it slows down?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on how many conversations PIP can store before it slows down. The context provided does not contain details about PIP's storage limits or performance thresholds related to the number of conversations.

## 259
Q: What is the maximum length of a PIP password?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 260
Q: What happens in D-20, a restore over a profile with a same-named document?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): 3. **D-20 (Medium, upper end):** a restore over a profile with a same-named document silently takes the wrong document and discards the backup's copy. 4. **D-21 (Medium, low end)** on the shortcut, and **D-17 (Low, upper)** on
ANSWER: In D-20, a restore over a profile that already holds a document of the same name but with different bytes, the system will overwrite the existing document with the one from the backup. This results in the loss of the original document's content, even if it had different bytes. The restore process does not preserve the original document's content in this scenario.

## 261
Q: What recall did the observer reach in run two?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 9/10 (90%) - **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: In run two, the recall of the observer was 9 out of 23 stated facts learned, which is approximately 39%.

## 262
Q: Which provider is always kept and always passes the Stage 8 gate?
REFERENCE (from docs/FREEZE_LIST.md): endpoint (Ollama down and the only endpoint unconsented, or every endpoint refused). Ollama alone is always kept and always passes the gate, and no route or script adds endpoints yet. It is the same state D-04 was in (§7.21).
ANSWER: The documents do not specify which provider is always kept and always passes the Stage 8 gate. The information provided focuses on the enforcement of provider consent and the behavior of unknown or non-local providers, but does not detail a provider that is exempt from the gate.

## 263
Q: Which provider is always kept and always passes the Stage 8 gate?
REFERENCE (from docs/FREEZE_LIST.md): endpoint (Ollama down and the only endpoint unconsented, or every endpoint refused). Ollama alone is always kept and always passes the gate, and no route or script adds endpoints yet. It is the same state D-04 was in (§7.21).
ANSWER: The document does not specify a provider that is always kept and always passes the Stage 8 gate. The enforcement boundary for Stage 8 covers unknown providers by refusing them, and the document does not indicate any provider that is exempt from this rule. If there is a specific provider that is always kept and passes the gate, it would need to be explicitly stated or demonstrated in the document.

## 264
Q: Which graphics card was in the machine used for the validation?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): (`VerifiedAndReputablePolicyState = 1`). - Python 3.12.10 (`.venv`), Flutter 3.44.2, Ollama 0.32.14 on an RTX 4060 Laptop GPU (8 GB). Live model `qwen2.5:7b`; `llama3.1:8b` and `phi3:mini` are also pulled.
ANSWER: I do not have information about the graphics card used for the validation in front of me.

## 265
Q: What number of key derivation iterations is actually used in the code?
REFERENCE (from docs/CONVENTIONS.md): `DEFAULT_MODEL_NAME`), and the whole `performance_targets` and `database` blocks. `database.kdf_iterations` is duplicated as a constant in `backend/core/db_key.py:42` (`KDF_ITERATIONS = 256_000`), which is the value that is actually used.
ANSWER: I do not have that information in front of me. The code or relevant documentation that details the number of key derivation iterations was not provided in the context.

## 266
Q: What fix was recommended for D-20 in _install?
REFERENCE (from docs/FREEZE_LIST.md): requires. Open the chosen file read-only. - **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/` aside with the database in `_install`, under the same stamp and undo list.
ANSWER: The fix for D-20 in _install involved not swapping `documents/` and `materialise_documents` repointing a record to a same-named file rather than writing the backup's bytes. The backup's text was not retrieved, and the replaced profile's same-named document was taken over. The first sign-in's re-ingest then overwrote the restored blob, so the backup's copy was lost.

## 267
Q: Were there uncommitted changes in the repository when the validation ran?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): ## 2. Revision and environment - Revision `f66a309` on `frontend_fix`, no tracked changes. - Windows 11 Home 10.0.26200, **Smart App Control on**
ANSWER: Based on the documents provided, there were no uncommitted changes in the repository when the validation runs were conducted. The runs were performed from pinned commits, and the harness now builds from a pinned commit, ensuring that the validation is based on stable, committed code.

## 268
Q: What does shared/ws_spec.py contain?
REFERENCE (from docs/ARCHITECTURE.md): `shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire events, imported by the stage that produces them, the pipeline that relays them, and the server that forwards them.
ANSWER: The document you provided does not contain any specific details about the contents of `shared/ws_spec.py`. It only mentions that the file's header explicitly states that introducing Pydantic in this file would be an inconsistency rather than an improvement, and that structured shapes are `TypedDict`, not Pydantic. Therefore, I do not have information about the actual content of `shared/ws_spec.py` in front of me.

## 269
Q: What is the expected style for code comments in this project?
REFERENCE (from docs/CONVENTIONS.md): code**, whether it was found live or by inspection, what was tried first, and what limitation remains. This is the house style, not noise — terse code reads as out of place here. → `backend/core/pinned_executor.py` (45 lines of reasoning before the first import), `frontend/flutter/pubspec.yaml`
ANSWER: I do not have that information in front of me.

## 270
Q: Where is the interpretation of the end-to-end observer results, including the hand review of the unlabelled rows?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): (the code's default, llama3.1:8b, was not available). Every case on a fresh profile in its first two weeks. Interpretation, including the hand review of the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->
ANSWER: The interpretation, including the hand review of the unlabelled rows, is detailed in the document `docs/FREEZE_LIST.md §7.14`. Specifically, it is part of the end-to-end Observer measurement results for the model `qwen2.5:7b` run on 2026-09-28.

## 271
Q: How many revisions of a plan are allowed before building a small version?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.4 Process - **Freeze features while promises are unverified.** - **Cap planning at two revisions.** If a spec needs a third, run a small version and let the result correct it (see §9, lesson 1).
ANSWER: According to the context, a plan can be revised up to two times before building a small version. If a third revision is needed, a small version should be run to correct it.

## 272
Q: Why did the shortcut choose the first backup of the day over the second?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and restores it. The restored profile lacks the change. - **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last name in `sorted()`, and `-` sorts before `.`. The same rule picks any name sorting after `pip_backup_` over the dated files whatever their age, and
ANSWER: The shortcut chose the first backup of the day over the second because the function `newest_backup()` in `restore_backup.py` sorts the backup files lexicographically. In this sorting method, the name `-2` sorts before `20261003`, which in turn sorts before `20261003-2`. Therefore, when the backups are sorted and the newest one is selected, the first backup `pip_backup_20261003.pipbak` is chosen over the second `pip_backup_20261003-2.pipbak`.

## 273
Q: What names are used for a used catch variable in the Flutter code?
REFERENCE (from docs/CONVENTIONS.md): `{"detail": …}` envelope**; screens store `error.toString()` in a nullable `_error` field and render it. → `lib/api_client.dart:17` - **Inconsistent:** a used catch variable is named both `catch (error)` (`lib/screens/decisions_view.dart`) and `catch (e)`
ANSWER: I do not have information on specific names used for catch variables in the Flutter code for this user's project. The Flutter codebase does not contain any recorded instances of catch variables being used, so I cannot provide any names based on the available records.
