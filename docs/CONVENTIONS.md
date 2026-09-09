# Conventions

Every rule below is derived from code in this repo, with one example file per
rule. Where a convention is applied inconsistently, both forms are named rather
than a winner picked.

## Naming and file layout

- **Pipeline stages are `stage_NN_<name>.py`, zero-padded, one per stage, each
  exposing a single `run()`.** The number is the execution order.
  → `backend/stages/stage_05_rag_retrieval.py`
- **Persistence modules are `<thing>_store.py` or the thing itself**, one per
  table group. → `backend/memory/conversation_store.py`,
  `backend/memory/decision_log.py`
- **API functions are `api_<verb>_<noun>(conn, …)`**, defined at module level in
  `server.py`, with the route closure of the same name minus the prefix.
  → `backend/api/server.py` (`api_list_projects` / `def list_projects()`)
- **Private helpers take a leading underscore**, including route-local ones.
  → `backend/api/server.py` (`_conn`, `_bearer_token`, `_db_path_or_default`)
- **Flutter screens live in `lib/screens/`, reusable widgets in `lib/widgets/`,
  cross-cutting singletons at `lib/` root.** → `lib/screens/projects_view.dart`,
  `lib/widgets/thinking_orb.dart`, `lib/theme.dart`
- **Inconsistent:** screen filenames use three suffixes — `*_view.dart` (nine
  files), `*_screen.dart` (`lib/screens/sign_in_screen.dart`), and no suffix at
  all (`lib/screens/model_browser.dart`). `onboarding_screen.dart` also sits at
  `lib/` root rather than in `lib/screens/`, unlike `sign_in_screen.dart`.

## Python: function shape

- **`conn` is the first positional parameter; options after it are
  keyword-only.** → `backend/memory/decision_log.py:216`
  (`list_decisions(conn, *, state="active", project_id=None)`)
- **Rows are returned as plain dicts, never row objects or model classes.**
  Return types are `dict[str, Any]` / `list[dict[str, Any]]`. There is no ORM
  and no Pydantic model anywhere in the backend.
  → `backend/memory/candidate_store.py:34`
- **Structured shapes are `TypedDict`, not Pydantic**, and are documentation
  only — nothing validates at runtime. `shared/ws_spec.py`'s header states this
  explicitly and explains that introducing Pydantic in one file would be an
  inconsistency rather than an improvement. → `backend/core/types.py`
- **Inconsistent:** optional type hints appear both ways —
  `Optional[str]` in `backend/memory/conversation_store.py:18` and `str | None`
  in `backend/memory/decision_log.py:37`. Both are current; new code in a file
  should match that file.

## State management (Flutter)

- **`StatefulWidget` + `setState`, no state-management package.** `pubspec.yaml`
  carries four runtime dependencies and none of them is one.
  → `lib/screens/decisions_view.dart`
- **Data is fetched in `initState()` and stored in a nullable field; `null`
  means "not loaded yet", an empty list means "loaded, nothing there".** The
  build method branches on that. → `lib/screens/decisions_view.dart:53`
- **Every `setState` after an `await` is guarded by `if (mounted)`** (53
  occurrences across `lib/`). → `lib/screens/decisions_view.dart:71`
- **Shared state uses a top-level `ValueNotifier` only where the alternative is
  threading a parameter through four widgets**, and the reasoning is documented
  in the file. There is exactly one. → `lib/profile_picture.dart:43`
- **Widget-tree colours come from a `ThemeExtension` read via `context.pip`,
  never from `static const` colours,** so both palettes work without any
  `if (dark)` branch. → `lib/theme.dart`

## Error handling

- **Stages fail open, and the pipeline wraps each call anyway.** Every stage
  invocation in `pipeline.run()` sits in `try/except` with a documented empty or
  safe fallback, logged to the trace rather than raised.
  → `backend/core/pipeline.py:258` onward (Stage 0, and every stage after it)
- **The memory layer raises `ValueError` with the sentence explaining the
  refusal; routes convert it to `HTTPException(422)`.** The sentence is the
  answer the user sees. → `backend/api/server.py:1762` (`correct_memory`)
- **One malformed row costs that row, not the operation.** A provider row that
  cannot be constructed is skipped with a warning and the chain continues.
  → `backend/core/pipeline.py:142`
- **Dart: API failures become `ApiException`, whose `detail` unwraps FastAPI's
  `{"detail": …}` envelope**; screens store `error.toString()` in a nullable
  `_error` field and render it. → `lib/api_client.dart:17`
- **Inconsistent:** the catch variable is `catch (error)` in 25 places and
  `catch (e)` in 8 (`lib/screens/model_browser.dart:75`,
  `lib/screens/sign_in_screen.dart:212`, others). No functional difference;
  match the file you are in.

## Async and threading

- **Backend code is synchronous except at the transport edge.** Stages, stores
  and the pipeline are ordinary functions; `async def` appears only in
  `server.py`'s routes, lifespan and WebSocket handler.
  → `backend/stages/stage_09_llm_streaming.py`
