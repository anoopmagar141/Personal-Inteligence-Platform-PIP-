# PIP — Reliability Plan and Governance Freeze

**Canonical document.** Update in place; do not create a second summary.
Location in the repo: `docs/FREEZE_LIST.md`.

**Status: evidence-first freeze, fixing by explicit authorization.** All
five evidence tracks returned (§7.2–§7.6); cross-track synthesis done
(§7.7); end-to-end profile boundary test run (§7.8). Production code has
changed only under four explicit authorizations, each fix test-first with
the test seen failing: profile boundary (§7.9), answers about the user
(§7.10), lost learning (§7.11), lock identity (§7.12). §7.7's fix order is
complete: the promise wording was decided 2026-09-28 (§4 now holds nine
promises). On 2026-10-01 the owner authorized four UI fixes from a
launch-checklist audit (§7.15), all landed. A product-wide validation pass
the same day (§7.16, report only) found four high-or-critical defects in
backup/restore, deployment and consent. The owner authorized the D-01,
D-03 and D-04 fixes; D-15, a sign-out/cache race found while verifying D-03
(§7.19); and D-14, a staged restore surviving its profile's deletion (found
while reviewing D-01). All five landed 2026-10-02 (§7.17, §7.18, §7.20,
§7.21, §7.22). On 2026-10-03 the owner authorized D-16, a chat turn left
with no terminal event when no provider may answer; landed the same day
(§7.23). The same day the migration journey was re-run end to end (§7.24,
report only): the data round trip holds, D-01/D-03/D-14 included, and five
new defects were found on the backup and restore path (D-17 to D-21). The
owner then authorized D-22, the turn a raising pipeline left unended, the
open item §7.23 named; landed the same day (§7.25), which also found D-23.
On 2026-10-07 the owner asked for the import and export logic to be tested
and its errors fixed: D-18, D-21, D-11, D-20, D-07, D-17, D-19 and D-09 landed
(§7.26). D-02 is an environment condition: it stopped reproducing on the owner's
machine on 2026-10-08 when they turned Smart App Control off themselves (§7.26), and is
still true wherever it is on. Anything further needs a new authorization.

Contents: 1 Principle · 2 Development strategy · 3 Classification ·
4 The nine promises · 5 Evidence · 6 Rejected methods · 7 Evidence tracks ·
8 Status · 9 Conversation record · 10 Background · 11 Freeze rule

---

## 1. Governing principle

> **Constrain the mechanism; do not merely restate the intent.**

PIP's costly bugs were not the ones that failed loudly. They failed
silently: encryption implemented but never given a key, a recovery path
never invoked, evidence collected but never checked, an Observer that
stopped learning with no error. The aim is not "errorless" development,
which is unachievable. The aim is that errors are caught **early, cheaply,
and by a mechanism** rather than by someone remembering to look.

---

## 2. Development strategy (standing method)

This applies to every change, during and after the freeze.

### 2.1 Decide before building
1. **Write the promise first** — one sentence saying what the change
   guarantees.
2. **Name the enforcing mechanism.** If none can be named, the promise is
   a hope and does not get written into any claim.
3. **Name what "broken" looks like from outside** — a DB row, a request
   count, a file on disk. If a failure would be invisible, make it visible
   before building anything else.

### 2.2 Build in this order
1. **Test first, run it against current code.** It may already pass;
   that saves a fix.
2. **Assert on outcomes, not return values** — DB state, network calls,
   files. Not "the function returned REJECT".
3. **Break it once by hand.** Weaken the guard, confirm the test fails,
   restore the guard. A test never seen failing proves nothing.
4. **Make the smallest change that passes.** No cleanup riding along.
5. **One commit per promise,** test in the same commit, one `docs/LOG.md`
   entry.

### 2.3 Standing rules
- **Fail closed.** Unknown provider, missing key, Ollama down → refuse
  and queue. Never fall back to something less safe.
- **One source of truth per rule.** A policy in both JSON and code means
  one of them is lying.
