# Grading sheet

Label each answer: CORRECT, DECLINES, WRONG or VAGUE (definitions in docs/eval/retrieval_e2e_protocol_2026-10-08.json).
The condition and the retrieved passages are not shown.

## 1
Q: What could an unisolated salt path in the tests have done to the real database?
REFERENCE (from docs/FREEZE_LIST.md): - **Tests never touch real data.** Every `PIP_*` path isolated in `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have made the real database permanently unopenable. - **Measure a flake before believing it.** Compare against a pinned
ANSWER: I do not have information about the user's projects or any context related to tests involving unisolated salt paths and their effects on real databases. Could you provide more details about the specific scenario or project you are referring to?

## 2
Q: Why does format_transcript indent lines that start with a role name?
REFERENCE (from docs/ARCHITECTURE.md): `Assistant:`, because `EvidenceLedger` parses those headers back out to decide who said a quote. Without the escaping, an assistant reply containing a line `User: I prefer Flask` parses back as a genuine user turn. - **The trace logs message length, never message text.** The original reason
ANSWER: I do not have the specific details of why the `format_transcript` function indents lines that start with a role name in front of me. Could you provide more context or information about this function?

## 3
Q: How many cases were in the end-to-end observer test set?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): ## Run 1 - cases: 37 (0 errored), total model time 197.9s - funnel: 31 candidates extracted by the model, 30 survived grounding
ANSWER: The end-to-end observer test set contained 37 cases.

## 4
Q: What is the maximum number of documents a person can upload to PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me. The context provided does not contain details about the maximum number of documents a person can upload to PIP.

## 5
Q: Which local model answered the chat turns during the journey?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): `restore_backup.py`, both with `--from --yes` and as the shortcut runs it (no arguments, typed `yes`); - **chat:** `/ws/chat` with a live local model (Ollama, `qwen2.5:7b`).
ANSWER: I do not have that in front of me.

## 6
Q: Why was qwen used for the observer measurement and not the default model?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): <!-- Raw output of scripts/eval_observer_end_to_end.py --repeat 3, 2026-09-28. Labels: backend/tests/observer_cases.py as committed in 1256b51, before this run. Model: qwen2.5:7b through Ollama 0.32.14 - the only model pulled on the machine (the code's default, llama3.1:8b, was not available). Every case on a fresh
ANSWER: The model `qwen2.5:7b` was used for the observer measurement because it was the only model pulled on the machine at the time, with the code's default model `llama3.1:8b` not being available.

## 7
Q: What did all the revisions of the audit specification produce?
REFERENCE (from docs/FREEZE_LIST.md): ### 9.2 Lessons 1. **Planning can become the sideways expansion it was meant to stop.** Ten revisions of the audit spec produced zero evidence; a small test would have produced some in an afternoon. Hence the two-revision cap.
ANSWER: I do not have information on the revisions of the audit specification in front of me.

## 8
Q: What is wrong with staged restore state being shared across profiles?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | D-21 | Medium (low end) | The desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used" | | D-17 | Low (upper) | An export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list | | D-19 | Low | Staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's: one profile can cancel another's restore, and an orphaned staged copy survives its profile's deletion |
ANSWER: The issue with staged restore state being shared across profiles is that it could lead to a situation where a restore intended for one profile mistakenly overwrites the data of another profile. Specifically, if a profile is deleted and a restore is staged for it, the staged restore should be canceled to prevent any data from being installed into the deleted profile's place. If the staged restore state were shared, a restore for one profile could potentially interfere with the delete operation of another profile, leading to data corruption or loss. This is why the mechanism ensures that the staged restore is canceled specifically for the profile being deleted, leaving other profiles' staged restores untouched.

## 9
Q: What happens to the file on disk when a document is deleted?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | D-04 | **High (latent)** | Consent fails open for an endpoint re-saved from local to remote, or registered under the id `ollama`: the full prompt is sent with no consent | | D-05 | Medium | After any restart, until a profile is chosen, the backend serves the unencrypted default slot: a request creates a plaintext `data/pip.db`, and chat typed then is stored in plaintext | | D-06 | Medium | Deleting a document leaves its plaintext file on disk and its content in the database (and so in every later backup) | | D-07 | Medium | A restored document whose original path exists on the target machine is never re-indexed; retrieval is silently empty |
ANSWER: When a document is deleted in PIP, the file on disk is not immediately removed. Instead, the system marks the document as deleted in the database, and the file remains on the disk until the profile's `data/` folder is cleaned up or the document is explicitly removed. This behavior ensures that the user can recover the document if needed, without losing the file on disk.

## 10
Q: In which order should entries be placed in the LOG file?
REFERENCE (from AGENTS.md): ## LOG.md entry format Verbatim, one line per entry, newest first:
ANSWER: Entries in the LOG file should be placed in chronological order, with the newest entries at the top. The main list should contain the newest 25 entries, and any older entries should be rolled into an `## Archive` section as summaries.

## 11
Q: How many REST method and path pairs refused bad credentials?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): PIP's security boundaries mostly hold when measured from outside. All 64 REST method+path pairs refuse bad credentials, every gated route refuses while locked, the WebSocket checks its token and origin, profiles stay
ANSWER: According to the document, all 64 REST method+path pairs refused bad credentials.

## 12
Q: How long may the AGENTS.md file be, and is that rule enforced?
REFERENCE (from docs/CONVENTIONS.md): ## Docs - **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.** It is loaded into an agent's context before every session, so its length is
ANSWER: The AGENTS.md file has a line count cap enforced by the `scripts/pre-commit` hook. According to the document `docs/CONVENTIONS.md`, the file must not exceed the line count limit specified by this hook, which is verified using `wc -l`. If the staged changes in AGENTS.md exceed the cap, the pre-commit hook will reject the commit.

## 13
Q: How many revisions of a plan are allowed before building a small version?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.4 Process - **Freeze features while promises are unverified.** - **Cap planning at two revisions.** If a spec needs a third, run a small version and let the result correct it (see §9, lesson 1).
ANSWER: I do not have that in front of me. The number of revisions allowed before building a small version of a plan can vary depending on the specific context and guidelines of the project. Could you provide more details about the project or the context in which this question arises?

## 14
Q: What did all the revisions of the audit specification produce?
REFERENCE (from docs/FREEZE_LIST.md): ### 9.2 Lessons 1. **Planning can become the sideways expansion it was meant to stop.** Ten revisions of the audit spec produced zero evidence; a small test would have produced some in an afternoon. Hence the two-revision cap.
ANSWER: The revisions of the audit specification produced zero evidence. Despite ten revisions, no tangible results were achieved, and a small test could have produced some evidence in an afternoon.

## 15
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: I do not have information on how the backend talks to Ollama if the ollama package is never imported. The context provided does not contain details about the backend's communication methods or the presence or absence of the ollama package in the codebase.

## 16
Q: Which test case got a sarcastic remark stored as a real preference?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): | retract_deadline | retraction | written decision_log: 1 to ship the beta in may. 0.7 active 2026-09-28t05:57:08z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending | | trap_sarcasm_css | sarcasm | - | - | 0/1 | - | | trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected | | trap_assistant_suggests_zig | assist
ANSWER: I do not have any recorded preferences for test cases or any sarcastic remarks in front of me.

## 17
Q: Which graphics card was in the machine used for the validation?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): (`VerifiedAndReputablePolicyState = 1`). - Python 3.12.10 (`.venv`), Flutter 3.44.2, Ollama 0.32.14 on an RTX 4060 Laptop GPU (8 GB). Live model `qwen2.5:7b`; `llama3.1:8b` and `phi3:mini` are also pulled.
ANSWER: I do not have information about the graphics card used in the validation machine in front of me.

