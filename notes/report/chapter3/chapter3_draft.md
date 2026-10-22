# CHAPTER 3: METHODOLOGY

## 3.1 Research and Development Method

PIP was built with an incremental development model, followed by an evidence-first reliability phase. In the incremental part, the system was built in numbered phases, each adding one part of the design, several of them ending with a tagged version and its tests. The design was kept in a separate design reference, whose architecture decision records were written early, in Phase 2. Table 3.1 lists the phases.

Table 3.1: Development phases of PIP

| Phase | Dates (2026) | What was built | Tests at the end |
|---|---|---|---|
| 0 | 3 July | Configuration, database schema and core components | – |
| 1 | 4 July | The Constitution and its enforcer | – |
| 2 | 5 July | Architecture decision records in the design reference | – |
| 3 | 9 July | The provider layer and the consent gate | 81 passed (version 0.3) |
| 4 | 11 July | The gap detector and the session snapshot | 97 passed (version 0.4) |
| 5 | 16 August | Stage 12, the validation layer, and the corrected-write path | 121 passed (version 0.5) |
| 6 | 16–17 August | Document storage, the vector index and Stage 5 retrieval | – |
| 7 | 17 August | Stage 11, the Observer, and evidence reinforcement across sessions | – |
| 8 | 17–18 August | The remaining stages of Stages 1–10, the chat WebSocket and the Flutter client | – |
| Reliability | 26 September to October | Each promise tested and each defect fixed test-first; a few authorised additions the evaluation needed (the audit log, one record per chat); the evaluations of Chapter 6 | 1,889 backend and 372 Flutter tests passed |

By September the system worked, but its most costly faults had been silent ones: encryption that was implemented but at first never given a key, a recovery path that was never called, and evidence that was collected but never checked. On 26 September 2026 the project therefore adopted a reliability freeze. Features were frozen: from then on, code changed only to fix a broken promise or, with explicit authorisation, to add something the evaluation needed, such as the audit log. Every change followed the same four rules:

1. Decide before building. Write the promise first, as one sentence saying what the change guarantees; name the mechanism that enforces it; and name what "broken" would look like from outside, such as a database row, a network request or a file on disk.
2. Test first. Write the test before the fix and run it against the current code; it may already pass, which saves a change. The test checks outcomes, such as what is stored or sent, not the value a function returns.
3. Break it once by hand. Weaken the guard on purpose, confirm that the test fails, and restore the guard. A test that has never been seen to fail proves nothing.
4. Make the smallest change that passes, and commit each promise separately, with its test and a log entry.

Each finding was classified in one of four ways: a mechanism that exists but is not connected to the real path; state that is missing, so the guarantee cannot be checked; a guarantee already enforced, which needs only its test; or a claim that is stronger than the mechanism, which is corrected by narrowing the claim. Evidence was ranked as well: a deterministic test on the real code path that checks the stored result, an observed network call, or a break-it result counts as strong evidence, while comments, documentation and function names do not count as evidence on their own.

The evaluations in Chapter 6 follow the same idea. The rule for judging each evaluation was written down before it was run; each run used a clean copy of the code taken from one commit; and each result file records the commit, the language model's exact version, the Ollama version and the version of the Constitution, so that every number in this report can be traced to the code that produced it. The whole project is kept in Git (329 commits by 22 October 2026), and a Git hook enforces the main architecture rule described in Section 3.5.

## 3.2 System Requirement Specification

### 3.2.1 Functional Requirements

Table 3.2 lists the functional requirements, each with the part of the system that provides it.

Table 3.2: Functional requirements

