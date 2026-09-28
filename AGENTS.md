# AGENTS.md

**PIP (Personal Intelligence Platform)** — a local-first desktop AI assistant
that runs its own model, keeps chat/memory/documents/decisions in an encrypted
database on the user's machine, and gates what it is allowed to learn about the
user through a deterministic Constitution enforcer.

## Stack

- **Backend:** Python, FastAPI + uvicorn. REST under `/api/v1/*`, one WebSocket
  at `/ws/chat` (the only chat transport, ADR-028).
- **Frontend:** Flutter (Dart SDK `^3.12.2`), native Windows desktop target.
  State is plain `StatefulWidget` + `setState` — **no state-management
  package**. One app-wide `ValueNotifier` (`lib/profile_picture.dart`).
- **DB:** SQLite via SQLCipher (`sqlcipher3`), schema in
  `backend/core/schema.sql`. Raw SQL, no ORM.
- **Vectors:** ChromaDB (`data/chroma/`), rebuildable, never authoritative.
- **LLM:** Ollama over HTTP via `urllib` (local, default `llama3.1:8b`) + an
  OpenAI-compatible provider for configured endpoints.
- **Key packages:** backend — `fastapi`, `uvicorn`, `sqlcipher3`,
  `cryptography`, `chromadb`, `grpcio==1.83.1` (exact pin — see
  `requirements.txt`), `sentence-transformers`, `pypdf`, `ddgs` (`ollama`
  is listed there but imported nowhere).
  Flutter — `http`, `web_socket_channel`, `file_picker`, `cupertino_icons`
  (unimported but required; see the comment in `pubspec.yaml`).

## Where things are

- `backend/api/` — `server.py` only: `create_app()`, middleware, all routes.
- `backend/core/` — pipeline orchestrator, auth, DB key/session key, instance
  lock, constitution enforcer + `constitutional.json`, `schema.sql`, trace.
- `backend/memory/` — one module per store, functions taking `conn` first.
- `backend/stages/` — `stage_00_*` … `stage_13_*`, one `run()` each. Neither
  it nor `api/` may import `sqlite3`/`chromadb`/`ollama` (hook-enforced).
- `backend/providers/` — `base_provider.py` + one file per LLM provider.
- `backend/config/` — `settings.json` (all tunables) and its loader.
- `backend/tests/` — pytest, one file per module under test.
- `backend/observer/` — **empty directory**, nothing lives here.
- `shared/` — `ws_spec.py`, the `/ws/chat` event TypedDicts used by both ends.
- `frontend/flutter/` — the deliverable client (`lib/`, `test/`, `windows/`).
- `frontend/web/` — older HTML/JS client, contract-proving, not the deliverable.
- `frontend/cli/` — `pip_cli.py`, a urllib-based CLI over the same REST surface.
- `scripts/` — PowerShell launchers/builders and Python maintenance scripts;
  `pre-commit` (ADR-025 import guard) is installed via `install_hooks.ps1`.
- `config/` — `provider_consent.json`, first-run seed only, not read at runtime.
- `installer/` — Inno Setup `PIP.iss` and app icons.
- `data/` — runtime state (db, chroma, logs, profiles). `dist/` — build
  output. Both gitignored.
- `docs/` — the docs below. `CLAUDE.md`, `GEMINI.md`, `.github/` and `.cursor/`
  hold one-line pointers to this file; `.agents/` exists and is empty.

## Rules for agents

a. Read `docs/ARCHITECTURE.md` before adding a feature or changing data flow.
b. Read `docs/CONVENTIONS.md` before writing code.
c. Never bulk-read `lib/` (or `backend/`). Use the folder map above to pick a
   directory, then grep. `server.py`, `profile_store.py`, `chat_view.dart` and
   `profile_view.dart` are all 1000+ lines — read the region, not the file.
d. After finishing a task, prepend one entry to `docs/LOG.md`.
e. If you change structure or a convention, update the matching doc in the same
   turn — `docs/ARCHITECTURE.md` for structure and data flow,
   `docs/CONVENTIONS.md` for conventions.

## Current focus

Reliability freeze: no feature work or speculative cleanup. Code changes
only as fixes the owner authorizes, test-first, one commit per promise
(`docs/FREEZE_LIST.md` §2). The promises, their evidence and every fix's
status live there - read it before any task, update it in place rather
than writing a new summary. Packaging is paused. A report may recommend a
fix; implementing it needs separate authorization.

## LOG.md entry format

Verbatim, one line per entry, newest first:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

Keep the newest 25 entries in the main list. When there are more, roll the
oldest ones into `## Archive` as 3-4 summary lines — not one line per entry.