## 18
Q: What happens to a conversation whose process was killed before the memory step ran?
REFERENCE (from docs/ARCHITECTURE.md): idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for a killed process, rebuilt at the next startup from `conversations` /`messages` where `observed_at IS NULL`. Catch-up drains in a background task, never inline before serving. Every sign-in gets its own: one still running from a previous
ANSWER: I do not have in front of me information about what happens to a conversation whose process was killed before the memory step ran.

## 19
Q: Why did the shortcut choose the first backup of the day over the second?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and restores it. The restored profile lacks the change. - **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last name in `sorted()`, and `-` sorts before `.`. The same rule picks any name sorting after `pip_backup_` over the dated files whatever their age, and
ANSWER: The shortcut does not inherently choose the first backup of the day over the second. According to the document, the shortcut with no `--from` parameter is designed to be used when `data/` contains two or more backups and the newest day has more than one backup. In such a case, the typical scenario is that the machine wrote the backups, for example after a lost live password, and the in-app restore is not available. The shortcut is meant to prompt the user to select the correct backup from the available options, not to automatically choose one.

If the document does not specify a default selection mechanism, it is likely that the user would be prompted to choose which backup to use. If there is a specific behavior where the first backup is chosen, it would need to be explicitly defined or implemented in the code. Based on the information provided, there is no indication that the shortcut automatically selects the first backup of the day.

## 20
Q: How many backend test files have their own local conn fixture?
REFERENCE (from docs/CONVENTIONS.md): a visible omission. Adding a new `PIP_*` path override means adding it here. → `backend/tests/conftest.py:17` - **Inconsistent:** 16 of 67 backend test files define their own local `conn` fixture (`sqlite3.connect(tmp_path / "pip.db")` + `initialize_schema`) instead
ANSWER: I do not have that information in front of me.

## 21
Q: What did the Backup screen say about an empty zero byte backup file?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | ID | Severity | One line | |---|---|---| | D-18 | Medium | An empty (0-byte) file is accepted as a backup ("0 rows across 0 tables, checked and ready"), and at the next backend start the profile is replaced by an empty one. A backup is checked only against itself, so a part-written export passes too | | D-20 | Medium (upper end) | An in-app restore over a profile that already has a document of the same name takes that file instead of the backup's, and the first sign-in overwrites the backup's copy with it |
ANSWER: The Backup screen would say "empty.pipbak - 0 rows across 0 tables, checked and ready. Close PIP and open it again to finish."

## 22
Q: What email address do I contact for PIP support?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have an email address for PIP support in front of me.

## 23
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: I do not have that information in front of me.

## 24
Q: What did the Backup screen say about an empty zero byte backup file?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | ID | Severity | One line | |---|---|---| | D-18 | Medium | An empty (0-byte) file is accepted as a backup ("0 rows across 0 tables, checked and ready"), and at the next backend start the profile is replaced by an empty one. A backup is checked only against itself, so a part-written export passes too | | D-20 | Medium (upper end) | An in-app restore over a profile that already has a document of the same name takes that file instead of the backup's, and the first sign-in overwrites the backup's copy with it |
ANSWER: The Backup screen would say "empty.pipbak - 0 rows across 0 tables, checked and ready. Close PIP and open it again to finish."

## 25
Q: Which open-source licence is PIP released under?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 26
Q: Is there an Android version of PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on an Android version of PIP in front of me.

## 27
Q: Is there an Android version of PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on an Android version of PIP in front of me.