| ID | Requirement | Provided by |
|---|---|---|
| FR‑ | The user can create a profile protected by a password, sign in, sign out, switch profile, rename it, change its password and delete it (deleting asks for the password again). | Sign-in screen; /auth routes |
| FR‑ | The user can chat with the assistant; the answer is streamed word by word, the steps the assistant takes are shown, and an answer can be stopped. | Chat screen; /ws/chat; Stages 0–10 |
| FR‑ | The assistant answers using what it knows about the user, their projects and decisions, and their documents. | Stages 3–7 |
| FR‑ | At the end of a conversation the assistant learns facts about the user (skills, preferences, goals, projects, topics, preferred style) through the evidence gate and the Constitution, and keeps a record of where the chat left off. | Stages 11–13 |
| FR‑ | The user can confirm or dismiss each fact the assistant asks about, and see, correct or delete what it has stored. | Review and Profile screens |
| FR‑ | The user can create projects and decisions, change a decision's state, and accept or dismiss decisions the assistant proposes. | Projects and Decisions screens |
| FR‑ | The user can upload documents, search them, and delete them; deleting removes the file and its stored copy. | Documents screen; /rag routes |
| FR‑ | When a message could use the web, the assistant offers a search showing the exact query, and searches only after the user clicks. | Stage 6; chat screen |
| FR‑ | The user can list, download, delete and select local models, and grant or revoke consent, for a chosen scope, for each outside provider: web search, and a cloud model if one is configured. | Model and Providers screens |
| FR‑ | The user can back up a profile to one encrypted file, restore it, and import a backup into a new installation. | Backup screen; export and restore scripts |
| FR‑ | The user can read, correct or clear each chat's record. | Chat record dialog |
| FR‑ | The user can see the trace of each message: which stages ran and how long each took. | Trace screen |

### 3.2.2 Non-Functional Requirements

The non-functional requirements are mainly the nine promises of the project. Each is checked by its own tests (Chapter 6). Table 3.3 groups them with the remaining requirements.

Table 3.3: Non-functional requirements

| Area | Requirement | How it is checked |
|---|---|---|
| Privacy | Nothing leaves the computer without the user's recorded consent for that service and purpose; no consent is preselected (Promise 6). The Observer runs only on a model recorded as local (Promise 5). | Tests that count what reaches a stand-in server |
| Security | Each profile's data is encrypted at rest with a key derived from its password (Promise 7). Nothing derived from one profile is served to another (Promise 8). | Tests on the stored files and through the real routes |
| Correct learning | The Observer writes only through the checks (Promise 1), never changes the user's name, language or time zone (Promise 2), writes sensitive facts only after confirmation (Promise 3), and stores only what the user's words support (Promise 4). | Tests on the database state; a blind review of the evidence gate |
| Correct answers | An answer about the user reflects the record as it is when asked (Promise 9). | Tests on the prompt the model receives |
| Auditability | Every learning decision leaves one row in an append-only audit log. | Tests that the log cannot be changed or deleted |
| Reliability | Every chat turn ends with an answer or an error, and a failed write is rolled back. | Tests through the chat WebSocket |
| Performance | The first word of an answer appears within about half a second on the test computer, and the model with its 16,384-token window fits in 8 GB of graphics memory. | Speed measurement (Chapter 6) |
| Usability | Readable contrast, named controls, a minimum window size, and a minimum password length. | Flutter widget tests |
| Maintainability | One test file per module, and an import rule enforced by a Git hook. | The test suites and the hook |

## 3.3 Tools and Technologies Used

Table 3.4 lists the main tools and the versions used for the final measurements.

Table 3.4: Tools and technologies

| Tool | Version | Used for |
|---|---|---|
| Python | 3.12.10 | The backend |
| FastAPI, Starlette, Uvicorn | 0.141.1, 1.6.0, 0.52.3 | The REST API, the chat WebSocket and the web server |
| SQLCipher (sqlcipher3) | 0.6.2 | The encrypted database, one per profile |
| cryptography | 50.0.0 | Encrypting the document index's text, and keyed hashes (HMAC) |
| ChromaDB | 1.5.9 | The vector index for document search |
| sentence-transformers, all-MiniLM-L6-v2 | 5.7.0 | Turning text into vectors, on the processor |
| pypdf | 6.16.1 | Reading uploaded PDF documents |
| ddgs | 9.15.0 | DuckDuckGo web search, only after the user's click |
| Ollama | 0.40.3 | Running the language model locally |
| qwen2.5:7b (Q4_K_M) | – | The language model |
| Flutter (Dart) | 3.44.2 | The Windows desktop application |
| http, web_socket_channel, file_picker | 1.2, 3.0, 12.0 | The app's REST calls, chat connection and file chooser |
| pytest (with pytest-timeout, pytest-asyncio), flutter_test | 9.1.1 | Backend and app tests |
| Git and GitHub | – | Version control and backup |
| PowerShell, Inno Setup | – | Launch, backup and restore scripts; the Windows installer |