- **Tests never touch real data.** Every `PIP_*` path isolated in
  `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have
  made the real database permanently unopenable.
- **Measure a flake before believing it.** Compare against a pinned
  baseline SHA. A "known flaky" symptom has already hidden one real
  regression (the two-minute startup hang).
- **Claims match mechanisms.** If the code cannot prove it, the docs do
  not say it.

### 2.4 Process
- **Freeze features while promises are unverified.**
- **Cap planning at two revisions.** If a spec needs a third, run a small
  version and let the result correct it (see §9, lesson 1).
- **Recommending ≠ implementing.** A discovery report may recommend a
  fix; a separate, explicit decision authorizes it.
- **Reports are read against their own stop condition** before any
  comparison with other reports.

### 2.5 Known limit of this strategy
It protects promises that have been written down. It does not catch bugs
in behavior nobody thought to promise. The only defense there is real
daily use: when something surprises you, turn it into a new promise with a
test.

### 2.6 Where these rules must live to be enforced
- `AGENTS.md` is at its **80-line cap**. Its "Current focus" section now
  points here (done 2026-09-26; still 80 lines, stale packaging text
  removed).
- `docs/LOG.md` is held at **25 entries**; the thirty-one oldest are rolled into
  twenty-seven Archive summary lines (done 2026-09-26).

---

## 3. Four-way classification

Every returned report resolves into exactly one category. "Gap" on the
original list meant **unverified**, not "bug requiring code".

| # | Category | Meaning | Typical response |
|---|----------|---------|------------------|
| A | Disconnected mechanism | Mechanism exists; the real path does not use it | Reconnect; add regression test |
| B | Missing state | The state needed to verify the guarantee is not stored | Add minimum state; test writer and reader |
| C | Already enforced | Mechanism already does what was promised | No code change; keep the test |
| D | Claim too strong | Code is fine; the written promise overstates it | Correct the wording; state the limitation |

---

## 4. The nine promises

### Promise 1 — Observer writes only through governance
**Claim:** Observer candidates reach memory only via grounding → evidence
gate → Stage 12 → Stage 13.
**Must prove:** reachability — no production path from Observer output to
storage that skips governance. A static import guard is a guard, not a
proof. A valid candidate must still be written; rejecting everything
proves the wrong property.
**Evidence (2026-09-28):** holds for memory candidates -
`backend/tests/test_observer_governance.py`, break-its seen failing (§7.13).
Decision candidates and the snapshot take separate gates (§7.13 finding 1).

### Promise 2 — Observer cannot write immutable fields
**Claim:** name, language, timezone change only by the user directly.
**Must prove:** a grounded, gate-passing candidate for these fields cannot
reach a DB write — tested on DB state, not on the enforcer's return value.
**Evidence (2026-09-28):** holds - the identity row never changes, three
independent layers (§7.13). A same-named preference can still be learned and
shown beside it (§7.13 finding 2).

### Promise 3 — Gated fields require confirmation
**Claim:** a gated field is not persisted without prior user confirmation.
**Must prove:** the write is unreachable without confirmation, on real DB
state. A JSON rule naming the field is not evidence.
**Evidence (2026-09-28):** holds for all four gated patterns, using shapes
the real gate accepts; written only after `resolve_pending` (§7.13).

### Promise 4 — Stored memory is supported by the user's words
**Limitation:** grounding proves a quote was said, not that it supports
the claim. Live case: a `python_level` candidate grounded in "I've been
comparing FastAPI and Flask".
**Current honest wording:**
> PIP verifies that Observer evidence was actually said and applies
> evidence-gate and Stage 12 threshold checks. Whether a genuine quote
> actually supports the claim drawn from it has not been separately
> measured.

**Evidence (2026-09-28):** measured end to end on 37 labelled conversations
with the real model (§7.14): 88–90% of learned memories true, the one false
memory being sarcasm; recall 30–39%, mostly lost at the gate. The gate alone
(`scripts/eval_evidence_gate.py`): 0 false accepts on 40 tuned and 25
held-out cases. The wording above predates both.

### Promise 5 — Observer runs only on authorized local providers
**Wording (decided 2026-09-28):**
> The Observer runs only against a provider recorded as local in both of
> its records: the endpoint's own entry (`llm_endpoints.is_local`; Ollama
> is local by definition) and its consent entry
> (`provider_consent.is_cloud = 0`). Both are attested by whoever configured
> the endpoint, never inferred from the hostname; PIP does not verify the
> machine boundary. When no provider passes, nothing is sent and the
> session stays queued; it is processed at a later start or sign-in once
> one does. No mid-session retry is promised.

**Limitation:** re-saving an existing endpoint as local updates only
`llm_endpoints`, so it stays refused until it is removed and added again
(§7.2 finding 2, not fixed).

**Reason:** a loopback address is not proof of locality (tunnels, remote
`OLLAMA_HOST`). Claiming proof would overclaim.
**Enforced by:** the Stage 11 gate (`stage_11_observer.py`, `run()`),
which requires both records; `drain_pending_on_startup` keeps a refused
session queued (§7.11).
**Evidence:** `backend/tests/test_observer_provider_authorization.py` - zero
requests to a loopback provider recorded as not local, break-it caught
(§7.2); a refused session processed at a later start (§7.11).
**History:** the first decided wording named `provider_consent.is_local`,
which does not exist (§7.2 finding 3), and "catch-up at the next launch"
held for one launch only until §7.11.
**Pinned test (Track 1):**
1. Counting stub on `127.0.0.1`, registered with `is_local = false`.
2. Ollama unavailable; trigger the real Observer path with a non-trivial
   user turn.
3. Assert stub requests = 0 and the session is pending-Observer.
4. Flip only `is_local` to `true`; Ollama stays unavailable.
5. Drive the real startup/lifespan catch-up with isolated data (not a
   direct drain call, not `launch_pip.ps1`).
6. Assert only `conversations.observed_at IS NOT NULL` and the session has
   left the pending queue. Do not assert `memory_observation_log`.
7. Manual break-it: weaken the gate, confirm stub count > 0 and the test
   fails, restore.

**As run (Track 1, §7.2):** step 2 uses the idle-timeout trigger, not
disconnect: under TestClient the disconnect path never reached the
Observer, and a first draft passed with the gate removed. Step 4 sets both
locality records (see §7.2 finding 2). Step 6 was too weak as written and
was strengthened: recovery stamps `observed_at` *before* the Observer runs,
and a `failed` row has also left the pending queue, so the test asserts the
queue row is `completed` and the stub received the extraction call.

### Promise 6 — Nothing leaves the machine without recorded consent
**Claim:** fail-closed, per-provider consent covering generation and web
search; nothing preselected.
**Scope:** test the enforcement boundary; no redesign. **Not** one of the
five current tracks — do not open a sixth investigation from it.
**Enforced by (2026-10-02):** Stage 8, on every provider and on web search.
- An unknown provider is refused.
- A provider counts as local, needing no consent, only when both its own
  report and its consent record say so; a disagreement is refused.
- Anything else needs consent: recorded, unrevoked, and covering the
  operation.
- Consent is recorded per provider id, and `add_endpoint` refuses the id of
  a built-in provider, so an id names one provider only (§7.21).

**Evidence:** `backend/tests/test_consent_before_sending.py` asserts on what
reaches a counting stub through the real pipeline (§7.21).
**Limitations:**
- Locality is attested, as in Promise 5: an endpoint saved as local by
  whoever configured it is believed.
- The built-in Ollama is local by definition. An Ollama `*-cloud` model
  would pass as local (D-08, §7.16, not fixed).
- An endpoint re-saved from remote to local stays refused until it is
  removed and added again (§7.2 finding 2).

### Promise 7 — Encryption at rest
**Rejected wording:** "Disk access alone yields only ciphertext."
**Wording (decided 2026-09-28):**
> Each profile's database is encrypted at rest under a key derived from
> its password. The document index stores chunk text and file paths
> encrypted under the same key; embeddings are not encrypted. Uploaded
> documents are also kept as ordinary files in the profile's documents
> folder, unencrypted - the encrypted copy is the one inside the database.
> Unencrypted by design: profile names in the profile registry, and a
> sign-in picture if the user publishes one. Plaintext written before a
> password was set, or by versions before §7.9, is not scrubbed. While a
> profile is signed in, its key is held in the backend's memory and also
> in its process environment, which every child process inherits.

**Limitation kept by decision:** the uploaded-file copy stays unencrypted
on disk. The alternative - keeping only the database copy and writing
files out only when a rebuild needs them - is a code change and was not
authorized.
**Enforced by:** SQLCipher on the database; Fernet/HMAC in `vector_store`
under the same key, which refuses to write without it (§7.9).
**Evidence:** §7.3 (key consumers and child-process inheritance, measured);
§7.8 (upload file on disk in plaintext, measured); `test_profile_boundary.py`
(no plaintext index writes after sign-out).
**History:** "document text is encrypted" overstated it - true of the
database copy, not of the uploaded file (§7.8); the key clause waited on
Track 2, which found the backend exports the key rather than receiving it.

### Promise 8 — Profile isolation
**Claim (adopted 2026-09-28):** nothing derived from one profile's data is
served to another profile or stored under it.
**Enforced by** the sign-out boundary every profile switch passes through:
`session_key.lock()` empties the response cache and moves the session
generation every cache key carries, so nothing one session caches is found
by another (§7.20); `vector_store` refuses
index reads and writes when the active profile has a password but no key is
held (`IndexLockedError`); uploads and ingestion are confined to the active
profile's own documents folder (`vector_store.documents_root()`).
**Evidence:** `backend/tests/test_profile_boundary.py`, through the real
routes, each test seen failing first (§7.8, §7.9).
**Limitations:** one backend process serves every profile, so isolation
rests on these mechanisms, not on OS process separation. A chat connection
already open at sign-out keeps its connection until the client drops it,
and questions asked on it are still answered from its own profile's
database; what it can no longer do is exchange cached answers with a later
session (§7.20). *(Corrected 2026-10-02: this used to say no new work
reaches the data, which §7.20's open-chat test shows it does.)* Files an
older version put in the shared `data/documents` folder stay there.
**Origin:** not in the original seven; the defects it covers were found by
the tracks and broke no written promise (§7.7, the §2.5 limit).

### Promise 9 — Answers reflect the current record
**Claim (adopted 2026-09-28):** an answer about the user reflects their
record as it is when asked.
**Enforced by:** every question reaches the model with the user's identity
and active projects (`stage_04._ALWAYS_TABLES`); the context never presents
what was looked up as the whole record, and names the sections it did not
look up (Stage 7 header, rule 4); a cached answer is never served after the
record changes (`record_version`, bumped by triggers on every table the
context draws from).
**Evidence:** `backend/tests/test_answers_about_the_user.py`, asserting on
the prompt the model receives (§7.10).
**Limitations:** goals, skills, preferences and tools are still fetched by
question category, so a phrasing Stage 1 misroutes gets "not in front of
me" for them rather than the answer. The tests check what the model is
told, not what it says; its replies are not measured.
**Origin:** as Promise 8 - found by Tracks 4a and 4b, outside the original
seven.

---

## 5. Evidence hierarchy

- **Strong:** deterministic test on the real path asserting DB state;
  observed provider calls; import-closure/reachability check; a break-it
  result showing a weakened guard is caught.
- **Medium:** code-path inspection with `file:line`; schema inspection;
  call-site census.
- **Weak (never sufficient alone):** comments, doc claims, function names,
  "implemented" labels, a JSON rule with no traced consumer, a test that
  only asserts config length or content.

> **A guard nobody has watched fail is not a guard.**

---

## 6. Rejected methods (and why)

| Rejected | Reason |
|----------|--------|
| Fixing before the evidence returns | A "gap" may be category C or D; code changes would be wasted or harmful |
| One universal fix ("remove `PIP_DB_KEY` everywhere") | Main DB and `vector_store` are separate consumers with possibly different answers |
| A test that relies on real OS PID recycling | Not controllable; first find what identity the lock stores |
| Merging 4a (routing) with 4b (cache) | Different failure modes; the fabrication incident had three independent causes |
| Trusting a test that uses an injected config | Fixtures and import caches can hide a mutation |
| Upgrading a doc claim into a guarantee | Especially for locality, semantic support, encryption, process identity |
| The full Constitution mutation audit (for now) | Grew past what could be executed; see §9, lesson 1 |

---

## 7. The five evidence tracks

All sent; each has its own stop condition and produces a report only.

| # | Track | Question | Method |
|---|-------|----------|--------|
| 1 | Observer/provider gate | Does the Observer enforce `is_local` on the real path, not via Stage 8 priority or hostname? | Test-first + manual break-it |
| 2 | `PIP_DB_KEY` | Which consumers (main DB vs `vector_store`) depend on the env key; which reads are redundant? | Discovery; two separate findings |
| 3 | PID-reuse lock | Can the lock distinguish the original PIP process from a later process with the same PID? | Discovery-first: what identity is stored |
| 4a | Stage 1 routing | Can classification still route an identity/project question away from the retrieval it needs? | Test-first on retrieval state, not intent label |
| 4b | Cache safety | Can a no-context answer be cached and replayed after correct context exists? | Two-step behavioral test |

Target test file for Track 1:
`backend/tests/test_observer_provider_authorization.py`.

### 7.1 Rules for returned reports
1. Read each report against its own stop condition only.
2. Classify it A–D (§3).
3. A report may **recommend** a fix (Track 3 may name a missing lock
   field). Implementation needs a separate, explicit authorization.
4. After all five are classified, look for cross-track patterns. One is
   **plausible but unverified**: Tracks 2 and 3 may both be category B
   (missing state). Do not write it into any promise until both reports
   confirm it independently.

### 7.2 Track 1 report — Observer/provider gate (2026-09-26)

**Stop condition:** does the Observer enforce locality on the real path, not
via Stage 8 priority or hostname? **Answer: yes. Category C.**

Evidence (strong): `backend/tests/test_observer_provider_authorization.py`,
real WS session → idle timeout → `_default_observer_provider` →
`OpenAICompatibleProvider` → counting stub on `127.0.0.1`. Registered
non-local: 0 stub requests, 0 Ollama calls, the refusal is
`ObserverLocalProviderError`, and `observed_at` stays NULL. Break-it
(gate at `stage_11_observer.py:772` disabled): stub receives
`POST /v1/chat/completions`, both tests fail; restored, both pass. Marked
local in both records, the real lifespan catch-up processes the session
(`completed`, one stub call).

Further findings, found by running the code (two temporary tests, since
deleted) — **recommendations only, nothing implemented:**

1. **Queue-not-fallback breaks at the next launch (category A).** If no
   local provider exists at startup, recovery sets `observed_at`, the drain
   gets `ObserverLocalProviderError`, and the row is marked `failed`, which
   is terminal. A second start does not retry it, so the session is never
   learned from, even after a local provider is added later. The retry
   mechanism exists (`pending_observer.RetryableError` → `deferred`), but
   `drain_pending_on_startup` (`session_lifecycle.py:309`) routes only
   `ObserverUnavailableError` into it. It fails closed (nothing leaves the
   machine), but the "queued for next launch" claim does not hold past the
   first start. **Fixed 2026-09-28 in `2306831` (§7.11).**
2. **Locality lives in two records, and they can disagree.**
   `llm_endpoints.is_local` (the provider's self-report) and
   `provider_consent.is_cloud`. The Stage 11 gate requires both.
   `add_endpoint` updates the first on re-save, but inserts the consent row
   with `ON CONFLICT DO NOTHING`, and no route changes `is_cloud`. So
   re-saving a non-local endpoint as local leaves it permanently refused.
   It fails closed, and the only way out is to remove and re-add the
   endpoint. This conflicts with §2.3 "one source of truth per rule".
3. **Promise 5 wording names a column that does not exist (category D).**
   There is no `provider_consent.is_local`. The attested record is
   `provider_consent.is_cloud` together with `llm_endpoints.is_local`. The
   wording needs an owner decision; it is not changed here. **Resolved
   2026-09-28: Promise 5 reworded in §4 (`2003817`).**

Not in scope, noted: `server.py` `_default_observer_provider` carries an
unreachable duplicate of its own fallback block after `return ollama`.

### 7.3 Track 2 report — `PIP_DB_KEY` (2026-09-26)

**Stop condition:** which consumers (main DB vs `vector_store`) depend on
the env key, and which reads are redundant? Two findings, one per
consumer, as required.

**Method.** Baseline full suite at `db2ddd8`: 1191 pass, 3 fail. All
three are in `test_llm_endpoint_store.py`, need a running Ollama, and pass
17/17 with `is_available` patched True. The same run intermittently hangs
in `test_ws_chat_accumulates_conversation_history_across_turns`, a known
flake (see `pytest.ini`); it happened once in three runs today. Then two
mutations, each in a throwaway worktree, full suite each: (A) `_conn()`
reads `session_key.current_key()` instead of the env; (B) the same for
`vector_store._get_db_key()`. Plus two temporary behavioural checks,
since deleted.

**Finding 1 — main DB (`server._conn`, `server.py:1004`): the env read is
redundant in-process. Category C for the read itself.**
- Mutation A changed nothing: 1191 pass, the same 3 fail. That is medium
  evidence ("no test notices").
- The code path agrees. Every in-process write of the variable is paired
  with `session_key._key`: set in `unlock`, `set_initial_password` and
  `change_password` (`session_key.py:190`, `230`, `370`), popped with it in
  `lock` (`:89`), and adopted into it at lifespan start (`:109`).
- No other backend code opens the main DB from the env.

**Finding 2 — `vector_store` (`_get_db_key`, `vector_store.py:124`): the
env read is load-bearing, and it fails open. Category A.**
- **Not redundant.** `scripts/restore_backup.py:318` sets the env purely so
  `vector_store` encrypts the rebuilt index; a script process has no
  `session_key`.
- Mutation B broke 8 `test_vector_store` tests, but they use the env as
  their switch for the encrypted path, so that is test mechanism, not
  production. (A ninth, `test_ws_chat_lazily_creates...`, failed on the
  race its own comment describes; that path does not use `vector_store`.)
- The consequence Mutation B *should* have exposed went unnoticed:
  `test_restore_backup` replaces `rebuild_vector_index` with a stub, so a
  restore that silently builds a plaintext index is not caught by any
  test.
- **Fails open.** With no key in the env, chunk text and the file path are
  written in plaintext even when the main DB is encrypted (the "no-op
  passthrough", `vector_store.py:120`). Confirmed by a run of the real
  functions: signed in, a chunk was stored encrypted; after
  `session_key.lock()` (what `POST /auth/lock` calls) on the same open
  connection, the next chunk's text and path were on disk in plaintext,
  and `check_consistency` then reported the document as drifted.
- **Reachability in the app is by code reading only, not demonstrated.**
  `/auth/lock` neither waits for nor cancels `_catch_up_task` (which runs
  `rebuild_if_drifted`), and a request already running keeps its
  connection. So an index rebuild or ingest in flight at sign-out writes
  plaintext.
- **Prediction, not verified:** a later re-index writes encrypted chunks
  under the HMAC id but does not remove the plaintext ones, so the
  plaintext would persist.

**Also confirmed: the key reaches child processes.** After unlock,
`GET /llm/catalog` runs `nvidia-smi` (`ollama_provider.py:184`) with the
inherited environment. A stand-in executable received the exact key in
`PIP_DB_KEY`.

**What this does to the decided outcome (§8.1).** The pre-accepted
completion was "redundant `vector_store` read + documented main-DB env
transport". The evidence says the reverse: the main-DB read is the
redundant one, and the `vector_store` read is the load-bearing transport,
with a fail-open. The §7.1 warning applied; the expected outcome was not
the result.

**Recommendations only — nothing implemented:**
1. `vector_store` fails closed when the main DB is keyed and no key is
   present, instead of writing plaintext.
2. `/auth/lock` waits for, or cancels, in-flight index writes before
   forgetting the key.
3. Pass the key to `vector_store` explicitly (as `reencrypt` already
   takes it) rather than through the env. Then the env export, and its
   inheritance by `nvidia-smi` or any future child, can go.
4. `test_restore_backup` asserts the rebuilt index is encrypted, not just
   that the rebuild was called with a key.

**Candidate Promise 7 final clause (owner decision):**
> While PIP is unlocked, the key is held in the backend's memory and is
> also exported to its process environment, where child processes inherit
> it. Index writes made without the key in that environment are stored
> unencrypted.

### 7.4 Track 3 report — PID-reuse lock (2026-09-27)

**Stop condition:** can the lock tell the original PIP process from a later
process with the same PID? First, what identity does it store? **Answer:
no. It stores a bare PID and nothing else. Category B (missing state).**

**What exists.**
- `instance_lock.acquire()` (`instance_lock.py:131`) writes `str(os.getpid())`
  to `data/pip.lock`.
- Every consumer reads only that integer and asks whether it is alive:
  - `acquire()` itself, via `_pid_is_running`: GetExitCodeProcess on
    Windows, `kill(pid, 0)` on POSIX;
  - `restore_backup.py:148`, `merge_projects.py:87` and
    `seed_demo_conversation.py:254`, all through `_pid_is_running`;
  - `launch_pip.ps1:84`, via `Get-Process`;
  - `_db.py`, `clear_poisoned_snapshot.py`, `retract_fabricated_candidates.py`
    and the two `seed_project_*` scripts, which only print a note.
- **What is missing:** anything that identifies *which* process, such as
  the process creation time or the executable. With a bare PID, "the PIP
  that wrote this" and "whatever now has that number" are the same state.

**Evidence (strong for the mechanism).** PID reuse was simulated, not waited
for (§6): the lock was pointed at a live `ping.exe`, which is exactly the
state recycling leaves behind. In a temporary test, since deleted:
- The real app lifespan refused to start with `AlreadyRunningError`
  ("PIP backend is already running (pid N) … Stop that instance first").
- `restore_backup.refuse_if_pip_is_running()` exited: "PIP appears to be
  running".
- The launcher's stale-lock block, run verbatim, kept the lock: `Get-Process`
  reported `PING`.
- Control: once `ping` exited, `acquire()` took the lock over.

The existing suite already pins this behaviour without naming it:
`test_acquire_raises_when_a_live_different_pid_holds_the_lock` uses the
pytest *parent* process, which is not PIP, as the holder.

**What broken looks like.** It fails *safe* for data: it refuses and
never steals, so two writers are never allowed. It fails *hard* for the
user:
- The backend does not start, and when the launcher starts it hidden
  that failure is invisible (by the launcher's own comment at `:71`; not
  demonstrated here).
- Restore and merge refuse to run.
- The error tells the user to stop "that instance" by PID, which after
  reuse is an unrelated process.
- The launcher's cleanup cannot help, because it asks the same question
  with the same missing state.

**Not measured:** how often Windows actually reuses a stale PID. That is a
property of the OS and was deliberately not tested (§6).

**Recommendation only — nothing implemented:** store the holder's process
creation time next to the PID, and treat the lock as held only if a live
process with that PID has that creation time. Every Python consumer
already goes through `_pid_is_running`, so one function changes. The
launcher's PowerShell check is a second copy of the rule and would need
the same field (§2.3, one source of truth).

**Noted, out of scope:** `acquire()` checks the file and then writes it
without an atomic create, so two backends starting at the same instant
could both take the lock. That is a race, not PID reuse, and was not
tested.

**Cross-track (§7.1 rule 4):** the prediction that Tracks 2 and 3 would
both be category B does not hold. Track 3 is B; Track 2 came back C and A.

### 7.5 Track 4a report — Stage 1 routing (2026-09-27)

**Stop condition:** can classification still route an identity or project
question away from the retrieval it needs? Asserted on what reaches the
model, not on the intent label. **Answer: yes, for most phrasings tried.
Category A.** Retrieval exists and works; the classifier disconnects it.

**Mechanism.**
- Stages 3 (decision log) and 5 (RAG) always run.
- Only Stage 4 (profile memory) is gated by category, through
  `stage_04._CATEGORY_TABLES`.
- `external_information`, `general_knowledge` and every unmapped category
  fetch `interaction_style` alone. `coding_question` and `research_request`
  fetch neither identity nor projects.
- Stage 1 checks categories in order: continuation, external, coding,
  research, then project, then personal. So any external keyword
  (`current`, `latest`, `recent`, `today`, `right now`), coding verb or
  research verb wins over the words "my" and "project".

**Evidence (strong).** A temporary test, since deleted, ran the real
`pipeline.run_sync` on a real DB seeded with a name (`Zarqa Venn`) and an
active project (`Heliotrope`). A recording provider captured the exact
prompt the model received.

| Question | Category | Name in prompt | Project in prompt |
|---|---|---|---|
| who am I? | personal | yes | yes |
| what's my name? | personal | yes | yes |
| list my projects | project | no | yes |
| what are my goals? | personal | yes | yes |
| what is my current project? | external | **no** | **no** |
| what's the latest on my project? | external | **no** | **no** |
| what have I been working on recently? | external | **no** | **no** |
| what am I working on right now? | external | **no** | **no** |
| what should I do today on my thesis? | external | **no** | **no** |
| what am I working on? | general | **no** | **no** |
| where did we leave off? | general | **no** | **no** |
| help me implement the next step of my project | coding | **no** | **no** |
| debug the login bug in my project | coding | **no** | **no** |
| compare my project vs a typical final year project | research | **no** | **no** |

10 of the 14 lost the project. The failures are the ordinary ways to ask
what you are working on.

**It is worse than missing context.** For "what is my current project?"
the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete
record, not a sample):` and then lists only the interaction style. Rule 4
of the same prompt tells the model to answer that it has nothing recorded.
- The expected answer is therefore a confident *"you have no project
  recorded"* while the project is in the database. That is the inverse of
  the fabrication incident: a false negative instead of an invention.
- Cause: `stage_07` renders "none recorded" only for tables in the
  category's expected set (`stage_07_context_assembly.py:173–213`). Tables
  outside it are silently omitted under a header that claims completeness.
- The model's actual reply was not observed; a fake provider was used.

**Side observation, Promise 6 territory — not investigated.** Five of these
personal questions also match the Stage 6 web-search trigger. With web
search consented, the message text would be sent to the search provider.
It is consent-gated, so this is not a leak; but a question about the user
triggering a web search is a routing effect, not an intent.

**Recommendations only — nothing implemented:**
1. Do not let the context header claim a complete record for tables that
   were not fetched. Either say which were not looked up, or drop
   "complete".
2. Fetch identity and active projects for every category. They are small,
   and the §4 "extra harmless context" reasoning already accepted this for
   the word "project".
3. If category precedence is kept, a first-person or "working on" signal
   should outrank the external, coding and research keywords.
4. Turn the table above into a permanent test on prompt content, the same
   shape as the probe.

### 7.6 Track 4b report — cache safety (2026-09-27)

**Stop condition:** can a no-context answer be cached and replayed after
the correct context exists? Two-step behavioural test. **Answer: yes, and
across profiles. Category A.** Freshness rules exist, but the replay path
is not connected to them.

**Mechanism (`response_cache.py`, `pipeline.py:306`).**
- The cache is a module-level dict held in process memory. Its key is
  `sha256(normalised message + project_id)`.
- It is checked after Stage 1 and **before** Stages 3–9. A hit therefore
  skips the decision log, the profile lookup, RAG and the model.
- The TTL is fixed when the answer is written: 24h for `general_knowledge`
  and `technical_explanation`, 1h for `external_information`, 0 for
  personal and project questions.
- The "decision log always overrides" rule (Part 7.1) is enforced only at
  write time (`decision_log_hit=`). The read does not consult the category
  or the decision log.
- Nothing outside `pipeline.py` references the cache. Nothing invalidates
  it on new documents, decisions, profile changes, sign-out or profile
  switch.

**Evidence (strong).** Temporary tests, since deleted, ran the real
pipeline with a recording provider. In each case step 1 asked with no
context and step 2 asked again after the context was added. A control
repeated step 2 with the cache cleared, to show the new context would
have been used.

| Case | Step 2, cache as-is | Control, cache cleared |
|---|---|---|
| Document ingested after caching ("explain how the Heliotrope sync engine works", technical, 24h) | model **not called**; `NO-CONTEXT ANSWER` replayed | model called; document in prompt |
| Decision logged after caching ("what is the best database for a desktop app") | model **not called**; stale answer replayed | model called; decision in prompt |
| Profile A's document-based answer, same question asked against profile B's database in the same process | B received **A's answer**; B's model not called | — |