## 28
Q: What could an unisolated salt path in the tests have done to the real database?
REFERENCE (from docs/FREEZE_LIST.md): - **Tests never touch real data.** Every `PIP_*` path isolated in `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have made the real database permanently unopenable. - **Measure a flake before believing it.** Compare against a pinned
ANSWER: The context does not provide specific details on what an unisolated salt path in the tests could have done to the real database. The information given focuses on the testing setup and outcomes, particularly how the tests handle the `export_backup.py` script and the behavior of the `Resolve-PipLastProfile` function under different conditions. Without additional context about potential impacts on the real database, I cannot make assumptions or provide specific scenarios.

## 29
Q: What number of key derivation iterations is actually used in the code?
REFERENCE (from docs/CONVENTIONS.md): `DEFAULT_MODEL_NAME`), and the whole `performance_targets` and `database` blocks. `database.kdf_iterations` is duplicated as a constant in `backend/core/db_key.py:42` (`KDF_ITERATIONS = 256_000`), which is the value that is actually used.
ANSWER: I do not have that information in front of me. Could you provide more context or details about the code you are referring to?

## 30
Q: Which graphics card does PIP require?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on which graphics card PIP requires. The documents provided do not mention specific hardware requirements for PIP, including graphics cards.

## 31
Q: How many people use PIP today?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 32
Q: Why were no retrieval quality results claimed in the validation pass?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): embedder (`harness/pip_embed_shim.py`): a deterministic hashed bag-of-words, not all-MiniLM. **Any result about retrieval quality is invalid under it**, and none is claimed.
ANSWER: I do not have any information about the validation pass or retrieval quality results in front of me for this user.

## 33
Q: What should the system do when Ollama is down?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.3 Standing rules - **Fail closed.** Unknown provider, missing key, Ollama down → refuse and queue. Never fall back to something less safe. - **One source of truth per rule.** A policy in both JSON and code means
ANSWER: When Ollama is down, the system should continue to operate using local data and cached information if available. If no local data is available, the system should inform the user that Ollama is currently unavailable and suggest alternative actions or provide fallback information where possible.

## 34
Q: Why were no retrieval quality results claimed in the validation pass?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): embedder (`harness/pip_embed_shim.py`): a deterministic hashed bag-of-words, not all-MiniLM. **Any result about retrieval quality is invalid under it**, and none is claimed.
ANSWER: I do not have any information about retrieval quality results in the provided context. The documents and records focus on project stages, tests, and preferences, but do not mention retrieval quality or validation passes related to retrieval.

## 35
Q: How many false rejects did the evidence gate have on the held-out set?
REFERENCE (from docs/ARCHITECTURE.md): queue. The reverse arrangement would pay for the same coverage in false *accepts* — beliefs written into the profile that the user never expressed. Measured cost on a held-out set: 1 false reject in 15 supported statements, 0 false accepts. `scripts/eval_evidence_gate.py` prints the numbers.
ANSWER: The evidence gate had one held-out false reject, labeled `held_accept_tool_habit`.

## 36
Q: How many cases were in the end-to-end observer test set?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): ## Run 1 - cases: 37 (0 errored), total model time 197.9s - funnel: 31 candidates extracted by the model, 30 survived grounding
ANSWER: The end-to-end observer test set contained 37 cases.

## 37
Q: What precision did the observer reach in its first run?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - Stage 13: {'written': 3, 'rejected': 22, 'pending': 5} - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5
ANSWER: In the first run, the precision reached by the observer was 89%. This means out of the 9 rows that were marked as either TRUE or TRAP, 8 were correctly identified as TRUE.

## 38
Q: After a new test passes, what must you do to be sure it proves anything?
REFERENCE (from docs/FREEZE_LIST.md): files. Not "the function returned REJECT". 3. **Break it once by hand.** Weaken the guard, confirm the test fails, restore the guard. A test never seen failing proves nothing. 4. **Make the smallest change that passes.** No cleanup riding along.
ANSWER: To ensure that a new test proves anything, you must verify that the test is correctly measuring the intended functionality or behavior. This involves several steps:

1. **Test Design**: Ensure the test is well-designed to cover the specific functionality or behavior you are testing. The test should be clear and unambiguous.

2. **Test Environment**: Confirm that the test is run in an environment that is consistent and free from external factors that could influence the outcome.

3. **Test Execution**: Run the test and observe the results. Ensure the test passes or fails as expected based on the requirements or expected behavior.

4. **Test Coverage**: Check that the test covers all relevant aspects of the functionality. There should be no gaps in the test coverage.

5. **Test Documentation**: Document the test case, including the steps, expected results, and actual results. This documentation helps in understanding the test and its outcome.

6. **Review and Validation**: Have the test reviewed by peers or stakeholders to ensure its validity and correctness. This can help catch any overlooked issues.

7. **Regression Testing**: If the test is part of a larger system, ensure that it does not break other functionalities. Run regression tests to confirm that the new test does not introduce any unintended side effects.

By following these steps, you can be more confident that the ne [CUT: answer longer than the sheet shows]

## 39
Q: Why did the shortcut choose the first backup of the day over the second?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and restores it. The restored profile lacks the change. - **Cause.** `newest_backup()` (`restore_backup.py:141-145`) takes the last name in `sorted()`, and `-` sorts before `.`. The same rule picks any name sorting after `pip_backup_` over the dated files whatever their age, and
ANSWER: I do not have that information in front of me. Could you provide more details about the context or the specific shortcut you are referring to?

## 40
Q: What happens to the file on disk when a document is deleted?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | D-04 | **High (latent)** | Consent fails open for an endpoint re-saved from local to remote, or registered under the id `ollama`: the full prompt is sent with no consent | | D-05 | Medium | After any restart, until a profile is chosen, the backend serves the unencrypted default slot: a request creates a plaintext `data/pip.db`, and chat typed then is stored in plaintext | | D-06 | Medium | Deleting a document leaves its plaintext file on disk and its content in the database (and so in every later backup) | | D-07 | Medium | A restored document whose original path exists on the target machine is never re-indexed; retrieval is silently empty |
ANSWER: When a document is deleted, the file on disk is typically marked as available for overwriting by the operating system. The actual data may remain until the space is needed for new files, at which point the system may write new data over the old file's location. The file's metadata, such as its name and location, is removed from the file system's directory structure. However, the data may still be recoverable using specialized software until it is overwritten.

## 41
Q: Why was qwen used for the observer measurement and not the default model?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): <!-- Raw output of scripts/eval_observer_end_to_end.py --repeat 3, 2026-09-28. Labels: backend/tests/observer_cases.py as committed in 1256b51, before this run. Model: qwen2.5:7b through Ollama 0.32.14 - the only model pulled on the machine (the code's default, llama3.1:8b, was not available). Every case on a fresh
ANSWER: I do not have information about why qwen was used for the observer measurement and not the default model. The context provided does not contain any details about the specific projects or decisions related to model selection.

## 42
Q: What is the expected style for code comments in this project?
REFERENCE (from docs/CONVENTIONS.md): code**, whether it was found live or by inspection, what was tried first, and what limitation remains. This is the house style, not noise — terse code reads as out of place here. → `backend/core/pinned_executor.py` (45 lines of reasoning before the first import), `frontend/flutter/pubspec.yaml`
ANSWER: I do not have that information in front of me for this project.

## 43
Q: Why was fine tuning rejected as a way to stop the model fabricating?
REFERENCE (from docs/FREEZE_LIST.md): - **Fine-tuning rejected as a fabrication fix.** The bug was deterministic (misleading context); training teaches tendencies, and the only corpus was the contaminated history. A smaller stock Observer model
ANSWER: I do not have information about why fine tuning was rejected as a way to stop the model from fabricating. I do not have any records related to the user's projects or decisions regarding model training methods.

## 44
Q: Which cloud storage service does PIP back up to automatically?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have any information on which cloud storage service PIP backs up to automatically. The context provided does not contain details about automatic backup services or configurations.

## 45
Q: What share of stated facts did the observer learn in run one?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: I do not have the information about the share of stated facts the observer learned in run one in front of me.

## 46
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: The lock-gate middleware is registered before the token authentication middleware so that it only ever sees authenticated requests. This ensures that the lock-gate middleware can enforce its rules based on the assumption that the request is already authenticated, as it would be after passing through the token authentication middleware.

## 47
Q: How many people work on the PIP project?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 48
Q: What happens to a conversation whose process was killed before the memory step ran?
REFERENCE (from docs/ARCHITECTURE.md): idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for a killed process, rebuilt at the next startup from `conversations` /`messages` where `observed_at IS NULL`. Catch-up drains in a background task, never inline before serving. Every sign-in gets its own: one still running from a previous
ANSWER: I do not have any information about what happens to a conversation whose process was killed before the memory step ran. The context provided does not contain details about such a scenario or the handling of conversations in that specific state.

## 49
Q: On what date will PIP be released to the public?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have a release date for PIP being made public in front of me.

## 50
Q: What precision did the observer reach in its first run?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - Stage 13: {'written': 3, 'rejected': 22, 'pending': 5} - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5
ANSWER: I do not have that information in front of me.

## 51
Q: Does PIP support voice input?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP supports voice input.

## 52
Q: What is the governing principle of the reliability plan?
REFERENCE (from docs/FREEZE_LIST.md): ## 1. Governing principle > **Constrain the mechanism; do not merely restate the intent.**
ANSWER: I do not have information about the governing principle of the reliability plan for this user in front of me.

## 53
Q: In the Flutter screens how can you tell data has not been fetched yet?
REFERENCE (from docs/CONVENTIONS.md): → `lib/screens/decisions_view.dart` - **Data is fetched in `initState()` and stored in a nullable field; `null` means "not loaded yet", an empty list means "loaded, nothing there".** The build method branches on that. → `lib/screens/decisions_view.dart:53`
ANSWER: In Flutter, you can indicate that data has not been fetched yet by using various UI elements and techniques. Here are some common methods:

1. **Loading Indicator**: Display a loading spinner or a progress bar to show that the data is being fetched.
2. **Placeholder Text**: Use placeholder text or a message like "Loading..." to inform the user that data is being fetched.
3. **Shimmer Effect**: Implement a shimmer effect to show a placeholder layout that mimics the final UI, giving the impression that the data is being loaded.
4. **Visibility of Widgets**: Initially hide the widgets that will display the fetched data and show them once the data is available.

Here is a simple example using a `CircularProgressIndicator` to show that data is being fetched:

```dart
import 'package:flutter/material.dart';

class DataFetchingScreen extends StatefulWidget {
  @override
  _DataFetchingScreenState createState() => _DataFetchingScreenState();
}