- **A WebSocket's DB work is dispatched to one pinned daemon thread**, because
  SQLCipher connections are thread-affine and a non-daemon worker can prevent
  the process from exiting. Never move this work to a `ThreadPoolExecutor`.
  → `backend/core/pinned_executor.py`
- **Long work is never awaited on a shutdown path.** Transcripts are queued to
  `pending_observer` and drained later; in-flight drains are cancelled, not
  joined, because the queue's `processing` state makes retry safe.
  → `backend/api/server.py` (lifespan shutdown block)
- **Streaming is a generator, not a callback.** `pipeline.run()` yields wire
  events and finishes with one `pipeline_complete` sentinel.
  → `backend/core/pipeline.py:217`

## Configuration

- **Tunables live in `backend/config/settings.json` and are read through
  `get_settings()` at call time**, not captured at import.
  → `backend/memory/decision_log.py:77`
- **Paths are overridable by environment variable with a default**, so tests can
  isolate them. → `backend/api/server.py:50` (`PIP_DB_PATH`)
- **Inconsistent / dead config:** `settings.json` contains keys nothing reads —
  `observer.model` (the model actually comes from
  `pipeline.get_active_model_name()`, falling back to the hardcoded
  `DEFAULT_MODEL_NAME`), and the whole `performance_targets` and `database`
  blocks. `database.kdf_iterations` is duplicated as a constant in
  `backend/core/db_key.py:42` (`KDF_ITERATIONS = 256_000`), which is the value
  that is actually used.

## Comments

- **Comments explain *why*, at length, and record the bug that motivated the
  code**, whether it was found live or by inspection, what was tried first, and
  what limitation remains. This is the house style, not noise — terse code reads
  as out of place here. → `backend/core/pinned_executor.py` (45 lines of
  reasoning before the first import), `frontend/flutter/pubspec.yaml`

## Docs

- **`AGENTS.md` is capped at 80 lines and the cap is enforced, not remembered.**
  It is loaded into an agent's context before every session, so its length is
  paid on every request; detail belongs in `docs/`, which is read on demand.
  → `scripts/pre-commit` (the check rejects a staged `AGENTS.md` over the cap,
  once the hooks are installed — see Hooks below)
- **Every file ends with exactly one trailing newline and no blank line.**
  `wc -l` therefore reports one fewer than the line number an editor shows for
  the end of the file. That gap is not a defect and must not be closed by
  deleting the final newline. → any file here; verified with `tail -c 1`

## Hooks

- **Cloning does not install the hooks; `scripts/install_hooks.ps1` does, once
  per clone.** Git will not run hooks straight from a clone — that is what stops
  a repository you cloned executing code on checkout — so this is a deliberate
  step, and until it is taken nothing enforces the ADR-025 import guard or the
  `AGENTS.md` cap. Both then fail open and silently: commits are accepted and
  the rules read as if they were being applied.
  → `scripts/install_hooks.ps1`
- **The installer points `core.hooksPath` at `scripts/` rather than copying
  into `.git/hooks/`.** A copy is a second version that drifts, and the one git
  actually runs is the untracked one nobody reviews. Editing
  `scripts/pre-commit` is therefore the whole of updating the hook.
- **`core.hooksPath` lives in `.git/config`, so it is per-clone and per-machine
  and cannot be committed.** Found the hard way: this repository carried the
  cap rule, the LOG entry saying the check was added, and no installed hook on
  the machine that wrote them.

## Tests

- **Backend: `backend/tests/test_<module>.py`, flat, one file per module under
  test, plain `def test_…` functions with `assert`.**
  → `backend/tests/test_decision_log.py`
- **Test names are sentences describing the behaviour**, not the method name.
  → `test_decision_confidence_uses_or_logic`
- **`conftest.py` owns environment isolation.** An autouse fixture redirects
  every path override (`PIP_DB_PATH`, `PIP_SALT_PATH`, `PIP_CHROMA_PATH`, …) to
  `tmp_path`, kept as a table so that adding an override without isolating it is
  a visible omission. Adding a new `PIP_*` path override means adding it here.
  → `backend/tests/conftest.py:17`
- **Inconsistent:** 13 of 58 backend test files define their own local `conn`
  fixture (`sqlite3.connect(tmp_path / "pip.db")` + `initialize_schema`) instead
  of a shared one; `conftest.py` provides `db_key` and isolation but no `conn`.
  → `backend/tests/test_decision_log.py:9`
- **Flutter: `test/<subject>_test.dart`, flat, one per screen or widget**, with
  a `FakeApi extends ApiClient` overriding just the methods that screen calls
  and recording them in a `calls` list. → `test/decisions_view_test.dart:20`
- **Empty directory:** `backend/tests/test_stages/` exists and contains nothing;
  stage tests are flat in `backend/tests/`.