The decision case breaks two stated rules at once. Once the decision
exists, the question is classified `project_question` (TTL 0, "never
cached"), and it matches the decision that "always overrides". Both
checks come after the cache read, so neither is consulted.

**Cross-profile.** Profiles are separate password-encrypted databases
served by one backend process. The cache key has no profile in it, and
the cache survives sign-out and switching.
So an answer built from one profile's documents or record is served to
another profile that asks the same words within the TTL. **This crosses
the boundary the per-profile encryption exists to keep.** Demonstrated at
the pipeline level with two databases in one process; the real
sign-out → switch → sign-in route sequence was not driven end to end.

**Interaction with 4a (not separately tested).** "what am I working on?"
is `general_knowledge`, so after §7.5's "you have no project recorded"
answer it would be cached and replayed for 24h. "what is my current
project?" (`external_information`) would be replayed for 1h. The two
defects compound; they remain separate causes (§6).

**Bounded by:** process lifetime (the cache is memory-only, so a restart
clears it) and the TTL.

**Recommendations only — nothing implemented:**
1. Include the active profile in the key, and clear the cache on sign-out
   and on profile switch. This is the confidentiality item and the most
   urgent.
2. Consult freshness at read time, not only at write time. Re-check the
   decision log before serving, or version the key by the last change to
   documents, decisions and profile.
3. Do not cache an answer whose context contained no user record, or that
   was produced for a question Stage 1 has since reclassified.
4. A permanent two-step test per case above.

### 7.7 Cross-track synthesis (2026-09-27)

Authorized 2026-09-27, run after all five reports were classified (§7.1
rule 4). Built only from §7.2–§7.6: no new code was run for it. A pattern
is stated as **confirmed** only when at least two reports show it
independently. Anything else is labelled.

#### Classification at a glance

| Track | Result | What breaks, as seen from outside |
|---|---|---|
| 1 Observer gate | C, plus A and D | Nothing leaves the machine; a session queued at startup is lost for good |
| 2 `PIP_DB_KEY` | C (main DB), A (`vector_store`) | Index text and file paths written as plaintext after sign-out |
| 3 PID lock | B | PIP refuses to start when a reused PID is alive |
| 4a Routing | A | "You have no project recorded" while the project is in the DB |
| 4b Cache | A | Stale answers replayed; one profile's answer served to another |

The original "gap" list meant *unverified* (§3). Of six findings, only
one, the Observer gate, turned out to be already enforced.

#### Pattern 1 — the sign-out / profile-switch boundary does not reach work already in memory. Confirmed (Tracks 2, 4b).

- `session_key.lock()` forgets the key, and `/auth/lock` refuses new
  routes.
- What already exists in the process is not touched:
  - Track 2: in-flight index writes read the now-empty env and store
    plaintext;
  - Track 4b: the module-level response cache keeps serving answers, now
    to a different profile.
- Both break the same thing: per-profile confidentiality, which Promise 7
  and the per-profile password exist to provide.
- Neither defect was found by looking at the boundary. They are separate
  mechanisms that fail at one moment.
- **Unverified link shared by both:** neither report drove the real
  `/auth/lock` → `/auth/profile` → unlock route sequence end to end. One
  such test would confirm or refute both at once (see "next evidence").

#### Pattern 2 — one rule, two copies. Confirmed present in all five tracks; confirmed harmful in three.

§2.3 "one source of truth per rule" is broken in every track:

| Track | Rule | Copy 1 | Copy 2 | Observed effect |
|---|---|---|---|---|
| 1 | Is this provider local? | `llm_endpoints.is_local` | `provider_consent.is_cloud` | Re-saving as local leaves the provider permanently refused |
| 2 | What is the key? | `session_key._key` | env `PIP_DB_KEY` | Paired in the backend, but the env copy is also the script transport and is inherited by `nvidia-smi` |
| 3 | Is PIP running? | `_pid_is_running` (Python) | `Get-Process` (launcher) | Both miss reuse; a fix to one leaves the other wrong |
| 4a | What was the model told exists? | `stage_04._CATEGORY_TABLES` | `stage_07` "complete record" header | The header claims completeness for tables never fetched |
| 4b | Is this answer still valid? | Write-time checks (TTL 0, decision override) | Read path (none) | Stale answers served past both rules |

Only Tracks 1 and 4a show the copies actually *disagreeing* in a run, and
4b shows one copy bypassed; in 2 and 3 the copies can drift but were not
seen to. So the confirmed claim is: the duplication is present in all
five, and it produced a wrong outcome in three (1, 4a, 4b).

#### Pattern 3 — mechanisms built as fail-closed held; mechanisms treated as optional carried correctness and failed open. Confirmed (Tracks 1, 3 vs 2, 4a, 4b).

- **Designed to refuse, and did:**
  - the Observer locality gate (1): zero requests, and the break-it was
    caught;
  - the instance lock (3): refuses, never steals.
- **Designed as a convenience, and failed open where correctness depended
  on them:**
  - `vector_store`'s "no-op passthrough" without a key (2);
  - the category default of `interaction_style` only (4a);
  - the response cache, documented as "never load-bearing for
    correctness" (4b), which the §7.6 evidence contradicts.

The safety-critical defects all sit in the second group. Implication,
labelled as a *recommendation* rather than a finding: classify a component
by what it can cause, not by what it was built for. If a component can
change what the user is told, or what reaches disk, §2.3 "fail closed"
applies to it.

#### Pattern 4 — the tests hid the defect; they did not merely miss it. Confirmed (all five).

| Track | How the existing or planned test concealed it |
|---|---|
| 1 | The planned step 6 would pass on failure (`observed_at` is set before the Observer runs); the first draft passed with the gate removed, because the disconnect path never ran under TestClient |
| 2 | `test_restore_backup` stubs the rebuild; `test_vector_store` runs an encrypted DB with a plaintext index as the default case |
| 3 | `test_acquire_raises_when_a_live_different_pid_holds_the_lock` pins "any live PID blocks" using a non-PIP holder, without naming the consequence |
| 4a | `test_stage_01_intent_classifier.py` makes 19 assertions on the category label and none on what reaches the prompt |
| 4b | `test_pipeline.py`'s autouse `isolated_response_cache` fixture was added because a cached answer from one test served a later one. That *is* the production defect; the fixture removed the symptom from the suite |

This is §2.2 ("assert on outcomes, not return values") and §5 ("a guard
nobody has watched fail is not a guard") confirmed from the other side: in
each track the test sat one layer too far in, or cleaned away the state
the defect lives in. The 4b case is the sharpest. Test isolation is right
for the suite, but it removed the only place the defect had ever been
seen, and the fixture's comment was never turned into a product finding.

#### Pattern 5 — keys that identify less than the thing they stand for. Confirmed (Tracks 3, 4b).

- The lock treats a PID as a process, but a PID names a process only for
  its lifetime (3).
- The cache treats message + project as an answer's identity, but the
  answer also depends on profile, documents and decisions (4b).
- Both are missing-state defects (category B in shape, even where the
  track as a whole is A).
- The same fix shape applies to both: add the missing identity (creation
  time; profile and record version) to the key.
- This is the missing-state pattern §7.1 predicted for Tracks 2 and 3.
  That prediction was wrong about Track 2 but right in kind: it appears
  in 3 and 4b.

#### Not confirmed — kept as predictions

- ~~Plaintext chunks survive a later re-index~~ — confirmed in §7.8.
- ~~In-flight writes during sign-out are reachable in practice~~ —
  confirmed on `/rag/ingest` in §7.8.
- A real model answers "no project recorded" (4a; a fake provider was
  used).
- The `test_ws_chat` hang (once in three full runs) is independent of
  Track 1's test file (not measured).

#### What this means for the promises (owner decisions; nothing rewritten here)

- **The largest defects fall outside the seven promises.** Cross-profile
  answers (4b) and wrong answers about the user (4a) break no written
  promise, because none covers them: exactly the §2.5 limit. Candidates:
  - **Promise 8, profile isolation:** nothing derived from one profile's
    data is served to, or stored under, another profile.
  - **Promise 9, current record:** an answer about the user reflects the
    record as it is when asked. Never a cached answer from before it
    changed, and never "none recorded" for data that was not looked up.
- **Promise 5:** "queued for the next launch" holds for one launch only
  (Track 1 A), and the named column does not exist (Track 1 D).
- **Promise 7:** the final clause is decided by Track 2. Pattern 1 adds
  that encryption at rest can be bypassed at the moment of sign-out.
  Candidate wording is in §7.3.

#### Suggested order for authorizing fixes (a recommendation, not a decision)

1. **The profile boundary (Pattern 1):** Track 2 recommendations 1–2 and
   4b recommendation 1. They are confidentiality defects and share one
   boundary, so one regression test covers both.
2. **Answers about the user (4a + 4b, compounding):** 4a recommendations
   1–2 and 4b recommendation 2.
3. **Lost learning:** Track 1 finding 1, a locality refusal at startup
   being terminal.
4. **Availability:** the Track 3 lock identity.
5. **Wording:** Promises 5 and 7, plus the decision on Promises 8–9.

Each fix follows §2.2: test first on the outcome, break it once, one
commit per promise.

#### Single highest-value next evidence

One end-to-end test through the real routes:
1. Sign in to profile A and index a document.
2. Ask a technical question (so the answer is cached).
3. Start an index rebuild and sign out mid-rebuild.
4. Switch to profile B, sign in, and ask the same question.
5. Assert: B's model is called; B's answer contains nothing from A; and
   no plaintext chunk exists in A's index.

It would move two of the "not confirmed" items above to confirmed or
refuted, and it becomes Pattern 1's permanent regression test.

### 7.8 End-to-end profile boundary test (2026-09-27)

This is the §7.7 "single highest-value next evidence" test, run through the
real routes (`/auth/profiles`, `/auth/setup`, `/rag/upload`, `/rag/ingest`,
`/ws/chat`, `/auth/lock`, `/auth/profile`, `/auth/unlock`) under a real
lifespan. It lives outside the suite (see "status of the test").

**Patched, and why:**
- the model provider, replaced by a recorder, so we see exactly what the
  model would be sent;
- the Observer, a no-op here because it is unrelated and would reach for
  Ollama;
- `vector_store.DOCUMENTS_ROOT`, a module constant aimed at the real
  `data/documents`, redirected to a temp folder so the test cannot write
  user data;
- a one-shot pause before the index write, so that sign-out lands while an
  ingest is in flight. It changes timing only.

**Results:**

| Claim under test | Result |
|---|---|
| Profile B is served profile A's answer (4b) | **Confirmed.** Bob, signed into his own new profile, asked the same question and received `ANSWER#1 citing QUOKKA-7`, Alice's answer built from Alice's document. `cache_hit: True`; Bob's model was never called. |
| An index write in flight at sign-out is stored in plaintext (Track 2) | **Confirmed on `/rag/ingest`.** Event order: ingest paused at the index write → `/auth/lock` returned 200 with no key held → ingest returned 200. The chunk text and its file path were stored in plaintext in Alice's index. |
| The plaintext survives a later re-index (Track 2 prediction) | **Confirmed.** Alice signed back in and catch-up finished. The plaintext chunk and plaintext path were still on disk, and no encrypted copy was added (2 chunks before and after). |
| The same through `/rag/upload` | **Not reproduced**, and not reachable in this form. The upload chunk was stored encrypted. `/rag/upload` is an `async` route that runs the embedding synchronously, so it holds the event loop and `/auth/lock` cannot run until it ends. That is **inferred from timing** (44.7s with a 30s pause, against 12.8s via `/rag/ingest`), not measured directly. It also means an upload stalls every other request while it embeds; that is out of scope and noted only. |

**New finding: uploaded documents are neither per-profile nor encrypted
on disk. Category A.**
- `profiles._activate` re-points `PIP_DOCUMENTS_ROOT`.
- But `/rag/upload` writes to `vector_store.DOCUMENTS_ROOT`
  (`server.py:767–775`), a constant fixed at import.
- `_validate_file_path` checks ingest paths against that same constant.
- Observed: Alice's uploads landed in the shared folder, not in
  `profiles/alice/documents`; both profiles' own `documents` folders
  stayed empty; and both files were visible from Bob's side.
- The uploaded file is written as the uploaded bytes: `heliotrope.txt` on
  disk contained `QUOKKA-7` in plaintext.
- This contradicts Promise 7's "document text … encrypted at rest" for
  the upload copy. It also means one profile's documents sit where
  another profile's ingest would accept them.

**Effect on §7.7.**
- Pattern 1 now has three confirmed mechanisms, all through real routes:
  the cache, in-flight index writes, and the upload folder.
- Two of §7.7's four "not confirmed" items are now confirmed:
  in-flight writes are reachable, and plaintext survives a re-index.
- The remaining two (the real model's answer in 4a, the `test_ws_chat`
  hang) are unchanged.
- Candidate Promise 8 (profile isolation) is now broken three ways.

**Status of the test.** It prints observations rather than asserting
correct behaviour, because all three defects are present and a test that
asserts the fix would fail. It was kept outside the repository pending a
decision, and was superseded by `test_profile_boundary.py` (§7.9):
- commit it as a strict `xfail` that turns green when fixed; or
- commit it with the fix, as Pattern 1's regression test (§2.2: test in
  the same commit as the change).

### 7.9 Profile boundary fixes (authorized 2026-09-27)

This is the first fix authorization under the freeze: §7.7's suggested
item 1, plus the §7.8 upload finding. Each fix followed §2.2:
- a promise, and the mechanism that enforces it;
- an end-to-end test through the real routes, **seen failing on the
  unfixed code** for the stated reason (which is the break-it);
- the smallest change, then the full suite;
- one commit per promise.

All five tests are in `backend/tests/test_profile_boundary.py`, which is
now Pattern 1's regression test.

| Commit | Promise | Mechanism | Seen failing before the fix as |
|---|---|---|---|
| `a1a1a6b` | An answer cached in one session is never served after it ends, in particular to the next profile | `session_key.lock()` empties the response cache | Bob's question never reached his model |
| `a37da7c` | No chunk or file path is written to the index in plaintext while the profile's DB is encrypted | `vector_store._get_db_key()` raises `IndexLockedError` when the profile has a salt but no key is held | chunk text reached disk in plaintext |
| `be74d70` | A document uploaded in a profile is stored in that profile's folder, and no other profile can ingest it | `vector_store.documents_root()` follows the profile; the `DOCUMENTS_ROOT` constant is removed; `adopt_shared_documents()` copies legacy records in at sign-in | the upload was stored in the shared folder; the legacy record was never adopted |
| `9327887` | Each sign-in runs its own catch-up | `_start_catch_up()` queues behind a running catch-up instead of skipping | Bob's unobserved conversation was never recovered |

The full suite passed after every commit; the last run was 1199 passed.

**The fourth promise was not in the authorized list.** It was found while
fixing the second one. The catch-up started by `/auth/setup` was still
running at sign-out, and it hit the new refusal, which was correct. But
the next sign-in then skipped its own catch-up because one "was running".
- This corrects the claim made when the fixes were planned, that
  fail-closed "covers" Track 2 recommendation 2. The refusal stopped the plaintext,
  but the refused work was never redone until catch-ups were queued.
- It was fixed under the same authorization, because it sits on the same
  boundary and a sign-in with no catch-up is a new session left without
  its recovery. Flagged here so the owner can object.

**Deliberately not covered (still open):**
- **Plaintext already on disk is not scrubbed.** That covers:
  - chunks written by the old in-flight path;
  - the originals left in the old shared folder (copied, not moved,
    because another profile may name the same file);
  - uploaded files, which are still written to the profile's folder as
    the uploaded bytes.

  The last contradicts Promise 7's "document text … encrypted at rest"
  for the file copy. It now needs a wording decision or a separate fix.
- **Same-profile staleness** (§7.6 recommendation 2): a new document or
  decision still does not invalidate a cached answer within one session.
  That is item 2 of the fix order.
- **`/rag/upload` holds the event loop while it embeds** (§7.8, inferred
  from timing). This is out of scope, and it is also why that route could
  not interleave with sign-out.
- **Promise 8 wording.** Profile isolation now has mechanisms and tests
  for the four paths above. Writing it as a promise is still an owner
  decision (§7.7).

### 7.10 Answers-about-the-user fixes (authorized 2026-09-28)

§7.7's suggested item 2: §7.5 (4a) recommendations 1–2 and §7.6 (4b)
recommendation 2. The same method as §7.9: each test was seen failing on
the unfixed code, then the smallest change, then the full suite, one
commit per promise. The tests are in
`backend/tests/test_answers_about_the_user.py` and assert on the prompt the
model receives through the real pipeline.

| Commit | Promise | Mechanism | Seen failing before the fix as |
|---|---|---|---|
| `55d1523` | Every question reaches the model with the user's identity and active projects | `stage_04._ALWAYS_TABLES` added to every category's table set | 11 of the 14 Track 4a questions |
| `3173f60` | The prompt never presents what was looked up as the whole record | The Stage 7 header says each section is complete and names the sections not looked up; rule 4 now says "not in front of you" instead of "not recorded" | "the complete record" still in the prompt |
| `111c43e` | A cached answer is never served after the user's record changes | A `record_version` counter bumped by triggers on `RECORD_TABLES` is part of the cache key | Stale answer served, with the model never called, after a document, a decision and a new project |

The last full-suite run was 1219 passed.

**Two test-design corrections, recorded because §5 applies to our own
tests too:**
- The first cache tests asked about "the Heliotrope sync engine" while
  Heliotrope was the seeded project. That made the question a project
  question, which is never cached, so the control failed and every
  staleness case passed on the unfixed code. The questions were changed
  until the control passed and the cases failed.
- The control (`test_an_unchanged_record_is_still_answered_from_the_cache`)
  stays as a guard. A trigger on a table written on the per-message path
  would quietly switch the cache off, and this test would catch it.

**Flake measured, not assumed.** `test_ws_chat_lazily_creates_…` failed
once under full-suite load during this work (its second failure today).
It replaces `pipeline.run`, so none of these changes run inside it. Run in
isolation it passed 15/15 on the change and 15/15 on the previous commit.

**Deliberately not covered (still open):**
- **Whether a real model behaves better with the new header and rule 4 is
  not measured.** The tests check what the model is told, not what it
  says. The fabrication incident is why rule 4 exists; its protection
  against guessing is kept word for word, and only "recorded" became "in
  front of you".
- §7.5 recommendation 3 (letting first-person signals outrank Stage 1's
  external, coding and research keywords) was not authorized. With
  identity and projects always sent, it now matters only for the other
  tables (goals, skills, preferences), which the prompt now names as not
  looked up.
- Personal questions that match the web-search trigger (§7.5 side note,
  Promise 6) are unchanged.
- The cache key still ignores conversation history, as before this work.
- **Candidate Promise 9 (current record)** now has mechanisms and tests
  for all three of its parts. Writing it down is an owner decision.

### 7.11 Lost-learning fix (authorized 2026-09-28)

§7.7's suggested item 3: §7.2 finding 1.

- **Promise:** a session the Observer could not process for lack of a
  local provider stays queued, and is processed at a later start once one
  exists, with nothing sent anywhere in between.
- **Mechanism:** `drain_pending_on_startup` translates
  `ObserverLocalProviderError` into `pending_observer.RetryableError`, as it
  already did for `ObserverUnavailableError`, so the row is deferred instead
  of `failed`.
- **Test:**
  `test_a_session_refused_at_startup_for_locality_stays_queued_for_a_later_start`
  in `backend/tests/test_observer_provider_authorization.py`. It uses the
  real lifespan catch-up twice, with a loopback stub recorded as not local
  and then as local. On the unfixed code it failed with `['failed']`. It
  passes now, and the stub receives nothing until the second start.
- **Commit:** `2306831`. It also corrects two Stage 11 docstrings that
  called the locality error a caller programming error and said LLM
  failures fail open.
- **Full suite:** 1217 passed and 3 failed. The three are the
  `test_llm_endpoint_store` tests that need a running Ollama (down on this
  machine, same assertion as the §7.3 baseline).

**Still open from Track 1:**
- Finding 2 (locality in two records that re-saving can leave in
  disagreement).
- Finding 3 (the Promise 5 wording names a column that does not exist).
- The unreachable duplicate block in `_default_observer_provider`.

**Unchanged by design:** a row deferred for locality is re-checked at every
start until a local provider exists. The check happens before any call, so
a start with none still sends nothing.

### 7.12 Lock identity fix (authorized 2026-09-28)

§7.7's suggested item 4: the §7.4 recommendation.

- **Promise:** the instance lock counts as held only by the process that
  took it. A later process handed the same PID does not block PIP.
- **Mechanism:** `data/pip.lock` holds `<pid> <creation time>`.
  `instance_lock.holder()` is the only place the rule is decided: held
  means that PID is alive **and** was created at that time. A creation
  time that cannot be read counts as held, so it fails toward refusing a
  free lock, never taking a held one. Every gate asks `holder()`:
  - `acquire()`;
  - the `restore_backup`, `merge_projects` and `seed_demo_conversation`
    gates;
  - the launcher, through the backend's own Python.
  A bare-PID file keeps its old meaning.
- **Tests:** `backend/tests/test_lock_identity.py`. A real holder takes
  the lock and exits, then the PID in the file is pointed at a live
  `ping.exe`, which is the state reuse leaves. On the unfixed code the
  backend, the restore script and the launcher's real block, cut from
  `launch_pip.ps1`, each refused. They were three tests, seen failing
  separately, and each passes now. The control, a live holder, is still
  refused by all three.
- **Commit:** `c940bed`.
- **Full suite:** 1220 passed and 4 failed. One was a lifespan test that
  read the file with `int()`; it was fixed in the same commit, and its
  file now passes 65/65. The other three are the Ollama-dependent tests
  (§7.3).

**Two decisions made during the fix (the owner may object):**
- **The launcher no longer repeats the rule in PowerShell.** The obvious
  port compares `Process.StartTime`, which is local time. Converting it
  back can be an hour off for a process started in the hour the clocks go
  back, and that error deletes a *live* lock, which is the one failure
  this lock exists to prevent. The launcher now asks `holder()` through
  Python, so the rule has one copy (§2.3).
- **Every script that parsed the file with `int()` had to change with the
  format.** Otherwise they would have read the new format as "not
  running", and a restore would have run over a live database.

**Not covered (still open):**
- `acquire()` still checks the file and then writes it without an atomic
  create. That is the §7.4 race note; it is not PID reuse, and it was not
  tested.
- The Linux branch of `_process_started_at` (`/proc/<pid>/stat`) is
  untested; this machine is Windows. Anywhere else the time is not
  recorded, and the lock behaves as before.
- Five note-only scripts (`_db.py` and four seed/cleanup scripts) print
  the file's raw contents, now including the creation time. That is
  cosmetic.

### 7.13 Promises 1–3 tests (authorized 2026-09-28)

This was the council's "one thing to do first" (council transcript,
2026-09-28). The work is tests, not fixes. Result: **all three promises
hold on the current code. Category C.**