class _DataFetchingScreenState extends State<DataFetchingScreen> {
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    // Simulate data fetching
    Future.delayed(Duration(seconds: 2), () {
      setState(() {
        _isLoading = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Data Fetching Example'),
      ),
    [CUT: answer longer than the sheet shows]

## 54
Q: How many cases were in the end-to-end observer test set?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): ## Run 1 - cases: 37 (0 errored), total model time 197.9s - funnel: 31 candidates extracted by the model, 30 survived grounding
ANSWER: I do not have that information in front of me.

## 55
Q: Was the exit criterion for the migration met?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and so does carrying on from the layout it creates. **The exit criterion is not met as worded** (§9). "Close PIP and open it again", the restart the app asks for, does not apply a restore (D-09, open),
ANSWER: I do not have that in front of me.

## 56
Q: What is wrong with staged restore state being shared across profiles?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | D-21 | Medium (low end) | The desktop shortcut, given two backups from one day, restores the older while saying "the newest will be used" | | D-17 | Low (upper) | An export taken while the app is committing rows fails verification, and the launcher says "Nothing was written" while a valid backup is left, unmarked, at the top of the Backups list | | D-19 | Low | Staged-restore state is one per installation but is shown, cancelled and replaced as the signed-in profile's: one profile can cancel another's restore, and an orphaned staged copy survives its profile's deletion |
ANSWER: The issue with staged restore state being shared across profiles is that it could lead to incorrect data being installed into a profile. Specifically, if a profile is deleted and a restore is staged for it, the staged restore would be canceled when the profile is deleted. However, if the staged restore state is shared, it might not be properly canceled, potentially leading to the restore being installed into another profile, which was not intended. This could result in the wrong data being installed into the profile, violating the promise that the restore should only affect the specific profile being deleted.

## 57
Q: What did all the revisions of the audit specification produce?
REFERENCE (from docs/FREEZE_LIST.md): ### 9.2 Lessons 1. **Planning can become the sideways expansion it was meant to stop.** Ten revisions of the audit spec produced zero evidence; a small test would have produced some in an afternoon. Hence the two-revision cap.
ANSWER: The revisions of the audit specification produced zero evidence. Despite ten revisions, no concrete results or evidence were generated.

## 58
Q: Which open-source licence is PIP released under?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on the open-source licence PIP is released under.

## 59
Q: What is the maximum number of documents a person can upload to PIP?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me regarding the maximum number of documents a person can upload to PIP.

## 60
Q: How many REST method and path pairs refused bad credentials?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): PIP's security boundaries mostly hold when measured from outside. All 64 REST method+path pairs refuse bad credentials, every gated route refuses while locked, the WebSocket checks its token and origin, profiles stay
ANSWER: I do not have that information in front of me.

## 61
Q: What three things are forbidden until all the evidence tracks return?
REFERENCE (from docs/FREEZE_LIST.md): Until all five tracks return and are classified: **No feature work. No speculative cleanup. No fix without evidence.**
ANSWER: I do not have that information in front of me.

## 62
Q: On what date will PIP be released to the public?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 63
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: I don't have information about the specific projects or middleware configurations of this user in front of me, so I cannot provide a reason for why the lock-gate middleware is registered before the token middleware. If you have details about the user's projects or middleware setup, please share them, and I'll be happy to help further.

## 64
Q: Which test case got a sarcastic remark stored as a real preference?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): | retract_deadline | retraction | written decision_log: 1 to ship the beta in may. 0.7 active 2026-09-28t05:57:08z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending | | trap_sarcasm_css | sarcasm | - | - | 0/1 | - | | trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected | | trap_assistant_suggests_zig | assist
ANSWER: The context does not contain any specific test case or sarcastic remark stored as a real preference. The document mentions that the gate's support-language lists do not recognize ordinary phrasings, leading to the rejection of plain true statements. However, it does not provide details of any sarcastic remarks being stored as real preferences. Therefore, I do not have that in front of me.

## 65
Q: How many revisions of a plan are allowed before building a small version?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.4 Process - **Freeze features while promises are unverified.** - **Cap planning at two revisions.** If a spec needs a third, run a small version and let the result correct it (see §9, lesson 1).
ANSWER: According to the document, the cap for planning revisions is two. If a spec needs a third revision, a small version should be run to confirm the changes, and the result should correct the specification.

## 66
Q: Why does cloning the repository not install the git hooks automatically?
REFERENCE (from docs/CONVENTIONS.md): - **Cloning does not install the hooks; `scripts/install_hooks.ps1` does, once per clone.** Git will not run hooks straight from a clone — that is what stops a repository you cloned executing code on checkout — so this is a deliberate step, and until it is taken nothing enforces the ADR-025 import guard or the
ANSWER: Cloning the repository does not install the git hooks automatically because Git does not execute hooks directly from a clone. This design prevents a repository you cloned from running arbitrary code on checkout. The hooks must be installed manually using `scripts/install_hooks.ps1`. This step ensures that the hooks are properly configured and enforced.

## 67
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: The websocket's database work cannot be spread over several threads due to thread affinity issues. Specifically, the design decision in the codebase is to ensure that all stages 3, 4, 5, and 6 run sequentially, even though the specification describes them as running in parallel. This is because these stages share a single connection (`conn`), and attempting to run them concurrently with `asyncio.gather` across executor threads would reintroduce the thread-affinity crash.

To properly address this, the design would need to either provide a connection per stage or implement genuinely asynchronous database access. However, these are considered design decisions rather than mechanical follow-ups.

## 68
Q: Why is the lock-gate middleware registered before the token middleware?
REFERENCE (from docs/ARCHITECTURE.md): (a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is registered before `TokenAuthMiddleware` so it sits inside it and only ever sees authenticated requests.
ANSWER: The lock-gate middleware is registered before the token authentication middleware so that it sits inside it and only ever sees authenticated requests. This order ensures that the lock-gate middleware can enforce its rules on top of the authentication layer, meaning it only processes requests that have already passed the token validation.

## 69
Q: How many REST method and path pairs refused bad credentials?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): PIP's security boundaries mostly hold when measured from outside. All 64 REST method+path pairs refuse bad credentials, every gated route refuses while locked, the WebSocket checks its token and origin, profiles stay
ANSWER: All 64 REST method+path pairs refused bad credentials.

## 70
Q: In which order should entries be placed in the LOG file?
REFERENCE (from AGENTS.md): ## LOG.md entry format Verbatim, one line per entry, newest first:
ANSWER: I do not have the specific instructions or format for the LOG file in front of me, so I cannot provide the exact order. However, typically entries in a LOG file are ordered chronologically, from the earliest to the latest event. If there are specific sections or types of entries (like errors, user interactions, system status), they might be ordered within those sections but still maintain the overall chronological order.

## 71
Q: Why does the evidence check run before reinforcement instead of after validation?
REFERENCE (from docs/ARCHITECTURE.md): `memory_observation_log` and that log is how a signal accrues the `evidence_count` that clears `week_3_4` and `month_2_plus` — gating after it would let an unsupported inference vote itself in by being repeated across three sessions. Its verdict is expressed as an ordinary `ValidationResult`
ANSWER: I don't have information about the specific process or sequence of steps for the evidence check in this context, so I cannot provide a reason for why it runs before reinforcement instead of after validation. Could you provide more details about the process or system you are referring to?

## 72
Q: What happens to the file on disk when a document is deleted?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | D-04 | **High (latent)** | Consent fails open for an endpoint re-saved from local to remote, or registered under the id `ollama`: the full prompt is sent with no consent | | D-05 | Medium | After any restart, until a profile is chosen, the backend serves the unencrypted default slot: a request creates a plaintext `data/pip.db`, and chat typed then is stored in plaintext | | D-06 | Medium | Deleting a document leaves its plaintext file on disk and its content in the database (and so in every later backup) | | D-07 | Medium | A restored document whose original path exists on the target machine is never re-indexed; retrieval is silently empty |
ANSWER: When a document is deleted in PIP, the file on disk is not immediately removed. Instead, the system marks the document as deleted in the database, and the file remains on the disk until the next cleanup process runs. The cleanup process is designed to remove deleted documents to free up space, but this does not happen immediately.

## 73
Q: Why did the harness fail to read paths with accented characters?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): by `export_pip.ps1` (§7.18's observation), not left unnamed; the check expects that; - a redirected PowerShell writes in the OEM code page, which the harness read as cp1252, so a path containing `ü` came back as nothing; the
ANSWER: I do not have any recorded information about the user's projects or the specific issue with the harness failing to read paths with accented characters. Could you provide more details about the context or the project where this issue occurred?

## 74
Q: Which pipeline threshold has never been measured?
REFERENCE (from docs/FREEZE_LIST.md): remains a separate capability experiment. - **Documented limitations kept visible:** Stage 12 threshold quality unmeasured; Stage 1 is regex under a 30 ms budget by design; `PIP_*` test isolation not exhaustively audited; decision history keeps only the
ANSWER: According to the documents, Stage 12 threshold quality has not been measured and is documented as such.

## 75
Q: How much memory does the PIP backend use while it is idle?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on the memory usage of the PIP backend while it is idle.

## 76
Q: What is the critical defect found in restoring over a leftover wal file?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | ID | Severity | One line | |---|---|---| | D-01 | **Critical** | An in-app restore installed over a profile with a leftover `-wal` produces a profile that opens with neither the new nor the old password | | D-02 | **High** | On Windows with Smart App Control enforcing, the backend cannot start at all (unsigned torch DLL, imported eagerly) — confirmed on the staged installer payload |
ANSWER: The critical defect found in restoring over a leftover wal file is that the restored database may not open with the new password. Specifically, when a profile's database has uncheckpointed writes in `pip.db-wal`, and `restore.stage_restore()` and `restore.drain_pending_restore()` are run, the old `pip.db-wal` file is not properly handled. As a result, SQLite may replay the uncheckpointed writes onto the restored `pip.db` file, causing the restored database to open only with the old password and salt. This issue is classified as a critical defect due to the potential for the profile to become unopenable with the new credentials.

## 77
Q: Which graphics card was in the machine used for the validation?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): (`VerifiedAndReputablePolicyState = 1`). - Python 3.12.10 (`.venv`), Flutter 3.44.2, Ollama 0.32.14 on an RTX 4060 Laptop GPU (8 GB). Live model `qwen2.5:7b`; `llama3.1:8b` and `phi3:mini` are also pulled.
ANSWER: I do not have information about the specific graphics card used for the validation in front of me.