Python was chosen for the backend because the libraries for language models, vector search and encryption are mature in Python. FastAPI provides both the REST routes and the WebSocket that streams answers. SQLCipher encrypts the whole database file with a key derived from the user's password, so the data is unreadable without it. Ollama runs the language model as a local server, so no conversation needs to leave the computer. Flutter produces a native Windows application from one code base, and qwen2.5:7b was chosen because it fits in the test computer's graphics memory with a 16,384-token window and because every measured result in this report was taken on it.

## 3.4 Feasibility Study

Table 3.5 summarises the feasibility of the project.

Table 3.5: Feasibility study

| Type | Finding |
|---|---|
| Technical | The system runs on one laptop: an Intel Core i9-14900HX, 16 GB of memory and an NVIDIA GeForce RTX 4060 Laptop GPU with 8 GB. The language model with its 16,384-token window occupies about 5.1 GiB of graphics memory, and 6.6–6.8 GB of the card is in use with a browser open. The embedding model runs on the processor, leaving the graphics card to the language model. |
| Economic | Every tool and both models are free to use. There is no cloud cost and no charge per request, because the model runs locally; the only cost is the computer, which the user already owns. |
| Operational | PIP is used like any desktop application: it is started from a shortcut, the user signs in to a profile, and once the language model has been downloaded it works without an internet connection, except for web search and an optional cloud model. A Windows installer was prepared with Inno Setup and does not need administrator rights. |
| Schedule | The working system was built in about seven weeks (Phases 0–8, July to August 2026), leaving September and October for testing, fixing and evaluation within the semester. |

## 3.5 System Architecture

Figure 3.1 shows the architecture of PIP. Everything except web search and an optional cloud model runs on the user's computer.

[Figure 3.1: System architecture of PIP (fig3-1_system_architecture.png)]

The user works in the Flutter desktop application. It has no logic of its own: it sends each request to the Python backend on the same computer, over HTTP for ordinary requests (/api/v1/...) and over one WebSocket (/ws/chat) for chat, where the answer is streamed back word by word. Every request carries a bearer token that the backend writes to a file at start-up, and the backend listens only on the computer's own address, 127.0.0.1.

The backend has four layers.

1. Transport (backend/api/server.py) receives requests. Three middleware layers check them in order: the allowed origin, the bearer token, and whether a profile is signed in. Each of the 68 REST routes calls a plain function that does the work, and each chat connection gets its own worker thread, because an encrypted database connection must stay on the thread that opened it.
2. Orchestration (backend/core/pipeline.py and backend/stages/) runs each chat message through Stages 0–10: measuring the time since the last session, classifying the message, routing it, checking the answer cache, looking up decisions, memory and documents, an optional web search, assembling the prompt, checking consent, streaming the answer from the model, and delivering it. At the end of a session, Stages 11–13 run separately: the Observer proposes what was learned, the evidence gate and the Constitution decide, and the result is written, queued as a question for the user, or rejected, with an audit row for each decision.
3. Persistence (backend/memory/) has one module per kind of stored data, each writing plain SQL to the profile's encrypted database, and a vector index for documents whose stored text is also encrypted.
4. Providers (backend/providers/) connect to language models through one interface: Ollama, reached at 127.0.0.1, and optionally a cloud model with an OpenAI-compatible interface. The backend uses such a cloud model only with consent; in this version it is configured outside the app, which offers no screen for adding one.

A Git hook enforces the main rule between these layers: no module in the transport layer or in the stages may import the database, vector-index or Ollama libraries directly; they must go through the persistence and provider layers.

Each profile has its own folder holding its encrypted database, its vector index, its uploaded documents and the salt used to derive its key. A few files are shared by all profiles: the list of profiles (names only), the bearer token, and a lock file that stops two copies of PIP running at once. Chapter 4 shows the design of each part in detail.