**Method.** `backend/tests/test_observer_governance.py` drives the real
session-end path, `stage_11_observer.run_session_end`, on an onboarded
profile.
- A scripted stand-in plays the Observer's LLM, which is the untrusted
  part; everything after it is real (grounding, the evidence gate, Stage 12
  with the Constitution, and Stage 13).
- Every assertion is on database state.
- Promise 3 uses candidate shapes the **real** gate accepts, taken from the
  held-out evaluation set.
- Promise 2 forces the gate to say yes: that is the worst case the promise
  has to survive.

| Promise | Test | Result on the current code | Break-it (throwaway worktree) |
|---|---|---|---|
| 1 | A supported candidate is written (so the chain doesn't just reject everything) | Pass | — |
| 1 | In a mixed extraction, every profile write is one the Constitution approved, and the profile changes by exactly those writes | Pass | Stage 13 also writing DISCARD/HARD_REJECT: **fails** |
| 1 | Census: outside the tests, only Stage 13 calls `write_approved_candidate`, and only Stage 13 and the verification loop call `create_memory_candidate` | Pass (medium evidence, §5) | A second caller added in Stage 11: **fails** |
| 2 | name, language_preference and timezone: a gate-passing candidate never changes `identity`, and is not queued as a question | Pass ×3 | The immutable rule alone removed: still passes, because the two other layers hold. Every layer opened: fails on the *queue* assertion (the conflict path queued it). Identity approved outright: **fails on identity unchanged** ×3 |
| 3 | goal_memory.\*, interaction_style.\*, active_projects.\*, skill_memory.\*.level: not written until confirmed, queued once, written after `resolve_pending` | Pass ×4 | The gated rule removed: **fails** ×4 |

**Identity is guarded three times over.** The immutable-field rule; the
writable-tables list, which excludes `identity`; and
`write_approved_candidate`, which has no identity branch at all. Breaking
any one of them leaves the promise intact.

**Findings from the probes (temporary tests, since deleted).
Recommendations only; each needs an owner decision.**

1. **Promise 1 is narrower in the code than in its wording (category D).**
   The claim covers the Observer's *memory candidates*, and for those it
   holds. But the Observer also produces **decision candidates** and a
   **session snapshot**, and neither goes through the evidence gate or the
   Constitution.
   - A decision must quote words the user actually said (an ungrounded one
     was dropped).
   - It is then scored on deterministic signals.
   - With two or more signals it is **auto-logged** into the decision log,
     which Stage 3 puts into prompts. Probe: "I'm going with FastAPI
     because Flask has no native async, instead of Django" → logged
     directly.

   The snapshot has its own grounding gate (`_snapshot_may_overwrite…`).
   Either the wording of Promise 1 names these separate gates, or decisions
   are routed through the evidence gate.
2. **The immutable fields can be shadowed in preferences (category A or
   D).** The Constitution matches immutable fields by *field name*, in any
   table. `preference_memory` is Observer-writable, and there is no stored
   preference named `language_preference` for the rule to see. On the real
   path (real gate, real Constitution), "I prefer French, please answer me
   in French from now on" wrote `preference_memory.language_preference =
   French`; `language` and `timezone` did the same. The prompt then holds
   both `language_preference: English` (identity) and
   `language_preference: French` (preferences).
   - The identity row itself never changed, so Promise 2 holds as worded.
   - The user did say it, so this may be legitimate learning.
   - But the model is shown two conflicting values for a field the promise
     calls immutable.
   - Options: refuse immutable field names in every table; map them to a
     pending question for the user; or state it as a limitation.

**Not covered:** the snapshot's own gate is not separately tested; and the
verification loop's queue writes were only counted in the census, not
exercised.

### 7.14 End-to-end Observer measurement (authorized 2026-09-28)

This was the council's main recommendation: measure the learning path as a
person meets it, rather than the gate alone.

**Method.** `scripts/eval_observer_end_to_end.py` runs each of 37 labelled
conversations (`backend/tests/observer_cases.py`) through the real local
model and `run_session_end()`, on a fresh isolated profile, and reads what
was learned from the database. The conversations contain 23 facts the user
states and 25 traps:
- third parties, hypotheticals and questions;
- negation, the past, retractions and sarcasm;
- words only the assistant said;
- the immutable fields;
- small talk, and mixed sessions.

The labels were committed in `1256b51`, before the first full run. Three
runs, because the model samples. The raw per-case output is in
`docs/eval/observer_end_to_end_2026-09-28.md`.

**Conditions:** model `qwen2.5:7b`, the only one pulled on this machine;
the code defaults to `llama3.1:8b`, which was not measured. Every profile
was in its first two weeks, where the Constitution accepts only candidates
the model labels *explicit*.

**Results.** The three runs agree closely.

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Precision, memory tables (true / true + false) | 8/9 | 9/10 | 7/8 |
| Precision, including decision-log entries (hand-reviewed) | 10/12 (83%) | 10/13 (77%) | 10/12 (83%) |
| **Recall**: stated facts learned (written or queued for confirmation) | 8/23 (35%) | 9/23 (39%) | 7/23 (30%) |
| …of which written outright | 3 | 4 | 3 |
| Traps reaching a belief table | 1/25 | 1/25 | 1/25 |

**Precision is high, and its one failure is systematic.** The same false
memory appeared in all three runs. "Sure, because Internet Explorer is my
favourite browser. Obviously." was stored as a preferred tool: the gate
judged it `EVIDENCE_SUFFICIENT` and the Constitution approved it. The
Firefox the user actually tests on was hard-rejected. **The gate cannot
read sarcasm**, which the council predicted; the gate corpus has no
sarcasm cases. Every other trap category held in every run: third
parties, hypotheticals, questions, negation, the past, the assistant's
words, a forged role line, and the immutable fields.

**Decisions are the weaker gate, as §7.13 predicted.** The keyword labels
could not classify 3–4 rows per run; all of them were decision-log
entries, auto-logged without the evidence gate. Reviewed by hand:
- Six stated a decision the user did make ("ship the beta in May", "run a
  half marathon in April", "continue using pytest", "won't learn Java"
  after "I'll pass").
- Four overstated a tentative remark as a decision:
  - "I'm not convinced" about Java was logged twice as a decision;
  - "probably not worth it" became "decided against rewriting in Elixir";
  - "to stay with Go" was logged though the user never said it.

The overstatements are what pull the combined precision down to 77–83%.

**Recall is low, and it has three causes.** Each cause is visible in the
funnel of every run.
1. **The evidence gate rejects plain true statements (the largest loss).**
   All of these were judged `EVIDENCE_NOT_ENTAILING` and discarded:
   - "Please keep your answers short from now on";
   - "I keep all my notes in Obsidian these days";
   - "I work mostly in TypeScript";
   - "I really like detailed explanations";
   - "I'm learning Rust";
   - "I write all my essays in LaTeX";
   - "a payments service" (as a project).

   The gate's support-language lists do not recognise ordinary phrasings.
   The gate evaluation's one held-out false reject,
   `held_accept_tool_habit`, is this same Obsidian phrasing. What looked
   like one miss there is most of the recall loss here.
2. **The model labels first-person facts as "inferred", inconsistently.**
   "I've been writing Python professionally for six years" and Go "for
   four years" passed the gate but were labelled *inferred*, and a
   first-two-weeks profile discards those
   (`threshold_violation_week_1_2`). Re-run, the same Go statement was
   labelled *explicit* and correctly queued for confirmation. With the
   label *explicit*, all three affected facts would have been queued
   (checked directly against Stage 12).
3. **The model extracts nothing** for some facts: repeated questions about
   vector clocks (a topic interest), "It's Kotlin", and "I deploy
   everything with Docker Compose" (extracted, then dropped by grounding).

**What this means for the thesis.** "Learns only what the user actually
said" is close to true for memory: about 9 in 10 of what it learns is
true, and the one failure is sarcasm, every time. But it learns roughly a
third of what users plainly say, and writes outright fewer than a fifth of
the facts stated. Most of the rest is either queued for confirmation or
lost at the gate. The gate trades recall for precision more steeply than
the gate-only evaluation showed. Decisions, which skip the gate, are
where overstatement gets in.

**Limitations of this measurement:**
- n is small: 23 facts and 25 traps.
- The labels were written by the measuring agent, not independently.
- Keyword matching could misclassify a row. Every non-TRUE row was
  reviewed by hand (listed above); the TRUE rows were not.
- One model (not the code's default), a first-two-weeks profile only, and
  English only.
- The queued-for-confirmation facts are counted as learned, but whether
  a user confirms them is not measured.

**Recommendations only; nothing changed:**
1. Add sarcasm cases to the gate corpus, and decide how the gate should
   treat them.
2. Widen the gate's support language for plain first-person statements
   ("I keep…", "I work mostly in…", "please keep…"), measured against both
   corpora so that precision is watched while recall rises.
3. Stop relying on the model's explicit/inferred label for first-person
   statements, or relax the weeks 1–2 rule for gated tables, which already
   ask the user.
4. Route decisions through the evidence gate (§7.13 finding 1). That is
   where the overstatements come from.

### 7.15 Launch-checklist UI fixes (authorized 2026-10-01)

A read-only audit of the Flutter client against the half of a web launch
checklist that applies to a desktop app (LOG 2026-10-01) found four
problems. The owner authorized all four, in this order, one commit each.

**Fix 1 - text contrast.**
- **Promise:** every text colour (text, muted, faint) in both palettes and
  on the sign-in stage is at least 4.5:1 on every surface it can sit on.
- **Mechanism:** the colour values themselves; `test/theme_test.dart` is
  the guard. Faint had been held to 3:1 as "metadata", but 3:1 is the
  large-text bar and faint is set at 11-13.5px in about sixty places.
- **Evidence:** the raised bar failed on the old palette in four places
  (light faint 2.86:1 and light muted 4.38:1 on surfaceRaised, dark faint
  3.22:1, sign-in faint 3.87:1 on the card). New values: light muted
  #5A5F6E, light faint #676C7C, dark faint #858A9A, sign-in faint
  #7B8195, all >= 4.61:1. A second test keeps faint quieter than muted.
  Full Flutter suite 302/302.
- **Not covered:** colours set as literals outside the palette (the
  sign-in screen's error red, chart and glow tints) are not in the test.

**Fix 2 - names for icon-only controls.**
- **Promise:** every control a screen reader can tap, on every tab, with
  the sidebar open or collapsed, has a name it can read.
- **Mechanism:** a `Tooltip` on each icon-only control (send/stop, delete
  conversation, the sidebar toggle, and each sidebar item while
  collapsed). `_SendButton` now requires its tooltip, so a new one cannot
  be built without a name.
- **Evidence:** `test/control_labels_test.dart` walks the semantics tree,
  not the widget tree, and fails on any tappable node with neither label
  nor tooltip. On the old code it found 13: the toggle, send, delete, and
  ten collapsed items (nine tabs and Sign out). It passes now. Full
  Flutter suite 305/305.
- **Found on the way:** collapsing the sidebar overflowed its header by
  2px (24px of room for a 26px toggle). This test is the first to
  collapse it, so the padding fix went in the same commit.
- **Not covered:** the delete control still exists only while the mouse
  hovers its row, so it is named but not reachable by keyboard. Dialogs
  and the sign-in screens are not walked.

**Fix 3 - a minimum window size.**
- **Promise:** the window cannot be made smaller than a client area every
  screen fits, 800x640 logical, unless the monitor's usable area is itself
  smaller.
- **Mechanism:** `WM_GETMINMAXINFO` in `windows/runner/flutter_window.cpp`.
  The size is defined once, as `kMinClientWidth`/`kMinClientHeight` in
  `flutter_window.h`. The frame is measured from the live window, scaled
  for the monitor's DPI, and clamped to the work area.
- **Evidence:** `test/minimum_window_test.dart` reads the two constants
  from the header and lays out every tab and the first-run sign-in screen
  at that size in Segoe UI. It failed before the fix (header defined
  none). Break-it: at 600px height it fails with the sidebar's 15px
  overflow. `tool/check_min_window.py` launches the release build and
  asks for 400x300. Before the fix the client area went to 252x163; after
  it, 800x640 at 1.5x scale. Full Flutter suite 307/307.
- **Chosen smaller than proposed.** The audit suggested about 1024x640;
  800x640 is the smallest size that measured clean. It leaves more room on
  small laptop screens, and the clamp covers the rest.
- **Not covered:** the exe check is a script, not part of `flutter test`,
  because it needs a release build. The sidebar still cannot scroll, so a
  screen shorter than about 615px logical (where the clamp applies) still
  overflows it. Dialogs were not laid out at the minimum.

**Fix 4 - the password minimum, checked before the round trip.**
- **Promise:** choosing a first password, changing it and restoring a
  backup all refuse a password under the backend's minimum before calling
  the backend, and the client's minimum is the backend's.
- **Mechanism:** `kMinPasswordLength` and `isLongEnoughPassword()` in
  `lib/api_client.dart`, used by all three forms. It counts code points
  (`runes`), as Python's `len()` does. Unlock is not checked: an existing
  password is sent as it is. The backend stays the authority.
- **Evidence:** sign-in setup and change-password each gained a test that
  a 7-character password never reaches the API. Both failed on the old
  code, which sent it and waited for the server. A third failing test
  covered four emoji, which are 4 code points but 8 UTF-16 units.
  `test/password_rule_test.dart` finds every `len(...password...) < N` in
  `session_key.py` and `restore.py` (three) and holds the constant to
  them. Break-it: at 6 the rule test and both screen tests fail. The old
  server-refusal test now types a long password, so it still tests the
  server's message. Full Flutter suite 311/311.
- **Not covered:** the backend's blank-password check (`strip()`) is not
  mirrored. A password of eight spaces passes the client and is refused
  by the server.

### 7.16 Product-wide validation pass (2026-10-01, report only)

Requested by the owner: validate every implemented workflow end to end,
from outside. **No production code changed.** Full record, condition matrix
and per-defect reproduction:
`docs/eval/reliability_validation_2026-10-01.md`. The probes and the
real-process journey drivers are in `docs/eval/reliability_2026-10-01/`.
They are named `probe_*.py` so the suite never collects them, and each
failing probe is its defect's regression test once a fix is authorized.

**Conditions.** Revision `f66a309`.
- Every run used isolated data dirs; the real `data/` was never opened.
- Live model `qwen2.5:7b`.
- **Smart App Control is on and blocks torch's unsigned DLL.** The backend
  suite and every real backend process therefore ran with a stand-in
  embedder (hashed bag-of-words). No retrieval-quality result is claimed.

**Suites.**
- Flutter: analyze clean, 311/311 tests, release build OK.
- Backend as-is: 842 passed, and 28 failed at import on the torch block.
  That block is the only failure cause.
- Backend with the stand-in: 1230 passed, 4 failed.
  - 3 need Ollama and pass once it is up (17/17).
  - 1 is retrieval-dependent and does not hold under the stand-in.

**Held (strong evidence):**
- **REST census:** all 64 REST method+path pairs refuse 3 kinds of bad
  credential; every gated pair returns 423 while locked; 7 path-encoding
  variants never serve data.
- **WebSocket:** token and origin checks hold (3 + 8 cases).
- **Traversal:** slugs and delete/ingest paths cannot escape their folders.
- **Profile ownership:** another profile cannot be renamed or deleted.
- **Two profiles on one machine:** fully isolated.
- **Consent:** unconsented, revoked, wrong-scope, other-endpoint and
  revoked-then-re-saved endpoints get zero requests. Web search does not
  run on a fresh install or after revoke.
- **Force-kill mid-conversation (real process):** the transcript is
  identical, the lock is taken over, and the Observer catch-up processes
  the session.
- **Provider failures:** stop-generation, a missing model, Ollama down and
  Ollama hung each fail cleanly in 4-12 s.
- **Backups:** the exported `.pipbak` holds no plaintext. Six kinds of bad
  backup are refused with nothing staged. A clean restore reproduces
  conversations, messages, decisions, projects, profile and documents
  exactly.
- **Installer payload:** carries no developer data.

**Defects (recommendations only; each needs an owner decision):**

| ID | Sev. | Cat. | Finding | Evidence |
|---|---|---|---|---|
| D-01 | Critical | B | A restore swaps `pip.db` and `salt.bin` but leaves the old `pip.db-wal`. SQLite replays it, so the restored profile opens with neither the new password nor the old one (its salt was moved aside). Same shape in `restore_backup.py`. `profiles.delete()` already handles sidecars. **Fixed 2026-10-02 (§7.17).** | Deterministic probe plus 2 of 3 real-process restores |
| D-02 | High | env | The backend cannot import under Smart App Control: torch is unsigned and imported eagerly via `vector_store.py:41`. Confirmed on the staged payload `D:\pip-build\PIP` | Import fails in the payload's own Python |
| D-03 | High | A | Export from the Backup screen fails with exactly one profile: `export_pip.ps1:62` passes `--db-path` only for `Count -gt 1` and falls back to `data/pip.db`. **Fixed 2026-10-02 (§7.18).** | Launcher's own condition on an isolated copy, plus a control |
| D-04 | High (latent) | A/B | Stage 8 trusts `provider_consent.is_cloud` alone, and `add_endpoint` never updates it. A local→remote re-save, or an endpoint registered as `ollama`, was sent the full prompt with no consent. The reverse of §7.2 finding 2. No route adds endpoints yet. **Fixed 2026-10-02 (§7.21).** | Counting stub through the real pipeline |
| D-05 | Medium | A | After a restart the backend serves the unencrypted `default` slot until a profile is chosen. `GET /status` created a plaintext `data/pip.db`, and a chat sent then was stored in plaintext; a phantom "Default" profile appeared and the next launch said `needs_migration`. The Flutter client avoids the window; the CLI does not | Real-process journey, canary on disk |
| D-06 | Medium | D/A | Deleting a document leaves its plaintext file and its `document_blobs` content, so it also travels in later backups | Through `DELETE /rag/documents` |
| D-07 | Medium | A | A restored document whose original absolute path exists is never re-indexed: write-back is skipped, and the rebuild's ingest refuses a path outside the profile. Retrieval is empty on every sign-in while the Documents screen lists it | Real-process restore |
| D-08 | Medium | D | `/llm/pull` accepts any name and this Ollama has cloud enabled, so a `*-cloud` model would carry chat and the Observer off the machine as "local" `ollama` | Code reading only (would contact an external service) |
| D-09 | Medium | A | "Close PIP and open it again to finish" does not apply a restore: the launcher reuses the running backend, so the swap waits for an unclean exit, which feeds D-01 | Code reading |
| D-10-13 | Low | | 500s for malformed onboarding input and a bit-flipped backup; a dismissed memory question is re-asked when the same words recur; Unlock sits below the fold at 1280x720 | Probes, screenshot |

**Not run:**
- a clean-VM installer lifecycle;
- a real remote provider;
- long-running use (resource leaks);
- driving the UI (one screenshot only);
- retrieval quality (the torch block).

**Exit criteria not met:** D-01 to D-04 are open, and the supported
migration workflow failed. *(2026-10-02: D-01 and D-03 fixed, §7.17 and
§7.18. The migration workflow has not been re-run end to end from the
Backup screen since; §7.18 says what stands in for that.)* *(2026-10-03:
re-run end to end through the script the Backup screen launches (the
button itself not driven), §7.24. Met with exceptions for the data round
trip; not
met as worded, because of D-09 and the new D-18 and D-20.)*

### 7.17 Restore sidecars fix, D-01 (authorized 2026-10-01, landed 2026-10-02)

The §7.16 D-01 recommendation, by the same method as §7.9–§7.12.

- **Promise:** a restore installs only the backup's database. Nothing
  the replaced database left beside it (`-wal`, `-shm`, `-journal`) is
  ever applied to the restored one. The replaced database keeps those
  files, under names SQLite pairs with the kept copy.
- **Mechanism:** both installers move each existing sidecar to
  `pip.db.superseded-<stamp><suffix>`, beside the kept database:
  - `restore._install()`, the in-app restore, run at startup;
  - `install()` in `scripts/restore_backup.py`.

  Each sidecar is checked on its own, because a WAL outlives a database
  deleted by hand. Every move goes on the existing undo list. The
  suffixes are one constant, `profiles.SQLITE_SIDECAR_SUFFIXES`, which
  `profiles.delete()` now also erases by (§2.3).
- **Tests:** ten, five per path, in `test_restore_in_app.py` and
  `test_restore_backup.py`.
  - **The crash is real.** A schema change under
    `wal_autocheckpoint = 0` always rewrites page 1; an UPDATE alone
    may not, and the restore survived one. The database and its WAL are
    copied out while the connection is open and copied back after it
    closes.
  - **The evidence is not consumed.** Sidecars are checked before
    anything opens the restored file, since any open replays a stale
    WAL.
  - **Outcomes, not proxies.** The restored file is checked by its rows,
    not by `verify_key`, which reads only `sqlite_master`.
  - **Against the unfixed code, 8 of the 10 fail for the stated
    reason.** The two that pass are the rollback guards (a refused
    rename puts the WAL back with its database): the old code never
    moved a sidecar to put back.
- **Break-it:** ten mutations of the fix, each applied alone and the
  file restored byte for byte. Every one is caught by at least one test:
  - sidecars not moved (each path);
  - sidecars renamed after themselves rather than the kept copy (each
    path);
  - sidecar moves left out of the undo list (each path);
  - sidecars moved only when the database exists (each path);
  - only `-wal` moved (script);
  - `-journal` dropped from the shared list.
- **Review:** an adversarial review (five lenses, three skeptics per
  finding) upheld four findings and refuted ten.
  - **Two test gaps on the script path.** Nothing checked that its kept
    copy keeps the WAL, or that `-shm` and `-journal` move, so a
    wrong-name mutation passed every script test. Both tests were added
    (the last two script mutations above). The first break-it had
    reported "wrong name" caught on both paths, but it had only been
    applied to the in-app path.
  - **Comments.** Three new comments claimed more than the evidence: a
    single outcome where the WAL's pages decide it, and that the script
    "exists for" crashes. Reworded.
  - **Out of scope:** D-14, below.
- **Commit:** the one that adds this section.
- **Full suite:** 1240 passed, 4 failed, run with the stand-in embedder
  because Smart App Control blocks torch here (§7.16 D-02).
  - The 4 failures are the 3 `test_llm_endpoint_store` tests that need a
    running Ollama, and the cached-answer test that needs real
    embeddings.
  - One earlier run of the same code stopped at the 300 s ceiling in
    `test_ws_chat_accumulates_conversation_history_across_turns`: the
    intermittent hang §7.3 records. That test runs none of this change
    (the startup drain returns early with nothing staged), and it passed
    in the runs before and after.

**Not covered (still open):**
- **Profiles already damaged by D-01 are not repaired.** The first open
  after the old swap replayed and deleted the stale WAL, so the damage is
  in the file. Restoring again from the `.pipbak` is the repair. The
  superseded copy from that earlier restore lacks its WAL-only rows.
- **D-14 (medium, A, predates this fix): a restore staged before its
  profile is deleted is still installed at the next start.**
  - `delete()` leaves `pending-restore.json` and the staged temp files,
    and `drain_pending_restore` checks only that the temp files exist.
  - The Default profile comes back. A named profile leaves an
    unregistered encrypted database in its folder, whose `rmdir` the temp
    files also block.
  - Reproduced by three independent skeptics.
  - **Recommendation only:** `delete()` cancels a pending restore whose
    target is under the profile, or the drain refuses a target whose
    profile is no longer registered.
  - **Fixed 2026-10-02 (§7.22)**, by the first of those.
- `scripts/migrate_encrypt_db.py` keeps its own sidecar list (`-wal`,
  `-shm`, no `-journal`) and deletes them after a checkpoint and close.
  Low risk; not changed.
- `delete()` still erases neither the `*.superseded-*` copies a restore
  keeps nor, now, their sidecars. The copies were left before this fix
  too.
- D-09 is unchanged: the swap still waits for the backend process to
  end, so "close PIP and open it again" does not finish a restore.

### 7.18 One-profile export fix, D-03 (authorized and landed 2026-10-02)

The §7.16 D-03 recommendation, by the same method.

- **Promise:** the Backup screen's Export backs up the profile that was
  last opened, with that profile's own salt, however many profiles there
  are.
- **Mechanism:** `scripts/export_pip.ps1` takes its answer from
  `Resolve-PipLastProfile` in `_profiles.ps1`, the rule `launch_pip.ps1`
  starts the backend by. The wrapper used to keep its own copy, which
  chose only when more than one profile was registered (§2.3).
  - The salt is set with the database every time. When the resolver
    answers "the original layout", an inherited `PIP_SALT_PATH` is
    cleared rather than kept.
  - The export console inherits `launch_pip.ps1`'s profile variables
    through the app, so a salt left to the environment names whichever
    profile was open at launch.
- **Tests:** `backend/tests/test_export_launcher.py` runs the real
  wrapper and its two helpers, copied into a temporary installation with
  a throwaway venv. It uses Windows PowerShell 5.1, as the app does. Only
  `export_backup.py` is a stand-in, recording the database and salt it
  would have opened.
  - Six cases. Against the unfixed wrapper the four D-03 cases fail:
    - a sole profile, with `last_used` recorded or stale;
    - the original layout under an inherited salt, with and without a
      registry.
  - The two controls pass: several profiles, and a caller's own
    `--db-path`.
- **Break-it:** six mutations, each caught by at least one test:
  - the old more-than-one gate;
  - the salt left to the environment;
  - an inherited salt kept for the original layout;
  - a caller's `--db-path` overridden;
  - the shared resolver answering "the original layout" for everyone;
  - the resolver's fallback removed.

  The inherited-salt mutation first went uncaught: under 5.1 the
  registered-Default case reaches the resolver's profile branch, not the
  one the mutation removed. The no-registry case (an installation from
  before profiles) was added, which does run it.
- **Found on the way (observation, not changed):** under Windows
  PowerShell 5.1, a single object returned from a function has no
  `.Count`. That is the PowerShell the app, the desktop shortcuts and
  the installer all launch.
  - So `Resolve-PipLastProfile`'s zero- and one-profile branches never
    run for a lone profile. It falls through to the `last_used` lookup
    and its fallback, which reach the same files: a lone modern
    profile's own, and `data/`'s own for a lone legacy one.
  - Under PowerShell 7 those branches do run.
  - Measured: with the one-profile branch mutated, all six tests still
    pass under 5.1.
  - Making them run under 5.1 would change the shared rule for no
    change in outcome, so it is left as it is.
- **Commit:** the one that adds this section.
- **Full suite:** 1245 passed, 5 failed.
  - Four are the known ones (§7.17).
  - The fifth, `test_an_answer_cached_before_sign_out_is_not_served_to_the_next_profile`,
    is a race this change does not touch. Run alone and interleaved, it
    failed 8 of 20 here and 7 of 20 at `f66a309`, before D-01 and D-03.
  - Recorded as D-15 (§7.19).

**Not covered (still open):**
- **The export itself was not re-run end to end from the Backup
  screen.** `export_backup.py` asks for both passwords through
  `getpass`, which reads the console, not a pipe. What stands in:
  - the launcher's choice, tested through the real wrapper;
  - the export given that choice, covered by `test_export_backup.py`
    and run in the control of the §7.16 reproduction.
- **The export follows the registry's `last_used`, not the app's active
  profile.** They are the same while signed in, which the Backup screen
  requires, because `last_used` is recorded only by a password that
  worked.
- The desktop-shortcut restore (`restore_pip.ps1`) still writes the
  legacy Default slot (§7.16 report, section 11), unchanged.

### 7.19 Answer cached after sign-out, D-15 (found 2026-10-02, report only)

Found while running the D-03 full suite, when §7.9's guard for the
cross-profile cache failed:
`test_an_answer_cached_before_sign_out_is_not_served_to_the_next_profile`.

- **Mechanism (category A, Pattern 1 again).** Stage 9 yields `done` and
  the server forwards it. Only then does the pipeline write the answer
  into the response cache (`pipeline.py`, after the Stage 9 loop). So a
  client that already has the whole answer can sign out before the write
  happens:
  - `session_key.lock()` empties the cache;
  - the write then lands after it;
  - the signed-out profile's answer is back in a cache whose key names no
    profile.

  §7.9 made sign-out clear what the cache held at that moment. It does
  not stop work already in flight from writing afterwards.
- **Evidence:**
  - **Deterministic:** with only `response_cache.set` delayed by one
    second, Bob was served `ANSWER#1`, Alice's answer, from the cache in
    5 of 5 runs, and his model was never called. Bob is a new profile
    asking Alice's question after she signed out. Probe:
    `docs/eval/reliability_2026-10-01/probes/probe_cache_race.py`.
  - **Natural rate:** the §7.9 test, run alone with runs interleaved,
    failed 8 of 20 at `12a0386` and 7 of 20 at `f66a309`. It has been
    failing for a real reason all along. Full-suite runs pass it more
    often, which is how it went unnoticed.
- **Reach in the app:** low likelihood, but the cost is Promise 8. It
  needs three things to line up:
  - the sign-out lands between the end of streaming and the cache write.
    That gap is normally milliseconds, but the write follows a trace
    write to the database, which can wait out its 5 s busy timeout;
  - the next profile asks the same words, with the same project;
  - it has the same `record_version`. Two new profiles start with the
    same counter: the probe's cache hit shows it.
- **Severity:** medium.
- **Recommendation only:** tie the write to the session that asked. For
  example, capture a sign-out epoch when the question arrives and refuse
  the write once it has moved, or put the epoch in the cache key. Moving
  the write ahead of `done` would not close it, because a sign-out can
  also land mid-stream.
- **The guard:** the §7.9 test is right; the code it guards is not. Its
  failure rate on this machine is the race's rate, not noise.
- **Fixed 2026-10-02 (§7.20).**

### 7.20 Sign-out cache fix, D-15 (authorized and landed 2026-10-02)

The §7.19 recommendation, by the same method, plus one more channel to the
same boundary.

- **Promise:** an answer cached by one signed-in session is never served
  to another. That includes an answer still being written when its
  session signs out, and a question asked on a chat connection left open
  through the sign-out.
- **Mechanism:** the response cache keeps a generation, and every key
  carries it.
  - `clear()` moves it, as well as emptying the cache. That is every
    sign-out, through `session_key.lock()`.
  - Each chat connection takes the generation once, when it opens, before
    its database is opened. Every question on that connection reads and
    writes under that number. `pipeline.run` takes one when the question
    arrives if it is not given one.
  - So an entry from an ended session sits under a number no later
    session looks up, and an old connection looks only under its own.
- **The second channel (found while writing the fix; covered under this
  authorization and flagged so the owner can object):**
  - A chat socket opened before a sign-out keeps working after it, as
    Promise 8 states, and it shared one cache with whoever signed in next.
  - Alice's socket, still open after Bob had signed in and asked, was
    served Bob's cached answer.
  - It is the same boundary as §7.19, seen from the other side. Taking the
    number per connection rather than per question closes it.
- **Tests:** three, each seen failing on the unfixed code:
  - `test_an_answer_still_being_written_at_sign_out_is_not_served_to_the_next_profile`
    (route). Alice's cache write is held until her sign-out has finished,
    which is the order the race produces, and the test checks the write
    had not come first. On the old code Bob was served Alice's answer in
    3 of 3 runs.
  - `test_a_chat_left_open_through_sign_out_is_not_served_the_next_profiles_answers`
    (route). On the old code Alice's open socket was served Bob's answer
    in 3 of 3 runs.
  - `test_an_answer_finished_after_its_session_signed_out_is_not_cached_for_the_next`
    (pipeline). The model signs the session out mid-answer, so the write
    lands after the cache was emptied and before `done`. That is why
    moving the write ahead of `done` would not have been enough.
- **The §7.9 guard:** 7–8 of 20 runs failed before the fix (§7.19). After
  it, 159 of 160 passed: 19 of 20, then 40 of 40, then 100 of 100 with
  every failing run's output kept.
  - The single failure came in the first batch, whose output was not
    kept. Nothing found since accounts for it: no path remains by which a
    later session's lookup can match an entry an earlier one wrote. It is
    recorded rather than rounded away.
- **Break-it:** four mutations, each caught:
  - sign-out no longer moving the generation (3 tests);
  - the generation dropped from the key (3 tests);
  - the connection no longer passing its number (the open-chat test);
  - the pipeline no longer taking one when the question arrives (the
    mid-answer test).

  A control, that an unchanged record is still answered from the cache,
  passed under every mutation. So the fix does not work by switching the
  cache off.
- **Commit:** the one that adds this section.
- **Full suite:** 1249 passed, 4 failed. The 4 are the known ones
  (§7.17); the §7.9 guard passed.

**Not covered (still open):**
- **The connection takes its number before opening its database.** A
  sign-out landing between the two fails the open. Only a complete
  sign-in of another profile inside that gap would give the connection the
  wrong pairing, and the database it then opened would be the next
  profile's: a boundary problem of its own, not the cache's. A sign-in
  derives a key for hundreds of milliseconds, and the gap is between two
  consecutive statements. Not tested.
- **An open chat connection still answers after sign-out,** from its own
  profile's database. Promise 8's limitation is now worded to say so.
  What §7.20 removes is that connection's exchange with other sessions
  through the cache.
- **Old entries stay in memory.** Entries written under an ended session's
  number are unreachable but kept until their TTL or the next sign-out
  empties the cache.

### 7.21 Consent locality fix, D-04 (authorized and landed 2026-10-02)

The §7.16 D-04 recommendation, by the same method. It also gives Promise 6,
which had no tests, its evidence (§4).

- **Promise:** nothing is sent to a provider that is not local without
  the user's consent for that provider. A provider counts as local only
  when both its records say so, and an endpoint cannot borrow the consent
  record of a provider that is not an endpoint.
- **Mechanism:** three parts.
  - **Stage 8 takes the provider's own claim.** For a configured endpoint
    that is `llm_endpoints.is_local`; the built-in Ollama is local by
    definition. The claim is a required argument, so a caller that leaves
    it out gets a TypeError rather than the old consent-only behaviour.
    The consent record alone was written when an endpoint was first saved
    and never updated.
  - **Both records must say local.** When the consent record says local
    and the provider does not, the records disagree and the gate refuses.
    That is the rule Stage 11 already applies to the Observer. Web search
    is never local.
  - **`add_endpoint` refuses a built-in id.** It refuses an id that has a
    consent record but no endpoint record: a built-in provider's,
    `ollama` or `web_search`. Consent is recorded per id, so the id has to
    name one provider. `remove_endpoint` deletes both records, so a
    removed endpoint's id is free again; a hard-coded list of ids would
    have been a third copy of them.
- **Tests:** `backend/tests/test_consent_before_sending.py`, 11 tests,
  through the real pipeline with a counting stub standing in for each
  provider.
  - **Seen failing first.** Five fail on the unfixed code:
    - an endpoint re-saved as remote, which was sent the prompt;
    - an endpoint under `ollama` and under `web_search`, neither refused;
    - an `ollama`-named row already in a database from before the refusal,
      which was sent the prompt as if local;
    - web search under a consent record wrongly saying local, which
      searched.
  - **Controls (pass before and after):** a local endpoint is used
    without consent; unconsented, revoked and other-endpoint consent send
    nothing; consent for web search only does not cover conversations; web
    search runs only while consented.
  - **Where the rule is pinned:** three gate unit tests in
    `test_stage_08_provider_gate.py` (disagreement refused, a cloud record
    still needs consent, the claim cannot be left out). The 16 existing
    gate calls in that file and `test_ticket5_providers.py` now state
    their provider's locality; their assertions are unchanged.
- **The built-in Ollama is not collateral.** An `ollama`-named impostor
  tried first is refused while the real Ollama beside it still answers.
  The gate judges each provider by its own claim, not by the id they
  share.
- **Break-it:** six mutations, each caught:
  - the disagreement no longer refused (4 tests);
  - the provider's claim ignored (2);
  - web search claiming local (1);
  - the built-in-id refusal removed (2);
  - the refusal widened to block re-saves (3, two of them existing
    endpoint-store tests);
  - the claim made optional and defaulting to local (1).
- **Ollama-dependent tests:** the three `test_llm_endpoint_store` tests
  that need a running Ollama were run with it up and passed (17/17 in
  that file), since they go through the changed `add_endpoint`.
- **Commit:** the one that adds this section.
- **Full suite:** 1266 passed, 1 failed, run with Ollama up so its three
  dependent tests ran too. The one failure is the cached-answer test that
  needs real embeddings (§7.17).

**Not covered (still open):**
- **Locality is still attested, not verified.** An endpoint saved as local
  by whoever configured it is believed (Promise 5's wording, kept).
- **D-08 is unaffected.** The built-in Ollama is local by definition, so
  an Ollama `*-cloud` model would still pass as local.
- **§7.2 finding 2 is unchanged.** An endpoint re-saved from remote to
  local stays refused until it is removed and added again: it fails
  closed. With this fix, a local-to-remote re-save is refused too, for the
  same reason. Neither silently sends anything.
- **No route adds endpoints yet,** so the defect and the fix are latent
  for the shipped app. The tests pin the behaviour for when one does.

### 7.22 Staged restore and profile deletion, D-14 (authorized and landed 2026-10-02)

The first of §7.17's two D-14 recommendations, by the same method.

- **Promise:** deleting a profile takes a restore staged for it with it.
  - Nothing is installed in the deleted profile's place at the next start.
  - The staged copy of the backup, a whole backup re-encrypted under the
    restore's new password, is erased with the rest of the profile.
  - A restore staged for another profile is untouched.
- **Mechanism:** `profiles.delete()` first calls
  `restore.cancel_pending_restore_for` with the profile's own `pip.db`. That
  cancels the staged restore, marker and staged files, only when it would
  replace that database. What the marker looks like stays known to
  `restore.py` alone.
  - **First,** before anything else in the delete can fail. A delete
    Windows refuses is only recorded for the next start, and the restore
    must not outlive the request while that waits.
  - **In `delete()`, not the route,** so the recorded delete finished at
    startup goes through it too.
- **Why not the other recommendation, refusing at the drain (reasoned, not
  tested):** a profile deleted and created again under the same name before
  a restart reuses the same folder. A drain checking the target by path
  would find a registered profile there and install the old backup over
  the new one's database, under a password its new owner never chose.
  Cancelling at the delete leaves nothing to install.
- **Tests:** four, in `test_profile_management.py`, through the real
  routes. The next start is a real lifespan.
  - **Named profile.** On the old code, after the next start the deleted
    profile's folder held a freshly installed `pip.db` and `salt.bin`.
  - **Default profile.** On the old code it was listed again after the next
    start.
  - **A delete that has to wait** (the erase refused, as Windows does). On
    the old code the restore stayed staged.
  - **Control:** a restore staged for another profile stays staged, its
    files intact, when a different profile is deleted.

  The first three failed on the old code for those reasons. The control
  passed before and after.
- **Break-it:** three mutations, each caught:
  - no cancel at all (3 tests);
  - any staged restore cancelled, whichever profile it was for (the
    control);
  - the cancel moved after the erase, which can fail first (the
    deferred-delete test).
- **Commit:** the one that adds this section.
- **Full suite:** 1267 passed, 4 failed. The 4 are the known ones
  (§7.17): Ollama was not running for this run.

**Not covered (still open):**
- **`profiles.remove()` does not cancel a staged restore.** It unregisters
  without erasing, and a restore staged for the removed profile would
  still be installed into its kept folder. Nothing in the app or the
  scripts calls `remove()`; only tests do.
- **A folder deleted by hand** takes the staged files with it. The drain
  already clears a marker whose files are gone.

### 7.23 A chat turn with no provider to answer it never ended, D-16 (found and fixed 2026-10-03)

Found while walking through how the pipeline behaves in each case, not by
any track. The owner authorized the fix test-first the same day.

- **Defect (A, latent):** when Stage 8 leaves no provider to ask, the
  pipeline returned its error result in `pipeline_complete`. That event
  never leaves the server: `stream_pipeline_to_websocket` keeps it for
  bookkeeping and forwards everything else. So the socket got
  `session_info` and four `stage` lines, then nothing. No `done`, `error`
  or `stopped` arrived. The client keeps the composer locked until one does
  (`chat_view.dart`, `_isStreaming`). The chat stayed "writing" and the
  next message was refused until the user left the conversation.
  - **Latent in the shipped app.** An empty list needs a configured
    endpoint (Ollama down and the only endpoint unconsented, or every
    endpoint refused). Ollama alone is always kept and always passes the
    gate, and no route or script adds endpoints yet. It is the same state
    D-04 was in (§7.21).
  - **Why the tests missed it:** every test in `test_ws_chat.py` replaces
    `pipeline.run` with a fake that always ends in `done`. The real path
    was only tested through `run_sync`, which reads `pipeline_complete`
    and so saw the error (§7.7 pattern 4).
- **Promise:** every chat turn ends on the socket with exactly one `done`,
  `error` or `stopped`. Not added to §4; whether it becomes a tenth promise
  is an owner decision.
- **Mechanism:** the pipeline yields `error` ("No consented provider
  available") before `pipeline_complete`, the text the result already
  carried. One line in `pipeline.py`. Provider selection, the gate and the
  server are unchanged.
- **Tests:** `backend/tests/test_chat_turn_ends.py`, 3 tests through the
  real `/ws/chat` and the real pipeline. Events are read on a thread,
  because the defect is an event that never comes and `receive_json()` has
  no timeout.
  - **Seen failing first:** Ollama down, one remote endpoint with no
    consent. On the old code the turn got no terminal event within 20 s.
    After the fix: one `error` per turn, no tokens, the endpoint sent
    nothing, and a second message on the same socket gets its own single
    `error`. Its first event is its own `stage` line, not a late one from
    the first turn.
  - **Controls (pass before and after):** Ollama down with nothing else
    configured ends in Stage 9's single "All providers failed" error. A
    consented endpoint still streams its answer and ends in one `done`.
  - **Client half:** `frontend/flutter/test/chat_turn_end_test.dart`, 2
    tests. An `error` shows the message, turns Stop back into Send, and the
    next message goes out. The control: stage lines with no ending event
    leave the composer locked, which is what the old server produced. Both
    pass on the unchanged client; it was already right.
- **Break-it:** four mutations, each caught:
  - the error sent twice (the second turn began with a stray `error`);
  - `done` sent instead of `error`;
  - the error sent after `pipeline_complete`, where the server has already
    stopped reading (no terminal event, as before the fix);
  - the client's `error` handler no longer unlocking the composer (the
    Flutter test).
- **Commit:** the one that adds this section.
- **Suites:** Flutter 313 passed (the 2 new ones included), `flutter
  analyze` clean. Backend 1273 passed, 1 failed, run with
  Ollama up. The one failure is the cached-answer test that needs real
  embeddings (§7.17).

**Not covered (still open):**
- **A pipeline that raises** instead of returning still ends the turn with
  no terminal event. *(Fixed 2026-10-03 as D-22, §7.25.)* The exception leaves `ws_chat`'s loop and the socket
  closes. Every stage is wrapped to fail open, and trace writes swallow
  their own errors, but the database reads in `_default_providers` and
  `get_active_model_name` are not wrapped. Whether the client unlocks on
  that disconnect was not checked.
- **The message is the gate's summary, not its reason.** It does not say
  that Ollama was down or which endpoint lacked consent; the trace does.

### 7.24 Migration journey re-run (2026-10-03, report only)

§7.16 failed the exit criterion "supported migration verified" on D-01 and
D-03. Both are fixed (§7.17, §7.18), as is D-14 (§7.22), and §7.18 noted
that the export had not been re-run from the Backup screen end to end. This
re-runs the whole journey. **Report only: no production code changed.** Full
record: `docs/eval/migration_rerun_2026-10-03.md`; harness:
`docs/eval/reliability_2026-10-01/migration/`.

- **How.** Each computer is a throwaway installation built from one pinned
  commit (`git archive`), with its own interpreter and `data/`, and its
  backend started the way `launch_pip.ps1` starts it. Export runs through the
  real `export_pip.ps1` (what the Backup screen launches, run directly). The
  in-app restore goes through `POST /backup/restore` and a backend restart
  done by the harness. The desktop-shortcut restore runs the real
  `restore_pip.ps1`, with and without arguments. Chat uses `qwen2.5:7b`.
  Only `getpass` prompts are answered by a test hook, and the embedding
  stand-in is used (D-02). The real `data/` was fingerprinted before and
  after every run: untouched.
- **Results at `9968e8c`:** 10 variants, 307 checks, 23 failed, every
  failure attributed:
  - main-killed 43/0, main-graceful 42/0;
  - main-killed under a path with spaces, parentheses and `é ü`: 43/0;
  - multi-profile export 22/0;
  - shortcut 37/1 (D-17);
  - shortcut as installed 11/2 (D-21);
  - same-machine 14/1 (D-07);
  - restore over a used profile 22/3 (D-20);
  - bad inputs and D-14: 50/5 (D-18, D-11);
  - staging 23/11 (D-18, D-19).

  Six of the variants also ran at `5cc54df` (shortcut without its
  original-layout leg) with the same verdicts apart from D-17's timing;
  multi-profile-export, shortcut-shipped, restore-over-used and the path
  run are `9968e8c` only. **Negative controls:** at `405b10b` the harness
  fails the
  one-profile export (D-03); at `044fafc` it fails the two D-14 checks the
  fix covers (the staged
  restore went with Zed; nothing was installed where Zed was).
- **What holds, in real processes:**
  - **D-01 on every in-app restore that had a WAL to swap (10 of 13).**
    Each of those WALs held committed frames including page 1: 272 KB after
    a force-kill with a chat open,
    964 KB after a clean stop, which does not checkpoint. The new password
    opens the restored profile, and the old and the backup's do not.
  - **D-03.** One-profile exports chose that profile. An export from a
    two-profile installation, signed into the second while the console
    inherited the first's `PIP_*`, exported the second.
  - **D-14,** for the restore its fix covers.
  - **The round trip.** Across two hops, conversations, decisions,
    projects, the active model, profile fields and documents compare equal.
    Documents are written back under the new machine's folder byte for byte
    and found by retrieval. The restored profile keeps working and carries
    on. The shortcut's original layout exports and restores onward.
  - **Bad input.** Seven of eleven bad inputs are refused with a 422.
- **New defects** (each put to a reviewer told to refute it; the
  reviewers' corrections to these findings are applied, no code changed):
  - **D-18 (medium, A): an empty file is accepted as a backup.** "0 rows
    across 0 tables, checked and ready". At the next backend start the
    profile is replaced by an empty database, the person's password is
    refused, and the original survives only as `pip.db.superseded-<stamp>`.
    The shortcut's
    `restore_backup.py` accepts an empty file too. A backup is checked only
    against itself, so (in the reviewer's synthetic probe, through
    `stage_restore`) a part-written export passes too.
  - **D-20 (medium, upper end; A/B): a restore over a profile with a same-named
    document takes that file.** `_install` does not swap `documents/`, and
    `materialise_documents` repoints a record to a same-named file rather
    than writing the backup's bytes ("may be newer than the backup's"). The
    backup's text is not retrieved and the replaced profile's
    same-named document is. The
    first sign-in's re-ingest then overwrites the restored blob, so the
    backup's copy is gone from the restored database. The restore dialog
    promises the documents are replaced. Same root as D-07.
  - **D-21 (medium, low end; A): the shortcut restores the first backup of
    the day.** `newest_backup()` sorts by name (`-2` sorts before `.`),
    while `restore_pip.ps1` lists by time and says "the newest will be
    used". The name used is printed, and `--from` recovers.
  - **D-17 (low, upper end; A): an export while the app commits rows fails
    and says nothing was written.** Counts are taken before two password
    prompts and must equal the export's. `export_pip.ps1` prints "Nothing
    was written" for any failure while a valid backup is left, unmarked, at
    the top of the Backups list. Measured routes: exporting soon after a
    chat closes, and exporting just after signing in to a restored profile,
    while the catch-up observes the conversations that came with it.
  - **D-19 (low, A): staged-restore state is one per installation but
    treated as the signed-in profile's.** Yara is shown Zed's staged
    restore as hers, and her Cancel erases it without a word to Zed. Over
    the API, a second staging orphans the first. An orphaned staged copy
    (a full re-encrypted copy of the backup) survives its profile's
    deletion, the residue §7.22 set out to prevent.
  - **D-11, two more 500s:** a folder as the path, and an empty backup
    password. Both are API-only.
- **Still open, reproduced:** D-07; D-11 (bit flip).
- **Harness provenance.** Another session changed `pipeline.py` (D-16,
  §7.23) during the first runs. One variant copied it mid-edit and another
  copied the finished but
  uncommitted fix; the change is in a branch no variant reaches. The harness
  now builds from a pinned
  commit, and every number above comes from such runs. Test-design errors
  found along the way are listed in the record (§8) and were corrected
  before the numbers above.

**Not covered:** the UI legs (the Export button's `cmd /c start`, the
picker, the banner, sign-in after a restore); the app's own restart, which
is D-09; a real second machine or Windows user, the installer's embedded
Python, the real embedding model; version skew between builds; large
profiles and power loss; documents other than small ASCII `.txt`; tables
beyond the compared views.

**Exit criterion: not met as worded.** Met with exceptions for the data
round trip at `9968e8c`. Not met for the workflow as a person performs it:
"Close PIP and open it again" does not apply a restore (D-09), and D-18 and
D-20 can silently replace a profile's data or a document with the wrong
thing. Those three are the owner's to decide.

**Recommendations (none implemented; each needs authorization):**
- **D-18:** refuse a backup that is not a completed PIP export, in both
  installers. At least refuse no tables, no rows or missing core tables.
  Properly, have a verified export write a completion mark that restore
  requires. Open the chosen file read-only.
- **D-20 (and likely D-07):** move the profile's `documents/` and `chroma/`
  aside with the database in `_install`, under the same stamp and undo
  list.
- **D-21:** one rule for the listing and the pick: newest by modification
  time.
- **D-17:** take the counts and the export from one read snapshot, and make
  the failure message true.
- **D-19:** scope the status, stage and cancel routes to the signed-in
  profile's `target_db`. Cancel a profile's own earlier staging when it
  stages again. Erase `restore-*.tmp.*` on profile deletion.
- **D-11:** answer a folder and an empty backup password with a 422.

### 7.25 A chat turn a raising pipeline left unended, D-22 (authorized and landed 2026-10-03)

The open item §7.23 named, by the same method. The owner authorized it the
same day.

- **Defect (A):** an exception from `pipeline.run()` propagated out of
  `stream_pipeline_to_websocket` and `ws_chat`'s loop. The socket closed
  mid-turn with no `done`, `error` or `stopped`, and the client's composer
  stayed locked (D-23 below).
  - **Not latent, unlike D-16.** Stage 9 falls back only on the two
    provider errors. Any other exception from a provider ends the pipeline
    with it: a model server answering in a shape the provider did not
    expect, for example. So do the database reads in `_default_providers`
    and `get_active_model_name`, which nothing wraps.
  - **After `done`** (a failure while caching the answer), the reply had
    been shown, but the connection still dropped and the reply was not
    saved.
- **Promise:** §7.23's, unchanged. Every chat turn ends on the socket with
  exactly one `done`, `error` or `stopped`, and a failed turn does not cost
  the connection.
- **Mechanism:** `stream_pipeline_to_websocket` guards the one call that
  runs the pipeline, `next(gen)`.
  - **On an exception** it logs the traceback. If no terminal event has
    gone out, it sends one `error`. It then returns what the client was
    shown, folded by `stage_09.accumulate`, the fold `pipeline.run()`
    already uses.
  - **The turn is saved as shown.** A finished answer is saved, as any
    finished answer is. A partial one is dropped, as the client drops it on
    `error`. The user's message is kept.
  - **A generator that ends without `pipeline_complete`** takes the same
    path; it used to raise.
  - **Only `next()` is guarded.** A send that fails because the client has
    gone still reaches `ws_chat` as a disconnect.
  - **Generic message.** The exception's text stays in the log, because an
    exception can carry model output or message text. The client is told
    the reply was abandoned and the details are in the backend log.
  - **Why the transport, not the pipeline:** this is the code that owns
    the wire contract and sees every exception, wherever in the pipeline it
    started. The pipeline cannot report its own crash.
- **Tests:** 3 more in `backend/tests/test_chat_turn_ends.py`, through the
  real `/ws/chat` and the real pipeline. Ollama is scripted to raise a
  `ValueError`; the cache is patched to fail after `done`.
  - **Raises before answering:** one `error`, no tokens, no exception text.
    The next message on the same socket is answered.
  - **Raises mid-reply:** the token, then one `error`. The partial reply is
    not saved; the user's message is.
  - **Raises after `done`:** nothing more is sent. The next turn begins
    with its own `stage` line, not a stray `error`, and the shown answer is
    saved.
  - **Seen failing first:** all three fail on the old `server.py`. The
    first two got no terminal event within 20 s. The third got `done`,
    then nothing for the second message, because the connection was gone.
    §7.23's three tests pass before and after.
  - **One test corrected before landing:** the mid-reply test first read
    the second turn's rows. The server saves a turn after sending its
    terminal event, so those rows race the socket closing. It now asserts
    only the first turn's rows, which are certain. It still fails on the
    old code.
- **Break-it:** six mutations, each caught:
  - no `error` sent (2 tests);
  - an `error` sent even after the turn had ended (1);
  - a partial reply saved as finished (1);
  - forwarded events not folded, so a finished answer was not saved (1);
  - the exception's text sent to the client (1);
  - the original code (all 3).
- **Commit:** the one that adds this section.
- **Suites:** Backend 1276 passed, 1 failed, run with the embedding shim
  (D-02) and Ollama up. The one failure is the cached-answer test that
  needs real embeddings (§7.17). No client code changed, so the
  Flutter suite was not re-run.

**Not covered (still open):**
- **D-23 (A, found by code reading, not run): the client never ends a turn
  on a dropped connection.** Only the sidebar's connection pill listens to
  `WsChatClient.status`, and `chat_view.dart` does not. The client
  reconnects; the new connection's `session_info` does not end the turn
  either, so the composer stays locked. For a chat started fresh, the
  reconnect also resets the screen's conversation id to none. The id is
  held only by `switchConversation`, and the server sends none for a
  connection that has not sent a message. Reached when the backend process
  dies or restarts mid-reply. Server-side fixes cannot reach it.
  **Fixed 2026-10-08, client side, test-first.** `ChatView` now listens to the
  status stream and ends the turn on a drop (a system line, the composer back to
  Send); a drop while idle or after a finished reply says nothing. `WsChatClient`
  now remembers the conversation id from a `session_info`, so the reconnect resumes
  it instead of starting a second conversation under the same transcript. 8 tests in
  `chat_connection_drop_test.dart` (the two that describe the defect failed on the
  unfixed screen), 5 mutations caught. Not driven in a window.
- **Stage 9 still does not fall back on an unexpected provider
  exception.** The turn now ends cleanly, but the next provider in the
  chain is not tried. Whether it should be is a Stage 9 decision, left
  alone here.
- **The failed turn is not in `trace_log` as one.** The pipeline's
  trace_id never reaches the server, so the trace stops at the last stage
  that logged. The traceback is in the backend log.

**Expected outcomes are not results.** "`vector_store` read is probably
redundant" and "the lock probably stores only a PID" are predictions, not
findings.

---

### 7.26 Import and export fixes (authorized 2026-10-07, landed 2026-10-07 to 2026-10-08)

The owner asked for the import and export logic to be tested and any error in
it fixed, before building a test profile to import. The open defects of §7.24
were taken one at a time, test first, the test seen failing, then a hand-made
mutation of the guard seen failing it again, one commit each. Branch
`fix-import-and-export-features`, from `32d41e4`.

| ID | Fix | Commit |
|---|---|---|
| D-18 | A backup is accepted only if something outside its own contents says it is a whole export. `backend/core/backup_mark.py` is the one rule for the export and both restores: the export writes a one-row `pip_backup_mark` table into the backup *before* copying a row (`writing`) and turns it to `complete`, with the table counts, only after `verify()`, reading it back. A file with no mark predates marks and is accepted if it holds PIP's `identity` table; an empty file, a file with none of PIP's tables, a `writing` mark and counts that no longer match the mark are each refused with a sentence. Both restores drop the mark from the database they build, and open the chosen file read-only (`backup_mark.open_read_only`), so a hot journal beside it is refused with a sentence instead of being played back into the person's own file. | `60f3f3e`, `bcef2bd` |
| D-21 | `newest_backup()` picks by modification time, then the date and number in the name read as numbers, as the listing and the Backup screen already order them. | `b6ea022` |
| D-11 | `stage_restore` answers a folder, an empty backup password, a new password equal to the backup password and a damaged backup with a `RestoreError` sentence (422), and removes whatever temporary files a failed call wrote. The last was found while testing: a failure after the converted database existed left a full re-encrypted copy of the data in the profile folder. | `adedaff` |
| D-20, D-07 | The swap (`restore._install`) and the shortcut's `rebuild_vector_index` move the profile's `documents/` and `chroma/` aside with the database, so the write-back starts from an empty folder. `materialise_documents` leaves a document alone only if its file is inside *this* profile's folder, so a restore into a second profile on the same machine writes its own copies. | `2458c9e` |
| D-17 | The counts and the copy come from one read transaction (`BEGIN`, count, `sqlcipher_export`, `COMMIT`), and an export that fails after its file exists removes the file, so "Nothing was written" is true. | `c4959e8` |
| D-19 | The status, cancel and replace routes act only on a restore staged for the signed-in profile; staging refuses while another profile's is waiting (unless its files are gone), replaces the profile's own earlier staging, and a profile's leftover `restore-*.tmp.*` are in `erasable_paths`. Found on the way: staged files were named by the second, and a second staging inside one second failed with "file is not a database"; they now carry a random suffix. | `f0cf397` |
| D-09 | Nothing stops the backend when the window closes. `scripts/_backend.ps1` finds PIP's backend by the owner of the port *and* a command line naming `backend.api.server`; `launch_pip.ps1` stops a running one only when `pending-restore.json` exists, so the restore is installed by a new backend; `restore_pip.ps1` offers to close it before restoring. Wider than §7.24 said: restore_backup.py refuses while the backend holds the lock, so the first-run "Import existing PIP", which sends the person to that shortcut, could not start on the machine it is shown on. | `5acf162` |

Evidence: 7 new test files (`test_backup_completeness.py`,
`test_restore_newest_backup.py`, `test_restore_bad_inputs.py`,
`test_restore_documents.py`, `test_export_race.py`, `test_restore_scoping.py`,
`test_backend_launcher.py`) and one changed (`test_restore_in_app.py` names the
marker's two new keys). Hand-made mutations: 9, 4, 5, 6, 5, 8 and 5 caught for the seven commits
in order, and 4 for the read-only open. Three tests passed vacuously and were rewritten after the break-it run
showed it (a folder named for the word asserted, an export test that failed
before the file existed, a missing mtime-versus-name case); one guard, the wait
for the port to free in `Stop-PipBackend`, is a timing guard no deterministic
test pins.

**Second round (2026-10-08), from the "still left" list.** Done test-first on the
branch `fix-restore-crash-safety`, which continues `fix-import-and-export-features`:

| What | Result | Commit |
|---|---|---|
| Power loss between "staged" and "restart" | A swap whose process died after the new database moved in and before the new salt did was read as "staged files gone"; the marker was cleared and the profile was left with a database no password opens. The next start now recognises that exact state and installs the salt; the other four crash points already recovered. 6 tests inject a `BaseException` from the Nth rename; 2 mutations caught. | `f7a85b9` |
| `restore_backup.py` interrupted | Ctrl+C or an error at "Type yes to proceed" left a full re-encrypted copy of the data in `data/`. `main()` is now a wrapper that removes what the inner run created and had not moved. 4 tests, 2 mutations. | `83ed303` |
| First-run import from the welcome screen | `POST /backup/import`, allowed only while no profile has a database; profile named after the person in the backup; validation shared with staging (`_open_checked_backup`) and run before anything is registered. Flutter dialog asks for both passwords. 13 backend tests, 16 Flutter tests, 6 + 6 mutations. Checked against a real backend process on a free port (19 of 19). | `d486974` |

Tested, no defect found:

- **A backup from an older PIP into the current one.** Databases were built from the real
  `schema.sql` of six earlier commits (2026-07-03, 08-19, 08-31, 09-02, 09-04, 09-28),
  exported with today's exporter, restored through the real shortcut script and signed in
  to with today's backend: every restore and sign-in succeeded, every screen's route
  answered 200, the backend log held no errors, and each restored database then had all 30
  tables and every column of a fresh current database - except the Phase-0 database of
  2026-07-03, which lacks six columns on `decision_candidates_pending` and
  `memory_candidates_pending` (added in mid-August). No real backup can exist from then,
  so it is recorded, not fixed. The test data was thin (an identity row, one conversation).
- **The Backup screen's Export button.** Its command line (`cmd /c start "PIP Export"
  powershell.exe ... -File <path>`, `backup_view.dart`) was run for real against a
  stand-in `export_pip.ps1` under paths with spaces, parentheses (`Program Files
  (x86)`), `&`, `^`, `!`, an apostrophe, and accented and Chinese characters: every
  one ran. It fails only for a path containing a matched pair of percent signs
  (`100%PATH% off`), which `cmd` expands as an environment variable. Left as a known
  limit: no real install lives under such a name.
- **A large backup.** A 322 MB database of incompressible document blobs plus 2000
  conversations exported in 5 s, staged in 6 s and swapped in under a second; the app's
  restore request has no client timeout. What a large restore costs is the re-index after
  sign-in, which runs as a background task, so sign-in does not wait, but retrieval is
  empty or partial until it finishes - minutes with the real embedding model on a big
  profile, not measured here (D-02). Peak memory was not measured (the reading failed).

**Smart App Control turned off by the owner (2026-10-08), and what that showed.**
The owner turned it off themselves (it is a one-way setting, so it was explained to them
and never changed here). Afterwards `VerifiedAndReputablePolicyState` read 0; torch
2.13.0+cpu imported; the real all-MiniLM-L6-v2 loaded from the local cache (the matching
passage scored 0.73 against the 0.6 threshold, an unrelated sentence 0.04, a reworded
question 0.46); the unsigned Release `pip_flutter_client.exe` started; and the full
backend suite passed **natively, with no embedding stand-in: 1361 passed, 0 failed**. The
original cache test as it stood at `32d41e4` also passes 21 of 21 under the real model,
which confirms the diagnosis in `f144840`: it had failed only because of the stand-in's
scores, not because of the cache. This makes D-02 an environment fact rather than a code
defect - on a machine with Smart App Control on, the backend still cannot import torch and
`pip_embed_shim.py` is still the workaround. It also makes retrieval-quality results valid
here, which they were not under the stand-in; none has been re-measured yet.

**A real window (2026-10-08).** The Flutter client was driven by hand through
a throwaway installation with the real `launch_pip.ps1`, `restore_pip.ps1` and
the real native file chooser. Smart App Control blocks the unsigned *Release*
executable on this machine (the same policy as D-02; it was not touched), but
the *Debug* build runs, so that is what was used. Seen: the welcome screen; the
rewritten import dialog (file name, full path, Copy button - the clipboard held
the full path); closing the window left the backend running; the shortcut
said PIP was still running, closed it on a typed yes, and restored 370 rows;
reopening showed "Welcome back", the profile unlocked with the new password and
the sidebar listed Session 14 down to Session 1, with the Profile screen showing
BatMan, 10 decisions and the project. Then the Backup screen: a new password
equal to the backup password was refused in red with the D-11 sentence; a real
restore staged ("Ready to restore on the next start", 370 rows, 31 tables);
closing and reopening through the launcher replaced the old backend (pid
changed, log line "restarting to apply a restore", `pending-restore.json`
consumed); the OLD password was refused and the NEW one opened all 14 sessions;
the replaced `pip.db`, salt and `documents/` were kept as `.superseded-<stamp>`.
Two things were answered by test hooks and are not the real console: the
password prompts of the shortcut (a script cannot type into a console) and its
final "yes" (PowerShell swallows piped input before a child Python process can
read its own prompt). Found on the way, not fixed: if `restore_backup.py` dies
at its confirmation prompt, its temporary restored copy is left in `data/`.

**A correction.** The first version of this section, and the message of commit
`60f3f3e`, said opening the chosen backup read-only was skipped because an
`ATTACH` from a read-only connection inherits its flags. That was an assumption
that had not been checked, and it is wrong: attaching a new database and running
`sqlcipher_export` from a read-only connection works. It was done in `bcef2bd`,
with two tests that fail while the file is opened read-write.

**Not done, stated rather than hidden.**
- The three agents sent to hunt for *unrecorded* import and export defects
  (first-run import, export side, restore core) did not complete: the session
  limit stopped them. What was found beyond §7.24 came from writing the tests,
  above. The first-run import journey was then driven in a real window (below),
  but the export side and the restore core were not hunted again.
- The shortcut (`restore_pip.ps1` / `restore_backup.py`) still always restores
  into a profile named "Default"; only the first-run screen's import names the
  profile after the person in the backup. The first-run import itself was checked
  against a real backend process, not in a real window (the author's own PIP was
  running, and the desktop tool matches applications by executable name).
- An older backup (no mark) that was cut short and still has an `identity`
  table cannot be told from a whole one.
- D-02 (Smart App Control blocks torch here) is untouched; every test ran under
  the embedding stand-in.
- A real second computer, or a second Windows user, was not available: every "other
  machine" is a throwaway installation on this one.
- `restore_backup.py`'s own install has the same rename order the in-app swap had
  before `f7a85b9`. It is one pass and not resumable, but re-running the shortcut
  from the same backup replaces whatever is there.

---

## 8. Status

### 8.1 Decisions made (choices; need no evidence)

| Decision | Status |
|----------|--------|
| Governing principle and development strategy (§1–2) | Adopted |
| Four-way classification (§3) | Adopted |
| Promise 5 wording: attestation, not proof | Decided |
| Ollama down → queue for next launch, never cloud | Decided |
| Promise 4 narrowed wording | Decided |
| Promise 7 wording except the Track 2 clause | Decided |
| Track 2 outcome "redundant `vector_store` read + documented main-DB env transport" counts as a valid completion | Decided |
| Stage 1 split into 4a/4b | Decided |
| `FREEZE_LIST.md` is the single canonical record | Decided |
| Full Constitution mutation audit deferred | Decided |
| Promise 5 reworded: both locality records; queued until a later start or sign-in (2026-09-28) | Decided |
| Promise 7 final wording, including the key-in-environment clause; uploaded file copy stated as a limitation, not fixed (2026-09-28) | Decided |
| Promise 8, profile isolation, adopted (2026-09-28) | Decided |
| Promise 9, answers reflect the current record, adopted (2026-09-28) | Decided |

### 8.2 Evidence status (facts; need reports)

| Track | Report | Classification |
|-------|--------|----------------|
| 1 Observer/provider gate | Returned 2026-09-26 (§7.2) | C; plus A (startup queue, fixed §7.11) and D (wording, fixed in §4 Promise 5). Finding 2, two locality records, still open |
| 2 `PIP_DB_KEY` | Returned 2026-09-26 (§7.3) | Main DB read: C (redundant, unchanged). `vector_store` read: A (load-bearing, failed open to plaintext; now fails closed, §7.9). Key still exported to the environment, stated in Promise 7 |
| 3 PID-reuse lock | Returned 2026-09-27 (§7.4) | B: stores a bare PID, so a reused PID blocks startup (fixed §7.12) |
| 4a Stage 1 routing | Returned 2026-09-27 (§7.5) | A: 10 of 14 identity/project questions lost the project; header claimed a complete record. Recommendations 1–2 fixed (§7.10); 3, Stage 1 precedence, open |
| 4b Cache safety | Returned 2026-09-27 (§7.6) | A: stale answers replayed after documents or decisions existed; one profile's answer served to another. Cross-profile fixed (§7.9), staleness fixed (§7.10) |
| Promises 1–3 tests | Written 2026-09-28 (§7.13) | C: all three hold, each break-it seen failing; two findings (decisions skip the gate; immutable names shadowed in preferences) |
| End-to-end Observer measurement | Run 2026-09-28 (§7.14) | 37 conversations, 3 runs, qwen2.5:7b: precision 88–90% (memory), 77–83% with decisions; recall 30–39%; sarcasm gets through |
| Promise 4 threshold measurement | Not started | — |
| Database census | Not run | — |
| Cross-track synthesis | Done 2026-09-27 (§7.7) | 5 confirmed patterns; 2 candidate promises; fix order recommended |
| End-to-end profile boundary | Run 2026-09-27 (§7.8); now `test_profile_boundary.py` | Cross-profile cache and in-flight plaintext confirmed via real routes; uploads not per-profile and plaintext on disk (A) |
| Profile boundary fixes | Landed 2026-09-27 (§7.9) | 4 promises enforced and tested; plaintext already on disk and same-profile staleness still open |
| Answers-about-the-user fixes | Landed 2026-09-28 (§7.10) | 3 promises enforced and tested; real-model effect of the new header unmeasured |
| Lost-learning fix | Landed 2026-09-28 (§7.11) | Locality-refused sessions stay queued; Track 1 findings 2-3 still open |
| Lock identity fix | Landed 2026-09-28 (§7.12) | Reused PIDs no longer block PIP; atomic-create race and Linux branch untested |
| Launch-checklist UI fixes | Landed 2026-10-01 (§7.15) | All four landed: contrast, control names, minimum window, password minimum. Open: hover-only delete control, sidebar does not scroll |
| Product-wide validation pass | Run 2026-10-01 (§7.16), report only | Boundaries, consent (ordinary cases), crash recovery and isolation held. D-01 restore over stale WAL (critical) fixed in §7.17, D-03 one-profile export in §7.18, D-04 consent fail-open on id reuse in §7.21. Open: D-02 Smart App Control blocks the backend, plus 5 medium and 4 low |
| D-01 restore sidecars fix | Landed 2026-10-02 (§7.17) | Both installers move the replaced database's `-wal`/`-shm`/`-journal` aside under the kept copy's name; 10 tests, 10 break-it mutations caught. Open: D-14 (a restore staged before its profile is deleted is still installed), profiles already damaged before the fix |
| D-03 one-profile export fix | Landed 2026-10-02 (§7.18) | `export_pip.ps1` takes its profile from the shared `Resolve-PipLastProfile` and always sets the salt with the database; 6 tests through the real wrapper under PowerShell 5.1, 6 break-it mutations caught. Noted: the resolver's one-profile branch never runs under 5.1 (same answer by its fallback) |
| Sign-out cache race (D-15) | Found 2026-10-02 (§7.19) | A: an answer written to the cache after sign-out cleared it is served to the next profile; deterministic with the write delayed (5/5); the §7.9 guard failed 7-8 of 20 runs alone. Fixed in §7.20 |
| D-15 sign-out cache fix | Landed 2026-10-02 (§7.20) | Every cache key carries the session generation sign-out moves, taken per chat connection; also closes an open socket being served the next session's answers. 3 tests seen failing first, 4 break-it mutations caught; the §7.9 guard 159/160 after the fix (one early failure, output not kept) |
| D-04 consent locality fix | Landed 2026-10-02 (§7.21) | Stage 8 counts a provider as local only when its own claim and its consent record agree; `add_endpoint` refuses built-in ids. 11 outcome tests (5 seen failing first), 3 gate unit tests, 6 break-it mutations caught. Promise 6 now has evidence. Open: locality attested not verified, D-08, §7.2 finding 2 |
| D-14 staged restore and deletion fix | Landed 2026-10-02 (§7.22) | `profiles.delete()` first cancels a restore staged for that profile's database, so nothing is installed in a deleted profile's place and the staged copy is erased. 4 route tests (3 seen failing first), 3 break-it mutations caught. Open: `profiles.remove()`, which nothing calls |
| D-16 chat turn with no terminal event | Found and landed 2026-10-03 (§7.23) | A, latent: with no provider left after Stage 8 the socket got stage lines and no done/error, so the chat stayed "writing". The pipeline now sends its error. 3 socket tests through the real pipeline (1 seen failing first), 2 Flutter tests, 4 break-it mutations caught. Open item, a pipeline that raises, fixed as D-22 (§7.25) |
| Migration journey re-run | Run 2026-10-03 (§7.24), report only | 10 variants, exports and shortcut restores through the real `export_pip.ps1` and `restore_pip.ps1`, 307 checks at `9968e8c`, every failure attributed; negative controls catch D-03 and D-14. Round trip holds (D-01 on every in-app restore that had a WAL to swap, D-03 with two profiles). New: D-18 empty or partial backup accepted (medium), D-20 same-named document taken over the backup's (medium, upper end), D-21 shortcut restores the first backup of the day (medium, low end), D-17 export race with a false "Nothing was written" (low, upper end), D-19 staged-restore state not scoped to the profile (low). Exit criterion not met as worded: D-09, D-18, D-20 |
| D-22 raising pipeline ends the turn | Landed 2026-10-03 (§7.25) | A: an exception from the pipeline closed the socket mid-turn with no done/error. The transport now ends the turn with one error, keeps the connection, and saves the turn as the client was shown it. 3 socket tests (all seen failing first), 6 break-it mutations caught. Found: D-23, the client never ends a turn on a dropped connection (code reading) |
| Import and export fixes | Landed 2026-10-07 to 2026-10-08 (§7.26) | D-18 empty or part-written backup refused through a completeness mark, D-21 newest backup by modification time, D-11 bad inputs answered with a sentence and no temporary copy left, D-20 and D-07 the backup's documents written back (the swap moves `documents/` and `chroma/` aside), D-17 one snapshot for the export's counts and copy, D-19 a staged restore scoped to its profile, D-09 the backend stopped so closing and reopening applies a restore and the shortcut can run. D-18 also opens the backup read-only. A second round the same day added a crash-safe swap (a restore whose process died between its last two renames is finished by the next start), a restore script that removes its temporary copy when interrupted, and the first-run import from the welcome screen (`POST /backup/import`, profile named after the person in the backup); an older-version backup and a 322 MB backup were tested with no defect found. Not done: the export side and the restore core were not hunted again for unrecorded defects (the helper agents ran out of usage), the shortcut still restores into "Default", and the new first-run import was checked against a real backend but not in a real window |

---

## 9. Conversation record

How this plan was reached, for future reference.

### 9.1 Sequence
1. **Initial review.** Goal judged sound and the stack defensible. Main
   risk: the governance layer (the graded contribution) was claimed but
   unmeasured, while recent work was mostly shell (installer, icons,
   profile UI).
2. **Evaluation design debated.** Corrections reached: grounding, the
   evidence gate and the Constitution catch *different* error classes;
   the gates run in sequence and the evidence gate must precede
   `reinforce_evidence()`, so they cannot be ablated independently; a
   "policy-only" test set is circular; the Constitution's value may be an
   invariant to test, not a rate to measure.
3. **Constitution audit spec.** Grew over about ten revisions (clause
   table, per-element mutation, guard vs live, canaries, flake protocol,
   census). It was never executed and produced no repository evidence.
4. **Pivot.** Dropped the audit. Adopted seven concrete promises, one
   outcome test and one break-it check each.
5. **Priorities set:** known gaps first, then Promise 7 wording, then the
   remaining promise tests. Everything else frozen.
6. **Gap decisions:** queue-not-fallback; locality as attestation;
   `PIP_DB_KEY` as two consumers; PID lock discovery-first; Stage 1 split
   into routing and cache.
7. **Five task specs sent.** Reports pending.
8. **Documentation.** This file made canonical; strategy (§2) adopted as
   the standing method.

### 9.2 Lessons
1. **Planning can become the sideways expansion it was meant to stop.**
   Ten revisions of the audit spec produced zero evidence; a small test
   would have produced some in an afternoon. Hence the two-revision cap.
2. **Predictions must stay labeled as predictions** until a report
   confirms them — the same "implemented ≠ active" error behind the
   original encryption bug.
3. **The narrowest honest claim beats the strongest unprovable one.**
   Promises 4, 5 and 7 all became stronger documents by claiming less.
4. **Discovery tasks must separate what exists from what is missing.**
   Tracks 2 and 3 may find missing state, not broken wiring, and that
   changes the fix.

### 9.3 Open questions for the owner
- Which recent bug would §2 have caught before shipping, and which would
  it have missed?
- When will the database census run, given it can change what the
  Promise 4 measurement is able to show?

---

## 10. Background (not part of the freeze mechanics)

- **Fine-tuning rejected as a fabrication fix.** The bug was
  deterministic (misleading context); training teaches tendencies, and the
  only corpus was the contaminated history. A smaller stock Observer model
  remains a separate capability experiment.
- **Documented limitations kept visible:** Stage 12 threshold quality
  unmeasured; Stage 1 is regex under a 30 ms budget by design; `PIP_*`
  test isolation not exhaustively audited; decision history keeps only the
  latest `state_reason`; semantic duplicate decisions are not
  deduplicated, by choice.

---

## 11. Freeze rule

Until all five tracks return and are classified:

**No feature work. No speculative cleanup. No fix without evidence.**

Each promise ends in exactly one state: *mechanism + passing evidence*,
*mechanism + documented limitation*, *missing state identified for a
later task*, or *claim narrowed to what the mechanism does*. A promise
that exists only in prose is not resolved.