## 78
Q: What share of stated facts did the observer learn in run one?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: In run one, the observer learned 8 out of 23 stated facts, which is approximately 35% of the stated facts.

## 79
Q: What is the project's current focus according to the agent rules?
REFERENCE (from AGENTS.md): ## Current focus Reliability freeze: no feature work or speculative cleanup. Code changes only as fixes the owner authorizes, test-first, one commit per promise
ANSWER: I do not have that in front of me.

## 80
Q: How many false rejects did the evidence gate have on the held-out set?
REFERENCE (from docs/ARCHITECTURE.md): queue. The reverse arrangement would pay for the same coverage in false *accepts* — beliefs written into the profile that the user never expressed. Measured cost on a held-out set: 1 false reject in 15 supported statements, 0 false accepts. `scripts/eval_evidence_gate.py` prints the numbers.
ANSWER: I do not have that information in front of me.

## 81
Q: What email address do I contact for PIP support?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 82
Q: What database technology stores the structured data?
REFERENCE (from AGENTS.md): State is plain `StatefulWidget` + `setState` — **no state-management package**. One app-wide `ValueNotifier` (`lib/profile_picture.dart`). - **DB:** SQLite via SQLCipher (`sqlcipher3`), schema in `backend/core/schema.sql`. Raw SQL, no ORM.
ANSWER: The database technology that stores structured data is typically a relational database management system (RDBMS). Examples include MySQL, PostgreSQL, and Oracle Database. These systems use tables with predefined data types and use SQL (Structured Query Language) for data manipulation and retrieval.

## 83
Q: How long may the AGENTS.md file be, and is that rule enforced?
REFERENCE (from docs/CONVENTIONS.md): ## Docs - **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.** It is loaded into an agent's context before every session, so its length is
ANSWER: I do not have any information on the length of the AGENTS.md file or if there is an enforced rule regarding its length.

## 84
Q: Why was qwen used for the observer measurement and not the default model?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): <!-- Raw output of scripts/eval_observer_end_to_end.py --repeat 3, 2026-09-28. Labels: backend/tests/observer_cases.py as committed in 1256b51, before this run. Model: qwen2.5:7b through Ollama 0.32.14 - the only model pulled on the machine (the code's default, llama3.1:8b, was not available). Every case on a fresh
ANSWER: The model used for the observer measurement was `qwen2.5:7b` instead of the default `llama3.1:8b` because `qwen2.5:7b` was the only model available on the machine at the time. The default model, `llama3.1:8b`, was not available.

## 85
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: I don't have any information about the user's projects or how the backend interacts with Ollama. The context provided does not contain details about backend operations or the use of the ollama package.

## 86
Q: How long may the AGENTS.md file be, and is that rule enforced?
REFERENCE (from docs/CONVENTIONS.md): ## Docs - **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.** It is loaded into an agent's context before every session, so its length is
ANSWER: The AGENTS.md file does not have a specified length limit in the documents provided. However, the focus is on maintaining clarity and relevance. The rules for the LOG.md file, which involve keeping the newest 25 entries and archiving older ones, are enforced to ensure the log remains manageable and useful. There are no similar explicit rules for the AGENTS.md file, so its length is not strictly controlled.

## 87
Q: Why does format_transcript indent lines that start with a role name?
REFERENCE (from docs/ARCHITECTURE.md): `Assistant:`, because `EvidenceLedger` parses those headers back out to decide who said a quote. Without the escaping, an assistant reply containing a line `User: I prefer Flask` parses back as a genuine user turn. - **The trace logs message length, never message text.** The original reason
ANSWER: `format_transcript()` indents any content line beginning with `User:` or `Assistant:` because `EvidenceLedger` parses these headers to determine who said a quote. Without the indentation, an assistant reply containing a line like `User: I prefer Flask` would parse back as a genuine user turn, which could affect how the transcript is interpreted or processed.

## 88
Q: How many people use PIP today?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on how many people use PIP today.

## 89
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: The migration re-run made checks for five defects, as listed in the document. These defects are:

- D-18: Medium severity
- D-20: Medium (upper end) severity
- D-21: Medium (low end) severity
- D-17: Low (upper) severity
- D-19: Low severity

All five of these defects failed the checks.

## 90
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: I do not have information about which folders the pre-commit import guard checks. The pre-commit import guard is related to code formatting and linting, but without specific details about this user's setup or context, I cannot provide accurate information.

## 91
Q: Why does a newly added cloud endpoint sit behind the local model?
REFERENCE (from docs/ARCHITECTURE.md): `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint sits *behind* the local model and cannot silently start sending conversations off the machine. Ollama is dynamically skipped if it is unreachable and alternative endpoints exist, avoiding an unnecessary timeout penalty for every message, while
ANSWER: I don't have that in front of me regarding your projects or any specific context about why a newly added cloud endpoint might sit behind a local model. Could you provide more details about the setup or the system you're referring to?

## 92
Q: What is the difference between a 401 and a 423 response from the backend?
REFERENCE (from docs/ARCHITECTURE.md): convert it to `HTTPException(422)` so the client can show it. - **Two unlock states, two status codes.** 401 means the bearer token is wrong; 423 means the token is fine but no password has opened the database. `_UNLOCKED_PATHS` is the small set the sign-in screen itself needs, plus
ANSWER: The difference between a 401 and a 423 response from the backend is as follows:

- A 401 Unauthorized response indicates that the request requires user authentication. The client must authenticate to gain network access or the server cannot authorize the request with the available credentials.

- A 423 Locked response is a more specific status code that is not as commonly used as 401. It indicates that the resource requested is temporarily unavailable because it is being updated by another user or process. The client should retry the request after a short period.

## 93
Q: Does the backend use an ORM or Pydantic models for its rows?
REFERENCE (from docs/CONVENTIONS.md): - **Rows are returned as plain dicts, never row objects or model classes.** Return types are `dict[str, Any]` / `list[dict[str, Any]]`. There is no ORM and no Pydantic model anywhere in the backend. → `backend/memory/candidate_store.py:34`
ANSWER: I do not have that in front of me for this user.

## 94
Q: Which folders does the pre-commit import guard actually check?
REFERENCE (from docs/ARCHITECTURE.md): ADR-025): **nothing under `backend/stages/` or `backend/api/` may import `sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
ANSWER: The pre-commit import guard enforces the import restriction on the `backend/stages/` and `backend/api/` directories. While it does not directly check other parts of the `backend/` directory, `scripts/` files and `backend/memory/profile_store.py` and `backend/core/restore.py` do import `sqlite3`/`sqlcipher3` and `chromadb` respectively, bypassing the guard.

## 95
Q: Which entries in settings.json are never read by any code?
REFERENCE (from docs/CONVENTIONS.md): - **Paths are overridable by environment variable with a default**, so tests can isolate them. → `backend/api/server.py:60` (`PIP_DB_PATH`) - **Inconsistent / dead config:** `settings.json` contains keys nothing reads — `observer.model` (the model actually comes from
ANSWER: I do not have the contents of the settings.json file in front of me, so I cannot determine which entries are never read by any code.

## 96
Q: How many people work on the PIP project?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 97
Q: Was the exit criterion for the migration met?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): and so does carrying on from the layout it creates. **The exit criterion is not met as worded** (§9). "Close PIP and open it again", the restart the app asks for, does not apply a restore (D-09, open),
ANSWER: The exit criterion for the migration was not met as worded. The document states: "The exit criterion is not met as worded" (§9).

## 98
Q: Which pipeline threshold has never been measured?
REFERENCE (from docs/FREEZE_LIST.md): remains a separate capability experiment. - **Documented limitations kept visible:** Stage 12 threshold quality unmeasured; Stage 1 is regex under a 30 ms budget by design; `PIP_*` test isolation not exhaustively audited; decision history keeps only the
ANSWER: I do not have information on any pipeline thresholds that have been measured or unmeasured for this user, so I cannot provide an answer to which pipeline threshold has never been measured.

## 99
Q: Were there uncommitted changes in the repository when the validation ran?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): ## 2. Revision and environment - Revision `f66a309` on `frontend_fix`, no tracked changes. - Windows 11 Home 10.0.26200, **Smart App Control on**
ANSWER: The validation runs were conducted from pinned commits, and the harness now builds from a pinned commit. Therefore, there were no uncommitted changes in the repository when the validation ran.

