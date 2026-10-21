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
still true wherever it is on. On 2026-10-16 a read-only review of D-22's fix
found five small problems; the owner authorized fixing two of them (D-24, D-25),
correcting the record and tightening the tests, landed the same day (§7.44). The
third, D-26, was authorized next and landed the same day (§7.45), and so was
the Stage 9 item §7.44 had left open, D-27 (§7.46). The owner then started the
blueprint's privacy and security cards with G-1: D-05, the plaintext base slot
before sign-in, is fixed (§7.47), and D-28 was found beside it. G-3 followed: D-08, a `-cloud`
Ollama model counted as local, is fixed (§7.48), and so is D-28, a profile
chosen before its password has been set (G-1b, §7.49), which also put right
G-1's refusal of the first-run import, and so is D-06, a
deleted document that left its file and its stored bytes behind (G-2,
§7.50), and so is the older web client's one-click grant of full consent
(G-6, §7.51). Anything further needs a new authorization.

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
Decision candidates have gone through the evidence gate too since G-4 (§7.60); the snapshot keeps
its own grounding gate (§7.13 finding 1).

### Promise 2 — Observer cannot write immutable fields
**Claim:** name, language, timezone change only by the user directly.
**Must prove:** a grounded, gate-passing candidate for these fields cannot
reach a DB write — tested on DB state, not on the enforcer's return value.
**Evidence (2026-09-28):** holds - the identity row never changes, three
independent layers (§7.13). Since G-4 a preference under an immutable field's
name is refused, and one stored before is kept out of prompts (§7.60); a
differently named one ("language") is not caught.

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
**Re-measured (2026-10-18, V-2, §7.55):** on a fresh qwen2.5:7b recording on Ollama 0.40.3, traps 0 of 75
and 36 of 36 learned rows true; on llama3.1:8b, traps 0 of 75. On 27 long made-up chats (1,400-4,800
words), 1 of 162 trick statements and near-misses reached the confirmation queue (D-33: a friend's exam
goal accepted by the gate as the user's interest), and 0 of 81 true facts were learned where their labels
look: the gate's support language rejected ordinary wordings ("I do all my diagrams in X", "my main
project this term is X") whatever the chat's length. D-33 is fixed (§7.61): a topic is the user's only when
they ask about it or say it in the first person.
**Measured blind (2026-10-20, M-1(a), §7.63):** of 58 quotes the gate accepted, 8 did not support their
claim (14%; 95% interval 7-25%): by the rule fixed in advance the wording above does NOT hold for the gate
alone. None of the 8 was stored without asking: the Constitution asked about 4, discarded 3, and wrote 1
(a true project filed as a preference). Of 58 sampled rejections, 20 did support their claim (34%).

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
- The built-in Ollama is local for a model that runs here. An Ollama
  `*-cloud` model is refused at pull and selection, and the provider
  reports itself not local for one already stored (D-08, §7.16; fixed
  2026-10-16, §7.48).
- An endpoint re-saved from remote to local stays refused until it is
  removed and added again (§7.2 finding 2).
- The server accepts any valid scope for any known provider from any caller
  that holds the API token. The dialog that explains the four scopes, with
  nothing preselected, is in the Flutter client; the older web client no
  longer grants at all (G-6, §7.51). The command-line client's `/consent`
  still defaults to `full_inference` when no scope is typed (D-30, §7.51).
- A question about the user is kept off the web only when Stage 1
  recognises it as one: a first-person phrase ("my", "I'm", "do I"), the
  word project or program, an active project's name, or a word shared with a
  recent decision. "what am I working on right now?" has none of these and,
  with web search consented, is still sent (D-31, §7.52).

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
authorized. Deleting a document removes its uploaded file and its stored
bytes (D-06, §7.50); copies made before the delete, and in earlier backups,
are not scrubbed.
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
Deleting a chat clears the "where we left off" note whichever chat wrote
it, removes the chat's queued transcripts and stops its session-end pass
(D-32, §7.53); what the Observer already learned from the chat stays, and
a catch-up already reading its queued transcript can still write a note.
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
| D-05 | Medium | A | After a restart the backend serves the unencrypted `default` slot until a profile is chosen. `GET /status` created a plaintext `data/pip.db`, and a chat sent then was stored in plaintext; a phantom "Default" profile appeared and the next launch said `needs_migration`. The Flutter client avoids the window; the CLI does not. **Fixed 2026-10-16 (§7.47).** | Real-process journey, canary on disk |
| D-06 | Medium | D/A | Deleting a document leaves its plaintext file and its `document_blobs` content, so it also travels in later backups. **Fixed 2026-10-16 (§7.50).** | Through `DELETE /rag/documents` |
| D-07 | Medium | A | A restored document whose original absolute path exists is never re-indexed: write-back is skipped, and the rebuild's ingest refuses a path outside the profile. Retrieval is empty on every sign-in while the Documents screen lists it | Real-process restore |
| D-08 | Medium | D | `/llm/pull` accepts any name and this Ollama has cloud enabled, so a `*-cloud` model would carry chat and the Observer off the machine as "local" `ollama`. **Fixed 2026-10-16 (§7.48).** | Code reading only (would contact an external service) |
| D-09 | Medium | A | "Close PIP and open it again to finish" does not apply a restore: the launcher reuses the running backend, so the swap waits for an unclean exit, which feeds D-01 | Code reading |
| D-10-13 | Low | | 500s for malformed onboarding input and a bit-flipped backup; a dismissed memory question is re-asked when the same words recur; Unlock sits below the fold at 1280x720 | Probes, screenshot |

**Not run:**
- a clean-VM installer lifecycle;
- a real remote provider;
- long-running use (resource leaks);
- driving the UI (one screenshot only);
- retrieval quality (the torch block; measured 2026-10-08, §7.27).

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
  an Ollama `*-cloud` model would still pass as local. *(Fixed 2026-10-16,
  §7.48.)*
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
  closes. Stages 0 to 7 are each wrapped to fail open, and trace writes
  swallow their own errors; Stage 8's gate catches only its own refusal,
  Stages 9 and 10 are not wrapped, and neither is the read in
  `_default_providers`, which `run()` calls on the Stage 8 line. Whether the
  client unlocks on that disconnect was not checked. *(Corrected
  2026-10-16, §7.44: this said every stage was wrapped and that nothing
  wrapped `get_active_model_name`. `run()` wraps its own call to it, for the
  cache key; the call inside `_default_providers` is the one that is not.)*
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
    provider errors, and anything else that left the pipeline closed the
    socket. What can: the database reads in `_default_providers`, a
    failure while the answer is cached or delivered (Stages 9 and 10 are
    not wrapped either), and a value a provider yields that is not text.
    *(Corrected 2026-10-16, §7.44: this bullet named "a model server
    answering in a shape the provider did not expect" as an exception
    that gets out of a provider. Neither shipped provider lets one out:
    both turn every error they raise while streaming into a provider
    error, which Stage 9 handles. The shape gets through as a value
    instead, which is D-25.)*
  - **After `done`** (a failure while caching the answer), the reply had
    been shown, but the connection still dropped and the reply was not
    saved.
- **Promise:** §7.23's, unchanged. Every chat turn ends on the socket with
  exactly one `done`, `error` or `stopped`, and a failed turn does not cost
  the connection.
- **Mechanism:** `stream_pipeline_to_websocket` guards the one call that
  runs the pipeline, `next(gen)`. *(Since §7.44 the guard also covers
  folding the event it returns.)*
  - **On an exception** it logs the traceback. If no terminal event has
    gone out, it sends one `error`. It then returns what the client was
    shown, folded by `stage_09.accumulate`, the fold `pipeline.run()`
    already uses.
  - **The turn is saved as shown.** A finished answer is saved, as any
    finished answer is. A partial one is dropped, as the client drops it on
    `error`. The user's message is kept.
  - **A generator that ends without `pipeline_complete`** takes the same
    path; it used to raise.
  - **Only `next()` is guarded.** *(Since §7.44: `next()` and the fold of
    the event it returns.)* A send that fails because the client has
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
  alone here. *(2026-10-16, §7.46: the one way a shipped provider gets such
  a thing out, a value that is not text, now counts as a provider failure and
  falls back. An exception that is neither provider error still ends the
  turn, on purpose; see there.)*
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
here, which they were not under the stand-in; the first measurement is §7.27.

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

### 7.27 Retrieval quality, first measurement with the real embedding model (run 2026-10-08, report only)

Report `docs/eval/retrieval_quality_2026-10-08.md`; tool `scripts/eval_retrieval.py`;
results for the real model and for the stand-in, and the 72 questions, in `docs/eval/`.
The questions were committed (`6c1720e`) before the first run. Real all-MiniLM-L6-v2 through
the pipeline's own `ingest_document` and `query`, on a temporary index; corpus seven project
documents as of `1577473`; 54 questions with a known answer, 14 plainly off-topic, 4 about PIP
and answered nowhere; searched with the first 12 words, as the pipeline does. A question counts
as answered when a returned passage contains a key phrase from the stated source.

**What it found.**
- As shipped (500-word chunks, cut-off 0.6, top 3) the right passage comes back for **2 of 54**
  questions. Ranking alone has it in the top 3 for 25 and in the top 10 for 34; the cut-off removes
  the rest, because the passage that answers scores a median 0.38.
- The score separates "about PIP" from "not about PIP" (best off-topic score 0.19; nothing came
  back from a cut-off of 0.20 up) but not the right passage from other passages on the same subject
  (median 0.38 for both). From 0.20 to 0.30 the answered count stays at 25, and only 18% to 23% of
  the passages handed to the model hold the answer.
- The 256-token tradeoff in `vector_store.py` is larger than its comment says: a median 500-word
  chunk is 855 tokens and 71% of chunk text lies outside what is embedded. The right passage is in
  the top 3 for 75% (12 of 16) when the answer starts inside the readable part and 34% (13 of 38)
  when it starts beyond it.
- 300-word chunks did best, 57% against 46% in the top 3, but 12 better against 6 worse on the same
  questions (p = 0.24) is not established; 200, 150 and 100 words were no better than 500.
- Stage 1's `skip_rag` gates nothing: Stage 5 runs on every turn (ADR-002) and `stage_02` ignores
  the flag. An early draft of the tool counted it as a gate; that was wrong and was removed before
  any result was recorded.
- With the stand-in the right passage is in the top 3 for 26% and the best off-topic score reaches
  0.58, so what it reports cannot be carried over either way.

**Limits.** One corpus of dense technical Markdown, probably unlike the owner's own documents; an
easy off-topic set (the hard case, a general question near a document's vocabulary, was not
tested); questions written by the same hand that read the documents; retrieval only, not whether
the model answers better or worse with extra passages; three runs agree to within one question.

**Nothing was changed.** The cut-off and the chunking are as they were, and the "~256 tokens"
comment is uncorrected. What the report supports, and what must come first (a second corpus and an
end-to-end check that extra passages do not make the model fabricate), is in its last section; the
end-to-end check is §7.28.
Either change alters what the model is told and needs the owner's authorisation.

### 7.28 Does a lower similarity cut-off help the answers? End-to-end check (run 2026-10-08, report only)

Report `docs/eval/retrieval_e2e_results_2026-10-08.md`; tool `scripts/eval_retrieval_e2e.py`;
protocol `docs/eval/retrieval_e2e_protocol_2026-10-08.json`, committed (`6e5140a`) before any run
along with 12 extra questions no document answers and a decision rule. The real pipeline
(`pipeline.run_sync`, Stages 0-10) on `qwen2.5:7b` at temperature 0, on the §7.27 corpus, with
the cut-off set to 0.60 (shipped), 0.45 and 0.30; 66 questions, 140 distinct prompts, graded
blind to condition by the same hand that wrote them.

**Verdict by the rule fixed in advance: a lower cut-off is not supported, at 0.45 or 0.30.**
Correct answers rose from 1 to 11 to 26 of 54 (sign test p < 0.01 each), and not one of the 12
unanswerable questions was answered with an invention in any condition, even when handed
on-topic passages. But wrong answers among the 54 rose from 4 to 7 to 9, and the rule said they
must not rise. The verdict is the same under a strict and a lenient reading of nine borderline
calls.

**What produced the wrong answers.** When the answer was in the prompt the model was right
20 of 20 times at 0.30. All six new wrong answers came from questions where passages came back
and none held the answer: 27 questions are in that position at 0.30, 8 of them answered wrongly
(30%) against 3 of the same 27 with no passages (11%). That is the failure recorded in §10
(misleading context, not a missing fact), reproduced at small scale. A higher cut-off does not
remove it: those six had top scores of 0.38 to 0.59.

**Also found.** Stage 7 caps the documents section at 800 words (`rag_chunks_tokens`), so of
three 500-word passages the model sees about 1.6; at 0.30 the answer was retrieved but cut for
5 questions. The prompt's grounding rules cover facts about the user only, and say nothing
about how to treat a document that does not state the answer.

**Not done.** Nothing in the pipeline was changed. The two levers this points at - a prompt rule
for documents and the 800-word budget - were not tested; each can be run through the same harness
as a new condition with a rule written first. Limits: one hand, one 7B model, one corpus of
technical Markdown, temperature 0 (a user's model samples), small numbers.

### 7.29 The hunt for unrecorded import and export defects (run 2026-10-08, five found and fixed)

The first item of the second priority list: three agents sent to look for defects nobody had
recorded in the first-run import, the export side and the restore core had been stopped by the
usage limit. This round was done inline. Method: read the code for the places user-typed text meets
SQL, a path, a comparison or a process-wide switch, then probe those places with inputs no earlier
test used. The earlier rounds had used one ASCII password, one ASCII name and one import at a time;
every defect found is a case of that.

**Found and fixed, each with a test seen failing first and hand-made mutations caught.**
- **A password or token in any script crashed three comparisons** (`6146381`).
  `hmac.compare_digest` and `secrets.compare_digest` raise `TypeError` for a `str` with a non-ASCII
  character. The export prompt (`_is_live_secret`) died with a traceback after the backup password
  had been typed twice; the shortcut restore's prompt did the same for a new password; and a
  request with a non-ASCII bearer token was a server error instead of a 401 (not a bypass - the
  exception ended the request). Compared as UTF-8 bytes now. 17 tests failed before; 3 of 3
  mutations caught.
- **A backup could not be imported if its owner's name had no a-z or 0-9** (`59bc820`). The folder name
  comes from `slugify`, which kept only those; a name in Devanagari or Chinese left nothing, and the
  import answered "A profile with that name already exists", which was false and had no way round.
  `slugify` now gives such a name `profile-` and eight hex digits of a hash; a name with no letter or
  digit in any script is still refused when creating a profile, and the import takes `imported-profile`
  for it. 8 tests failed before; 3 of 3 mutations caught.
- **Two imports at once raced** (`cc6ff87`). Activating a profile points the whole process at it, so a
  second import moved the first one's target: one run gave a 500 ("the staged restore was not
  installed"), another gave both a 200 with one reporting the other profile's state. A lock now answers
  the second with a 409. The dialog already disables its button, so this was reachable only from
  outside the screen. 1 test failed before; the mutation is caught.
- **The provider-consent seed raced** (`f1cf5b9`). It counted the rows and, if none, inserted the defaults; the
  sign-in and the catch-up thread each open their own connection to a new profile and both can read "empty", so the
  second insert hit `UNIQUE(provider_id)`. Seen once, out of the lifespan's shutdown, in a full backend run
  (an upload test that passes alone, 3 of 3), then found by reading. The insert is now `ON CONFLICT DO NOTHING`;
  1 test failed before; the mutation is caught.

**Probed, no defect.** Twelve passwords with quotes, semicolons, a backslash, `%s`, spaces at both ends,
300 characters, a tab and an SQL injection string, through the real export and the import (the only
failures were the non-ASCII ones above; `a;b--c` plus `!` was seven characters, a test mistake). Names
`Zoë`, `O'Brien`, `CON` and sixty-four letters import. The document write-back
(`materialise_documents`) uses only the file's base name inside the profile's folder, so a crafted backup
cannot write elsewhere; an empty or `..` name is repointed to a directory, not written. Every
`PRAGMA key` and `ATTACH` quotes its text (`_sql_quote`). `backup_mark.check` builds one query from a table
name in the backup's own record; the connection is read-only, so this is reasoned, not demonstrated, and
not changed.

**Not done, stated rather than hidden.**
- A real console's `getpass` with non-ASCII input was not exercised (a pipe stands in); Windows reads
  it as Unicode.
- A password typed in different Unicode normal forms on two machines would derive different keys; no
  evidence it happens, and nothing normalises. A lone surrogate in a JSON password would fail the key
  derivation with an encode error; no keyboard produces one.
- The real second computer, and the real-window run of the first-run import, are still outstanding.

### 7.30 The two levers on the cut-off, and the check on the owner's own document (run 2026-10-08, report only)

Reports `docs/eval/retrieval_levers_results_2026-10-08.md` and `docs/eval/own_docs_results_2026-10-08.md`; tool
`scripts/eval_retrieval_levers.py`. The untested levers §7.28 pointed at (a prompt rule for documents, D; a documents
budget of 1800 words in place of 800, E; both, F) were run on 40 **held-out** questions (30 answerable drawn by a seeded
sampler, 10 no document answers), against the shipped setting (A) and plain 0.30 (C), with the wording, questions and
decision rule committed before any run (`a1e5f97`). Rule D had been written to address the six wrong answers of §7.28, so
judged on those 66 questions it could only confirm itself.

**Verdict by the rule fixed in advance: neither lever, nor both, is supported.** Wrong answers among the 30 must not rise
above the shipped setting's 4; they were 6 (D), 8 (E) and 7 (F), while correct answers rose by 12 or 13 with none worse
and no invented answer to the 10 unanswerable questions. The validity guard held (plain 0.30 gave 8 wrong, so the set could
have shown a fix). The same under the strict and lenient readings of 30 borderline calls.

**What happened.** The prompt rule left the 15 misleading-passage questions exactly where they were (8 declined, 6 wrong);
the larger budget had nothing to rescue on the held-out questions (the answer was never retrieved-but-cut) and swapped two
gains for two losses. On the development questions both looked better (D: wrong 9 to 5; E: correct 26 to 32), which is what
tuning to a test set looks like and why they decided nothing. Re-running 12 development questions under `num_ctx` 8192
reproduced the earlier answers' text for 9 of 24 runs: grades matched, text did not.

**The owner's own document** (their synopsis, 2,993 words, kept out of git; hashes in `own_docs_manifest_2026-10-08.json`,
committed `90d2607` first). PIP does not accept `.docx` (`.pdf .md .txt .py .json .html` only). Search: found at 0.60 for
**0 of 26** questions, at 0.30 for 7, at 0.20 for 13, at 0.15 for 15; the passage that answers scores a median 0.26
(0.38 on the technical notes), so prose is harder, not easier. Answers: 1 correct as shipped, **8 at 0.30** (p = 0.039),
wrong 3 to 1, no invention; the levers changed nothing. Verdict **inconclusive**: the guard was not met (plain 0.30 did not
reproduce the wrong-answer problem here). 11 of the 26 got no passage even at 0.30, which the search step predicts.

**Not done.** Nothing in the pipeline is changed. A cut-off below 0.30 (0.15 to 0.20 finds 13 to 15 of the 26 on the owner's
document) was not run end to end, because the protocol fixed 0.30 in advance; it needs its own. Retrieval that returns fewer
passages with no answer in them (a better embedder, token-aware chunks, a check of passage against question) was not tested.
Limits: one hand, one 7B model, temperature 0, one 7-chunk document.

### 7.31 A graceful stop of the backend: measured, not built (run 2026-10-08)

The launcher stops a running backend with a hard stop (`_backend.ps1`, `taskkill`), by design (ARCHITECTURE: nothing can
ask for a graceful one). The open question on the priority list was whether that costs anything real enough to justify a
shutdown route - a new endpoint that can end the process, which needs its own locking down. No defect had been shown, so
it was measured first (`docs/eval/reliability_2026-10-01/journey_kill_midstream.py`: a real backend process and a live
`qwen2.5:7b`, the process hard-stopped eight tokens into an answer, restarted, signed in).

**Result: nothing durable is lost.** The transcript after the restart was identical to the one before the kill (the finished
turn intact); the restart took 1.8 s and took over the lock; the same conversation resumed over the socket and the model
answered from its history ("you decided to use Postgres ... because you need JSON columns"); and the next start's catch-up
logged the decision from the cut-off session without being asked. This agrees with the 2026-10-01 validation (§7.16: a
force-kill with the socket open, transcript identical, catch-up processed the session).

**What it does cost.** The turn that was being answered: neither the question nor the partial reply is in the transcript
afterwards, because a turn is saved when it finishes. Nothing a graceful stop could save without also changing when turns
are written, which is a different decision and not one this measurement supports.

**Decision.** No shutdown route is built; the open item is closed on this evidence. Priority 3 is otherwise done: the
chat-connection drop (D-23) and the four failing tests were fixed earlier, and old unmarked backups cannot be detected in
code (export again).

### 7.32 Response cache respects the selected model (fixed 2026-10-10)

- **Promise:** after the selected Ollama model changes, an identical question cannot receive the prior model's cached answer.
- **Mechanism:** `response_cache.cache_key()` includes the selected model name from `llm_settings`; the pipeline uses it for lookup and storage. If the setting cannot be read, that turn bypasses caching.
- **Test-first evidence:** the outcome test failed on the old code because it returned model one's answer after switching to model two. Removing the model component from the key made the test fail again.
- **Verification:** focused pipeline/cache tests passed (42); the full backend suite on the fix alone passed (1399). The combined integration suite below also covers this commit.

---

### 7.33 A-2 schema-table and trigger coverage guard (integrated 2026-10-11)

- **Promise:** every table in a freshly initialized profile database is listed in `RECORD_TABLES` or explicitly excluded with a reason; every listed table has INSERT, UPDATE, and DELETE version triggers.
- **Mechanism:** `backend/tests/test_record_version_coverage.py` compares `sqlite_master` against both lists and checks trigger names. `llm_settings` is excluded from `record_version` because the selected model has its own response-cache key component.
- **Break-it evidence:** removing `documents` from the list while adding `_test_unlisted` makes the real coverage assertion fail and name both. Dropping the `documents` DELETE trigger makes the trigger assertion fail and name it. Weakening each assertion by hand made its break-it test fail with DID NOT RAISE.
- **Limitation:** a fresh-schema test cannot see tables created lazily by application code or only by migrations; review the exclusion list whenever the schema changes.
- **Verification:** 5 focused tests passed; combined pipeline/cache/coverage tests passed (47); full backend suite on `integration/memory-first` passed: **1403 passed in 986.34 s**.
- **History:** initial A-2 test `90cfbb7`; strengthened break-it checks `a076c5a`; integrated with cache fix `4ea3376` in merge `1ac8bb8`.

---

### 7.34 B-1 provider, search, and consent honesty fixes (integrated 2026-10-11)

- **Promise 1 — provider status:** the initial Writing event names the provider and model about to answer. If a provider fails and Stage 9 tries another, it emits a new Writing event naming that provider and model before the attempt. The two outcome tests failed on the old behavior and when either status rule was removed.
- **Promise 2 — web search:** trigger words match whole words; personal and project categories skip web search; a status event shows the exact query sent even when there are no results; the consent choice explains that a short query (normally the first 12 words) may leave the machine. Tests failed on the old substring, category, empty-result, and consent-copy behavior. Break-it mutations caught substring matching, removing the category guard, and hiding a sent query with no results.
- **Promise 3 — revocation:** `api_revoke_consent()` commits the revocation and clears the response cache, so an answer cached under the prior permission state is unavailable. The regression failed before the fix and when the cache-clear call was removed.
- **Promise 4 — provider fallback docs:** `docs/ARCHITECTURE.md` now states that an enabled, previously consented endpoint may be used automatically when Ollama is unreachable; provider priority does not grant consent.
- **Verification:** the B-1 backend module passed (8 tests); the Flutter provider screen tests passed (17). The merged full backend suite passed with the project virtual environment: **1411 passed in 959.02 s**. A preliminary system-Python run had one failure in the existing sign-out cache race test; it passed alone and did not recur in the configured-environment full run.
- **History:** separate promise commits `a245253`, `19a9015`, `bcc5f2b`, and `4ae00fb`; integrated in merge `cbc4aca`.

---

### 7.35 B-2 per-stage trace durations (integrated 2026-10-12)

- **Promise:** each pipeline trace row records its stage duration in integer milliseconds, so a slow operation can be found from the trace instead of inferred from the whole answer time.
- **Mechanism:** the pipeline times Stages 0–10, response-cache lookup, and each denied provider gate; `trace_log.duration_ms` is nullable for older or non-pipeline rows. The legacy composite-key rebuild now always creates `duration_ms` and copies its prior rows, whether the migration runs before or during that rebuild.
- **Break-it evidence:** the 50 ms Stage 4 delay asserts at least 50 ms. A second 50 ms denial test failed before timing was added (recorded 0 ms). The legacy table regression failed before the migration fix (column missing); the existing repeated-stage test also caught a direct rebuild that discarded the column.
- **Live measurement:** one local Ollama chat on isolated backend port 53450 completed with `done`; its 12-row trace totaled 3,155 ms. Stage timings: pipeline 0, Stage 0 0, Stage 1 2, Stage 2 0, cache 0, Stage 3 3, Stage 4 0, Stage 5 retrieval 583, Stage 6 web 0, Stage 7 context 0, Stage 9 LLM stream 2,567, Stage 10 delivery 0 ms. One run on this machine; values rounded to milliseconds.
- **Verification:** 6 focused migration/timing tests passed; full backend suite passed: **1416 passed in 984.76 s**.
- **Limitation:** rounding can show a fast operation as 0 ms; this is elapsed wall-clock time, not CPU time. The measurement is one local run and is not a performance benchmark.
- **History:** B-2 implementation `1b80982`; migration/timing correction committed separately before integration.

---

### 7.36 Observer raw-output recording and unchanged-gate replay (run 2026-10-12)

Recorded all 37 labelled Observer conversations three times with `qwen2.5:7b` (111 case runs, zero errors). The raw
outputs and stamp are in `docs/eval/observer_raw_recording_2026-10-12.json`; the summary and replay check are in
`docs/eval/observer_recording_2026-10-12.md`. Replay through the unchanged pipeline matched the live report for every
case and pooled funnel, learned row, fact and trap result. The pooled result was 105 model candidates, 104 surviving
grounding, 38 learned rows (27 TRUE, 8 UNLABELLED, 3 TRAP), 25/69 stated facts learned, and 3/75 traps reaching a
belief table. Model-call time summed to 609.8 seconds; the approximate stamp-to-file wall interval was 616.4 seconds.
No Observer prompt, evidence gate, Constitution or stages changed. Ollama's runtime context size remains unknown; the
recording captures the configured 8,000-token transcript cap separately. This recording is valid for gate-only
comparisons while its recorded prompt, model and code commit remain unchanged.

---

### 7.37 A-1 evidence gate accepts ordinary first-person statements (run 2026-10-13)

- **Promise:** plain first-person statements the gate used to reject ("I keep all my notes in Obsidian", "I work mostly in TypeScript", "keep your answers short") are accepted for the claim types they support, while third-party statements, hypotheticals, negations, questions, past-tense statements, text only the assistant said, and sarcasm are still refused.
- **Order of work:** the 20 new accept cases and 20 near-miss traps were committed before the gate was touched (`4ca3e66`). The old gate was then scored on them (`b7eaec3`): 1 of 20 accepts right, 17 of 20 traps refused, **3 false accepts**, 19 false rejects.
- **Mechanism (`backend/core/evidence_gate.py`):** more first-person support phrases for tool and note habits, answer style, skills and day-job work, goals, and projects ("I have a small app underway"). On every table except `topic_interests`, a quote is refused when the sentence it was cut from is a question, when it carries a tentative word ("maybe", "might", "someday"), or when its user turn has the frame "sure, because ... obviously". For style, a "don't want / don't like / hate" in front of the phrase refuses it even when the quote left that out.
- **Gate sets** (`scripts/eval_evidence_gate.py --include-new`; `docs/eval/a1_gate_baseline_2026-10-12.txt`, `a1_gate_after_2026-10-12.txt`): the new set 20 of 20 accepts and 20 of 20 refusals, **0 false accepts**, 0 false rejects. The tuned set (40) and earlier held-out set (25) are unchanged with 0 false accepts each. The one held-out false reject (`held_accept_tool_habit`, "I do all my writing in Obsidian these days") is left as it was on purpose, so that set does not become a tuning set.
- **Recorded Observer answers** (37 conversations, 3 runs, A-0's recording replayed with no model call; `a1_observer_old_gate_2026-10-12.md` against `a1_observer_new_gate_2026-10-12.md`): traps reaching a belief table 3 of 75 to **0 of 75** (1, 1, 1 of 25 to 0, 0, 0); stated facts learned 25 of 69 to 37 of 69 (8, 8, 9 of 23 to 12, 12, 13); of the learned rows that carry a label, true ones 27 of 30 to 39 of 39. No case got worse in any run. The recall figures in §7.14 are the old gate's.
- **Review found two defects in the first version of the question refusal; both fixed test-first.** It asked whether the whole turn ended in a question mark. So it dropped a plain fact that shared a message with a question ("I use Neovim for everything. Any plugin suggestions?"; "My goal is to finish my thesis draft by December. Can you help me plan it?"; the old gate had learned both), and it let a question through whenever the turn did not end on one ("Should I use Helix as my editor? I use Neovim." cut to its first sentence was a false accept). It now judges the sentence the quote is cut from, and a quote said plainly once stays accepted even if the same words were asked about elsewhere. The recorded answers contain no turn that mixes a fact with a question (the one recorded mixed case keeps them in separate turns), so the replay could not have shown either defect; 8 of the 12 new tests fail on the first version, 3 of those as false accepts.
- **Break-it:** 12 hand-made removals or weakenings, each caught by at least one test: two new accept phrases, the hypothetical, sarcasm, style-negation and question refusals, the question refusal put back to turn level, the abbreviation skip ("vs.", "e.g."), the "followed by a space" rule ("v1.2"), "any occurrence" in place of "every occurrence", the look-through of closing quotation marks, and "any mark after a fragment is a question".
- **Limits:** the 20 + 20 cases were written by the agent that then edited the gate and the accept side reuses the phrases it added, so they show the gate knows these phrases, not that it generalises. The replay corpus is the one the lost phrasings were found in, and holds only while the Observer prompt, schema and model are unchanged. The sarcasm refusal matches one frame. A tag question ("I use Neovim, right?") is refused as a question. Sentence ends are `.`, `!` and `?` only (no full-width marks). The open finding from the probe on 2026-10-13 (a quote that spans a question and a statement could take the claimed value from the question and the support phrase from the statement; the gate before A-1 accepted it too) is fixed in the G-9 follow-up below.
- **G-9 follow-up (2026-10-16): a value or a support phrase that only a question carries is not evidence.** The case from that probe was one of eleven shapes the A-1 gate accepted (each test written first and seen failing as EVIDENCE_SUFFICIENT): the claimed value only in a question, for a preference ("Should I use Helix? I use Neovim." cited whole for Helix), a goal, a skill and a project; the support phrase only in a question ("Should I use Helix? Neovim is fine." for Neovim); a question in quotation marks followed by a statement; an abbreviation inside the question ("vs."); a question between two statements; a fragment cut from a question in quotation marks; and a question closed by a comma ("Should I use Helix?", he asked.), whole and as a fragment. Step 6 now looks for the value and for the support language in the quote without its questions (`_declarative_text` in `backend/core/evidence_gate.py`). A quote with no question is read exactly as before, `topic_interests` keeps its exemption, and the same quote claimed for the value its statement does name (Neovim) is still accepted. The sentence-end rule now counts closing quotation marks and brackets as part of the mark and treats a question mark closed by a comma or semicolon as an end, which also closes the same holes in the fragment rule above. Evidence: 17 new tests (11 refusals, 6 acceptances), 10 hand-made weakenings each caught by a test, and the three gate sets and the recorded-Observer replay come out identical to A-1's (0 false accepts on every set); those sets hold no quote that mixes a question and a statement, so they could not have shown this defect or its fix. Limits: `interaction_style` still reads its marker from the whole quote ("Can you keep your answers short? Thanks." cited whole is accepted; the question alone is refused); a question mark glued to a letter, as in a web address, is deliberately not a sentence end; the cases were written by the agent that wrote the fix. Full backend suite on the G-9 branch: **1498 passed in 1227.17 s** (the main line's 1481 plus the 17 new tests; one run, no failures).
- **Verification:** the 293 tests in the gate, Observer and session files passed; full backend suite on the A-1 branch: **1478 passed in 889.71 s** (one run, no failures; for scale, 1416 on `integration/memory-first` before A-1's cases and tests). The merged tree on `integration/memory-first`, run before the merge commit was made, is identical to the A-1 tip: **1478 passed in 933.51 s**.
- **History:** cases `4ca3e66`, old-gate baseline `b7eaec3`; the gate change, its tests and the evidence files are `6399367`; integrated in merge `cad8d82`.

### 7.44 Two holes in the turn-end guarantee, D-24 and D-25 (found by review; authorized and landed 2026-10-16)

D-22's fix (§7.25) was reviewed read-only the same day, on clean copies of
the commit: three reviewers, each with a different lens (the server change;
whether exactly one terminal event holds on every path a turn can take, and
what the client does with each; whether the tests prove what §7.25 says),
and then one skeptic per finding, told to refute it and to default to "not
real". 13 agents. 10 findings, none refuted, which are five distinct
problems, all low once the skeptics had rated them. Nine ways a turn can end
were traced and each gave exactly one terminal event, so the promise held.
The owner authorized fixing the first two problems below, correcting the
record and tightening the tests; the third was recorded and left open, then fixed (§7.45).

- **D-24 (A, low): a Stop with nothing left to stop was answered with an
  error.** `ws_chat_client.stop()` says the backend drops a Stop sent when
  nothing is streaming (Part 15.2). `ws_chat`'s main loop read it as a
  request with no `message` and sent "message is required", which the
  client shows as an "Error:" row and takes as ending whatever turn it has
  open.
  - **Three ways in:** sent while idle; sent after a turn's last read of
    the queue, in the final moments of a normal turn; and sent while the
    pipeline was blocked on a slow first token and then raised. A turn reads
    a Stop only between events, and D-22's early return does not read again,
    so that third Stop was still queued when the turn ended. The first two
    predate D-22.
  - The second error followed the first with no await between the two
    sends, so a message typed in the gap was not reachable. The cost was a
    duplicate, meaningless row.
- **D-25 (A, low): a token that is not text closed the connection with no
  terminal event, through the line D-22 added.** The transport folds every
  event it forwards (`stage_09.accumulate`) to know what the client was
  shown. §7.25 put that fold after the send and outside the guard.
  `OpenAICompatibleProvider._tokens_from_line` yields a chunk's `content`
  as it finds it (run: a list of parts comes out as a list), and nothing in
  the provider raises, so its own wrapping of errors never sees it. The
  list was sent to the client, whose token handler does `event.data as
  String`, and the fold then raised `TypeError` out of `ws_chat`'s loop:
  the socket closed mid-turn, D-22's symptom, and a later message got
  nothing.
  - D-22 did not make it worse: before it, the pipeline's own fold raised
    the same error out of the same loop. D-22's guard did not cover this
    input.
  - Reachable in the shipped app only through an OpenAI-compatible endpoint,
    and no route adds one yet (§7.23).
- **Promise:** §7.23's and §7.25's, and two more: a Stop is never answered
  with an error of its own, and an event the transport cannot fold is
  never sent.
- **Mechanism:** both in `backend/api/server.py`.
  - **D-24:** `ws_chat`'s main loop drops a request whose `type` is `stop`
    and carries on. A request with no text that is anything else is still
    answered "message is required". What a turn does with a Stop it reads
    between events is unchanged.
  - **D-25:** the fold moves inside the guard and runs before the send. An
    event it cannot fold is withheld, and the turn ends as it does for any
    other failure of the pipeline: one generic `error`, the traceback in
    the log, the turn saved as the client was shown it. A send that fails
    is still a disconnect and still reaches `ws_chat` as one.
- **Tests:** 9 added in `backend/tests/test_chat_turn_ends.py` and the six
  already there tightened (15 in the file now), through the real `/ws/chat`
  and the real pipeline.
  - **Seen failing first (5 of the 15):** the two Stop tests, which got
    "message is required"; and the three non-text-token cases, which got no
    terminal event in 20 s, with the fold's `TypeError`, after the bad token
    had been sent.
  - **Pass on the unfixed code too (10):** the six existing tests and four
    of the new ones. They hold the code to what it already promised; the
    break-it list below says which test guards what.
  - **A check after the last turn.** `_Events.settled()` collects what
    arrives in the half second after a turn's terminal event, and every
    test asserts it is empty. `turn()` stops at the first terminal event,
    so a duplicate was only ever noticed when it landed at the start of a
    following turn, and the last turn of a test has none.
  - **Raised after an `error`, and after a `stopped`.** §7.25's guard
    against a second terminal event was only exercised after `done`; a
    version that remembered only `done` passed every test. Delivery is now
    made to fail after Stage 9's "All providers failed", and after a Stop.
  - **The log the client is sent to.** The generic message says the details
    are in the backend log; a test now checks the traceback is there.
  - **A generator that ends without `pipeline_complete`,** claimed in
    §7.25 and not tested.
  - **Control:** a request with no text that is not a Stop is still
    answered "message is required" (and `test_ws_chat.py`'s existing
    missing-message test, unchanged).
- **Break-it:** 10 mutations of the fix, one at a time on a clean copy, each caught:
  - the Stop no longer dropped (the two Stop tests);
  - every request without a message dropped, not only a Stop (my control test, which gets no answer; and
    `test_ws_chat.py`'s existing missing-message test, which then waits for an error that is never sent and
    hangs: it was killed at 60 s);
  - the fold back after the send and outside the guard (the three non-text-token cases);
  - the fold inside the guard but after the send, so the bad token is still sent (the same three);
  - the guard against a second terminal event remembering only `done` (the tests that raise after an `error` and
    after a `stopped`);
  - the same guard forgetting `stopped` (the test that raises after a `stopped`);
  - a second error sent after any terminal event once the connection has history, the version the old six tests
    let through (caught after `done`, after an `error` and after a `stopped`, by the check after the last turn);
  - the traceback no longer logged (the log check);
  - the exception's text sent to the client (the test that raises before answering);
  - no error sent when a turn fails (7 tests).
- **Record corrected (D):** three statements in §7.23 and §7.25, each marked
  where it stands.
  - **"Every stage is wrapped to fail open"** (§7.23). Stages 0 to 7 are.
    Stage 8's gate catches only its own refusal; Stages 9 and 10 are not
    wrapped; the read in `_default_providers`, which `run()` calls on the
    Stage 8 line, is not.
  - **"`get_active_model_name`, which nothing wraps"** (§7.23, §7.25).
    `run()` wraps its own call to it, for the cache key; the call inside
    `_default_providers` is the one that is not.
  - **The example of a crash** (§7.25). "A model server answering in a shape
    the provider did not expect" does not get an exception out of a
    shipped provider: both turn every error they raise while streaming into
    a provider error, which Stage 9 handles. The shape gets through as a
    value, which is D-25. What does leave the pipeline as an exception is a
    failure outside the providers: a database read, the cache write,
    delivery. The test fixture's docstring said the same and is corrected.
    §7.25's "not latent" still holds, on those grounds.
- **Suites:** Backend 1507 passed, 0 failed (16 min 37 s), run with the embedding shim on a clean export of `c0edb29` plus this change. The turn-end file alone passed 8 runs in 8. No client file changed, so the Flutter suite was
  not re-run.

**Not covered (still open):**
- **D-26 (A, found by the review): the database writes around a turn are
  not guarded.** *(Fixed 2026-10-16, §7.45. Not "low", as rated here: see
  there.)* `start_session` and `create_conversation`
  run before a turn's first event, and both `append_message` calls run
  after its terminal event. `ws_chat` catches only `WebSocketDisconnect`,
  so a failure in any of them (a locked or full database) closes the
  connection: with no terminal event if it comes before the turn, and with
  the reply already shown if it comes after. §7.25 said only `next()` was
  guarded and this is what that left; its promise line read as broader.
  Reproduced in the review through the real `/ws/chat`. Needs its own
  authorization, and a decision on what the client should be told when its
  message could not be saved.
- **A non-text token ends the turn; it is not skipped.** Stage 9 does not
  treat it as a contract violation, as it does a provider that yields
  nothing, so the next provider is not tried. Whether it should be is a
  Stage 9 decision, left alone with the other fall-back question under
  §7.25. *(Fixed 2026-10-16, §7.46, D-27.)*
- **The pipeline's generator is left suspended** when a failed fold ends a
  turn. It is closed by garbage collection on the event-loop thread, as a
  mid-stream disconnect already leaves it. Nothing in the chain
  (`pipeline.run()`, Stage 9, both providers) has a `finally`, a
  `BaseException` handler or a database call that closing it would run: it
  closes the connection to the model server and nothing else. Read, not
  tested.
- **The client is unchanged.** `ws_chat_client.dart`'s comment, that the
  backend just drops a Stop with nothing streaming, is now true. Not run in
  a window.

### 7.45 A failed write around a chat turn closed the connection, D-26 (authorized and landed 2026-10-16)

The third problem of §7.44's review, which that section left open. The owner
authorized it the same day.

- **Defect (A, medium):** a database write that failed around a chat turn
  ended the handler, and the connection with it. §7.44 rated it low, as a
  failure of a locked or full database. It does not need one. Foreign keys
  are enforced, and two ordinary things trip them. Both were reproduced on
  `HEAD` through the real `/ws/chat` with nothing patched:
  - **A message naming a project that no longer exists.**
    `create_conversation` raises `FOREIGN KEY constraint failed` before the
    turn's first event, so the client got nothing at all, not the stage
    lines and not an error, and the chat sat "writing": D-16's symptom from
    a different line.
  - **A conversation deleted while a chat is open on it.** The turn is
    answered and shown, then `append_message` fails on the same constraint
    and the handler dies. The reply is on screen, the connection is gone,
    and the turn is in no transcript.
  - **And a write that fails leaves its first statement pending.**
    `append_message` is three statements and a commit. Closing the
    connection threw that away; keeping the connection, which is the point,
    would have let the next write's commit save it.
- **Promise:** a failed write around a turn costs neither the connection
  nor the integrity of the next write, and no message is answered into a
  chat that is not being kept: it is saved, or the person is told it was not
  answered.
- **Mechanism:** all in `backend/api/server.py`.
  - **`_run_write`** runs one write on the connection's own thread and, if
    it fails, rolls it back and raises. Every write around a turn goes
    through it.
  - **Before a message is answered,** whatever an earlier turn could not
    save, the session count and the conversation row are written inside a
    guard. A failure refuses the message: one `error` ("This chat could not
    be saved just now, so your message was not answered. Send it again, or
    start a new chat if this keeps happening. The details are in the backend
    log."), nothing sent to the model, the connection kept. The text names no
    cause; the exception stays in the log. The session is counted only after
    its write has gone through. It was marked first, which a handler that
    died could afford.
  - **After a turn,** its messages are queued with the time they happened,
    then written. A write that fails leaves them queued and is logged with
    its traceback. They are written, in order and with their own times,
    before the next message is looked at; if that fails too, the message is
    refused as above, so a chat that cannot be saved is not carried on
    silently. At most one turn is ever queued, since a message is refused
    while the queue cannot be written.
  - **The failed save is not announced when it happens.** The turn has
    ended, and the only event there is for a failure is an `error`, which
    would be a second terminal event for the turn, and which the client
    takes as the end of the next one. A decision, listed below.
- **Tests:** 5 added to `backend/tests/test_chat_turn_ends.py` (20 in the
  file now), through the real `/ws/chat` and the real pipeline. Two use the
  real triggers above. Two inject a failure: `begin_session` locked once, and
  a write that fails after its row is inserted, run for each of the pair of
  messages.
  - **Seen failing first (all 5):** on `HEAD` the exception left the handler
    in each, at `create_conversation`, at `start_session`, at the user
    message's write, at the reply's write, and at the write after the
    conversation was deleted. The 15 earlier tests passed.
  - **What they pin:** the refusal is a single `error` with nothing else
    around it and no exception text in it; the refused message never reaches
    the model and leaves no conversation row; the session is counted exactly
    once; after a half-written failure the rows are exactly the four
    expected, in order, with none doubled; the retried rows carry the first
    turn's time and not the retry's; a failed save after a reply sends
    nothing; and the next two messages are refused without being answered.
- **Break-it:** 10 mutations of the fix, one at a time on a clean copy, each caught:
  - a failed write not rolled back (the two half-written-save cases);
  - the queue not written before the next message is looked at, so nothing refuses it (the
    deleted-conversation test);
  - a queued row dropped when its write fails instead of kept (the two half-written-save cases
    and the deleted-conversation test);
  - the refusal removed, so a failed write before the turn ends the handler again (the stale-project
    test, the session-count test and the deleted-conversation test);
  - the session marked counted before its write (the session-count test);
  - the retried rows stamped at the time of the retry, not of the turn (the two half-written-save cases);
  - the exception's text added to the error the client is sent (the three refusal tests, through the
    check on the text);
  - the refusal sent and the message answered anyway (the same three);
  - the failed save announced as a second error (the two half-written-save cases and the
    deleted-conversation test);
  - a failure of the queue ignored before the next message, so it is answered anyway (the
    deleted-conversation test).
- **Suites:** Backend 1512 passed, 0 failed (15 min 31 s), run with the embedding shim on a clean export of `7239b81` plus this change. The turn-end file alone passed 8 runs in 8. No client file changed, so the Flutter suite was not re-run.

**Decision made here (easy to reverse):** a save that fails after a reply was
shown is told to the person only when they send the next message. Telling
them at once needs an event that does not end a turn, and a client that shows
it; neither exists. No client file changed.

**Not covered (still open):**
- **A turn still queued when the connection closes is not saved.** It is
  logged when the write fails, and the Observer at disconnect still learns
  from it, since it reads the history in memory, but the saved transcript
  lacks it. The disconnect path is the one the `TestClient` harness cannot be
  relied on to run (see the flaky disconnect test), so it is read, not tested.
- **The refusal does not say which write failed.** The log does. For a
  deleted project, "send it again" will fail again until the person changes
  the project scope, which the client holds.
- **The writes that fail open on purpose are unchanged:** trace entries and
  document access counts.

### 7.46 A token that is not text is a provider failure, D-27 (authorized and landed 2026-10-16)

The Stage 9 item §7.44 left open, by the same method. The owner asked for it
to start the same day.

- **Defect (A, low):** Stage 9 passed on whatever a provider yielded as a
  token. `OpenAICompatibleProvider` yields a chunk's `content` as it finds it,
  so a server that streams structured content (a list of parts), or a null,
  put a value that is not text into the stream. Since §7.44 (D-25) that no
  longer closes the connection: the transport withholds it and ends the turn
  with one generic error. But a provider whose first token was not text was
  not treated as having failed, so the next provider in the chain was never
  asked, and the person got an error that named nothing.
  - Reachable in the shipped app only through an OpenAI-compatible endpoint,
    and no route adds one yet (§7.23): the committed `server.py` has none.
- **Promise:** a provider that yields something that is not text has failed,
  the same as one that yields nothing. Another is tried if nothing was shown
  yet, and a turn that had already shown something ends with the
  interruption, never with a second provider's answer under the first.
- **Mechanism:** in `backend/stages/stage_09_llm_streaming.py`, a token that
  is not a `str` raises `ProviderExecutionError`, inside the loop that
  already handles the two provider errors, after the stop check (a stop still
  wins) and before the token is sent. Everything after that is the existing
  fallback: before any text, the next provider; after some, "Response
  interrupted: ...".
  - **The message names the type, not the value.** What a provider sent may
    be anything, and this text reaches the client.
  - **Consent is unchanged.** Stage 8 has already removed every provider
    without it, so the fallback goes only to consented ones, as for any other
    provider failure.
  - **The empty string is still text.** A provider that streams an empty
    piece is not broken.
  - **The transport's guard stays** (§7.44, D-25), for whatever produces an
    event it cannot fold. Its three tests were moved onto a fake pipeline:
    Stage 9 now refuses these first, and left as they were the tests would
    have passed without exercising the guard.
- **Tests:** 10 added to `test_stage_09_llm_streaming.py` (22 in the file) and
  2 end-to-end to `test_chat_turn_ends.py` (22 in the file), through the real
  `/ws/chat` with a local second endpoint, which needs no consent.
  - **Seen failing first:** 8 of the 10 unit tests and both end-to-end tests.
    The other two unit tests are controls that pass either way: the empty
    string, and a stop arriving before a bad token. The three D-25 tests pass
    before and after the move, since they hold the transport, which this does
    not change.
  - **Break-it:** 6 mutations, one at a time on a clean copy, each caught:
  - the check removed (the eight unit tests that fail on the old code and both end-to-end tests);
  - the check made before the stop is looked at (the stop-first control, and the tests that read the
    message the mutation changed);
  - the offending value put into the message (the type-name checks, the after-text test and the
    end-to-end leak check);
  - the empty string refused as well (the empty-string control);
  - the transport's fold put back after the send and outside the guard (the three transport tests,
    now on a fake pipeline);
  - the fold inside the guard but after the send, so the bad token still goes out (the same three).
- **Suites:** Backend 1524 passed, 0 failed (16 min 7 s), run with the embedding shim on a clean export of `cb58910` plus this change. The two test files passed 8 runs in 8. No client file changed, so the Flutter suite was not re-run.

**Not covered (still open):**
- **An exception that is neither provider error still ends the turn.** The
  other half of the fall-back question under §7.25, left as it is on purpose.
  Both shipped providers turn every error they raise into one of the two, so
  only a bug could produce one, and falling back on a bug would send the
  prompt to a second provider for it.
- **Structured content is refused, not read.** A server that streams its text
  as a list of parts gets no answer from this provider: its first token fails
  it. Reading the parts would be new behaviour and was not asked for.

### 7.47 G-1: no database before anyone has signed in, D-05 (authorized 2026-10-16)

The first of the blueprint's privacy and security cards. It overlaps a guard
another session left uncommitted in `_conn()`, for an installation whose registry
lists nobody (with its own test, `test_empty_installation_creates_nothing.py`, and
no FREEZE_LIST section or LOG line of its own). That guard is kept, and widened.

- **Defect (A, medium; D-05, §7.16):** after a restart nothing has activated a
  profile, so the process points at the base slot (`data/pip.db`,
  `data/salt.bin`), where the installation lived before profiles existed. With
  profiles registered that slot holds nothing, `session_key.state()` calls it
  "setup" (no salt, no data), and `LockGateMiddleware`, which only gated
  "locked", let everything through. `_conn()` then opened the missing database
  and `open_app_connection()` created an empty unencrypted `pip.db` there.
  - **Reproduced on `HEAD` through the real routes.** Two profiles made with
    passwords, the first run ended, a second start (a real lifespan), nobody
    signed in. Of 65 method-and-path pairs, 7 are the sign-in set. Of the other
    58, **56 were served** (27 returned data, 6 crashed inside on the empty
    payload) and 2 answered 423. The base slot ended up with `pip.db`,
    `pip.db-wal` and `pip.db-shm`.
  - **The chat socket was accepted,** so a message sent in that window was
    stored unencrypted beside the encrypted profiles.
  - **A "Default" profile appeared** in the sign-in list that nobody made:
    `['default', 'alice', 'bob']` for two registered profiles.
  - **The other session's guard does not reach it.** With that guard added to
    `HEAD`, the same three tests fail: it refuses only when the registry lists
    nobody, and here it lists two.
- **Promise:** with profiles registered and nobody signed in, no request
  creates or writes a database. The answer is 423 (4423 on the chat socket)
  until a profile has been chosen and opened.
- **Mechanism:** one rule, in `backend/api/server.py`.
  - **`_no_profile_is_open()`:** a registry exists, and the profile the process
    is pointed at is not in it. `_is_locked()` adds that to the old "locked"
    state, only when the state is "setup". *(G-1b, §7.49, replaced it with
    `_has_profiles()`: a registry exists, with no condition on which profile
    the process is pointed at.)*
  - **Asked in three places that used to write `state == "locked"` for
    themselves:** the lock gate, the chat socket's check before `accept()`,
    and `_conn()` as the backstop. A case missing from any one would have been
    found through it.
  - **The other session's `_conn()` guard is widened, not replaced.** It asked
    "the registry lists nobody"; this asks "the process is pointed at none of
    the profiles the registry lists", of which an empty list is one case. Its
    two tests still pass, and its 423 handler for `LockedError` is used as it
    was.
  - **Only when a registry exists.** An installation that never registered a
    profile has none to be pointed away from, and the tests, which build
    databases at isolated paths with no registry, are exactly that.
  - **The sign-in screen is unaffected:** its routes are exempt by the gate's
    own list, and choosing a profile and unlocking it, then using the app,
    works as before. *(Not quite: the welcome screen's first-run import,
    `POST /backup/import`, was not on that list and was refused with 423 after
    the last profile was deleted. Found and fixed in G-1b, §7.49.)*
- **Tests:** 6 in `backend/tests/test_no_plaintext_database_before_sign_in.py`,
  through the real routes and a real second lifespan.
  - **Seen failing first (4 of 6, on `HEAD`):** the census, the chat socket,
    the backstop in `_conn()`, and the phantom profile. The other two are
    controls that pass before and after: starting the backend creates nothing
    in the base slot, and signing in after the restart still works.
  - **A status code cannot say which of the gate and the backstop answered,** so
    the backstop has its own test, calling `_conn()` directly.
- **Break-it:** 6 mutations, one at a time on a clean copy, each caught:
  - the whole rule disabled (the census, the chat socket, the backstop, the phantom profile, and the
    other session's own empty-installation test);
  - the lock gate left on the old condition (the census alone: the routes that check their payload
    first answered 422, not 423);
  - the chat socket left on the old condition (the socket test);
  - the `_conn()` backstop left on the old condition (the backstop test);
  - the rule made to cover only a registry that lists someone (the other session's
    empty-installation test);
  - the registry no longer required (24 of the existing tests in `test_ws_chat.py`,
    `test_api_server.py` and `test_pipeline.py`, which build databases with no registry).
- **Suites:** Backend 1532 passed, 0 failed (17 min 43 s), run with the embedding shim on a clean export of `d560c30` plus the working-tree `server.py` and both test files, so with the other session's guard included. The two test files passed 8 runs in 8. No client file changed, so the Flutter suite was not re-run.

**Found beside it (D-28, A, medium; fixed the same day, §7.49):** a profile that has been
created and chosen but has no password yet is in "setup" too, and the rule
above lets it through, because the process *is* pointed at a registered
profile. Reproduced through the real routes: create a profile, one
`GET /status`, and a plaintext `pip.db` exists in that profile's own folder,
the state becomes `needs_migration`, and `POST /auth/setup` is refused with
"run scripts/set_db_password.py". The profile cannot be set up through the app
after that, and a chat sent in the window would be stored unencrypted. The
catch-up has refused to create a database that is not there since a fresh
install hit the same thing (`_start_catch_up`); the routes never did. Whether
the Flutter app reaches the window was checked in G-1b (§7.49). The fix is the
same rule one step further, "setup" with a registry means no database route,
which changed more than G-1's card and was authorized as its own.

**Not covered (still open):**
- **An installation with no registry at all** (a first run, before any profile
  exists) is unchanged: a request can still create the base database. It cannot
  be told apart from the tests' own situation without a registry, and the
  blueprint's card is about profiles being present.

### 7.48 G-3: a cloud model is not a local one, D-08 (authorized 2026-10-16)

The second of the blueprint's privacy and security cards.

- **Defect (D, then A; medium; D-08, §7.16):** Ollama can run a model on its own
  servers. Signed in to Ollama, a model whose name ends in `-cloud`, or whose
  tag is `cloud`, is answered over the internet through the same local port and
  API as a model on this disk. `OllamaProvider.get_model_info()` said
  `is_local: True` for any model name, and the `ollama` consent record says
  local, so Stage 8 and the Observer's own check, which compare the two,
  agreed with each other and were both wrong. A conversation, and the
  Observer's whole session transcript, went off the machine as though it were
  local. Three ways in:
  - **`POST /llm/pull`** accepts any name.
  - **`POST /llm/active-model`** accepts a name Ollama lists, and Ollama lists a
    cloud model once someone has run it.
  - **A name already stored,** from before.
  - **Read, not demonstrated,** as the card says: showing it for real would have
    been the leak. Here Ollama is a stub that records what it is sent, and on
    `HEAD` it was sent the conversation for a stored cloud model (the turn ended
    `success`).
- **Promise:** a conversation is never sent to a model Ollama runs elsewhere
  under the name of a local provider. A cloud model cannot be pulled or
  selected, and one already stored is refused like any provider whose own claim
  and consent record disagree.
- **Mechanism:** one predicate, `is_cloud_model()` in
  `backend/providers/ollama_provider.py`: the whole word `cloud` at the end of a
  name (`-cloud`, `:cloud`, `/cloud`, or the whole name), case and surrounding
  spaces ignored. Used in three places.
  - **Pull and selection** refuse with one sentence ("... would run it on its
    own servers, so your conversation would leave this machine. PIP only uses
    models that run here."), as 400 and 422. The selection check runs **before**
    Ollama is asked whether the name is real: that lookup fails open when Ollama
    is down, so that choosing a model for when it is back is not blocked, and a
    cloud name must not ride that.
  - **The provider** reports `is_local: False` for such a name. Stage 8 then
    refuses it (its claim and the consent record disagree: D-04's rule), and so
    does Stage 11 (`ObserverLocalProviderError`, the session stays queued), for
    a name stored before this fix. Neither stage changed.
  - **Fails closed.** A local model that merely has "cloud" inside its name
    (`cloudy:7b`, `cloud-atlas:3b`, `my-cloud-model:13b`) is not caught; one that
    really is called `cloud` is.
- **Tests:** 43 in `backend/tests/test_cloud_model_is_not_local.py`, through the
  real routes, pipeline and Stage 11, Ollama a stub.
  - **Seen failing first:** 28 of the 43 on `HEAD`. The other 15 are controls
    that pass before and after: local names are still recognised as local,
    pulled, selected (also while Ollama is down) and used.
  - **What they pin:** the refusal sentence, on six cloud spellings; that Ollama
    is never asked to pull; that the active model is unchanged; that a stored
    cloud name sends nothing; that the Observer's transcript is not sent; and
    that a cloud name is refused while Ollama is unreachable.
- **Break-it:** 7 mutations, one at a time on a clean copy, each caught:
  - the pull no longer refusing a cloud name (the six pull tests);
  - the selection no longer refusing it (the two selection tests, one of them with Ollama down);
  - the provider claiming to be local for any name (the six provider tests, the stored-name test and
    the Observer test);
  - the predicate missing the `:cloud` tag (one case in each of the recognised, provider and pull tests);
  - the predicate matching any name that contains "cloud" (`cloudy:7b` and the other local names, in
    the recognised, provider and pull controls);
  - the predicate case-sensitive (the upper-case name, in the same three);
  - the predicate sensitive to surrounding spaces (the padded name, in the recognised and provider
    tests; a pull strips it first).
- **Suites:** Backend 1575 passed, 0 failed (13 min 11 s), run with the embedding shim on a clean export of `5a5a244` plus this change, with nothing else running. A first run, alongside other test runs of mine, had one failure, `test_profile_boundary.py::test_a_sign_in_gets_its_own_catch_up_while_the_previous_sessions_is_still_running`; it passed 6 of 6 alone on this change and 6 of 6 on `5a5a244`, and the quiet re-run passed everything, so it was load. The new file passed 8 runs in 8. No client file changed, so the Flutter suite was not re-run.

**Not covered (still open):**
- **The name is the signal.** It is the only one available before anything is
  sent, and it is how Ollama names its cloud models. Ollama's own listing
  carries more about such a model; it was not used, because it could not be
  checked against a live Ollama here without contacting one.
- **A stored cloud name ends the turn with "No consented provider available"**
  and the Observer's session stays queued. The person is not told why in that
  message; the log has Stage 8's reason.
- **The picker still lists a cloud model** that Ollama has, until it is chosen
  and refused with the sentence.

### 7.49 G-1b: no database for a profile that has no password, D-28 (authorized 2026-10-16)

The third of the blueprint's privacy and security cards: the one G-1 found
beside itself (§7.47). It also puts right something G-1 itself broke, found on
the way (second bullet).

- **Defect (A, medium; D-28):** a profile that has been created and chosen but
  has no password yet is in "setup" too: no salt, no data. G-1's rule let it
  through, because the process *is* pointed at a registered profile.
  - **Reproduced on `HEAD` through the real routes.** Create a profile, ask any
    database route once, and a plaintext `pip.db` exists in that profile's own
    folder; the state becomes `needs_migration`; and `POST /auth/setup` is
    refused ("run scripts/set_db_password.py"). The profile can no longer be
    given a password through the app, and a chat sent in that window would be
    stored unencrypted. Of the 58 gated method-and-path pairs, 56 were
    served (27 returned data).
  - **The Flutter app does not reach the window.** Read from the code, not run in
    a window: it asks `/auth/state` first and calls no database route before the
    profile is unlocked. What can reach it is anything holding the API token: the
    older web client, a script, a second window.
- **Also found, and G-1's own doing: the welcome screen's Import.** The first-run
  import (`POST /backup/import`) is the one route the sign-in screen calls that is
  not on the gate's exempt list. It opens no live database (it checks a backup
  file, registers a new profile and stages the restore) and carries its own rule.
  After the last profile is deleted the registry file stays behind, listing nobody,
  and the welcome screen comes back; G-1's gate then answered it 423 before the
  route could run, so the button was dead. Seen failing on `HEAD`. Found when the
  full suite was run on G-1b's rule alone: one existing test, which expects the
  route's own 409 for a chosen profile with no password, got the gate's 423.
- **Promise:** a request never creates a database that has no password. With
  profiles registered, "setup" means 423 (4423 on the chat socket) until
  `/auth/setup` has chosen the password, however the process came to be there;
  and the sign-in screen's own routes, the first-run import among them, are never
  refused by the gate.
- **Mechanism:** G-1's rule one step further, in `backend/api/server.py`.
  - **`_has_profiles()`** replaces `_no_profile_is_open()`: a registry exists, even
    one that lists nobody. `_is_locked()` is "locked", or "setup" with a registry,
    asked in the same three places: the lock gate, the chat socket before
    `accept()`, and `_conn()`.
  - **The condition got simpler, not only wider.** G-1 asked whether the profile
    the process is pointed at is registered, because that told the empty base slot
    from a chosen profile. Once both are refused the question has one answer for
    both, so it went.
  - **The sign-in screen and `/auth/setup` are unaffected:** both are in the
    gate's exempt list, and `/auth/setup` is how a database comes to exist, as is
    creating a profile.
  - **`/backup/import` joins that list.** The route refuses for itself (409) as
    soon as any profile is registered or anyone is signed in, so the gate has
    nothing to add; in a locked installation it now answers with its own sentence
    instead of "PIP is locked".
  - **Only when a registry exists,** as before (§7.47).
- **Tests:** 7 added, through the real routes: 5 in
  `backend/tests/test_no_plaintext_database_before_sign_in.py` (now 11) and 2 in
  `backend/tests/test_first_run_import.py` (now 15).
  - **Seen failing first (5 of the 7, on `HEAD`):** the census of every gated
    route, the chat socket, `_conn()` called directly, and the whole defect as a
    sequence (a database route, then the password: the route must answer 423 and
    `/auth/setup` must then work and leave an encrypted file); and the import after
    every profile was deleted. The other two pass before and after: setting the
    password straight away still works, and a chosen profile with no password still
    gets the import route's own sentence, not the gate's.
  - **G-1's six still pass,** and so do the other session's two and the whole
    first-run import file.
- **Break-it:** 9 mutations, one at a time on a clean copy, each caught:
  - the whole rule disabled (8 of the 11 tests in the sign-in file: the four new ones and the four of G-1 that
    need it; the three controls pass);
  - the lock gate left on the old condition (the census of G-1 and the new one);
  - the chat socket left on the old condition (the socket test of G-1 and the new one);
  - the `_conn()` backstop left on the old condition (the backstop test of G-1 and the new one);
  - G-1's narrower rule put back, "the process is pointed at none of the registered profiles" (exactly the four
    new tests that need the new behaviour: the gate, the socket, the backstop and the request-then-password
    sequence);
  - the first-run import left to the lock gate again (the new import-after-delete test, the new own-sentence
    test, and the existing test that expects the route's own 409);
  - the import route's own refusal removed, so that the exemption alone would guard it (the same existing test,
    its locked-profile twin, and the new own-sentence test);
  - the registry no longer required (24 of the 153 tests in `test_ws_chat.py`, `test_api_server.py`,
    `test_pipeline.py` and `test_sign_in.py`, which build databases with no registry);
  - every state but "unlocked" refused, which is wider than "setup" (41 of the same 153: it also refuses
    `needs_migration` and the no-registry setup those tests use).
- **Suites:** Backend 1582 passed, 0 failed (17 min 6 s), run with the embedding shim on a clean export of `5a3000a` plus this change, with nothing else running. A first attempt was cut short about half way when the machine stopped (no result, not a failure) and was run again from the start. An earlier full run on the rule alone, before the import route was put on the exempt list, had one failure, `test_first_run_import.py::test_it_is_refused_once_any_profile_has_a_database` (423 where the route's own 409 was expected), which is how the import problem was found. The new tests passed 8 runs in 8. No client file changed, so the Flutter suite was not re-run.

**Found beside it, not fixed (D-29, A, low):** the import route's own rule is
meant to be "no profile has a database", but it reads
`any(p.exists for p in profiles.list_profiles())`, and `exists` is a method, so
the test is on the method object and is true for any registered profile.
Through the real routes: create a profile and do not give it a password, then
import a backup, and the answer is 409 "PIP already has a profile on this
computer" although no profile has a database. It only over-refuses, so it is
safe, and the welcome screen cannot reach it (it is shown only when no profile
is listed). Not fixed: it is outside this card, and the right fix (call it) lets
an import through in a state nobody has watched it work in.

**Not covered (still open):**
- **An installation with no registry at all** is unchanged (§7.47): a request can
  still create the base database on a first run, before any profile exists. The
  app creates a profile first, so it does not; the tests' own situation cannot be
  told apart without a registry.
- **The sentence at the gate** is the old one for every refusal ("PIP is locked.
  Sign in to open your data."). For a profile with no password yet, "choose a
  password" would be truer. No client shows it in this window.
- **The import in a real window** was not watched (blueprint card V-1); the route
  was driven through the real backend, as before.

### 7.50 G-2: deleting a document removes the copies PIP made of it, D-06 (authorized 2026-10-16)

The fourth of the blueprint's privacy and security cards.

- **Defect (D, then A; medium; D-06, §7.16):** `DELETE /rag/documents` removed a
  document's chunks from the index and marked its registry row "removed", and
  stopped there. Beside the person's own file, PIP holds a document in three
  places, and two of them stayed:
  - **The uploaded file** in the profile's documents folder, an ordinary
    readable file (Promise 7 says uploads are kept there, unencrypted).
  - **Its bytes in `document_blobs`,** inside the encrypted database, and so
    inside every backup made afterwards.
  - **Reproduced on `HEAD` through the real routes.** Upload `budget.txt` through the real route and delete it through the real route: the answer is 200 and the document leaves the list and the search, but the file is still in the profile's documents folder with its bytes, the `document_blobs` row is still there, and a backup exported afterwards by the real export script carries it (one stored document in the backup, as before the delete). The original validation probe for this defect (`test_D1_document_delete_lifecycle`, `docs/eval/reliability_2026-10-01`) fails the same way on `HEAD` ("deleted document's plaintext file remains on disk") and passes now.
- **Promise:** a deleted document leaves nothing of itself that PIP made: not the
  file in the profile's documents folder, not its stored bytes, so not a later
  backup. Promise 7's wording stays true: it says uploaded documents are kept as
  files, and a deleted one is no longer kept.
- **Mechanism:** `vector_store.delete_document()`.
  - **The file, only if it is PIP's to remove.** It must resolve inside this
    profile's own documents folder, the rule ingest already applies
    (`_validate_file_path`). A registry row can name a file elsewhere: a backup
    restored into a second profile on the same machine records paths into the
    first profile's folder (D-07). That document is forgotten and the file is left
    alone.
  - **A file that cannot be removed stops the delete.** Held open on Windows, or
    read-only: the route answers 500 with a sentence ("The file budget.txt could
    not be removed (...), so the document was kept. Close anything that has it
    open, then delete it again."), the document stays registered, and deleting it
    again works. The other order says "removed" and leaves a readable file that
    nothing in the app can reach, because the document is no longer listed to be
    deleted again. A file that is already gone is nothing to do.
  - **The order:** the file, then the chunks, then the registry row and the
    `document_blobs` row in one commit. The index and the key are asked for before
    the file is touched, so a locked profile still fails before anything is removed.
  - **A name can be uploaded again.** The first upload's file used to stay, so a
    second upload of `budget.txt` was stored as `budget (1).txt`.
- **Tests:** 12 in `backend/tests/test_deleting_a_document_removes_its_copies.py`, through
  the real routes with a signed-in profile; what is asserted is what is left on
  disk and in the database, and what a fresh export of the encrypted profile
  holds.
  - **Seen failing first (9 of the 12, on `HEAD`):** the file left in the folder; the stored bytes left in the database; the deleted document still in a backup made afterwards; the bytes of a deleted document left beside another's (two tests, the second asked on the same connection); a registry row naming a file elsewhere keeping its stored bytes; a file that cannot be removed still answered 200; a document whose file was already gone keeping its stored bytes; and a name uploaded again being stored as `budget (1).txt`.
  - **What passes before and after:** that a path which is not a document touches nothing (the validation probe's D-2), that a sign-out landing in the middle of a delete removes nothing, and that a deleted document is not found a second time.
- **Break-it:** 7 mutations, one at a time on a clean copy, each caught:
  - the stored bytes no longer removed (8 of the 12 tests);
  - the file no longer removed (the file test, the cannot-be-removed test and the upload-again test);
  - no containment, so a file outside the profile's folder is removed too (the outside-the-folder test);
  - a file that cannot be removed ignored, and the delete carried on (the cannot-be-removed test);
  - the stored bytes of every document removed, not only this one's (the same-connection test, and only that one:
    a second connection stores the bytes of any active document again at start-up and hides it);
  - the document forgotten first and the file removed after the commit (the cannot-be-removed test);
  - the file removed before the index and the key are asked for (the sign-out-in-the-middle test).
- **Suites:** Backend 1594 passed, 0 failed (16 min 29 s), run with the embedding shim on a clean export of `001774c` plus this change, with nothing else running. The new file passed 8 runs in 8. The validation probe for this defect (`probe_boundaries.py` D1 and D2, copied into a scratch export) failed D1 on `HEAD` and passed both with the change. No client file changed, so the Flutter suite was not re-run.

**Not covered (still open):**
- **A file the person put in the documents folder by hand** and then ingested is
  removed with its document: PIP keeps no record of which files it wrote and
  which were placed there, and the ingest sentence tells people to place files
  there. The Documents screen only uploads copies.
- **The registry keeps a "removed" row** (path, content hash, date) for a deleted
  document. It holds no content.
- **Older copies are not scrubbed:** backups made before the delete, a file an
  older version left in the shared `data/documents` folder, free pages inside the
  encrypted database, and the index's own files until they are compacted (the
  chunk text in them is encrypted).
- **A failed delete reaches the person through the Documents screen's error line:**
  the Flutter client unwraps the route's `detail` sentence (`ApiException`) and
  prints it above the list. Read from the code, not looked at in a window.

### 7.51 G-6: the older web client does not grant consent, G-6 (authorized 2026-10-16)

The fifth of the blueprint's privacy and security cards.

- **Defect (A, low; the blueprint's planning note, now verified):** `frontend/web/`
  is the HTML/JS client PIP was proven with before Flutter, and the backend still
  serves it at `/`. Its Providers tab showed a "Grant consent" button on every
  cloud provider that was not consented to, and one click sent
  `consent_scope: "full_inference"`: the broadest of the four scopes, with no
  sentence saying what would leave the computer and no way to choose a narrower
  one. Promise 6 says nothing is preselected. The Flutter client stopped doing
  this (its own header comment says the button used to send full_inference for
  every provider, "in this client and in the web prototype before it") and asks
  for one scope, nothing preselected, each saying what actually leaves. The web
  client was never changed.
  - **Seen on `HEAD` from what the server serves,** the bytes a browser would
    run: `GET /app.js` returns a script that renders a `data-consent` "Grant consent" button for a cloud provider that is not consented to and, on a click, posts `{ consent_scope: "full_inference" }` to `/providers/<id>/consent`; neither the script nor the page says anywhere that consent is given elsewhere.
- **Promise:** consent is only granted where the person is told what it covers,
  and chooses a scope. Revoking, which only ever narrows what PIP may do, can be
  done from either client.
- **Mechanism:** `frontend/web/app.js` no longer renders the button or handles a
  click on it; in its place a cloud provider that is not consented to reads
  "Grant it in the PIP app". The Providers paragraph in `index.html` says the same
  in a sentence. The Revoke button stays.
- **Tests:** 3 in `backend/tests/test_web_client_consent.py`. The web client has no
  test harness, so they read what the server actually serves at `/app.js` and `/`
  (the same bytes a browser would run): that none of a consent call, a grant button or the name of the broadest scope is in it,
  that it says where consent is given, and that Revoke is still there. They pin
  that the call is not there; they are not a behaviour test of the page.
  - **Seen failing first (2 of the 3, on `HEAD`):** that the served script has no consent call, no grant button and not the name of the broadest scope (it had all three), and that it says where consent is given (it did not).
  - **Passing before and after:** that Revoke, the button and what handles it, is still there.
- **Break-it:** 4 mutations, one at a time on a clean copy, each caught:
  - the grant button put back with its handler (the no-consent-call test and the says-where test);
  - a grant still posted, only with a narrower scope (the no-consent-call test: it pins that there is no call, not
    which scope it carries);
  - the sentence saying where consent is given taken out of the tab and the paragraph (the says-where test);
  - the Revoke button taken away (the revoke control).
- **Suites:** Backend 1597 passed, 0 failed (17 min 30 s), run with the embedding shim on a clean export of `df220e1` plus this change, with nothing else running. The new file passed 8 runs in 8. The change is two web files that no other test reads, and no Flutter file changed, so the Flutter suite was not re-run.

**Found beside it, not fixed (D-30, A, low):** the command-line client has the
same shape in a typed command. `/consent PROVIDER_ID` in `frontend/cli/pip_cli.py`
sends `full_inference` when no `--scope` is typed (its usage line says "Default
scope: full_inference"), a default the person did not choose, which is what
Promise 6 rules out. It is not a click and the CLI is not shipped, so it is not
the card's case; not fixed, outside it.

**Not covered (still open):**
- **The server still accepts any valid scope for any known provider** from any
  caller that holds the API token (`POST /providers/<id>/consent`). Nothing on
  the server side asks that a scope was explained; the Flutter dialog is the only
  place that does. Added to Promise 6's limitations.
- **The page was not opened in a browser.** The tests read the served bytes; the
  new text is one `<span>` and one sentence.
- **A person who only has the web client** cannot now grant consent to a cloud
  provider from it. The PIP app is the deliverable; the web client is kept as a
  contract-proving reference (ARCHITECTURE).

### 7.52 P-1: a question about the user is not sent to the web, D-31 (authorized 2026-10-17)

The first card of the final plan's step 1 (BLUEPRINT P-1, issue #1 of
`notes/pip-issues-and-solutions-for-review-2026-10-17.md`).

- **Defect (D-31, A, low: only with web search consented, and then the first
  12 words):** Stage 1 checked the news words ("today", "current", "latest",
  "news", ...) before it asked whether a message was about the user or a
  project, and the pipeline's web guard skips Stage 6 only for the personal,
  project and continuation categories. So "what is my current project?",
  "what's the latest on my project?" and "what should I do today on my
  thesis?" were filed as `external_information`, and with web search consented
  their words went to the search provider. §7.5 noted it as a side observation,
  "not investigated". The guard's own test (`test_b1_honesty_fixes.py`) stubs
  Stage 1 and hands the pipeline a category, so the routing in front of the
  guard was never tested.
  - **Seen on `HEAD` (069f9bc)** through the real pipeline with the real
    Stage 1, web consent granted and Stage 6 replaced by a recorder: all 7 of
    the new test's questions about the user sent their words; 4 of the 14 §7.5
    phrasings sent one query each.
- **Promise:** 6. A question about the user's own work is not a web search,
  so it is not sent under the web-search consent.
- **Mechanism:** `stage_01_intent_classifier.run` asks "about a project?" (the
  existing project word, active project name and decision-overlap check) and
  "about the user?" (the existing first-person patterns) before it asks "news?".
  Only the news check moved: coding and research keep their place ahead of
  project and personal. The only messages whose category changes are those
  with a news word and one of those signals, from `external_information` to
  `project_question` or `personal_question` (neither is cached, and both look
  up more of the profile). No words added. A message that triggers Stage 6
  always carries a Stage 1 news word (Stage 6 matches the same words, whole),
  so web search still fires for `external_information` only, as before.
- **Tests:** `backend/tests/test_personal_questions_stay_off_the_web.py`, 12
  cases, both lists fixed before the fix was written: 7 questions about the
  user or a project that carry a whole-word web trigger (3 from §7.5, 4 in
  wording that appears in neither §7.5 nor Stage 1's lists) send 0 queries; 5
  plain news questions still send 1 each.
  - **Seen failing first:** 7 of 7 on `HEAD`. The 5 news controls passed
    before and after.
  - **One existing test changed:**
    `test_the_prompt_does_not_present_what_was_looked_up_as_the_whole_record`
    used "what is my current project?" as an `external_information` question,
    which does not look up goals. It is a `project_question` now, which does,
    so the test asks "what am I working on?" (`general_knowledge`, no goals)
    instead. Same assertions.
- **Break-it:** 2 mutations, each alone on the fixed file and restored by copy
  (`cmp` equal):
  - the personal branch disabled: 3 failed (the thesis, "do I", "I'm behind");
  - the project branch disabled: 1 failed ("any news on Heliotrope?"); the
    other project questions also say "my" or "I'm", fall to the personal branch
    and stay unsent.
- **The 14 §7.5 phrasings re-run** (seeded name and active project, web
  consent on): web queries sent 4 before, 1 after. Categories changed: "what is
  my current project?" and "what's the latest on my project?" to
  `project_question`, "what should I do today on my thesis?" to
  `personal_question`. Name and project reached the prompt in 14 of 14 before
  and after (Stage 4's always-looked-up tables, already in place).
- **Suites:** Backend 1610 passed, 0 failed (17 min 44 s), on the main
  checkout's working tree at 069f9bc plus this change, which also holds other
  sessions' uncommitted work (the `httpx2` requirement and its one test), with
  nothing else running; the three changed files were compared byte for byte
  with the copies taken before the run. No Flutter file changed, so the Flutter
  suite was not re-run.

**Not covered (still open):**
- **A question the existing checks do not recognise is still sent.** "what am I
  working on right now?" (one of the 14) has no "my", "I'm" or project word, so
  it is still news and, with web search consented, its words still go out.
  Catching it means adding words, which the owner's rule rules out; the plan's
  later web decider (#17) replaces this ordering, and when unsure it says no.
  Added to Promise 6's limitations.
- **The cost, accepted on purpose:** a real news question that says "my",
  names an active project, uses the word "program", or shares a word longer
  than three letters with one of the 20 newest decisions is no longer searched
  (for example "latest news on the space program"). Not measured on real use.
  A wrong "no" costs a missed web result; a wrong "yes" sends the user's own
  words out.
- **"what have I been working on recently?" is still `external_information`**
  (Stage 1 finds "recent" inside "recently"). It sends nothing, because Stage 6
  matches whole words only.

### 7.53 P-2: deleting a chat removes what PIP kept from it for later, D-32 (authorized 2026-10-17)

The second card of the final plan's step 1 (BLUEPRINT P-2, issue #2 of
`notes/pip-issues-and-solutions-for-review-2026-10-17.md`).

- **Defect (D-32, A, medium):** deleting a chat removed its messages and
  nothing PIP had kept from it for later. Three ways it came back:
  - **The note.** The "where we left off" note (`session_snapshot`) is one row
    per profile with nothing saying which chat wrote it. A deleted chat's topic,
    decisions, open problems and next step kept reaching every new chat's first
    prompt until another chat ended and overwrote it. Seen on `HEAD` (7e358af)
    through the real `DELETE /api/v1/conversations/{id}` route and the real
    pipeline: the deleted chat's topic was in the next chat's prompt.
  - **The app's own delete order** (found while writing the card, not in it):
    `chat_view.dart` `_delete` deletes the open chat first and then leaves it,
    and leaving ends the chat connection, whose disconnect trigger ran the
    session-end Observer pass on that chat's turns. So deleting the chat you
    are in ran the pass on a chat that no longer existed: it learned from it
    and wrote its note straight back. Seen on `HEAD` with the pass replaced by
    a recorder: it was handed the deleted chat's transcript.
  - **The queue.** A chat open when the server stopped, or left by a killed
    process, waits in `pending_observer` as a transcript with nothing naming
    the chat. Deleting the chat before the next start left it there: the
    catch-up learned from it, and the transcript stayed in the table (and so
    in every backup) after the chat was gone. Seen on `HEAD` for both ways in.
- **Promise:** 9 (answers reflect the current record). Deleting a chat means
  PIP does not keep using it.
- **Mechanism:**
  - `api_delete_conversation` removes the chat's queued transcripts
    (`pending_observer.discard_for_conversation`, any status), clears the note
    (`session_snapshot.clear_snapshot`), then deletes the chat. It checks the
    chat exists first, so an unknown id still answers 404 and touches nothing.
  - `pending_observer` has a new nullable column `conversation_id`, added to an
    existing database by `apply_column_migrations` with no backfill. The
    shutdown path (`enqueue_for_shutdown`, from the id `ws_chat` now keeps in
    `session_state`) and crash recovery (`recover_unobserved_conversations`)
    fill it.
  - `run_observer_now` (the idle and disconnect triggers) does not run the pass
    for a chat that no longer exists, and if the chat was deleted while the
    pass ran it clears the note the pass wrote.
- **Tests:** `backend/tests/test_deleting_a_chat_forgets_it.py`, 8:
  - **Seen failing first (7 of 8 on `HEAD`):** the note through the real route
    (with a precondition that the note does reach the prompt before the
    delete); the pass not run on a deleted chat; no note after a delete during
    the pass; a shutdown-queued transcript not learned or kept after its chat is
    deleted, with a second chat's transcript still learned; the same for a
    crash-recovered transcript; `ws_chat` telling the shutdown path which chat
    it is; and the upgrade test, a queue row written by an older PIP (no
    column) kept and still drained after the migration (on `HEAD` it errors:
    the column it drops does not exist).
  - **Passing before and after:** a chat that still exists is observed as
    before (the control for the new check).
- **Break-it:** 6 mutations, each alone, restored byte for byte, each caught:
  the delete keeping the note (1 test); the delete keeping the queued
  transcripts (2); the pass running on a deleted chat (1); the note kept when
  the chat is deleted mid-pass (1); `ws_chat` not giving the chat's id to the
  shutdown path (1); the shutdown queue not linked to its chat (1).
- **Suites:** Backend 1618 passed, 0 failed (17 min 43 s): P-1's 1610 plus
  these 8, on the main checkout's working tree at 7e358af plus this change
  (which also held other sessions' uncommitted `httpx2` requirement and its
  test), with nothing else running; the six changed code and test files were
  compared byte for byte with copies taken before the run. The neighbouring
  files (session lifecycle, queue, API server, chat socket, profile store,
  record-version coverage, Observer authorization) passed 182 of 182 first. No
  Flutter file changed, so the Flutter suite was not re-run.

**Not covered (still open):**
- **The note is cleared whichever chat wrote it.** Deleting any chat also
  clears a note another chat wrote; the next chat to end writes a fresh one.
  The note cannot say which chat it came from; one record per chat (#13) is
  the real fix.
- **What a pass learned before the delete stays.** Memories, decisions and
  candidates the Observer took from a chat (at its end, or during a pass the
  delete raced) are not taken back by deleting the chat. Only the note is.
- **A catch-up already reading the deleted chat's queued transcript** at the
  next start is not stopped; it can finish and write its note. Rare (the delete
  has to land during the catch-up of that very chat), and not closed.
- **Rows queued before this change** have no `conversation_id` and cannot be
  traced to a chat; a deleted chat's old queued transcript stays and is
  drained as before. And `pending_observer` keeps every processed transcript
  (`completed`, `failed`) indefinitely, for chats that were not deleted too;
  that retention is unchanged.

### 7.54 S-1: every evaluation result carries a run stamp (authorized 2026-10-17)

The first card of the final plan's step 2, the validity baseline (BLUEPRINT
S-1). Needed by every run in V-2: a number is only comparable with another if
both came from the same system.

- **Gap:** of the five evaluation scripts, one stamped its results, and only
  with `--save-raw`: `eval_observer_end_to_end.py` recorded the model's digest
  and the commit in its raw recording, but not in its report or its `--json`
  result. `eval_retrieval_e2e.py` and `eval_retrieval_levers.py` recorded the
  model tag (and the levers run its pinned num_ctx); `eval_retrieval.py` the
  embedder; `eval_evidence_gate.py` nothing. None recorded Ollama's version
  (it updated itself once during this project), the model's digest (a tag is
  mutable: a re-pull can point `qwen2.5:7b` at other weights), whether the
  working tree had uncommitted edits, or which Constitution was in force (its
  version has not been bumped across rule changes, BLUEPRINT G-5).
- **Mechanism:** `scripts/_stamp.py`, standard library only (so the evidence
  gate's script still runs under any interpreter), and it only reads: Ollama
  over HTTP (`/api/version`, `/api/tags`, `/api/show`), never the ollama CLI,
  which starts the app and can install an update.
  - `run_stamp(model, options_sent=...)`, called by every evaluation at the
    start of a run, before any number exists: date; git commit, a dirty flag
    for tracked files and the changed paths; the Constitution's version and
    the sha256 of its text with LF line endings; and, for a run that calls a
    model, Ollama's version, the model's tag, digest and own default
    parameters, and the options the harness sends (a key recorded as null was
    not sent, so Ollama's or the model's default applied: PIP sends no
    temperature and no num_ctx). A model run whose digest or Ollama version
    cannot be read refuses to start (`StampError`).
  - `resumable_state(path, initial, stamp)` for the two retrieval harnesses
    that save after every answer and can be resumed: one stamp per start, so a
    file holding answers from two starts says so.
  - `markdown(stamp or stamps)` for the top of every report; a result from
    before stamps existed says "none recorded".
- **Per script:** the evidence gate prints the stamp before its report; the
  observer harness stamps every run (a replay records the recording's stamp
  under `replayed_from` and no model), and writes it into `--json` (now
  `{"stamp", "runs"}`), `--out` and `--save-raw`; `eval_retrieval.py` puts it
  in its results and its report; the end-to-end and levers harnesses keep
  `stamps` in their state file and print them in the scored report.
- **Tests:** `backend/tests/test_run_stamp.py`, 23: 12 on the helper against
  a stub Ollama, a throwaway git repository and the real Constitution; 11 on
  the scripts. Seen failing first: 10 of the 11 script tests on the unchanged
  scripts (no stamp in the evidence gate's output, the observer's `--json` a
  bare list, `KeyError: 'stamp'` in the retrieval results, no `_stamp` call in
  any of the five); the 11th only checks there are scripts to check. The
  helper's 12 were written with it and not seen failing beyond its absence. `test_observer_replay.py`: 5 tests changed, for the `--json`
  shape and because their fake Ollama now also has to answer `/api/version`;
  same assertions, plus the context window is now checked as `num_ctx` not
  sent.
- **Break-it:** 8 mutations, each alone, restored byte for byte, each caught: a
  model with no digest stamped anyway (3 tests); a server with no version
  stamped anyway (1); the dirty flag ignoring edits (1); the Constitution hash
  keeping line endings (1); the evidence gate's report without the stamp (2);
  the observer's `--json` without it (3); the retrieval results without it (1);
  the end-to-end state built without it (1).
- **Suites:** Backend 1641 passed, 0 failed (18 min 0 s): P-2's 1618 plus
  these 23, on the main checkout's working tree at d5f9b88 plus this change
  (which also held other sessions' uncommitted `httpx2` requirement and its
  test), with nothing else running; the eight changed script and test files
  were compared byte for byte with copies taken before the run. No Flutter file
  changed, so the Flutter suite was not re-run.

**Not covered (still open):**
- **The two model-calling retrieval harnesses were not run.** Their generate
  step needs a running Ollama and minutes per question, so the tests pin that
  they call `run_stamp`, build their state with `resumable_state` and print the
  stamps (by reading their code), not that a real run's file holds a stamp. No
  live stamp against the real Ollama was taken either: it was not running, and
  starting it is the owner's call (V-2 asks first).
- **What Ollama does with an option that is not sent is not recorded**: the
  server's default context window depends on its version and settings, which
  the stamp records only as "not sent". V-2's window probe measures it.
- **Result files from before this card** carry no stamp; they stay as they are.

### 7.55 V-2: the validity baseline - the trust numbers on a new Ollama, a second model and long chats (run 2026-10-17/18, report only)

The final plan's step 2 (BLUEPRINT V-2, issue #22): every headline learning and trust number (39 of 39
true, 0 of 75 traps, 37 of 69 learned) came from 37 chats of 12-60 words, one model, Ollama 0.32.14. No
code in `backend/` changed. Rules: `docs/eval/v2_2026-10-17/PROTOCOL.md`, committed before each run
(1ca8dd4 for b, c, d; 4744eda for a). Every run from a clean worktree of the rules' commit, Ollama 0.40.3
started as `ollama serve`, nothing else running; every result carries the S-1 stamp. Results:
`RESULTS_b_c_d.md` and `RESULTS_a.md` in that folder. A first attempt at b and c was killed when the
machine slept and kept nothing; the reported runs are the rerun with the machine held awake.

- **(b) qwen2.5:7b on Ollama 0.40.3: HOLDS.** Today's code on the 2026-10-12 recording reproduces 39/39,
  0/75, 37/69 exactly. A new 3-run recording (same digest, same Observer prompt hash; the first outputs
  today's gate, tuned on the old recording by A-1, had not seen): traps 0 of 75 (at most about 4%), no
  learned row TRAP, 36 of 36 true, 35 of 69 stated facts learned. Its replay reproduces it, 111 of 111
  cases, timestamps aside.
- **(c) llama3.1:8b: SUPPORTED** - worded as fixed in advance, "the guard's accept and reject rules hold on a
  second model's phrasings". Traps 0 of 75, no TRAP row, 33 of 69 learned (bar: at least 17, half of
  qwen's), 0 of 111 errored, from 174 proposed candidates against qwen's 110. Not a paired comparison.
- **(d) the window as shipped:** with no `num_ctx` sent, Ollama gives qwen 4096 tokens on this GPU (its own
  log: "vram-based default context ... 4096") and cuts a longer prompt from the FRONT to about half the
  window: 2,050 of 10,639 tokens read, the first line lost. With 16384 the whole prompt is read, for about
  0.7 GB more GPU memory (4.75 against 5.47 GB). Tokens per word: 1.41 prose, 1.86 the Observer's
  instructions, which come first in its prompt.
- **(a) long chats: TRUST DOES NOT CARRY OVER, by the rule.** 27 made-up chats of about 1,400, 2,700 and
  4,800 words, each with the same three true facts, three trick statements and three near-misses (a fact's
  sentence shape, someone else's entity), rotated over start, middle and end, on profiles 1, 3 and 9 weeks
  old. 0 errored.
  - 1 of 162 trick statements and near-misses reached a belief table: "My friend wants to pass the Azure
    Fundamentals exam by March", in the longest chat on a week-1 profile, passed the evidence gate as the
    user's `topic_interests` and was queued as a question to the user (the Constitution required
    confirmation), not written. The harness counts a queued row, as it did for 0 of 75. **D-33.**
    Trick statements proper: 0 of 81.
  - 0 of 81 true facts learned in the tables their labels name, at every length, position and age. The
    model did propose them (Excalidraw 12 times, Lanternfish 13, the exam goal 10), mostly correctly; the
    evidence gate rejected most as having no "support language" (F1 11 of 12, F2 11 of 13). The same
    candidates get the same verdicts with or without the chat around them: the cause is wording ("I do all
    my diagrams in Excalidraw", "my main project this term is Lanternfish"), not length. 4 true facts were
    written to tables their labels do not name (the exam goal as two topics and a preference, Lanternfish
    as a preference); 3 more passed the gate and were discarded on week-3 and week-9 profiles, by design.
  - The window: the 1,400- and 2,700-word chats were read whole (2,572 and 4,058 tokens; the second 38 under
    the window, so it overflows while the model writes); the 4,800-word chat was cut to 2,050 of 6,506
    tokens (32%), the Observer's instructions lost, and the model still answered in the required JSON.
    The Observer took 10-30 s per chat (load apart).
- **Beside the rules, on every model and set:** the decision path (issue #3; decisions skip the gate) logged
  remarks from trick-statement chats as decisions (2 on qwen, 6 on llama in the short set: "I'll pass",
  "will not use Emacs", the Elixir hypothetical), a tentative "not convinced we should move to Java" 2 and 3
  times, and on long chats the assistant's study advice as the user's decision. On llama, "my sister loves
  Java" once left `java` in `topic_interests`, a table that chat's labels do not name.

**What it means for the thesis numbers:** 0 of 75 and 36-39 of 36-39 true hold on the current Ollama, on
fresh samples and on a second model, for short chats. On long chats a third person's goal got through the
gate once (D-33), and recall measured by the labels fell from about half to 0 of 81, because the gate's
support language is the A-1 list tuned on the short set and does not cover ordinary phrasings (the baseline
#19 is measured against). Nothing was tuned on these sets.

**Found beside it, not fixed (D-33, A, medium):** the evidence gate passes a third person's statement as
the user's own `topic_interests` ("My friend wants to pass the Azure Fundamentals exam by March" is
EVIDENCE_SUFFICIENT run through `adjudicate` alone, outside any chat). The short set's third-party traps
(a sister, a manager, a professor) were stopped; this wording and this table were not. The Constitution's
confirmation step stopped the write; the user would have been asked. No code change in V-2; fixed in §7.61.

**Not covered (still open):**
- One run per long chat, one model on the long set; the long set's planted wordings are the author's, so
  0 of 81 is a statement about these wordings, not about all phrasing.
- What Ollama drops when the output overflows the window (the 2,700-word chat) is not visible in its counts.
- `pip-work/v2-runs` (a detached worktree at 4744eda) was left in place for later runs.

### 7.56 W-1: one settings block - a 16k window, qwen2.5:7b, temperature 0.0 (authorized 2026-10-16, built and measured 2026-10-18)

The final plan's step 3 (BLUEPRINT W-1; issues #4, #6 and the 16k half of #5).

- **Defect (from V-2, §7.55):** `OllamaProvider.chat` sent only `num_predict`, so chat and the Observer ran in
  Ollama's default window, 4096 tokens on this 8 GB GPU, and a longer prompt was cut silently from the front:
  on a 4,800-word chat the Observer's instructions were never read. PIP budgets in words (1.41 tokens a word
  of prose, 1.86 of the Observer's instructions). The default model was llama3.1:8b in
  `pipeline.DEFAULT_MODEL_NAME` and in `OllamaProvider`, and `settings.json` named an `observer.model` nothing
  read, while every measured number is on qwen2.5:7b (DEC-17).
- **Mechanism (b3f1eb2):** `settings.json` `llm`: `default_model` qwen2.5:7b, `num_ctx` 16384, `temperature`,
  `tokens_per_word` 2.0 (above every measured ratio). `pipeline.DEFAULT_MODEL_NAME` and `OllamaProvider`'s
  default read it; `observer.model` is gone. Every request, chat and Observer alike, sends the same `num_ctx`.
  The Observer's transcript cap follows from the window, 6,576 words (it was 8,000 checked against nothing).
  Before sending, the provider estimates the prompt at the safe ratio and flags one that would not fit;
  after, it keeps Ollama's `prompt_eval_count`, and the Stage 9 and Observer trace lines record it with the
  window. The observer harness's stamp records the options really sent.
- **Tests:** `backend/tests/test_llm_settings_block.py`, 13, through a fake `/api/chat` server that records the
  request. 12 failed on 4744eda; the 13th, the chosen temperature, failed before the value was set. Three
  tests changed with reason (two pinned "no `num_ctx` is sent"; one used qwen2.5:7b as "another model being
  downloaded", now the default).
- **Break-it:** 7 mutations, each alone, restored byte for byte, each caught: no window sent (7 tests); a
  temperature sent before one is chosen (1); the pipeline default back to llama3.1:8b (2); the Observer cap
  ignoring the window (1); the fit flag never set (1); the Observer trace without the window (1); an unsafe
  tokens-per-word ratio (1).
- **Measurement** (`docs/eval/w1_2026-10-18/`, rules committed with the code before any run; clean worktree,
  Ollama 0.40.3 as `ollama serve`, desktop and Brave open):
  - **Run 1, the window, on V-2's 27 long chats: NOT MET by the rule.** Bar 1, every prompt read in full: met,
    27 of 27 (the 4,800-word chat 6,506 of 6,506 tokens; V-2 read 2,050). Bar 3, observed on the GPU: met,
    `size_vram` equal to `size` (5.47 GB) in all 39 polls with the model loaded, `nvidia-smi` 6,569-6,768 of
    8,188 MiB in use. Bar 2, not worse than V-2: facts by position 2 of 81 against 0 (met), but trick
    statements and near-misses 2 of 162 against 1, and 2 TRAP rows against 1 (**not met**). Both hits are
    near-misses in the 1,400-word chats, whose prompts were read whole in V-2 as well; in both the evidence
    gate rejected the memory, and the near-miss reached the decision log through the Observer's decision path,
    which skips the gate (issue #3, G-4): a friend's exam goal and advice about a cousin's project, logged as
    the user's decisions. The model sampled differently on the same input (one run per chat); the window did
    not change what those chats were given.
  - **Run 2, the temperature, on the 37 short chats x 3:** not sent (V-2): 0 of 75 traps, 35 of 69 learned;
    0.3: 0 of 75, 36 of 69; 0.0: 0 of 75, 36 of 69. A tie by the rule (within 3), which goes to the lower
    temperature: **0.0**, set in `settings.json` and pinned by a test. At 0.0 the three runs were identical,
    output for output, so they are one draw.
- **Suites:** Backend 1658 passed, 0 failed, on b3f1eb2's tree; 1659 passed, 0 failed, with the temperature
  set (the pinning test added). No Flutter file changed.

**Not covered (still open):**
- **W-1's bar 2 is not met**, by the decision path (G-4, step 4). Re-measure the long set after G-4 lands.
- **Chat at temperature 0.0 was not measured** for answer quality; the rule was the Observer's. Greedy
  sampling can repeat itself on long answers.
- **Machines other than this one:** 16384 fits an 8 GB RTX 4060 with 1.4 GB to spare; a smaller GPU or a
  CPU-only machine was not tried (E-4).
- One run per long chat; the near-miss count moves between runs (1, then 2 of 162).

### 7.57 C-14: a learned decision keeps its chat's project and its chat, D-34 (authorized 2026-10-18)

The first card of the final plan's step 4 (BLUEPRINT C-14, issue #14; its card was written when reached).

- **Defect (D-34, A, medium):** the Observer was called without the chat's project: the idle and disconnect
  triggers passed only the chat's id, and the startup queue and crash recovery passed neither, so
  `route_observer_decision` logged every learned decision with `project_id` NULL. A decision queued to ask the
  user (`decision_candidates_pending`) had no project column, so promoting it wrote NULL too. Stage 3 searches a
  project chat's decisions with `project_id = ?`, so a project never found a decision learned in its own chats.
  Nothing recorded which chat a decision came from, which one record per chat (#13) needs.
  - **Seen on `HEAD` (0ae28db)** through the real Observer path (Stage 11 to `decision_log`) with a provider
    answering in the model's shape: a decision learned at the end of a chat in project Lanternfish was not in
    the prompt of the next Lanternfish chat ("what did we decide about the database").
- **Promise:** 9 (answers reflect the current record).
- **Mechanism:** one source for "the chat's project": the chat's `conversations` row, created with the project the
  app sends (`conversation_store.project_of`). `run_observer_now` reads it from the chat's id when no project is
  given, which is what the triggers pass; the startup queue's drain now hands its runner the row's chat id (opt-in,
  `with_conversation_id`, so other runners are unchanged), and the runner reads the project the same way; crash
  recovery queues the chat id (P-2), so it follows. `run_session_end` and `route_observer_decision` carry
  `project_id` and `conversation_id`; a logged decision stores both (`decision_log.conversation_id`, new); a
  queued one stores both (`decision_candidates_pending.project_id`, `.conversation_id`, new) and promotion keeps
  them. The three columns are nullable and added to an existing database with no backfill: an old row cannot
  say where it came from and keeps behaving as before (no project, no chat). The schema comments sit outside the
  table bodies: SQLite rewrites that text when a column is dropped, and a comment beside the dropped column
  broke the rewrite (found by the upgrade test's own setup).
- **Tests:** `backend/tests/test_learned_decisions_keep_their_project.py`, 7: the end of a project chat logs its
  project and chat; the next chat in that project is shown the decision; a chat with no project logs none; a
  queued decision keeps both when promoted; the same through the shutdown queue and through crash recovery; an
  upgraded database keeps and promotes an old queued row as before.
  - **Seen failing first (7 of 7 on `HEAD`):** six on the missing chat column (nothing recorded the chat at
    all), and the one that shows the project bug as a user meets it: the next chat in the project was not shown
    the decision.
  - **One existing test file changed:** P-2's stand-ins for the Observer now accept the `conversation_id` it is
    passed.
- **Break-it:** 5 mutations, one per path, each alone, restored byte for byte, each caught: the end of a chat not
  looking up the project (3 tests); a logged decision without its chat (4); a queued decision without its
  project (1); promotion dropping the project (1); the startup queue without the chat id (2).
- **Suites:** Backend 1666 passed, 0 failed (17 min 59 s), on the main checkout's working tree at 0ae28db plus
  this change (with other sessions' uncommitted `httpx2` requirement and its test), nothing else running; the
  changed files were compared byte for byte with copies taken before the run. No Flutter file changed.

**Not covered (still open):**
- **Memory candidates** (preferences, skills) are not per project and were not changed.
- **A deleted chat's decisions** keep its id, pointing at nothing; what they should do is #13's question.
- **A chat moved to another project afterwards:** the decision keeps the project the chat had when the Observer
  ran.

### 7.58 G-5: the Constitution's version is bumped and checked at sign-in, D-35 (authorized 2026-10-18, DEC-6)

The second card of the final plan's step 4 (BLUEPRINT G-5). Owner decision DEC-6, 2026-10-18: on a mismatch,
warn loudly and keep running.

- **Defect (D-35, A, low):** `backend/core/constitutional.json` declares "version 1.0, locked before Observer
  build" and was edited twice after that with no bump: gated fields became table-and-field patterns
  (2026-07-04, 1fcdc42) and `session_continuity` left `observer_may_write` (2026-08-16, 9ace30e). Its own
  `amendment_process` says "on_startup: check profile.constitution_version vs current"; nothing did, and every
  profile stored the literal "1.0" from `complete_onboarding`, whatever rules were in force. So "which rules
  decided this?" had no answer, and an edit to the rules could go unnoticed.
- **Promise:** 1 and 3 rest on the Constitution being the rules that were measured; the thesis's "auditable
  enforcement" needs to say which rules decided a record.
- **Mechanism:**
  - the rules are now version 1.1, with a changelog entry naming the two silent edits; no rule changed;
  - `backend/core/constitution_version.py` registers each released version with the sha256 of its LF-normalised
    text (`KNOWN_VERSIONS`; the same fingerprint the S-1 run stamp records). `check(conn)` reports an edit
    without a bump (the text does not match its version's fingerprint, or the version is not registered) and a
    profile that last ran other rules; `check_and_record(conn)` warns for each (log at WARNING, a
    `constitution` trace row) and then records the version now in force, so a change is reported once;
  - the sign-in catch-up runs it first, in its own try: DEC-6, nothing may stop PIP; `/status` reports
    `constitution` (version, the profile's, warnings), read-only; a new profile records the version it starts
    under instead of "1.0".
- **Tests:** `backend/tests/test_constitution_version.py`, 8: the rules in force are a registered version with
  this exact text and a changelog entry; the run stamp records the same fingerprint; an edit without a bump is
  reported; a profile that last ran 1.0 is warned once (log and trace), recorded, and then quiet; a new profile
  records the current version; an unreadable rules file is a warning, not a failed start; `/status` reports it;
  and signing in, through the app's own start-up catch-up, runs the check and records the version.
  - **Seen failing first:** the whole file on `HEAD` (320159f), where the check did not exist.
- **Break-it:** 5 mutations, each alone, restored byte for byte, each caught: an edit without a bump not compared
  (1 test); the new version never recorded (2); no trace row for the warning (2); onboarding back to the literal
  "1.0" (1); sign-in not running the check (1).
- **Suites:** Backend 1674 passed, 0 failed (18 min 14 s), on the working tree at 320159f plus this change (with
  other sessions' uncommitted `httpx2` requirement and its test), nothing else running; the changed files were
  compared byte for byte with copies taken before the run. No Flutter file changed.

**Not covered (still open):**
- **The app does not show the warning.** It is in the log, the trace and `/status`; the Flutter client reads
  none of them for this. Someone who never opens the trace will not see it.
- **Results from before S-1** cannot say which rules they ran under. Results from S-1 on carry the fingerprint:
  V-2's and W-1's runs recorded `3908bd8d...`, the text labelled 1.0 with both silent edits in it, which is the
  same set of rules as 1.1 (only the version and changelog changed).
- **A version is registered by hand:** forgetting to register a new version makes the next sign-in warn "not a
  registered version", which is the intended reminder.

### 7.59 G-7: the governance audit log, D-36 (authorized 2026-10-18, DEC-5 confirmed)

The third card of the final plan's step 4 (BLUEPRINT G-7, A-3; issue #20). Owner decision DEC-5, confirmed
2026-10-18: the thesis keeps the word "auditable". Built in the card's four parts, each test first.

- **Gap (D-36, A, medium for the thesis):** a candidate the guard refused left a `logger.info` line and nothing
  else; `trace_log` is diagnostic and purged after 90 days. Candidates had no id, Stage 13 returned a bare
  string, Stage 11's drops were log-only, a queued question kept no reason, and one Constitution reason
  (`threshold_violation_month_2_plus`) covered two different rules. So "an auditable enforcement mechanism" could
  not show, a month later, what the guard decided about a candidate or why.
- **Promise:** 1 says every write goes through governance; the thesis's "auditable enforcement" needs a lasting
  record of what governance decided, for the candidates it refused as much as for those it wrote.
- **Mechanism:**
  - **Part 1, the table:** `governance_audit_log` (candidate_id, candidate_hmac, session_no, stage, actor,
    outcome, reason_code, target_table, field_name, evidence_count, confidence, conversation_id, decided_at),
    with CHECKs on actor, outcome and stage (`stage` NULL for anything that is not a pipeline stage; a user action
    never has one), and BEFORE UPDATE / BEFORE DELETE triggers that abort. The HMAC salt is random, made once, in
    its own one-row table `governance_audit_salt` with the same triggers: not a column on `profile_meta` (A-3's
    sketch), because that row does not exist before onboarding and a pass can run before it; not derived from
    the database key, which a password change replaces. `candidate_id` columns on both pending tables (nullable,
    no backfill). `conversation_id` was added to A-3's design so a deleted chat's rows still name the chat
    (C-14 now carries it). One writer, `backend/memory/governance_audit.py`, which refuses an unknown reason,
    outcome or actor, and a user action with a stage.
  - **Part 2, every terminal outcome:** every candidate gets an id when Stage 11 sanitises it, carried into the
    pending row it may become. Stage 11 records its drops (malformed, label not allowed, skill level not a
    number, evidence not in the transcript, evidence only in already-observed turns), its per-candidate errors
    (only if Stage 13 had not already written the row), and each decision candidate (malformed, assistant echo,
    quote not in the transcript or only in earlier turns, logged, queued, duplicate, failed). Stage 13 records
    each of its outcomes (written, write failed, queued, already queued, rejected), crediting the stage whose
    verdict decided it: 11 for an evidence-gate rejection, 12 for a Constitution verdict, 13 for the write.
    `threshold_violation_month_2_plus` is now `..._evidence` and `..._confidence`.
  - **Part 3, the user's answers:** confirm, dismiss, "no" to a check-in question (which retires the stored
    value), promote a decision, dismiss a decision: one row each, actor `user`, no stage, after the action has
    taken effect, under the queued row's candidate id (so it joins the system's row: same id, same
    fingerprint, same chat) or `legacy:<table>:<rowid>` for a row queued before ids existed.
  - **Part 4, reading it back:** `summary()` (rows, per outcome, per reason, per actor) and `history(candidate_id)`
    (the system's decision, then the user's answer).
- **Tests:** `backend/tests/test_governance_audit_log.py`, 52, all through the real code (Stage 11 with a provider
  answering in the model's shape, Stage 13, the resolution functions, the real export script, the in-app restore,
  `session_key.change_password`):
  - part 1 (15): the tables exist; a row holds a fingerprint and no text; UPDATE and DELETE abort on both
    tables; the salt is made once; the fingerprint is stable per profile and differs between profiles; the
    writer refuses what the log does not define; the session is recorded (0 before onboarding); an old database
    gains the id columns; legacy ids are distinct per row;
  - part 2 (24): every ValidationResult status (8 cases) and every evidence-gate rejection state (6) through
    Stage 13, one row each with the right stage and reason; already queued; a write that fails twice; the month-2
    split; every Observer drop and decision route in one session; a queued and a duplicate decision; a candidate
    that raises; a resumed chat; only the writer inserts (no other module inserts, updates or deletes); every
    stored reason is known; a candidate that fails after its row was written gets no second row;
  - part 3 (6): confirm (joins the system's row and its chat), dismiss, retire, promote and dismiss a decision,
    legacy ids, a failed answer leaves no row;
  - part 4 (5): the reader's counts for a seeded session; one candidate's history; a deleted chat's rows stay and
    hold no text; a backup and restore keep every row, the four triggers and the salt (and a DELETE still
    aborts); a password change keeps the salt and the same fingerprint;
  - found while recording (2): a candidate Stage 13 saved whose audit row could not be written is not recorded
    as rejected (it was: Stage 13 raised after the write, and Stage 11's per-candidate isolation recorded
    `candidate_error`, a row saying the opposite of what happened; Stage 13 now logs a row it cannot write, like
    every other audit call); every reason the Constitution enforcer can give is in the known set, so a new one
    cannot cost its rows quietly.
  - **Seen failing first:** each part's tests against the code before that part (parts 1-3 all failing; part 4's
    two reader tests failing). The round-trip, password and no-second-row tests check behaviour already in place
    once parts 1 and 2 existed, so they passed when written; the last is held by a break-it below. Of the two
    found while recording, the first failed before its fix (the saved candidate had a `candidate_error` row);
    the second passed when written and is held by a break-it.
  - **Existing tests changed:** seven tests that send a rejection through Stage 13 (six in
    `test_stage_13_profile_update.py`, one in `test_half_wired_tables.py`, which the first full run caught) used
    made-up reasons ("threshold_violation", "below_threshold") that no code produces; they now use real
    Constitution reasons, since the writer accepts only real ones. A queued question with an unknown reason is
    still recorded (as `queued`, stage 13), so three pending tests with made-up reasons are unchanged. The schema
    test and the record-version coverage list name the two new tables (excluded from `RECORD_TABLES`: never read
    into a prompt).
- **Break-it:** 12 mutations, each alone, restored byte for byte, each caught: the UPDATE trigger removed (2
  tests); the salt made on every call (5); an unknown reason accepted (1); a Stage 13 rejection unrecorded (10);
  a grounding drop unrecorded (2); the error path ignoring an existing row (1); a queued row losing its id (5);
  a user's confirm unrecorded (1); every legacy row sharing one id (2); a decision's outcome unrecorded (3);
  Stage 13 raising when its row fails (1); a Constitution reason the log does not know (1).
- **Terminal branches, all writing:** `stage_11_observer.run` (memory: sanitise None, not grounded; decision:
  sanitise None, assistant echo, not grounded), `run_session_end` (the resumed-chat filter, the per-candidate
  except, every decision route), `stage_13_profile_update.run` (written, failed, pending new and already queued,
  rejected), `resolve_pending`, `dismiss_pending`, `decision_log.promote_pending`, `decision_log.dismiss_pending`.
  An unparseable model answer has no candidates and so no rows.
- **Migration harness:** no change needed. Its fixed list is of launcher scripts, and G-7 adds none; each
  installation is built from `git archive`, so the new module travels with `backend/`.
- **Suites:** Backend 1726 passed, 0 failed (18 min 3 s), on the working tree at 4e9adf7 plus this change (with
  other sessions' uncommitted `httpx2` requirement and its test), nothing else of mine running; the changed files
  were compared byte for byte with copies taken before the run. Two earlier full runs: the first (1723 passed, 1
  failed) found the seventh test with a made-up reason, the second was stopped to fix the Stage 13 false row above.
  No Flutter file changed.

**Not covered (still open):**
- **Thesis wording, stated:** append-only within the trust boundary, logged, not tamper-evident. Whoever holds
  the profile key can drop the triggers; a hash chain in the same database could be recomputed. The salt lives in
  the same database, so someone with the key could guess short values from their fingerprints; that person can
  already read the whole profile.
- **Not audited:** a decision made by hand (`/decide`, `create_decision`), and the creation of a check-in question
  by the verification loop (its answer is audited). Neither is an Observer candidate.
- **A failed audit write is logged, not raised** (Stage 13 outcomes, Stage 11 drops, decisions, user answers):
  the action stands, and an error must not cost the session's other candidates, record a saved candidate as
  rejected, or tell the user an answer failed when it did not. Such a candidate then has no row.
- **No view of the log in the app or the API**; it is read through `summary()` and `history()`.
- **Rows from before G-7 do not exist**: the log starts empty on every profile.

### 7.60 G-4: the Observer's decisions go through the evidence gate, and an immutable name is not a preference, D-37 (authorized 2026-10-17, DEC-7 = A; built 2026-10-18)

The fourth card of the final plan's step 4 (BLUEPRINT G-4; issue #3). Owner decision DEC-7 = A (2026-10-17): fix
the code, not the promise wording.

- **Defect (D-37, A, medium):** the two findings §7.13 left open on 2026-09-28.
  - **Decisions skipped the evidence gate** (finding 1). A decision candidate was checked for grounding only (its
    quote somewhere in the transcript, the assistant's turns included) and then logged or queued on the signals the
    model claimed for itself. §7.14 found four tentative remarks logged as decisions ("I'm not convinced" about
    Java twice, "probably not worth it" as "decided against rewriting in Elixir", "to stay with Go"); W-1's long
    chats (§7.56) logged a friend's exam goal and a line the assistant said, which is why W-1's bar 2 failed.
  - **An immutable field's name could be stored as a preference** (finding 2). The Constitution refused name,
    language_preference and timezone only when the candidate's own table already held a value, and
    preference_memory never does, so "I prefer French, please answer me in French from now on" wrote
    `preference_memory.language_preference = French`, and every prompt then carried two language preferences.
- **Promise:** 1 (every Observer write goes through governance) and 2 (the immutable fields).
- **Mechanism:**
  - **Decisions:** `run_session_end` asks the gate about each decision before `route_observer_decision`, under a
    new `decision_log` contract: commitment language (goal_memory's list, reused, so no new words), the user's own
    turn, not a question, a hypothetical or sarcasm, no meaning-changing omission, and a calibrator: the decision
    has to share a word with what the user committed to once the commitment phrase is taken out (so "User decided
    to rewrite the backend in Elixir" is not anchored to "I've decided to go to bed early tonight" by "decided").
    The plain anchor and the contradiction check are not used: the decision text is the model's sentence, and a
    decision to move away from something is stated in the words the contradiction check reads as one. A refused
    decision gets its G-7 row (stage 11, the gate's state as the reason). The gate can only remove a decision; one
    it passes is logged or queued on the same signals as before. A decision made by hand (`/decide`) is unchanged.
  - **The shadowing:** the Constitution's rule 1 refuses an immutable field's name as a `preference_memory` field
    whatever is stored, names compared by letters and digits only ("Time Zone" is timezone). Stage 4 leaves such a
    preference stored before G-4 out of the prompt; `get_profile` (the memory screen) still lists it, so the user
    can see it and delete it.
- **Tests:** `backend/tests/test_observer_decisions_through_the_gate.py`, 16, through the real session-end path
  with a stand-in model giving the recorded quotes and decision texts: the four §7.14 overstatements are neither
  logged nor queued, each leaving a stage-11 audit row; W-1's two near-misses (a friend's goal, the assistant's
  advice) are not logged; a decision text sharing only "decided" with its quote is not logged; three decisions the
  user stated (Postgres, the half marathon, "Good, I'll stay put") are still logged and a one-signal one still
  queued; the three immutable names and "Time Zone" are neither stored nor queued as preferences (the gate passed
  them; the Constitution refuses, stage 12, `immutable_field`); a shadow preference stored before G-4 is not in
  Stage 4's rows and is still in `get_profile`.
  - **Seen failing first:** 12 of 16 on 934cf04; the four "still logged or queued" checks passed there, as they
    must.
  - **Existing tests changed:** fixtures in three files whose decisions the gate now refuses, each now quoting a
    first-person statement, since those tests are about routing, the audit log and the project, not phrasing:
    `test_stage_11_observer.py` ("I'm going with FastAPI for the backend, what do you think?" and "I'll probably use
    Redis for caching, does that sound right?" are questions to the gate), `test_governance_audit_log.py` and
    `test_learned_decisions_keep_their_project.py` ("We decided to use Postgres...", see below).
- **Break-it:** 7 mutations, each alone, restored byte for byte, each caught: decisions skipping the gate (7 tests);
  a decision needing no commitment language (4); the decision anchored on the commitment phrase too (1); a refused
  decision leaving no audit row (4); the immutable rule in preferences only when a value is stored (4); field names
  compared exactly (1); a stored shadow preference reaching the prompt (1).
- **Gate evaluation:** `scripts/eval_evidence_gate.py` gives the same output on 934cf04 and with G-4, apart from the
  run stamp (0 false accepts on both sets; the one held-out false reject unchanged): the new contract is used only
  by decisions.
- **Replays (the card's "done when"), no model:** every recording replayed through 934cf04 and through G-4
  (`scripts/eval_observer_end_to_end.py --replay`): the 2026-10-12 recording (3 runs x 37 chats), V-2's qwen and
  llama recordings (3 x 37 each) and long chats (27), W-1's long (27) and short temperature-0.0 (3 x 37)
  recordings. The rule is the card's: no trap newly reaching a belief table, the 4 cases not logged, dropped true
  decisions counted.
  - **No row was added anywhere.** The only rows removed are decisions: of 197 that reached routing (74 logged,
    123 queued on 934cf04), the gate removed 154 (48 logged, 106 queued) and kept 43 (26 logged, 17 queued).
  - W-1's two TRAP rows (both decisions) are gone on W-1's own recording.
  - **Every removed decision read by hand, with its chat:** 124 right to remove (79 tentative, a question, a
    fragment or no decision at all; 24 the assistant's words; 17 a preference, which the memory path handles; 4
    someone else's). **Real decisions removed: 9 on a strict reading** (5 "Good, I'll stay put" and 1 Postgres
    decision whose quote carried the "User:" label, 1 AWS-exam goal the same, 2 AWS-exam goals whose quote ends in
    the question the user asked next); **30 on a lenient one**, adding the borderline calls §7.14's review counted
    as decisions (8 Excalidraw and 2 pytest habits, 4 "I'll pass" about learning Java, 3 the corrected beta
    deadline, 3 "Yes, next week" for a migration plan, 1 "I don't plan to" use Emacs). The harness's own keyword
    labels on the removed logged rows: 2 TRAP, 1 TRUE, 45 unlabelled.
- **W-1's run 1 again, with the model** (the card's last step; W-1's committed run-1 rule, unchanged; results in
  `docs/eval/g4_2026-10-18/`): the 27 long chats from a clean worktree at 69252d9, Ollama 0.40.3 started as
  `ollama serve`, qwen2.5:7b, num_ctx 16384, temperature 0.0. **All three bars met:** every prompt read in full
  (27 of 27); 0 of 162 tricks or near-misses reached a belief table and no learned row is TRAP (W-1: 2 and 2, bar
  2 not met), and true facts learned are 0 of 9 in every cell (V-2's baseline; W-1's own run had 2 of 81); the
  whole model on the GPU in all 42 loaded polls, 6,817-6,848 of 8,188 MiB in use with no browser open (W-1
  measured with Brave open). The same model answers through 934cf04 give 12 learned rows, 3 of them TRAP, and 3
  of 162: the difference is G-4's. The gate refused all 15 decisions that reached it: 9 an Excalidraw habit (true,
  not a decision; the memory gate refuses that wording too), 6 the assistant's answers about a friend's exam and
  a cousin's app.
- **Suites:** Backend 1742 passed, 0 failed (18 min 29 s), on the working tree at 934cf04 plus this change (with
  other sessions' uncommitted `httpx2` requirement and its test), nothing else of mine running; the changed files
  were compared byte for byte with copies taken before the run. No Flutter file changed.

**Not covered (still open):**
- **D-38, found here: the gate refuses a quote that carries its turn's "User:" label.** The ledger holds each turn
  without its role label, so "User: Good, I'll stay put." is not found though the user said exactly that: 7 of the
  9 strict losses. The same step judges memory candidates, so it costs them too. A false reject (the safe
  direction). Not fixed: outside the card.
- **Decision wording the commitment list does not hold is lost:** "we decided", "I'm going with", "let's go with".
  Widening the list would be a new word list, which the owner ruled out (2026-10-17); not done. Three test
  fixtures had used such wording.
- **A differently named shadow is not caught:** `preference_memory.language = French` (§7.13 saw "language" too)
  does not carry an immutable field's name; only the Constitution's own names are refused.
- **A decision made by hand** (`/decide`) does not pass through the gate, as the card says.

### 7.61 D-33: a statement about someone else is not the user's topic (authorized 2026-10-18)

The fifth item of the final plan's step 4 (BLUEPRINT card D-33, written 2026-10-18 at the owner's request), found by
V-2 (§7.55). No owner decision needed; the owner's rule applies: no new word lists, and tests in wording no list
was written for.

- **Defect (D-33, A, medium):** in V-2's longest chat, "My friend wants to pass the Azure Fundamentals exam by
  March" passed the evidence gate as the user's `topic_interests` (field "exam") and was queued as a question to
  the user. Every other table's support contract needs first-person language ("I prefer", "I'm learning"), and
  that is what stops "My sister is learning Rust"; `topic_interests` needs none ("a question is as good as an
  assertion for 'this came up'"), so a sentence about someone else passed as the user's own interest.
- **Promise:** 4 (stored memory is supported by the user's words: here, words about themselves).
- **Mechanism:** for a topic, the gate reads only what raises it as the USER's: the questions they asked (a quote
  cut short of its sentence's question mark counts as that question) and the statements they made in the first
  person. A statement about someone else is context. The one word read is the pronoun "I" (whose sentence it is,
  not what it means), so no list of phrasings is added; the sentence splitting is the gate's own, moved into
  `_sentence_pieces` and shared with `_declarative_text`, whose behaviour is unchanged. A refusal says why
  ("names 'exam' only in a statement about someone else, neither asked about nor said in the first person").
- **Tests:** `backend/tests/test_topic_raised_by_the_user.py`, 11: the recorded candidate and three third-person
  wordings no list holds ("My cousin is studying for the CKA exam", "Priya wants to learn Haskell before summer",
  "Our neighbour runs a Kubernetes cluster at home") are refused; still accepted: the corpus's two questions, a
  quote cut short of its question mark, two first-person statements in no list ("I'm curious about CRDTs lately",
  "I've been reading about vector clocks all week"), and the user's own question about a friend's plan; and the
  recorded candidate through the real session-end path is neither written nor queued, with a stage-11 audit row.
  - **Seen failing first:** 5 of 11 on 2aa731b (the four refusals and the session-end test); the six accepts
    passed there, as they must.
- **Break-it:** 5 mutations, each alone, restored byte for byte, each caught: a topic read from the whole quote
  again (5 tests); a first-person statement no longer raising a topic (2); a question no longer raising one (3); a
  quote cut short of its question mark read as a statement (1); the letter i anywhere counted as the pronoun (5).
- **Gate evaluation:** `scripts/eval_evidence_gate.py` gives the same output on 69252d9 (2aa731b's code) and with
  D-33, apart from the run stamp: 0 false accepts on both sets, the corpus's topic accepts unchanged.
- **Replays, no model:** all seven recordings (the six G-4 replayed, and G-4's own long-chat run) through 69252d9
  and through D-33. **No row was added anywhere; 2 learned rows were lost, both statements about someone else:**
  the V-2 near-miss itself (queued, TRAP) and "My sister is a nurse and she loves Java, she keeps telling me to
  learn it" written as the user's topic "Java" (llama; the short set's labels do not list topic_interests for
  that trap, so the harness had it unlabelled). Four more topic verdicts moved on candidates the Constitution
  discarded anyway: the same sister sentence again, and three of the user's own elliptical answers with no "I"
  ("A payments service.", "a scheduling app for sailing clubs", "our sync is broken"): the cost of the rule,
  nothing learned lost.
- **Suites:** Backend 1753 passed, 0 failed (18 min 28 s), on the working tree at 2aa731b plus this change (with
  other sessions' uncommitted `httpx2` requirement and its test), nothing else of mine running; the changed files
  were compared byte for byte with copies taken before the run. No Flutter file changed.

**Not covered (still open):**
- **An elliptical answer raises no topic:** "A payments service." in reply to "What are you working on?" carries no
  "I" and is not a question, so it is refused as a topic (3 such candidates in the replays, all discarded by the
  Constitution anyway). A false reject, the safe direction.
- **"We" is not read as the user:** "We're moving everything to Kubernetes" raises no topic.
- **A question about someone else's plans still raises its topic**, as the card says (the user asked it); with the
  gate's one-shared-word anchor, a multi-word topic can still be anchored by one word of that question.

### 7.62 #13: one checked record per chat, the "small PIP", D-39 (authorized 2026-10-18; built 2026-10-18 to 2026-10-20)

The sixth item of the final plan's step 4 (BLUEPRINT card #13, written first at the owner's request; PROTECTED,
the owner's own headline design). No owner decision needed. Built in the card's four parts, each test first.

- **Defect (D-39, A, medium):** "where we left off" was ONE row per profile (`session_snapshot`, `CHECK (id = 1)`),
  overwritten by every chat that passed the Observer's substance check and loaded into every project's prompt. So
  each chat's summary replaced the last; a chat in one project opened on another project's last chat; a chat
  opened before the previous chat's Observer pass had run got an older note, or none; deleting any chat had to
  clear the note whichever chat had written it (P-2, §7.53), because the row did not say; and the app had no screen
  for it, so the user could neither see what PIP would carry forward nor correct it.
- **Promise:** 9 (answers reflect the current record), and the owner's design: each chat a "small PIP" with its own
  record, tied to its project.
- **Mechanism:**
  - **Part 1, one record per chat:** `chat_records` (chat id, unique when present, cascading with its chat;
    project, set null with its project; topic, open problems, decisions, next step; date; source `observer`,
    `user` or `earlier_note`). `run_session_end` writes its chat's record with its project under the existing
    substance check; a later pass of the same chat replaces its own record only; a pass with no chat adds an
    unattributed one. On upgrade the single note moves into `chat_records` as `earlier_note` (moved in one commit,
    so never twice) and nothing writes `session_snapshot` again. In `RECORD_TABLES`. Deleting a chat deletes its
    record and no other (`delete_chat_record`, which replaces `clear_snapshot`), as does the deleted-during-the-pass
    path.
  - **Part 2, the right record:** the chat socket tells the pipeline which chat a message is in; the pipeline
    chooses once, before the cache, this chat's record, else its project's latest, else the newest; Stage 7
    prints which it is, its date and "written by PIP when that chat ended; it may be wrong" (or "corrected by the
    user"); the answer cache key names the chosen record (`context_key`), since two chats in one project can now
    be given different context.
  - **Part 3, not yet summarised:** a chat with no record of its own is also shown the end of the previous chat
    (the newest other chat with messages in the same project, else overall) after that chat's last Observer pass:
    up to 4 messages of up to 40 words, labelled "not yet summarised", after the record in the same budget; the
    cache key names the last message shown (messages do not move the record version).
  - **Part 4, read, correct, clear:** `GET`, `PUT` and `DELETE /api/v1/conversations/{id}/record`; the read carries
    what the chat produced (its learned decisions, `decision_log.conversation_id`, and its audit outcomes as
    counts, `governance_audit_log.conversation_id`). A correction is validated with a sentence (topic present and
    at most 300 characters; lists of at most 20 texts of at most 300), becomes `source = 'user'`, and the
    Observer's later passes leave it alone. The app: a "Where we left off" button in the open chat's footer opens
    a dialog with the record, who wrote it and when, the chat's decisions and outcomes, Edit (the backend's refusal
    shown, the form kept) and Clear (asked first).
- **Tests:** `backend/tests/test_chat_records.py`, 32 (part 1: 9, part 2: 8, part 3: 6, part 4: 9), through the real
  session-end path, pipeline and routes; one in `test_ws_chat.py` (the socket names the chat);
  `frontend/flutter/test/chat_record_dialog_test.dart`, 8.
  - **Seen failing first:** part 1, 7 of 9 (the two that keep today's behaviour passed, as they must); part 2, 6 of
    6; part 3, 3 of 5 (two controls passed); part 4, 9 of 9; the app, 7 of 7 (it could not build). Added after a
    break-it run found a gap, each held by the mutation that showed it: two in part 2 (a resumed chat beside a
    newer chat in its project; two chats in one project and the cache), one in part 3 (an empty chat must not hide
    the one before it, a fix made with it), one in the app (Cancel keeps the record); the socket test passed when
    written (its fix came first) and is held by its break-it.
  - **Existing tests changed:** `test_session_snapshot.py` (the singleton tests now pin per-chat records: a chat's
    second write replaces its own, two chats keep two, deleting one keeps the other, an honest False);
    `test_pipeline.py` (its seed writes a record); `test_deleting_a_chat_forgets_it.py` (its note is the deleted
    chat's own record, and the pass that outlives its chat isolates the write the missing chat refuses).
- **Break-it:** 31 mutations, each alone, restored byte for byte, each caught. Part 1 (7): a later pass keeping the
  chat's old record instead of replacing it; deleting one chat's record deleting all; the old note not carried over;
  copied instead of moved; records outside `RECORD_TABLES`; the Observer writing no chat id; no explicit delete and
  no cascade. Part 2 (6): the socket not naming the chat; no own record; no project record; the cache key not
  naming the record; the record unlabelled; Stage 7 given the newest record whatever the chat. Part 3 (6): the end
  not shown; already-summarised messages shown; the previous chat taken from any project; a chat with its own
  record shown another's end; the key not naming the end; an empty chat counted as the previous chat. Part 4 API
  (6): the Observer overwriting a correction; a correction still marked the model's; an empty topic accepted; no
  decisions linked; clearing keeping the record; a corrected record still called the model's guess. The app (6):
  PIP's record not called possibly wrong; a refusal closing the form; the lines sent unsplit; no footer button;
  clearing not waiting for the answer; Cancel still clearing.
- **Suites:** Backend 1786 passed, 0 failed (22 min 54 s, slower because the app's widget tests ran beside it for
  part of the time), on the working tree at 0c8fc7f plus this change (with other sessions' uncommitted `httpx2`
  requirement and its test); the changed backend files were compared byte for byte with copies taken before the run.
  A first run had stopped at 20% when the computer slept (exit 4, no test failed). Flutter 346 passed (338 + 8), the
  generated platform files unchanged.

**Not covered (still open):**
- **The newest record of all is still the last resort**, so a chat with no project, or in a project with no record
  yet, is shown the last chat's record from wherever it was; the prompt names it "your last chat" with its date.
- **Documents are not linked to the chat** that used them: nothing records which chat a document served.
- **The record is the model's summary**, labelled as such; the model can still lean on a wrong one until the user
  corrects or clears it. The app has no list of all records, only the open chat's.
- **The "not yet summarised" end is short** (4 messages of 40 words) and shares the record's 250-token budget, so a
  long record can push it out.
- **`session_snapshot` stays in the schema**, read only to carry an older database's or backup's note over.
- **Not checked in a real window** (V-1): the dialog is tested as widgets.

### 7.63 M-1(a): Promise 4 measured blind, does a quote the gate accepts support its claim? (run 2026-10-20, report only)

BLUEPRINT M-1 part (a), the last item of the final plan's step 4. Design note `docs/eval/m1a_2026-10-20/DESIGN.md`,
approved by the owner and committed before anything was built (b03f928); grader A by the owner's choice.

- **Method:** the V-2 recordings (qwen2.5:7b short 3 x 37, llama3.1:8b short 3 x 37, qwen long 27) replayed through
  the real Stage 11 path at b03f928 (`observer.run`, then `evidence_gate.adjudicate`, no model call). Kept: memory
  candidates whose quote is genuinely the user's (SUFFICIENT, NOT_ENTAILING, CONTRADICTORY); one item per recording
  + chat + claim + quote: 58 accepted, 166 rejected. Graded: all 58 accepted and 58 rejected drawn by seed 20261020,
  shuffled, the verdict, model and run hidden (`sheet.md`, built by `build_sheet.py`; every item matches a claim the
  harness itself produced). The key's SHA-256 was committed with the sheet before grading (6bd9400) and checked when
  scoring. One grader: a fresh Claude session that had never seen the verdicts, told to read only the sheet; it
  answered S / D / U with a reason for each D and U (`grades.txt`). Scored by `score.py` (`RESULTS.md`).
- **Result:**
  - **False accepts: 8 of 58 accepted quotes did not support their claim on the strict reading (14%; 95% interval
    7-25%), 7 of 58 on the lenient one. By the rule fixed in the design: Promise 4's wording DOES NOT HOLD** for the
    gate alone (0 = holds, 1-3 = mostly holds, 4 or more = does not hold).
  - The 8: five skills recorded at level 1.0 (expert) from "I've written Go professionally for four years" and
    alike (D-40); two topics "marathon" from "My friend says I should do a full marathon but that's crazy" (D-41);
    one project filed as a preference, "project_management" = "Lanternfish, a budgeting app..." (D-42, graded
    UNCLEAR: true, in the wrong table).
  - **What happened to them after the gate** (the same replays' Constitution and Stage 13 columns): 4 queued to ask
    the user (skill levels are a gated field), 3 discarded by the week-1-2 rule, 1 written (the misfiled project). So
    no item graded DOES NOT was stored without asking the user; the gate alone does not keep that promise, the
    Constitution behind it did here.
  - **False rejects: 20 of the 58 rejected quotes did support their claim (34%; 95% interval 24-47%)**, both
    readings: 7 "my main project this term is Lanternfish" (as a project, or the project named in a preference); 5
    short answers ("A payments service.", "Mostly backend services.", "a scheduling app for sailing clubs"); 3 a
    problem the user is working on, as a project or goal ("our sync is broken", "My build is slow"); 2 "Please
    answer me in French from now on" (as an answer style); and one each "I do all my diagrams in Excalidraw these
    days", "I deploy everything with Docker Compose" and "I don't write Kotlin at all" (as level 0). Applied to the 166
    rejected, roughly 40 to 78 supported quotes were refused: the V-2 0-of-81 finding, measured blind. Reported, not
    judged (the design).
- **Causes, read in the code (not fixed: a measurement card):**
  - **D-40 (A, low):** the skill calibrator lets an expertise phrase ("years", "professionally") support any level
    from 0.7 up, so 1.0 passes; nothing caps the level at what the words say. A skill level asks the user first.
  - **D-41 (A, low):** D-33's rule reads a sentence as the user's when it has the pronoun "I", and "My friend says I
    should do a full marathon" has one; reported speech defeats it. The Constitution discarded both here.
  - **D-42 (A, low):** "my main" is a preference marker (an elliptical habit, "my main editor"), so "my main
    project this term is Lanternfish" supports a preference about anything named in it, while the project contract
    rejects the same sentence (its markers say "my project", not "my main project").

**Not covered (still open):**
- One grader, and a model; the owner did not check a sample (option C was not chosen). The skill-level calls are
  the grader's reading of "roughly that level" (1.0 = more than four or six years said).
- One author's made-up chats, English, two models; decisions were not part of the sheet (they were read one by one
  in G-4, §7.60).
- The downstream column comes from the replays at 0c8fc7f, whose gate, Constitution and Stage 13 are those of
  b03f928.

### 7.64 #19: a fact that falls short of the count is asked about, and a correction reads as an update, D-43 (authorized 2026-10-20)

The last thesis item of the final plan (step 5; BLUEPRINT card #19, written first; MEMORY_BRAIN M-2). No owner
decision needed. The plan's third part, matching a repeat by meaning, is left out on purpose (the card).

- **Defect (D-43, A, medium):** after week 2 the Constitution needs the same fact in 2 chats (weeks 3-4), then 3 chats
  and confidence 0.7 (month 2+, about 4 chats for a stated fact), counted only when the exact wording comes back; in
  weeks 1-2 a fact the model labels "inferred" is dropped. A candidate the evidence gate had accepted - the user's
  own words, supporting the claim - was thrown away with a log line before any "ask the user" step, and a
  correction a month in ("I switched to Helix") was one sighting, lost the same way.
- **Promise:** 1 and 3 unchanged (nothing is written without the Constitution or the user's yes); the thesis's
  learning claim.
- **Mechanism:**
  - **Asked, not dropped:** Stage 13 turns a DISCARD whose reason is one of the four count reasons into one question
    (`origin = 'shortfall'`, `REQUIRES_CONFIRMATION`), never a write, for the tables holding beliefs about the user
    (preference, skill, goal, project, answer style; not topics, tools or document habits). Only the Observer's
    session-end pass asks (`ask_on_shortfall`), at most `observer.max_shortfall_questions_per_chat` (2) per chat;
    past the cap, and for every other caller, the candidate is dropped as before. The existing duplicate check
    applies; the contradiction log keeps its input; the audit row says deferred with the count reason; confirming
    writes the value as the user's (`resolve_pending`, unchanged).
  - **A correction reads as an update:** `list_pending` carries the value already stored for that table and field
    (`current_value`, from Stage 12's own lookup); confirming replaces it.
  - **The app words it:** Review asks "Should I remember this?" with "PIP would normally wait to hear this more than
    once before keeping it, so it is asking you instead", and for a correction "Update this?" with "Now: A" above
    the new value.
- **Tests:** `backend/tests/test_shortfall_questions.py`, 13, through the real session-end path at weeks 1, 3 and 9:
  a supported fact seen once is asked about in week 3, week 1 (labelled inferred) and month 2, and not written;
  confirming writes it as user-verified; at most 2 per chat, the cap per chat; the same fact in a second chat is not
  asked twice; a topic and a gate rejection are still dropped; Stage 13 on its own still drops; a correction carries
  the stored value, and confirming replaces it; nothing stored means no current value. `review_view_test.dart`, 2
  new (the shortfall reason, not the gated-field one; "Update this?" with "Now: Neovim").
  - **Seen failing first:** 10 of 13 backend (the topic, gate-rejection and Stage-13-alone controls passed, as they
    must); both app tests.
  - **Existing test changed:** `test_observer_long_chat_harness.py` pinned that a fact said once at nine weeks
    is learned not at all; it is still not written, and is now asked about (`["queued"]`). The first full run found
    it.
  - **A race in #13's socket test, found and fixed:** `test_the_pipeline_is_told_which_chat_each_message_belongs_to`
    (§7.62) read a fixed number of events, one short of the first turn's "done", so the second message could
    arrive while the first turn was still being sent and the test waited for a reply that never came; it hung the
    second full run. It now reads each turn to its end; 20 of 20 runs alone passed.
- **Break-it:** 11 mutations, each alone, restored byte for byte, each caught: a shortfall dropped again (10 tests);
  the Observer never asking (10); no cap (1; first written as a mutation that did not compile, re-run); the cap
  carried across chats (8); topics asked about (1); gate rejections asked about (1); the question filed as an
  ordinary observer question (4); the stored value not shown (1); the app giving the gated-field reason (1), not
  showing an update (1), showing an update with nothing stored (3).
- **Measured (the card's rule, fixed before the run), replays of the recordings, no model:**
  - **Short set (V-2 qwen, 3 x 37): stated facts learned or asked 35 of 69 -> 41 of 69 (met)**; all six added are
    questions labelled TRUE (Python and Go skill levels, Helix over Neovim), at most 1 per chat; written rows
    unchanged (20); traps 0 of 75 -> 0 of 75 (met).
  - **Long set (G-4's run, 27 chats): 0 of 81 -> 0 of 81, NOT met.** No true-fact candidate there reaches the count
    step: the gate refuses them first for its wording ("I do all my diagrams in Excalidraw", "my main project this
    term is Lanternfish"; M-1(a)'s false rejects, §7.63). Trick statements and near-misses 0 of 162 -> 0 of 162.
  - One added question asks about Go at level 1.0, the level M-1(a) graded too high (D-40): asked, not written.
- **Suites:** Backend 1799 passed, 0 failed (18 min 38 s), on the working tree at ccdbc25 plus this change (with
  other sessions' uncommitted `httpx2` requirement and its test); the changed backend files were compared byte for
  byte with copies taken before the run. Two earlier full runs: the first had 1 failure (the harness test above,
  updated), the second hung on #13's socket test (the race above, fixed). Flutter 348 passed (346 + 2), the
  generated platform files unchanged.

**Not covered (still open):**
- **The long chats' facts are still lost**, at the gate's wording, which #19 does not touch; fixing it needs either
  more support phrases (a word list, which the owner ruled out) or a way to judge support by meaning. A decision for
  the owner.
- **The same fact worded differently can be asked twice** (the duplicate check is exact); the plan's meaning-matching
  part is not built.
- **How often users confirm** these questions is not measured (no real users).
- **Two per chat** is a chosen number, not a measured one.

### 7.65 Step 6: a follow-up inside one chat keeps its thread (#7, #8, #9, #10, #12), D-44 (authorized 2026-10-20)

The first Product step below the cut line (BLUEPRINT card "Step 6", written first). No owner decision needed. Q-1
(#11, the greeting) has its own card and is not part of this.

- **Defect (D-44, A, medium):** five ways a follow-up inside one chat lost what it was about.
  - **#12:** the prompt never said what day it is, so "yesterday", "last week" or "by Friday" could not be placed.
  - **#8:** after a 10-minute break the idle Observer pass cleared the open chat's history, so the next message
    started from nothing.
  - **#9:** history trimming stopped at the first message, counting from the newest, that did not fit its
    1,000-token budget, so one long reply emptied the history, the last exchange included.
  - **#10:** the answer cache did not know the chat, so a follow-up ("why?") could be answered with another chat's
    saved answer for up to 24 h.
  - **#7:** decisions and documents were searched with Stage 1's hint, the first 12 words of the newest message
    only, so "and why?" found nothing it referred to.
- **Promise:** none weakened, and nothing new leaves the machine: the web query is still the first 12 words of the
  current message (DEC-14), and the date is the machine's own clock.
- **Mechanism:**
  - **#12:** Stage 7 adds "Today is Tuesday, 20 October 2026." (the machine's local date, `pipeline._today`) after
    the system instructions; the cache key names the date, so a cached answer is not replayed on another day.
  - **#8:** a successful idle pass keeps the history and marks what it read with the mark a resumed chat already
    uses (`observed_prefix`, the turns so far); the disconnect pass is shown those turns but counts only the later
    ones as new evidence. A failed idle pass marks nothing, so the next pass takes its turns again.
  - **#9:** `_trim_conversation_history` always keeps the last exchange: the question whole if it fits half the
    budget, the reply cut to what is left; older messages fill the rest, oldest dropped first. When the whole
    prompt is over its budget, the history is still trimmed oldest first in the priority order (unchanged).
  - **#10:** the cache is read and written only for a chat's first message (no history yet).
  - **#7:** Stages 3 and 5 search with the previous user message and the whole current one
    (`pipeline._search_text`); a first message is searched with its whole text, where it was the 12-word hint.
- **Tests:** `backend/tests/test_keep_the_thread.py`, 11, through the real pipeline with a stand-in model that
  records its prompt (Stage 7 alone for #9): the prompt names the day; a cached answer is not replayed the next day;
  a 4,000-word reply is kept shortened, the question whole; earlier messages go first; a history that fits is passed
  whole; a follow-up is neither answered from the cache nor saved to it; a first message still uses it; "and why?"
  finds the decision its previous message asked about; Stages 3 and 5 get the previous and the whole current
  message; the web query is still the first 12 words. `test_ws_chat.py`, 3 new for #8, through the chat socket with
  a short idle timeout and a stand-in Observer: the next message after the idle pass still sees the chat; the
  disconnect pass counts only the turns after it (`observed_prefix == 2`); after a failed idle pass it counts
  everything (`observed_prefix == 0`).
  - **Seen failing first:** 11 of 14; the three that check what must not change (a history that fits, a first
    message cached, the 12-word web query) passed, as they must.
  - **A test mistake, found and fixed:** the #8 tests first ran without the app's startup, so an earlier test's
    shutdown flag kept the disconnect pass off; they passed alone and failed in their file. They now start the app,
    as the other disconnect tests do (28 of 28 in the file).
  - **A design point, changed back:** the first version also kept the last exchange when the whole prompt was over
    budget; that would drop decisions, profile, documents or the chat's record before the history, against the
    priority order, so the overall trim is as it was.
- **Break-it:** 12 mutations, each alone, restored byte for byte, each caught by its test: no date line; the cache
  key without the date; a long reply dropped instead of shortened; older messages kept past the budget; a follow-up
  read from the cache; a follow-up saved to it; decisions searched with the hint; documents searched with the hint;
  the web query given the earlier message; the history cleared after the idle pass; the idle pass marking nothing
  read; a failed idle pass marking its turns read.
- **Suites:** Backend 1813 passed, 0 failed (20 min 19 s; 1799 + 14), on the working tree at 52f9e42 plus this change, with other sessions' uncommitted changes in it (the httpx2 requirement and its test; evidence_gate.py and two of its tests, changed by another session and found after the run); the changed files were compared byte for byte with copies taken before the run. Flutter 348 passed (no app change).
- **Not measured with a model:** the card asked for none (a cheap step).

**Not covered (still open):**
- **A whole prompt over its budget** (a long pasted message) can still lose the last exchange; the priority order
  decides there, on purpose.
- **Only the previous user message** joins the search: a follow-up about something two questions back is not
  helped.
- **Retrieval with the longer search text is not re-measured:** the §7.27 harness was not run. A first message is
  now searched with its whole text, not 12 words. (Corrected 2026-10-21: this said the PC blocks torch, the real
  embedder's library; that stopped on 2026-10-08, and torch 2.13.0 imports here.)
- **The time of day is not given,** and a machine with a wrong clock or time zone gives a wrong day.
- **Fewer cache hits:** a follow-up now always reaches the model; how often the cache served follow-ups was not
  measured.
- **The break was tested with a 0.05 s idle timeout** and a stand-in Observer, not a real 10-minute wait or a real
  model.

### 7.66 Q-1: a new user's greeting on qwen2.5:7b, 0 of 104 "no record" replies (run 2026-10-21, report only; no code change)

BLUEPRINT card Q-1 (#11), the owner's "when I type hi, PIP says I don't have a record; it feels dumb". The
2026-10-17 probe (`docs/eval/greeting_2026-10-17/`) found it on llama3.1:8b (3 of 30) and phi3:mini (12 of 30),
never on qwen2.5:7b (0 of 15 for a new user, too few to bound the rate).

- **Rule, fixed before the run:** `docs/eval/q1_greeting_2026-10-21/RULE.md` (sha256 9c049a47c4f6..., recorded in
  the results). At most 1 of N "no record" replies closes the card with no code change; 2 or more stops and reports.
- **Run:** commit 33dd522 in a clean worktree (stamp: no uncommitted tracked changes; Constitution 1.1; qwen2.5:7b
  digest 845dbda0ea48...; Ollama 0.40.3, started with `ollama serve` and stopped after). The real pipeline
  (`pipeline.run_sync`, the profile's active model through the real `OllamaProvider`: 16384-token window,
  temperature 0.0, 2000 tokens), on 4 made-up new users (onboarded with a name and English, nothing else) x 26
  greetings (the 3 used before, the card's 6, 17 more chosen for the run and in no list in the code) = 104, each
  the first message of its chat; the answer cache emptied per user; every path in a temporary folder, `data/`
  never opened. All 104 answered; every call was qwen2.5:7b.
- **Result: 0 of 104** (the 2026-10-17 pattern found none; reading all 104 by hand added none and removed none).
  **The bar is met: Q-1 closes with no code change.** Over these wordings and users the rate is below about 3%
  (95%, rule of three).
- **Report only:** the name was used in 103 of 104 (the miss: "hola", answered in Spanish though the profile says
  English); no reply invented a chat, a project or a fact; every prompt held "Projects: none recorded." and the
  date line, and qwen volunteered neither.
- **Found, D-45 (A, low, privacy):** "hey pip, how are you doing today?" is a web-search question: "today" is a
  Stage 6 trigger word and Stage 1 files the message as `external_information`, so Stage 8 was asked 4 times (once
  per user) and refused for lack of consent. With web search consented, the greeting's first 12 words would go to
  the search provider. Not fixed: the owner decides (the owner's rule rules out another word list).
- **Kept for the write-up:** llama3.1:8b and phi3:mini show the reply, qwen2.5:7b does not; model behaviour varies
  while the deterministic guard does not.

**Not covered:** the chat socket and the app window (the pipeline was run directly); other models; languages other
than English; real users.

### 7.67 Three gate fixes: a quote's "User:" label, the expert level, "my main", D-38, D-40, D-42 (authorized 2026-10-20; committed 2026-10-21)

The owner's list of "small gate bugs found this week" (2026-10-20, "start"; 2026-10-21, "finish the gate bugs: run
the suite and commit what left"). The owner's rule applies: no new word lists, tests in wording no list was written
for. The replays below found D-46; the owner chose to commit the three as they are and record D-46 as open.

- **Defects:**
  - **D-38 (A, low; §7.60):** the evidence ledger holds each turn without its "User:" header, so a quote the model
    copied with the header ("User: Good, I'll stay put.") was EVIDENCE_NOT_FOUND although the user said exactly
    that: 7 of G-4's 9 strict decision losses. Memory candidates go through the same step.
  - **D-40 (A, low; §7.63):** any expertise phrase ("years", "professionally", "i work mostly in") supported any
    level from 0.7 to 1.0, so five skills were accepted at 1.0 (expert) from "I've written Go professionally for
    four years" and alike, graded unsupported in M-1(a).
  - **D-42 (A, low; §7.63):** "my main" was a preference marker, so "my main project this term is Lanternfish, a
    budgeting app..." was accepted as preference "project_management" and written.
- **Promise:** 4 (a stored memory is supported by the user's words). D-38 is a false reject, D-40 and D-42 false
  accepts.
- **Mechanism** (`backend/core/evidence_gate.py`):
  - D-38: before every check, a quote that begins "User:" and is not found as written is looked up without the
    label (`_without_user_label`). Who said it is still the ledger's answer, from the turn the words are found in,
    so an assistant reply quoting "User: I always use Flask." (indented by `format_transcript`) stays the
    assistant's. A quote found with its label keeps it; an "Assistant:" label is never taken off (that could only
    turn a refusal into an accept).
  - D-40: a level above 0.9 (`_EXPERIENCE_CEILING`) needs the quote itself to say "I'm an expert" or "I am an
    expert" (`_EXPERT_MARKERS`: two phrases the skill list already held, not a new list). Experience language still
    supports up to 0.9 (the suite's own case: "ten years professionally" supports 0.9). The bare word "expert" is
    not used: "I'm not an expert" contains it.
  - D-42: "my main" is removed from the preference markers. It ranks a project, a worry or a complaint as readily
    as an editor ("my main complaint about Kubernetes" was a Kubernetes preference); narrowing it with "project"
    would be a word fix that leaves "my main focus". Removing an allowlist entry can only add false rejects.
- **Tests:** 16 new. `test_evidence_gate.py` (13): D-38, a decision cited "User: Good, I'll stay put." and a memory
  candidate with a lower-case label are accepted, the label cannot make an assistant line the user's
  (EVIDENCE_NOT_USER_SOURCE), and an "Assistant:" label stays (EVIDENCE_NOT_FOUND); D-40, M-1(a)'s three sentences
  and two in no list ("I've built Elixir services for a living for five years.", "I'm not an expert in Elixir, but
  I've built services in it for years.") are refused at 1.0, while 0.9 from the five-years sentence and 1.0 from
  "I'm an expert in Elixir; ..." and "Honestly I am an expert at Elixir, ..." are accepted; D-42, the recorded
  Lanternfish candidate and two in no list ("My main project right now is Tidewater, ...", "My main complaint about
  Kubernetes is all the YAML.") are refused. `test_observer_decisions_through_the_gate.py` (3): G-4's three stated
  decisions, quoted with the label, are logged through the real session-end path.
  - **Seen failing first:** 13 of 16 on 52f9e42 (every defect case); the guards and the accepts passed there, as
    they must.
- **Break-it:** 5 mutations, each alone, restored byte for byte, each caught: the label kept (5 tests), an
  "Assistant:" label also taken off (1), the ceiling at 1.0 (5), the bare word "expert" allowed (1), "my main" put
  back (3).
- **Gate evaluation:** `scripts/eval_evidence_gate.py --include-new` gives the same output on 35974b9 and with the
  fixes, apart from the run stamp: 0 false accepts on every set.
- **M-1(a)'s graded items, rebuilt from the key** (`docs/eval/gate_fixes_2026-10-21/`; the rebuilt verdicts on
  35974b9 agree with the recorded ones on all 116): 6 verdicts change, all accepted to refused, and they are 6 of the
  8 graded false accepts (the five 1.0 skills and Lanternfish). No item graded supported changes. The other 2 are
  D-41's, not touched. Not a new measurement: the fixes were written from these items, so §7.63's verdict stands.
- **Replays, no model** (the six recordings G-4 replayed and G-4's own long-chat run, through 35974b9 and with the
  fixes; `replays_changed.txt`):
  - D-38: 6 of G-4's 7 label-caused strict losses come back, the Postgres decision logged (llama) and "Good, I'll
    stay put." queued in 5 runs (qwen 2, W-1 short 3). The seventh, the AWS exam goal, is now found but ends in a
    question ("What is a sensible way to space out revision?"), which the gate refuses whatever the label (G-9's
    rule; G-4's listing had shortened the quote). The Postgres goal is queued too. Most other labelled quotes now
    fail entailment instead of being not found, with no outcome changed; a quote that runs into the next turn
    ("... Assistant: Spaced practice ...") is still not found.
  - D-40: 7 skills queued at 1.0 for the user to confirm (Go 5, Python 1, TypeScript 1, in llama and qwen) are now
    refused, so they are not learned at all. The gate gives a verdict and cannot lower a level. Facts learned 181 to
    175 of 519 (7 fewer, plus the Postgres goal).
  - D-42: the Lanternfish preference is no longer written (V-2 long, M size).
  - **A trap now reaches a belief table: 0 to 1 of the replayed traps.** V-2's long recording writes topic "Elixir"
    from T2, "If I ever had a free summer I might look at Elixir, but honestly that is not going to happen. What is
    it actually good at?", which the label had kept out; W-1's long recording passes it too, with two of the user's
    own questions, and the Constitution discards all three there. The same quote without the label is
    EVIDENCE_SUFFICIENT on 35974b9: D-46 below. Four of the user's own questions ("What do the Cache-Control and
    ETag headers actually do in HTTP?" and alike) are written as topics in V-2's chat.
  - Learned rows: written 94 to 99 (TRUE 71 to 72, unlabelled 23 to 26, TRAP 0 to 1); queued 120 to 115.
- **Suites:** Backend 1830 passed, 0 failed (19 min 43 s), in a clean worktree at 35974b9 plus the three changed
  files only; the committed files were compared byte for byte with the ones that ran. No Flutter file changed.

**Not covered (still open):**
- **D-46 (A, low): a hypothetical first-person sentence raises a topic.** D-33's rule takes any sentence with "I"
  as the user raising a topic, and topics skip the hypothetical check the other tables have, so "If I ever had a
  free summer I might look at Elixir" is the user's topic "Elixir". Found by these replays; before D-38 the model's
  label usually hid it, so G-4's 0 of 162 on the long chats (§7.60) partly rested on D-38. Not fixed: the owner's
  choice (2026-10-21).
- **D-41** (reported speech with "I") is not touched.
- **"My main project" is still not a project:** the project markers say "my project" and "my current project";
  adding "my main project" would widen a word list. 7 of M-1(a)'s 20 false rejects are that sentence.
- **The expert phrase is not tied to the skill:** "I'm an expert in Python and I've written Go for years" supports
  Go at 1.0. Skill levels are gated, so the user is asked before one is written.
- **"Neovim is my main editor" alone is no longer a preference** (a false reject). No recorded chat has a "my main"
  sentence other than Lanternfish's.
- **A decision's stored quote keeps the label** (`raw_quote` "User: Good, I'll stay put."); only the gate's
  comparison drops it.

### 7.68 #21 documents: a stated limitation of v1.0, not built (written 2026-10-21; no code change, no new run)

The final plan's step 7 (`notes/pip-issues-and-solutions-for-review-2026-10-17.md`, #21), below the cut line: build it
"or a written limitation (cause measured and identified, out of scope for v1.0)". The owner chose the limitation
(2026-10-21, "write the documents limitation next"). Every number below was measured before (§7.27, §7.28, §7.30);
one was re-read from committed results, as marked. Nothing in the pipeline changed.

- **What a user meets** (shipped: 500-word chunks with 50 overlap, cut-off 0.60, top 3, an 800-word documents
  budget): a question about an uploaded document is almost never answered from it. Seven technical documents, 54
  questions: the passage that answers came back for 2 (§7.27). End to end on qwen2.5:7b: 1 correct, 41 declined
  ("I don't have that in front of me"), 4 wrong, 8 vague, and none of 12 unanswerable questions got an invented
  answer (§7.28). The owner's own prose (a 2,993-word synopsis, kept out of git): 0 of 26 found, 1 correct answer
  (§7.30). So the feature fails mostly by declining, and 4 of 54 times by answering wrongly.
- **Causes, measured:**
  1. **Most of every chunk is never searched.** Chunks are 500 words; all-MiniLM-L6-v2 reads 256 tokens; a median
     chunk is 855 tokens, so 71% of chunk text is outside what is embedded. The right passage is in the top 3 for 12
     of 16 questions whose answer starts in the readable part and 13 of 38 when it starts beyond it (§7.27).
  2. **The cut-off sits above where answers score.** The passage that answers scores a median 0.38 on the technical
     notes and 0.26 on prose; 0.60 lets through 2 of 54 and 0 of 26, while ranking alone has the answer in the top 3
     for 25 of 54 (§7.27, §7.30).
  3. **The query: fixed, and it does not change the result.** Search used the first 12 words; since step 6
     (33dd522, §7.65, #7) it uses the whole message plus the previous one. Re-read on 2026-10-21 from the committed
     2026-10-08 results (`docs/eval/retrieval_results_2026-10-08_real.json`, the "full question" rows, which is what
     a first message is now searched with): the same 2 of 54 at 0.60, 25 of 54 in the top 3, a median answering
     score of 0.38. A follow-up's added previous message is not measured.
- **Why not just lower the cut-off:** measured twice and not supported. Technical notes, end to end: correct 1 / 11
  / 26 of 54 at 0.60 / 0.45 / 0.30, but wrong 4 / 7 / 9, against a rule that wrong must not rise (§7.28). On 30
  held-out answerable questions, 0.30 with a documents prompt rule, an 1,800-word budget, or both gave 6 to 8 wrong
  against the shipped 4, and plain 0.30 gave 8 (§7.30). The
  wrong answers come from passages that do not hold the answer: at 0.30 only 23% of what the model is handed holds
  it. On prose, 0.30 gave 8 correct with no extra wrong (p = 0.039), inconclusive by the validity guard.
- **Why it is out of scope for v1.0:** the fix is an order of steps, each with its own measurement (#21): chunks of
  at most 256 tokens, then re-index every document, then a cut-off measured on both kinds of document with the bar
  fixed before the run (BLUEPRINT cards R-2, then R-1). A cut-off measured on today's index would not carry over,
  because that index never embedded most of each chunk. That is days of work below the cut line, and half of it
  would leave retrieval less well understood than it is now.
- **For the thesis, as worded here:** "Answering questions from uploaded documents is not a working feature of PIP
  v1.0. At the shipped settings, retrieval returns the passage that holds the answer for 2 of 54 questions on
  technical notes and 0 of 26 on prose. Two causes were measured: 500-word chunks against an embedding model that
  reads 256 tokens, so most of each chunk is never searched, and a similarity cut-off of 0.60 above where answering
  passages score (median 0.38 and 0.26). Lowering the cut-off alone raised wrong answers (4 to 9 of 54). The failure
  is mostly conservative: of 54 answerable questions the model declined 41 and answered 4 wrongly, and it invented
  no answer to 12 unanswerable ones. Smaller chunks, re-indexing and a re-measured cut-off are future work."

**Not covered (still open):**
- The "~256 tokens" comment in `backend/memory/vector_store.py` still understates the gap (a 500-word chunk is about
  855 tokens); R-2's one-line comment fix, not done here.
- `.docx` is not accepted (`.pdf .md .txt .py .json .html` only).
- Measured on one technical corpus and one prose document, questions by one hand, one 7B model at temperature 0.
- Numbers from the hashed stand-in embedder are never carried over (§7.27).

### 7.69 D-45: no click, no search, PIP asks before every web search (authorized 2026-10-21, the owner's option 1)

Found by Q-1 (§7.66). Numbered 7.69 because another session's note already names §7.68 for #21. BLUEPRINT card D-45,
written first.

- **Defect (D-45, A, medium; §7.66 first rated it low, for greetings only):** with web search consented, any message
  with one of Stage 1's trigger words (latest, today, current, news, price, who won, recent, weather, right now)
  that was not filed as a personal or project question was searched at once, its first 12 words sent to the search
  provider. Checked 2026-10-21 through the real Stage 1: "I feel tired today", "feeling anxious about the exam
  today", "we had a big fight today" and "today I finished chapter two" were all sent.
- **Promise:** 6, made stronger: consent now lets PIP ask, and each search needs its own click.
- **Owner decision:** option 1 of four (ask first). The others: take "today" off the list, let the model decide, a
  written limitation.
- **Mechanism:**
  - **The first pass sends nothing.** Whether a message would be searched (trigger word, category, Stage 8 consent)
    is decided before the answer cache. Such a turn is answered without the web, says so (stage "web", "Web search
    not sent", "asks you first: '<query>'", skipped), is neither read from nor saved to the cache, and its result
    carries `web_search_offer`, the exact query. Only a run given `approved_web_query` sends it, with Stage 8 checked
    again at that moment; that run is not cached either.
  - **The socket** sends `web_search_offer` {offer_id, query} after the turn's done (additive, `shared/ws_spec.py`).
    Offers live in the connection's memory under a random id, are used once and are gone at disconnect. {"type":
    "web_search", "offer_id"} answers the same question again with exactly that query, the history from before the
    question (not repeated), the new answer saved as an assistant message only; any other id gets one error and
    nothing is sent.
  - **The app** shows the offer under that answer as a button, Search the web for: "<query>", with "Only these words
    are sent to the search provider."; a tap sends the approval, removes the button and streams the new answer, with
    no new user bubble. The consent text says PIP asks before each search.
  - **Unchanged:** the query is the first 12 words (DEC-14); personal and project questions are never searched or
    offered (P-1); without consent nothing is offered; the older web client (frontend/web) shows no button, so it
    never searches.
- **Tests:** `backend/tests/test_ask_before_web_search.py`, 14, through the real pipeline and Stage 1 with Stage 6
  recorded: the five D-45 sentences and a news question send nothing and are offered exactly their first 12 words;
  the first pass says what it would send; an approved search sends exactly the offer, once, and its results reach
  the answer; consent is checked again; an approved answer never comes from the cache; a turn with an offer is not
  cached; no consent, a question about the user and no trigger word get no offer. `test_ws_chat.py`, 5 new: an offer
  after the reply; approving answers the same question with that query and the history from before it, saved as an
  assistant message only; an offer is used once; an unknown offer sends nothing; an offer does not outlive its
  connection. `web_search_offer_test.dart`, 4: the button with the exact words; a tap sends that search, removes the
  button and adds the answer with no new user bubble; no offer, no button; the consent text.
  - **Seen failing first:** the new and changed pipeline tests 23 of 30 (the 7 that passed are the unchanged
    personal-question tests); socket 4 of 5 (an unknown offer already got an error, since a message with no text is
    refused); app 3 of 4 (the no-offer control passed).
  - **Existing tests changed, on purpose:** six pinned an immediate search and now offer first and search when
    approved: `test_pipeline.py` (2), `test_b1_honesty_fixes.py` (1), `test_personal_questions_stay_off_the_web.py`
    (1, five cases), `test_keep_the_thread.py` (1) and `test_consent_before_sending.py` (1, also checking that an
    offer made while consent stood sends nothing once it is revoked). The first full run found the last one.
  - **A test design point:** the socket tests send one empty message after the reply, which the server always
    answers with an error, so a missing offer fails the test instead of waiting; the first run before the fix waited
    until it was stopped.
- **Break-it:** 17 mutations, each alone, restored byte for byte, each caught by its test: the first pass searching
  again; the approved run sending the message, not the offer; consent not checked again; a turn with an offer
  cached; an approved search cached; an offer without consent; a question about the user offered; the offer left out
  of the result; the socket sending no offer; an offer usable twice; the approved prompt repeating the question; the
  question saved again; offers outliving their connection; the button without the exact words; a tap sending
  nothing; the button staying after a tap; the consent text not saying PIP asks. (The app runs' output first could
  not be read on this console; they were run again with the output read as UTF-8, and each failed on its own test.)
- **Suites:** Backend 1850 passed, 0 failed (19 min 3 s), on the working tree at a09d9d1 plus this change, with other sessions' uncommitted changes in it (the httpx2 requirement and its test; 7e2304a, documents only, was committed by another session during the run); the changed files were compared byte for byte with copies taken before the run. The first full run had 1 failure, the sixth test that pinned an immediate search (above), updated; 11 of 11 in its file, then the full run again. Flutter 352 passed (348 + 4).

**Not covered (still open):**
- **The real app window was not used** (V-1 needs the owner), and no real search was sent.
- **Cost:** a news question needs one more click, and its first answer is written without the web.
- **The trigger words are unchanged:** a message without one is never offered a search, as before.
- **The searched answer is a second reply** to the same question; the first stays in the chat and in what the
  Observer reads.
- **An offer is lost** when the chat reconnects; asking again makes a new one. The older web client cannot search.

### 7.70 Long chats learn almost no true facts: a stated limitation of v1.0 (decided and written 2026-10-21; no code change, no new run)

The owner's decision on the open question "long chats still learn 0 of 81 facts, because the gate refuses everyday
wording": state it as a limitation in the thesis (2026-10-21, "write the 0 of 81 limitation next"). The two other
options were set aside: more support phrases in the gate (a word list, which the owner ruled out on 2026-10-17)
and judging support by meaning (too large for the days left). Every number below comes from the recordings already
committed, replayed through a09d9d1 (the gate as it is now; `docs/eval/gate_fixes_2026-10-21/`), no model.

- **What is measured.** V-2's long-chat set (§7.55): 27 made-up chats of about 1,400, 2,700 and 4,800 words, each
  with the same three true facts (F1 "I do all my diagrams in Excalidraw these days, it's the only drawing tool I
  actually open"; F2 "my main project this term is Lanternfish, a budgeting app for student hostels"; F3 "I want to
  pass the AWS Solutions Architect Associate exam by March"), three trick statements and three near-misses, rotated
  over start, middle and end, on profiles 1, 3 and 9 weeks old.
- **Result, learned or asked, in the tables the labels name:**
  - **0 of 81 on G-4's run** (W-1's rule on the G-4 code, §7.60), the recording #19 measured (§7.64); unchanged by
    a09d9d1. Trick statements and near-misses: 0 of 162.
  - 1 of 81 on V-2's long recording and 3 of 81 on W-1's, all three F3 when the model cited the statement without
    its question, asked of the user rather than written. Traps 0 of 162 on W-1's; 1 of 162 on V-2's since a09d9d1,
    the D-46 topic (§7.67).
  - Short chats, the same pipeline: 39 of 69 (V-2 qwen; 41 before a09d9d1 dropped two "Go at 1.0" questions), 35
    (V-2 llama), 48 (W-1 short), 49 (2026-10-12), with traps 0 of 75 on each.
- **Where the 81 are lost, G-4's run** (each fact x 27 chats; the gate's own reasons, re-run with `adjudicate`):
  - F1 Excalidraw: proposed in its table 18 times, all refused as carrying no preference support language; not
    proposed 9 times.
  - F2 Lanternfish: proposed 27 times; refused 12 as having no project support language ("my main project" is not
    among the project phrases), 12 because the quote runs on into the user's next question ("How should I name the
    tables for shared expenses?") and a quote that ends in a question is read as a question (`_only_ever_asked`), 3
    not found.
  - F3 the exam goal: not proposed as a memory 21 times (3 of them only as a decision), 3 times in other tables, and
    the 3 in its table refused because the quote runs on into "What is a sensible way to space out revision?".
  - So the losses are two, and length is not one of them (V-2 found the same candidates get the same verdicts
    without the chat around them): the gate's allowlist does not hold the wording, or the cited message ends in a
    question; and the model does not propose the fact. The blind measurement agrees: 20 of 58 quotes the gate
    refused did support their claim (34%; §7.63).
- **Why it is the price of the design, and not fixed:** the gate fails toward rejection on purpose (ARCHITECTURE:
  "The evidence gate is an allowlist"): an unknown wording is a lost memory, never an invented one, and the same
  pipeline wrote no trick statement on the long set's G-4 run. Recall is what that costs. The two fixes are both out
  of scope: a longer phrase list is the brittle word list the owner ruled out, and a judge of meaning would put a
  learned model in the trusted step the gate was built without, which is more than the days left. Reading a quote
  that ends in a question as a statement would let a question pass as a fact.
- **For the thesis, as worded here:** "PIP v1.0 learns little from long, natural conversations. In 27 made-up chats
  of 1,400 to 4,800 words, each holding the same three true facts, it learned or asked about 0 of 81 facts on the
  recording used for the thesis numbers (1 and 3 of 81 on two other recordings of the same chats), while writing
  none of 162 trick statements and near-misses. The model proposed most of the facts. The deterministic evidence
  gate refused them, either because their everyday wording ("I do all my diagrams in Excalidraw these days", "my
  main project this term is Lanternfish") is not in its list of support phrases, or because the quoted message
  ended in a question, which the gate refuses on purpose. A blind check agrees: a third of the quotes the gate
  refused did support their claim. On short, direct statements the same pipeline learns or asks about 35 to 49 of
  69 facts. This is the cost of a gate that fails toward rejection: it trades recall for not writing beliefs the
  user never expressed. A longer phrase list or a judge of meaning are future work."

**Not covered (still open):**
- One author's made-up chats, in English, mostly one model (qwen2.5:7b); real users' long chats are not measured.
- The model's share (facts never proposed, F3 above all) is not separated from its prompt. It is not the window on
  G-4's run, which read all 27 prompts whole at 16k (§7.60); V-2's long recording was made at 4096 (§7.55).
- D-46, the topic trap V-2's long recording now writes, is open (§7.67).

### 7.71 V-1: the real window, first-run import, the web-search button, the record dialog and a backend stop, D-47 (run 2026-10-21, report only)

The last item in the plan (BLUEPRINT card V-1). Driven by Claude through screen control in a throwaway copy, with the
owner's OK; the owner allowed the two test passwords to be typed this once, for that copy only (the new one is kept in
the copy's folder, TEST_PASSWORD.txt). The owner's first "all as expected" came before the copy had run (its data
folder was empty) and is not part of this record.

- **The copy:** `D:\FINAL YEAR PROJECT\pip-work\v1-window`: `git archive 05c6523` of backend/, shared/, config/ and
  scripts/; its own .venv (a .pth onto the development site-packages, no test hooks); the Release app built from
  05c6523's client on 2026-10-21; its own data folder and port 8790 (PIP_PORT, PIP_API_BASE, PIP_WS_URL); started by
  the real launch_pip.ps1, which started Ollama with `ollama serve`. The owner's PIP was not running, port 8765 stayed
  free, `data/` was never opened, and screen control was granted for that one executable by its full path.
- **A, first-run import: as expected.** Welcome screen; Import existing PIP; the file chooser; the import dialog with
  the file name and full path; three passwords; "Imported "BatMan". Sign in with the new password you just chose.";
  signed in. Sidebar: Session 14 down to Session 1. Profile: BatMan, English, UTC, 10 decisions, 2 things learned,
  the project "PIP - Personal Intelligence Platform".
- **B, the web-search button (D-45): as expected.** Providers: web_search "not consented"; the consent dialog's
  web_search_only text says PIP asks before each search; granted. In a new chat, "what is the weather in Kathmandu
  today?" was answered without the web, with Search the web for: "what is the weather in Kathmandu today?" and "Only
  these words are sent to the search provider." under it; its steps said "Web search not sent - asks you first".
  "I feel tired today" was answered and offered, not clicked, and nothing was sent. The weather click removed the
  button; the steps said "query sent: 'what is the weather in Kathmandu today?'", web_search_used Yes; the searched
  answer came as a new reply with no new user bubble. One real search went to DuckDuckGo.
  - Seen: the searched answer is added at the end of the chat, after the "I feel tired today" exchange, with nothing
    saying which question it answers.
- **C, Where we left off (#13): opens.** On Session 14: "No record of this chat yet. PIP writes one when a chat with
  something to summarise ends.", with Write it and Close. Nothing was written.
- **D, the backend stopped mid-answer (D-23): the turn ends, the chat does not come back.**
  - As expected: while "explain how a hash map works, in detail" was being written, the test backend (only the
    process on 8790) was stopped. The chat said "The connection to PIP was lost before this reply finished. Send
    your message again.", kept no partial answer, gave Send back and showed "disconnected".
  - Not as expected: the backend was started again the way the launcher starts it and came back locked (a
    password-protected profile needs a sign-in), so it refused the chat socket (4423, logged as 403). The window
    never showed the sign-in screen, and its reconnects multiplied: 30,800 attempts in about two minutes, over 1,000
    a second and rising, 277 CPU-seconds in the window, until it was closed.
- **D-47 (A, medium, found here): the chat's reconnects double on every failed attempt.** `ws_chat_client.dart`
  schedules a reconnect from both `onError` and `onDone`, and a refused connection fires both, so each failure starts
  two attempts two seconds later and they double every round, whatever the refusal (a locked backend, a stopped one).
  And a socket refused as locked never brings the app back to sign-in, so the chat cannot resume in that window. Not
  fixed.

**Not covered:** the restore shortcut and the Backup screen's restore; the chat resumed after a new sign-in (the
window was closed to stop the reconnects); the Review screen's questions (#19); the other screens.

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
| Long-chat learning (0 of 81) stated as a limitation of v1.0, not a longer phrase list and not a judge of meaning (2026-10-21, §7.70) | Decided |

### 8.2 Evidence status (facts; need reports)

| Track | Report | Classification |
|-------|--------|----------------|
| 1 Observer/provider gate | Returned 2026-09-26 (§7.2) | C; plus A (startup queue, fixed §7.11) and D (wording, fixed in §4 Promise 5). Finding 2, two locality records, still open |
| 2 `PIP_DB_KEY` | Returned 2026-09-26 (§7.3) | Main DB read: C (redundant, unchanged). `vector_store` read: A (load-bearing, failed open to plaintext; now fails closed, §7.9). Key still exported to the environment, stated in Promise 7 |
| 3 PID-reuse lock | Returned 2026-09-27 (§7.4) | B: stores a bare PID, so a reused PID blocks startup (fixed §7.12) |
| 4a Stage 1 routing | Returned 2026-09-27 (§7.5) | A: 10 of 14 identity/project questions lost the project; header claimed a complete record. Recommendations 1–2 fixed (§7.10); 3, Stage 1 precedence, open |
| 4b Cache safety | Returned 2026-09-27 (§7.6) | A: stale answers replayed after documents or decisions existed; one profile's answer served to another. Cross-profile fixed (§7.9), staleness fixed (§7.10) |
| Promises 1–3 tests | Written 2026-09-28 (§7.13) | C: all three hold, each break-it seen failing; two findings (decisions skip the gate; immutable names shadowed in preferences) |
| End-to-end Observer measurement | Run 2026-09-28 (§7.14) | 37 conversations, 3 runs, qwen2.5:7b: precision 88–90% (memory), 77–83% with decisions; recall 30–39%; sarcasm gets through. These are the old gate's figures: after the A-1 gate change the same recorded answers give 0 of 75 traps and 37 of 69 facts learned (§7.37) |
| Promise 4 threshold measurement | Run 2026-10-20 (§7.63), blind | DOES NOT HOLD by the rule fixed in advance: 8 of 58 accepted quotes (14%, 95% 7-25%) did not support their claim (5 expert skill levels, 2 a friend's suggestion, 1 a project filed as a preference); the Constitution asked about 4, discarded 3, wrote 1. False rejects 20 of 58 sampled (34%, 95% 24-47%) |
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
| D-04 consent locality fix | Landed 2026-10-02 (§7.21) | Stage 8 counts a provider as local only when its own claim and its consent record agree; `add_endpoint` refuses built-in ids. 11 outcome tests (5 seen failing first), 3 gate unit tests, 6 break-it mutations caught. Promise 6 now has evidence. Open: locality attested not verified, D-08 (fixed 2026-10-16, §7.48), §7.2 finding 2 |
| D-14 staged restore and deletion fix | Landed 2026-10-02 (§7.22) | `profiles.delete()` first cancels a restore staged for that profile's database, so nothing is installed in a deleted profile's place and the staged copy is erased. 4 route tests (3 seen failing first), 3 break-it mutations caught. Open: `profiles.remove()`, which nothing calls |
| D-16 chat turn with no terminal event | Found and landed 2026-10-03 (§7.23) | A, latent: with no provider left after Stage 8 the socket got stage lines and no done/error, so the chat stayed "writing". The pipeline now sends its error. 3 socket tests through the real pipeline (1 seen failing first), 2 Flutter tests, 4 break-it mutations caught. Open item, a pipeline that raises, fixed as D-22 (§7.25) |
| Migration journey re-run | Run 2026-10-03 (§7.24), report only | 10 variants, exports and shortcut restores through the real `export_pip.ps1` and `restore_pip.ps1`, 307 checks at `9968e8c`, every failure attributed; negative controls catch D-03 and D-14. Round trip holds (D-01 on every in-app restore that had a WAL to swap, D-03 with two profiles). New: D-18 empty or partial backup accepted (medium), D-20 same-named document taken over the backup's (medium, upper end), D-21 shortcut restores the first backup of the day (medium, low end), D-17 export race with a false "Nothing was written" (low, upper end), D-19 staged-restore state not scoped to the profile (low). Exit criterion not met as worded: D-09, D-18, D-20 |
| D-22 raising pipeline ends the turn | Landed 2026-10-03 (§7.25) | A: an exception from the pipeline closed the socket mid-turn with no done/error. The transport now ends the turn with one error, keeps the connection, and saves the turn as the client was shown it. 3 socket tests (all seen failing first), 6 break-it mutations caught. Found: D-23, the client never ends a turn on a dropped connection (code reading) |
| D-24 stray Stop answered with an error, D-25 token the fold cannot take | Found by review and landed 2026-10-16 (§7.44) | A, low, both. A Stop with nothing streaming is dropped instead of answered "message is required"; the fold of each forwarded event moved inside D-22's guard and ahead of the send, so a token that is not text is withheld and ends the turn with one error instead of closing the socket. 5 of 15 tests failed first, 10 break-it mutations caught; the record's statements about what is wrapped, and its example of a crash, corrected |
| D-26 failed write around a chat turn closed the connection | Found 2026-10-16 (§7.44), landed 2026-10-16 (§7.45) | A, medium: a project that no longer exists, or a conversation deleted under an open chat, ended the handler, with no ending event before the turn or after the reply was shown. Writes now go through a rollback; a message whose setup writes fail is refused with one error; a turn that cannot be saved is queued, retried in order before the next message, and that message is refused if it still cannot be written. 5 tests (all failed first, two on real triggers), 10 break-it mutations caught. Open: a failed save is told only at the next message; a turn queued at disconnect is not saved |
| D-27 a token that is not text is a provider failure | Landed 2026-10-16 (§7.46) | A, low: a server streaming structured content, or a null, put a non-text token into the stream; a provider whose first token was one was not treated as failed, so the next was never asked. Stage 9 now fails it like one that yields nothing: the next provider before any text, "Response interrupted" after. The message names the type, never the value. 10 unit and 2 end-to-end tests (8 + 2 failed first), 6 break-it mutations caught; the transport's guard kept and its tests moved onto a fake pipeline. Open: an exception that is neither provider error still ends the turn, on purpose |
| G-1 / D-05 plaintext base slot before sign-in | Fixed 2026-10-16 (§7.47) | A, medium: with profiles registered and nobody signed in, 56 of 58 gated routes were served and the chat socket accepted, from a plaintext database created in the base slot, and a "Default" profile appeared. One rule (`_is_locked`, whose condition was `_no_profile_is_open` until G-1b replaced it with `_has_profiles`, §7.49) now answers 423 at the gate, 4423 at the socket and `LockedError` in `_conn()`, widening another session's uncommitted guard. 6 tests (4 failed first), 6 break-it mutations caught. Found beside it: D-28, fixed in G-1b (§7.49), which also put right the first-run import this refused |
| D-28 / G-1b a profile chosen before its password gets a plaintext database | Fixed 2026-10-16 (§7.49) | A, medium: one request to any database route, before `/auth/setup`, created a plaintext `pip.db` in the profile's folder; the state became `needs_migration` and `/auth/setup` was refused, so the profile could not be given a password through the app, and 56 of 58 gated routes were served. G-1's rule one step further: with a registry, "setup" is refused at the gate, the chat socket and `_conn()` (`_has_profiles` replaces `_no_profile_is_open`). The first-run import, which G-1's gate had made dead after the last profile was deleted, is on the exempt list now. 7 tests (5 failed first), 9 break-it mutations caught |
| D-29 the first-run import refuses for any registered profile | Found 2026-10-16 (§7.49), open | A, low: the route's rule is meant to be "no profile has a database" but tests the method `exists`, not its result, so a profile with no password yet also refuses it, with a sentence that is untrue then. Over-refuses only; the welcome screen cannot reach it. Not fixed |
| G-3 / D-08 a cloud model counted as local | Fixed 2026-10-16 (§7.48) | D then A, medium: Ollama's own `-cloud` models were answered over the internet but reported local, so a conversation and the Observer's transcript could leave the machine. One predicate (`is_cloud_model`): a pull and a selection are refused with a sentence (the selection before Ollama is asked, which fails open), and the provider reports itself not local, so Stage 8 and Stage 11 refuse a name already stored. 43 tests (28 failed first), 7 break-it mutations caught |
| G-2 / D-06 a deleted document left its file and its stored bytes | Fixed 2026-10-16 (§7.50) | D then A, medium: `DELETE /rag/documents` removed the chunks and marked the row, but the uploaded file stayed in the documents folder and its bytes stayed in `document_blobs`, so in every later backup. Delete now removes the file (only one inside the profile's own folder; one that cannot be removed stops the delete with a sentence) and the stored bytes. 12 tests (9 failed first), 7 break-it mutations caught |
| G-6 the older web client granted full consent in one click | Fixed 2026-10-16 (§7.51) | A, low: `frontend/web/` sent `consent_scope: "full_inference"`, the broadest scope, for any cloud provider on one click, with nothing explained and nothing chosen. The button and its handler are gone; the tab says to grant it in the PIP app; Revoke stays. 3 tests (2 failed first) that read the served files, 4 break-it mutations caught. The server still accepts any valid scope from any token holder |
| D-30 the command-line client's /consent defaults to full_inference | Found 2026-10-16 (§7.51), open | A, low: `/consent PROVIDER_ID` with no `--scope` grants the broadest scope, a default the person did not choose. A typed command, in a client that is not shipped. Not fixed |
| D-31 a question about the user sent to the web | Fixed 2026-10-17 (§7.52) | A, low: with web search consented, a message with a news word was filed as news before Stage 1 asked whether it was about the user or a project, so "what is my current project?" sent its first 12 words to the search provider. Stage 1 now asks that first (no words added). 12 tests (7 failed first), 2 break-it mutations; the 14 §7.5 phrasings send 1 query instead of 4. Open: a phrasing Stage 1 does not recognise as about the user is still sent |
| D-32 a deleted chat kept reaching later prompts | Fixed 2026-10-17 (§7.53) | A, medium: deleting a chat removed its messages only. Its "where we left off" note kept reaching every new chat's first prompt; the app's own order (delete the open chat, then leave it) ran the session-end pass on the deleted chat and wrote the note back; and a transcript queued for the next start was learned from and kept. The delete now removes the chat's queued transcripts (new `pending_observer.conversation_id`) and clears the note, and the pass skips a chat that is gone. 8 tests (7 failed first), 6 break-it mutations. Open: the note is cleared whichever chat wrote it; what was already learned stays |
| S-1 a run stamp on every evaluation result | Built 2026-10-17 (§7.54) | Method: one of five evaluation scripts stamped its results, and only with --save-raw. `scripts/_stamp.py` now records, at the start of every run, the commit and a dirty flag, the Constitution's version and hash and, for a model run, Ollama's version, the model's digest and the options sent (a model run that cannot read them refuses to start); every result file and report carries it, one per start for a resumed run. 23 tests (10 script tests failed first), 8 break-it mutations. The two model-calling retrieval harnesses were not run |
| V-2 validity baseline (b, c, d, a) | Run 2026-10-17/18 (§7.55), report only | qwen2.5:7b on Ollama 0.40.3: traps 0 of 75, 36 of 36 true, 35 of 69 learned (HOLDS); llama3.1:8b: traps 0 of 75, 33 of 69 learned (SUPPORTED). As shipped the window is 4096 and a longer prompt is cut from the front (2,050 of 10,639 tokens read). 27 long chats: 1 of 162 trick statements or near-misses reached the queue (D-33) and 0 of 81 true facts were learned where labelled, lost to the gate's wording rules, not to length (TRUST DOES NOT CARRY OVER, by the rule) |
| D-33 a third person's goal accepted as the user's interest | Fixed 2026-10-18 (§7.61) | A, medium: "My friend wants to pass the Azure Fundamentals exam by March" was EVIDENCE_SUFFICIENT for the user's `topic_interests` and reached the confirmation queue on a long chat. A topic is now the user's only when they ask about it or say it in the first person (the pronoun "I"; no list of phrasings). 11 tests, 5 break-it mutations; replays: nothing added, 2 rows lost, both about someone else. Cost: an elliptical answer with no "I" ("A payments service.") raises no topic |
| W-1 one settings block: 16k window, qwen2.5:7b, temperature 0.0 | Built and measured 2026-10-18 (§7.56) | A, medium: Ollama's default 4096 window cut long prompts from the front and the default model was llama3.1:8b in code. Every request now asks for 16384 (all 27 long prompts read in full; fully on the GPU, 6.6-6.8 of 8 GB in use with a browser open); qwen2.5:7b is the one default; temperature 0.0 chosen by a fixed rule. 13 tests, 7 break-it mutations. Its long-chat bar 2 is NOT met: 2 near-misses (1 before) reached the decision log, which skips the gate (G-4) |
| D-34 a learned decision saved with no project | Fixed 2026-10-18 (§7.57) | A, medium: the Observer was called without the chat's project and a queued decision had no project column, so every learned decision was saved with none and a project's own lookup never found it. The project is now read from the chat's row on every path (end of chat, shutdown queue, crash recovery), and logged and queued decisions keep the project and the chat's id. 7 tests (7 failed first), 5 break-it mutations |
| D-35 the Constitution edited after it was locked, its version never checked | Fixed 2026-10-18 (§7.58) | A, low: constitutional.json said 1.0 and was edited twice with no bump; every profile stored the literal 1.0 and nothing compared it. Now 1.1 with a changelog, each version registered with its text's fingerprint, and a sign-in check that warns (log, trace, /status) and keeps running (DEC-6). 8 tests, 5 break-it mutations. The app does not show the warning yet |
| D-36 a refused candidate left no lasting record | Fixed 2026-10-18 (§7.59) | A, medium for the thesis: a candidate the guard refused left a logger line only, and trace_log is purged after 90 days. Now an append-only `governance_audit_log` (triggers abort UPDATE and DELETE) holds one row for every terminal outcome of an Observer memory or decision candidate and for every user answer to a queued question, with an HMAC fingerprint and never the text, through one writer that refuses an unknown reason (DEC-5). 52 tests, 12 break-it mutations. Append-only within the trust boundary, not tamper-evident; decisions made by hand are not audited; no view in the app |
| D-37 the Observer's decisions skipped the evidence gate; an immutable name could be a preference | Fixed 2026-10-18 (§7.60) | A, medium (§7.13 findings 1-2, DEC-7 = A): decisions were logged on grounding and the model's own signals, so tentative remarks, a friend's goal and the assistant's words became the user's decisions; `preference_memory.language_preference = French` sat in every prompt beside identity's English. Decisions now pass the gate (goal_memory's commitment language reused, the user's own words); the Constitution refuses an immutable name as a preference and Stage 4 keeps an old one out of prompts. 16 tests, 7 break-it mutations. Replays: nothing added; 154 of 197 decisions removed, 124 rightly, 9 real ones lost (30 lenient). W-1's run 1 re-run with the model: bar 2 met (0 of 162, W-1 had 2) |
| D-38 the gate refuses a quote carrying its turn's "User:" label | Fixed 2026-10-21 (§7.67) | A, low: a quote that begins "User:" and is not found as written is looked up without the label; who said it is still the ledger's answer, and an "Assistant:" label is never taken off. On the replays 6 of G-4's 7 label-caused decision losses come back; it also let D-46's trap through |
| D-39 one "where we left off" note for every chat and project | Fixed 2026-10-20 (§7.62) | A, medium (#13): the note was one row per profile, overwritten by every chat, loaded into every project, cleared whichever chat was deleted, and invisible in the app. Now one record per chat (`chat_records`) with its project, deleted with its chat; a chat is shown its own, else its project's latest, else the newest, labelled and dated; the previous chat's unsummarised end; the record can be read, corrected and cleared in the app. 32 + 1 backend and 8 app tests, 31 break-it mutations. Documents are not linked to chats |
| D-40 a skill level of 1.0 accepted from "N years professionally" | Fixed 2026-10-21 (§7.67) | A, low: experience language supports a level up to 0.9; above it the quote must say "I'm an expert". 5 of M-1(a)'s 8 graded false accepts are refused now (not a re-measurement); on the replays 7 true skills queued at 1.0 are refused instead of asked |
| D-41 reported speech with "I" passes as the user's topic | Found 2026-10-20 (§7.63), open | A, low: D-33's first-person rule reads "My friend says I should do a full marathon" as the user's; two such topics in M-1(a), both discarded by the Constitution. Not fixed |
| D-42 "my main project" accepted as a preference | Fixed 2026-10-21 (§7.67) | A, low: "my main" is no longer preference language, so the Lanternfish sentence is not a preference. It is still not a project: that would need a wider word list |
| D-43 a genuine fact short of the count dropped silently | Fixed 2026-10-20 (§7.64) | A, medium (#19): a candidate the gate accepted but the Constitution refused for a count (or an inferred label in weeks 1-2) was thrown away, so learning nearly stopped after week 2 and a correction a month in was lost. Now one question (origin shortfall), at most 2 per chat, for belief tables only; a correction shows the stored value. 13 + 2 tests, 11 break-it mutations. Short set 35 -> 41 of 69 learned or asked, traps 0 of 75; long set 0 of 81 unchanged (lost at the gate's wording) |
| D-44 a follow-up inside one chat lost its thread | Fixed 2026-10-20 (§7.65) | A, medium (#7, #8, #9, #10, #12): the prompt never named the day; a 10-minute break cleared the open chat's history; one long reply emptied the history; a follow-up could get another chat's cached answer; decisions and documents were searched with the newest message's first 12 words. Now the day is in the prompt and the cache key; the idle pass marks what it read and keeps the history; the last exchange is always kept, shortened; only a chat's first message is cached; Stages 3 and 5 search with the previous and the whole current message, the web query unchanged. 11 + 3 tests, 12 break-it mutations. Open: a whole prompt over budget can still lose the last exchange; retrieval with the longer text not re-measured |
| Q-1 a new user's greeting answered "no record" | Run 2026-10-21 (§7.66), closed, no code change | qwen2.5:7b on the real pipeline, 4 made-up new users x 26 greetings: 0 of 104 no-record replies by the pattern and by reading all 104; the bar (at most 1) met. llama3.1:8b and phi3:mini showed it on 2026-10-17 |
| D-45 a message with a trigger word sent to the web without asking | Fixed 2026-10-21 (§7.69) | A, medium (§7.66 first rated it low, for greetings only): with web search consented, "I feel tired today" and any message with a trigger word not about the user or a project went to the search provider at once. Now no click, no search: the turn is answered without the web and ends with an offer of the exact words; only a click sends them, with consent checked again. 14 + 5 backend and 4 app tests, 17 break-it mutations |
| D-46 a hypothetical first-person sentence raises a topic | Found 2026-10-21 (§7.67), open | A, low: topics skip the hypothetical check and D-33's rule takes any sentence with "I", so "If I ever had a free summer I might look at Elixir" is the user's topic. The model's "User:" label had hidden it; with D-38 fixed one replayed trap is written. Not fixed: the owner's choice |
| V-1 real-window check | Run 2026-10-21 (§7.71), report only | In a throwaway copy (05c6523, port 8790, the Release app): the first-run import, the D-45 web-search button and the record dialog worked as expected, and the D-23 turn end too; after a restart the locked backend refused the chat, the window never asked to sign in, and its reconnects multiplied (D-47) |
| D-47 the chat's reconnects double on every failure | Found 2026-10-21 (§7.71), open | A, medium: ws_chat_client.dart reconnects from both onError and onDone, so a refused connection (a locked or stopped backend) starts two attempts and they double every 2 s: 30,800 in two minutes, 277 CPU-seconds. A socket refused as locked never brings back the sign-in screen. Not fixed |
| Import and export fixes | Landed 2026-10-07 to 2026-10-08 (§7.26) | D-18 empty or part-written backup refused through a completeness mark, D-21 newest backup by modification time, D-11 bad inputs answered with a sentence and no temporary copy left, D-20 and D-07 the backup's documents written back (the swap moves `documents/` and `chroma/` aside), D-17 one snapshot for the export's counts and copy, D-19 a staged restore scoped to its profile, D-09 the backend stopped so closing and reopening applies a restore and the shortcut can run. D-18 also opens the backup read-only. A second round the same day added a crash-safe swap (a restore whose process died between its last two renames is finished by the next start), a restore script that removes its temporary copy when interrupted, and the first-run import from the welcome screen (`POST /backup/import`, profile named after the person in the backup); an older-version backup and a 322 MB backup were tested with no defect found. Not done: the export side and the restore core were not hunted again for unrecorded defects (the helper agents ran out of usage), the shortcut still restores into "Default", and the new first-run import was checked against a real backend but not in a real window |
| Retrieval quality measurement | Run 2026-10-08 (§7.27), report only | Real all-MiniLM-L6-v2, 54 known-answer questions over 7 project documents: as shipped (0.6 cut-off) the right passage comes back for 2 of 54, though ranking alone has it in the top 3 for 25; the score separates off-topic questions (best 0.19) but not the right passage from others on the same subject; a median 500-word chunk is 855 tokens and 71% of its text is not embedded; 300-word chunks 57% against 46%, not established. Nothing changed; threshold and chunking changes need authorisation, a second corpus and an end-to-end check first |
| Cut-off end-to-end check | Run 2026-10-08 (§7.28), report only | Real pipeline on qwen2.5:7b, 66 questions, three cut-offs, rule fixed in advance. Lower cut-off NOT supported: correct answers 1 / 11 / 26 of 54 at 0.60 / 0.45 / 0.30 and no invented answer to 12 unanswerable questions, but wrong answers 4 / 7 / 9 (the rule said they must not rise). The wrong ones come from passages that did not hold the answer; Stage 7's 800-word cap also hides retrieved answers. Nothing changed; a document rule in the prompt and the 800-word budget are the untested levers |
| Hunt for unrecorded import/export defects | Run 2026-10-08 (§7.29), five fixed | A password or bearer token in any script crashed the export prompt, the shortcut restore's prompt and the token check (`compare_digest` on `str`): fixed. A backup whose owner's name has no a-z or 0-9 could not be imported ("already exists"): fixed. Two imports at once raced: fixed. The provider-consent seed raced between two connections: fixed. Probed with no defect: odd ASCII passwords, document write-back paths, SQL quoting. Not done: a real console's non-ASCII `getpass`, a real second computer, the real-window first-run import |
| Levers on the cut-off, and the owner's own document | Run 2026-10-08 (§7.30), report only | Held-out set of 40: neither the document prompt rule (D), the 1800-word budget (E) nor both (F) is supported - wrong answers 6 / 8 / 7 against the shipped setting's 4, though correct answers rose by 12-13 and nothing invented; D and E only looked better on the development questions they were shaped on. Owner's own document (a 2,993-word synopsis, kept out of git): found at the shipped 0.60 for 0 of 26 questions, 7 at 0.30, 15 at 0.15; answers 1 correct shipped, 8 at 0.30 with no extra wrong; inconclusive by the validity guard. Nothing changed; a cut-off below 0.30 and retrieval that returns fewer no-answer passages are untested |
| #21 document search almost never finds the answer | Written up as a v1.0 limitation 2026-10-21 (§7.68), not built | Product, below the cut line: 500-word chunks against a 256-token embedder, and a 0.60 cut-off above where answering passages score (median 0.38 technical, 0.26 prose); 2 of 54 and 0 of 26 found as shipped, 1 of 54 answered correctly, none invented. The whole-message query of step 6 gives the same 2 of 54 on the committed results. Lowering the cut-off alone raised wrong answers (§7.28, §7.30). Future work: smaller chunks, re-index, then a re-measured cut-off |
| Long chats learn almost no true facts | Stated as a v1.0 limitation 2026-10-21 (§7.70), not fixed | Thesis: 0 of 81 true facts learned or asked on G-4's long-chat run (1 and 3 of 81 on two other recordings), traps 0 of 162; the model proposes most facts and the gate refuses their wording or a quote that ends in a question; short chats 35 to 49 of 69. M-1(a), blind: 20 of 58 refused quotes were supported. The owner chose the limitation over a phrase list or a judge of meaning |
| Graceful stop of the backend | Measured 2026-10-08 (§7.31), not built | A hard stop mid-answer lost nothing durable: transcript identical, 1.8 s restart, conversation resumed, the catch-up logged the decision. Only the turn being answered is gone (saved when finished). No shutdown route built |

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