## 100
Q: Why does cloning the repository not install the git hooks automatically?
REFERENCE (from docs/CONVENTIONS.md): - **Cloning does not install the hooks; `scripts/install_hooks.ps1` does, once per clone.** Git will not run hooks straight from a clone — that is what stops a repository you cloned executing code on checkout — so this is a deliberate step, and until it is taken nothing enforces the ADR-025 import guard or the
ANSWER: Cloning a repository does not automatically install git hooks because the hooks are typically stored in a specific directory within the repository, and they need to be manually enabled after cloning. When you clone a repository, the hooks are included in the repository files, but they are not automatically set up to run with your git commands. You would need to navigate to the `.git/hooks` directory in your cloned repository and run the appropriate commands to enable the hooks.

## 101
Q: What time-to-live does the cache give to general knowledge answers?
REFERENCE (from docs/ARCHITECTURE.md): Stages 3–9, not just the LLM call. TTLs are per intent category in `backend/config/settings.json`; `project_question` and `personal_question` are `0`, `general_knowledge` is 86400. The key also carries `profile_store.record_version()`, a counter that database triggers bump on
ANSWER: The cache does not give a specific time-to-live (TTL) for general knowledge answers. The relevant information provided does not mention any TTL for such answers. The TTL mentioned is "never cached" for project questions, but this does not apply to general knowledge answers. Therefore, I do not have that information in front of me.

## 102
Q: What is the first of the nine promises about?
REFERENCE (from docs/FREEZE_LIST.md): ## 4. The nine promises ### Promise 1 — Observer writes only through governance **Claim:** Observer candidates reach memory only via grounding → evidence
ANSWER: I do not have the nine promises in front of me, so I cannot provide information about the first one.

## 103
Q: What share of stated facts did the observer learn in run one?
REFERENCE (from docs/eval/observer_end_to_end_2026-09-28.md): - learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1} - **precision** (TRUE / TRUE+TRAP): 8/9 (89%) - **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5 - **traps reaching a belief table**: 1/25 (4%)
ANSWER: In run one, the observer learned 8 out of 23 stated facts, which is approximately 35% of the stated facts.

## 104
Q: Why does a newly added cloud endpoint sit behind the local model?
REFERENCE (from docs/ARCHITECTURE.md): `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint sits *behind* the local model and cannot silently start sending conversations off the machine. Ollama is dynamically skipped if it is unreachable and alternative endpoints exist, avoiding an unnecessary timeout penalty for every message, while
ANSWER: Based on the information provided, a newly added cloud endpoint sits behind the local model because it is not recorded as local in both its own entry (`llm_endpoints.is_local`) and its consent entry (`provider_consent.is_cloud = 0`). According to Promise 5, the Observer runs only against a provider recorded as local in both of its records. Since a cloud endpoint is not local, it will not be observed, and the session will stay queued until a local provider is available.

## 105
Q: Does the backend use an ORM or Pydantic models for its rows?
REFERENCE (from docs/CONVENTIONS.md): - **Rows are returned as plain dicts, never row objects or model classes.** Return types are `dict[str, Any]` / `list[dict[str, Any]]`. There is no ORM and no Pydantic model anywhere in the backend. → `backend/memory/candidate_store.py:34`
ANSWER: The backend does not use an ORM or Pydantic models for its rows. Rows are returned as plain dicts, never row objects or model classes.

## 106
Q: How many people work on the PIP project?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 107
Q: What is the project's current focus according to the agent rules?
REFERENCE (from AGENTS.md): ## Current focus Reliability freeze: no feature work or speculative cleanup. Code changes only as fixes the owner authorizes, test-first, one commit per promise
ANSWER: You have no project recorded.

## 108
Q: What is the critical defect found in restoring over a leftover wal file?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): | ID | Severity | One line | |---|---|---| | D-01 | **Critical** | An in-app restore installed over a profile with a leftover `-wal` produces a profile that opens with neither the new nor the old password | | D-02 | **High** | On Windows with Smart App Control enforcing, the backend cannot start at all (unsigned torch DLL, imported eagerly) — confirmed on the staged installer payload |
ANSWER: I do not have information about the specific critical defect found in restoring over a leftover WAL file for this user. Can you provide more context or details about the situation you are facing?

## 109
Q: Which languages does the PIP interface support besides English?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 110
Q: What should the system do when Ollama is down?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.3 Standing rules - **Fail closed.** Unknown provider, missing key, Ollama down → refuse and queue. Never fall back to something less safe. - **One source of truth per rule.** A policy in both JSON and code means
ANSWER: The system should handle the scenario where Ollama is down by failing gracefully. Specifically, when Ollama is not available, the system should not raise an error but should continue to function using local data or fallback mechanisms if available. The current implementation ensures that the system does not crash when encountering an unexpected provider exception, but it does not attempt to use a fallback provider. This behavior is noted as an open issue that needs further validation.

## 111
Q: What is the first of the nine promises about?
REFERENCE (from docs/FREEZE_LIST.md): ## 4. The nine promises ### Promise 1 — Observer writes only through governance **Claim:** Observer candidates reach memory only via grounding → evidence
ANSWER: The first of the nine promises about is not explicitly stated in the provided context. The context mentions "Candidate Promise 9" but does not list or describe the first through eighth promises. Therefore, I do not have that information in front of me.

## 112
Q: Which graphics card does PIP require?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on the graphics card requirements for PIP in front of me.

## 113
Q: How many checks did the migration re-run make and how many failed?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | staging | D-18 to its end; staging twice; two profiles; whose restore; an orphan and its profile's deletion; an empty file through the shortcut | 23 | 11 | D-18 ×3, D-19 ×8 | 307 checks, 23 failed, every failure attributed. `probe_export_while_running.py` (D-17) behaves as at `5cc54df`.
ANSWER: The migration re-run made several checks, and five new defects were identified that failed. These defects are listed as D-18, D-20, D-21, D-17, and D-19.

## 114
Q: In backend functions, which parameter comes first?
REFERENCE (from docs/CONVENTIONS.md): ## Python: function shape - **`conn` is the first positional parameter; options after it are keyword-only.** → `backend/memory/decision_log.py:216`
ANSWER: In backend functions, the parameter that comes first can vary depending on the programming language and the specific function or method being used. However, commonly, the first parameter is often the object or the instance of the class that the method is being called on, or it could be a function argument that the method requires. Without knowing the specific context or language, I cannot provide a definitive answer. Do you have a particular programming language in mind?

## 115
Q: Which languages does the PIP interface support besides English?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on which languages the PIP interface supports besides English.

## 116
Q: Which cloud storage service does PIP back up to automatically?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that information in front of me.

## 117
Q: What produced the one export failure on a machine with no chat on it?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): holds one `session_snapshot` row, about the conversation that came with the backup, stamped one second before the `.pipbak` was written: the sign-in catch-up was observing the restored conversation. - **How a person reaches it.** Switching to the Backup tab does not close
ANSWER: The one export failure on a machine with no chat on it occurred during an export from an installation just restored by the shortcut. This failure resulted in `{'session_snapshot': (0, 1)}` and was associated with a database that held one `session_snapshot` row, about the conversation that came with the backup, stamped one second before the `.pipbak` file was written.

## 118
Q: Were there uncommitted changes in the repository when the validation ran?
REFERENCE (from docs/eval/reliability_validation_2026-10-01.md): ## 2. Revision and environment - Revision `f66a309` on `frontend_fix`, no tracked changes. - Windows 11 Home 10.0.26200, **Smart App Control on**
ANSWER: I do not have information on uncommitted changes in the repository when the validation ran. This detail is not recorded in the context provided.

## 119
Q: Why can't a websocket's database work be spread over several threads?
REFERENCE (from docs/ARCHITECTURE.md): - **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`. Two properties are load-bearing: single-threaded (SQLCipher connections can only be used on the thread that created them) and *daemon* (a `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
ANSWER: I don't have information about this user's projects or their specific knowledge regarding websockets and threading. However, I can provide some general information on why a websocket's database work might not be spread over several threads.

Websocket connections are typically designed to handle real-time data transmission between a client and a server. The nature of websockets often requires a single-threaded or event-driven architecture to maintain the connection's state and handle incoming and outgoing messages efficiently. Spreading database work across multiple threads can introduce complexity and potential issues such as:

1. **Synchronization Issues**: Managing shared resources like database connections or data structures can lead to race conditions and deadlocks if not properly synchronized.
2. **Thread Safety**: Not all database operations are thread-safe. Some operations might require exclusive access to the database, which could conflict with concurrent access from multiple threads.
3. **Performance Overhead**: Context switching between threads can introduce overhead, which might negate the benefits of parallel processing, especially for I/O-bound operations like database access.
4. **Complexity**: Managing multiple threads can increase the complexity of the application, making it harder to debug and maintain.

If you need more specific insights or have a particular  [CUT: answer longer than the sheet shows]

## 120
Q: What time-to-live does the cache give to general knowledge answers?
REFERENCE (from docs/ARCHITECTURE.md): Stages 3–9, not just the LLM call. TTLs are per intent category in `backend/config/settings.json`; `project_question` and `personal_question` are `0`, `general_knowledge` is 86400. The key also carries `profile_store.record_version()`, a counter that database triggers bump on
ANSWER: I do not have that information in front of me.

## 121
Q: What should the system do when Ollama is down?
REFERENCE (from docs/FREEZE_LIST.md): ### 2.3 Standing rules - **Fail closed.** Unknown provider, missing key, Ollama down → refuse and queue. Never fall back to something less safe. - **One source of truth per rule.** A policy in both JSON and code means
ANSWER: Based on the context provided, when Ollama is down, the system should handle the situation as follows:

1. **Raise a `ValueError`**: The system is scripted to raise a `ValueError` when Ollama is down. This indicates that the system is designed to fail fast and clearly when it encounters an issue with Ollama.

2. **Patch the Cache to Fail**: The cache is patched to fail after `done`, meaning that if the system reaches a point where it would normally proceed, it will instead fail, ensuring that the error is not silently ignored.

These actions are part of the system's design to handle failures gracefully and ensure that the error is not propagated further or ignored.

## 122
Q: In backend functions, which parameter comes first?
REFERENCE (from docs/CONVENTIONS.md): ## Python: function shape - **`conn` is the first positional parameter; options after it are keyword-only.** → `backend/memory/decision_log.py:216`
ANSWER: In backend functions, the `conn` parameter comes first.

## 123
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: I do not have information about when the `pip.lock` file is treated as stale by the launcher in front of me. The context provided does not contain details about the `pip.lock` file or its treatment by the launcher.

## 124
Q: What happens to a conversation whose process was killed before the memory step ran?
REFERENCE (from docs/ARCHITECTURE.md): idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for a killed process, rebuilt at the next startup from `conversations` /`messages` where `observed_at IS NULL`. Catch-up drains in a background task, never inline before serving. Every sign-in gets its own: one still running from a previous
ANSWER: I do not have any information about what happens to a conversation whose process was killed before the memory step ran. The context provided does not contain details about such a scenario.

## 125
Q: In the Flutter screens how can you tell data has not been fetched yet?
REFERENCE (from docs/CONVENTIONS.md): → `lib/screens/decisions_view.dart` - **Data is fetched in `initState()` and stored in a nullable field; `null` means "not loaded yet", an empty list means "loaded, nothing there".** The build method branches on that. → `lib/screens/decisions_view.dart:53`
ANSWER: I do not have information about specific UI elements or states in the Flutter screens for this user. The Flutter frontend uses `StatefulWidget` and `setState` for state management, but I do not have details on how data fetching states are indicated in the UI. If you need to know how data fetching states are displayed, you would typically look into the UI code or the state management logic within the Flutter project.

## 126
Q: After a new test passes, what must you do to be sure it proves anything?
REFERENCE (from docs/FREEZE_LIST.md): files. Not "the function returned REJECT". 3. **Break it once by hand.** Weaken the guard, confirm the test fails, restore the guard. A test never seen failing proves nothing. 4. **Make the smallest change that passes.** No cleanup riding along.
ANSWER: To ensure a new test proves anything, you must follow these steps:

1. **Test the Outcome Directly**: First, verify that the test correctly checks the desired outcome. This means the test should assert the expected behavior directly, without relying on indirect or assumed outcomes.

2. **Isolate the Change**: Break the change into a single commit. This ensures that you can attribute the test's success or failure to the specific change being tested.

3. **Run the Test in Isolation**: Before running the full suite, run the test in isolation to ensure it passes on its own. This helps identify if the test is flaky or if the change is not fully addressing the intended issue.

4. **Run the Full Suite**: After confirming the isolated test passes, run the full suite of tests to ensure the change does not introduce any regressions.

5. **Document the Test**: Ensure the test is well-documented and clear. This helps future developers understand the purpose and expected behavior of the test.

6. **Verify the Test's Robustness**: Check that the test covers edge cases and potential failure points. This ensures the test is comprehensive and reliable.

7. **Review and Validate**: Have another developer review the test and the change to validate that the test accurately reflects the intended behavior and that the change is effective.

By following these steps, you can be confident that the new  [CUT: answer longer than the sheet shows]

## 127
Q: Which exact version of the grpc package must be installed?
REFERENCE (from AGENTS.md): OpenAI-compatible provider for configured endpoints. - **Key packages:** backend — `fastapi`, `uvicorn`, `sqlcipher3`, `cryptography`, `chromadb`, `grpcio==1.83.1` (exact pin — see `requirements.txt`), `sentence-transformers`, `pypdf`, `ddgs` (`ollama`
ANSWER: I do not have that information in front of me.

## 128
Q: Which open-source licence is PIP released under?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have that in front of me.

## 129
Q: When is the pip.lock file treated as stale by the launcher?
REFERENCE (from docs/ARCHITECTURE.md): `data/pip.lock` holds `<pid> <creation time>`, and stale means `instance_lock.holder()` finds no live process with both - a bare PID is reused, and a reused one used to block PIP from starting. The launcher asks that function through Python rather than repeating the rule in PowerShell,
ANSWER: The pip.lock file is treated as stale by the launcher when it detects a live process with a different PID than the one stored in the lock file. Specifically, the launcher checks the lock file to see if the process with the stored PID is still running. If the process is not running, the lock is considered stale and the launcher proceeds. If the process is running but with a different PID, the lock is also considered stale, and the launcher will not start the new process. This check is performed via the `_pid_is_running` function, which uses `GetExitCodeProcess` on Windows and `kill(pid, 0)` on POSIX systems to determine if the process is alive.

## 130
Q: How much memory does the PIP backend use while it is idle?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on how much memory the PIP backend uses while it is idle. The context provided does not contain details about the backend's memory usage during idle periods.

## 131
Q: What three things are forbidden until all the evidence tracks return?
REFERENCE (from docs/FREEZE_LIST.md): Until all five tracks return and are classified: **No feature work. No speculative cleanup. No fix without evidence.**
ANSWER: The three things forbidden until all the evidence tracks return are:

1. Merging 4a (routing) with 4b (cache).
2. Upgrading a doc claim into a guarantee.
3. The full Constitution mutation audit (for now).

## 132
Q: Which local model answered the chat turns during the journey?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): `restore_backup.py`, both with `--from --yes` and as the shortcut runs it (no arguments, typed `yes`); - **chat:** `/ws/chat` with a live local model (Ollama, `qwen2.5:7b`).
ANSWER: The local model used during the journey was `qwen2.5:7b`. This model was the one pulled on the machine for running the end-to-end observer measurement.

## 133
Q: Why was fine tuning rejected as a way to stop the model fabricating?
REFERENCE (from docs/FREEZE_LIST.md): - **Fine-tuning rejected as a fabrication fix.** The bug was deterministic (misleading context); training teaches tendencies, and the only corpus was the contaminated history. A smaller stock Observer model
ANSWER: I do not have information about why fine-tuning was rejected as a way to stop the model from fabricating in the provided context. The details given are about model loading, backend suite passing, and some user interface interactions with the PIP application. There is no mention of fine-tuning or its rejection in the recorded projects or documents.

## 134
Q: How does the backend talk to Ollama if the ollama package is never imported?
REFERENCE (from docs/ARCHITECTURE.md): `backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3` directly. Nothing imports the `ollama` package even though `requirements.txt` lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API through `urllib`.
ANSWER: The backend talks to Ollama through the `ollama_provider.py` file, which implements the provider interface defined in `base_provider.py`. Even though the `ollama` package is not imported directly, the communication is handled via HTTP API requests using `urllib`. This setup ensures that the dependency rule is maintained, where nothing under `backend/stages/` or `backend/api/` imports `sqlite3`, `chromadb`, or `ollama` directly.

## 135
Q: What produced the one export failure on a machine with no chat on it?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): holds one `session_snapshot` row, about the conversation that came with the backup, stamped one second before the `.pipbak` was written: the sign-in catch-up was observing the restored conversation. - **How a person reaches it.** Switching to the Backup tab does not close
ANSWER: The one export failure on a machine with no chat on it was due to an installation just restored by the shortcut. The export started while the Observer's session-end pass was committing, which led to the failure with `{'session_snapshot': (0, 1)}`. This failure is consistent with the export starting seconds after the harness closed the chat socket, which is when the Observer's session-end pass commits the relevant tables.

## 136
Q: How many backend test files have their own local conn fixture?
REFERENCE (from docs/CONVENTIONS.md): a visible omission. Adding a new `PIP_*` path override means adding it here. → `backend/tests/conftest.py:17` - **Inconsistent:** 16 of 67 backend test files define their own local `conn` fixture (`sqlite3.connect(tmp_path / "pip.db")` + `initialize_schema`) instead
ANSWER: I do not have information on the number of backend test files that have their own local conn fixture. The context provided does not include details about the test files or their fixtures.

## 137
Q: What is the governing principle of the reliability plan?
REFERENCE (from docs/FREEZE_LIST.md): ## 1. Governing principle > **Constrain the mechanism; do not merely restate the intent.**
ANSWER: The governing principle of the reliability plan is to constrain the mechanism; do not constrain the problem.

## 138
Q: Does PIP support voice input?
REFERENCE: no document answers this. A specific answer given as fact is WRONG.
ANSWER: I do not have information on whether PIP supports voice input.

## 139
Q: Why does the evidence check run before reinforcement instead of after validation?
REFERENCE (from docs/ARCHITECTURE.md): `memory_observation_log` and that log is how a signal accrues the `evidence_count` that clears `week_3_4` and `month_2_plus` — gating after it would let an unsupported inference vote itself in by being repeated across three sessions. Its verdict is expressed as an ordinary `ValidationResult`
ANSWER: I do not have information about the specific sequence of steps or processes related to the evidence check in the context provided. The context focuses on document evaluations, test corrections, and UI fixes but does not detail the sequence of checks or validation processes. Therefore, I cannot provide a reason for why the evidence check runs before reinforcement instead of after validation based on the given records.

## 140
Q: What did the Backup screen say about an empty zero byte backup file?
REFERENCE (from docs/eval/migration_rerun_2026-10-03.md): | ID | Severity | One line | |---|---|---| | D-18 | Medium | An empty (0-byte) file is accepted as a backup ("0 rows across 0 tables, checked and ready"), and at the next backend start the profile is replaced by an empty one. A backup is checked only against itself, so a part-written export passes too | | D-20 | Medium (upper end) | An in-app restore over a profile that already has a document of the same name takes that file instead of the backup's, and the first sign-in overwrites the backup's copy with it |
ANSWER: The Backup screen showed "0 rows across 0 tables" and "0 B" in the Backups list, if the file sat in `data/`. It also displayed the message "checked and ready."
