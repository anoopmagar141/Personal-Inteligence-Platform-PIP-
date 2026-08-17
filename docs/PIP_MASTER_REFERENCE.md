# PIP — PERSONAL INTELLIGENCE PLATFORM
## Master Reference Document
### Version: 3.0 — Post-Schema-Finalization
### Status: Architecture Complete, Implementation Starting

> **PURPOSE OF THIS DOCUMENT**
> This document is the single authoritative reference for PIP. It supersedes all earlier
> versions of the architecture document. Any AI, engineer, or reviewer reading this cold
> should have complete context to continue development without prior conversation history.
> Decisions marked [EMPIRICALLY VERIFIED] were tested in a live sandbox. Decisions marked
> [FINALIZED] are locked. Decisions marked [OPEN] require action before proceeding.

---

## DOCUMENT MAP

```
Part 1  — Core Idea and Problem Statement
Part 2  — Design Philosophy and Hard Constraints
Part 3  — What PIP Is Not (Permanent Exclusions)
Part 4  — Success Definition (Tiered)
Part 5  — Feature Priority Order
Part 6  — System Architecture
Part 7  — 14-Stage Message Pipeline
Part 8  — Memory Architecture
Part 9  — Constitutional System
Part 10 — Security Architecture (UPDATED: SQLCipher)
Part 11 — Storage Architecture (FINALIZED after 5 review rounds)
Part 12 — Observer Architecture
Part 13 — Provider Architecture
Part 14 — Frontend and Client Architecture
Part 15 — API and Transport Specification
Part 16 — All ADRs (001–025+)
Part 17 — Folder Structure (FROZEN)
Part 18 — Phase Roadmap (Phase 0–10)
Part 19 — Settings Reference (settings.json)
Part 20 — Finalization Status (What is locked vs open)
Part 21 — Implementation Sequence for Phase 0
Part 22 — Onboarding Question Script
Part 23 — Command Reference
Part 24 — Glossary
```

---

# PART 1 — CORE IDEA AND PROBLEM STATEMENT

## 1.1 The Problem

Every existing AI assistant has the same structural failure: **amnesia**.

The user explains themselves every session. Their goals, project history, communication
preferences, decisions — nothing persists. Cloud memory features exist behind subscriptions,
send personal data to third parties, and store only shallow preferences like formatting style.

The result: every session starts at zero. The LLM is smart but blind.

For users doing long-term intellectual work — engineers, researchers, architects — this
means spending 10–15 minutes per session re-establishing context that existed in the
previous one. The AI is helpful once context is rebuilt. It is useless before that.

## 1.2 The Solution

    The LLM knows the world. PIP knows YOU.
    Together they form one intelligent system —
    deeply personalized, fully local, completely private.

PIP is a locally-hosted software layer that wraps around an existing LLM and provides it
with a structured, persistent, encrypted memory system. The LLM handles reasoning and
language generation. PIP handles everything the LLM cannot:

- Who the user is (skills, preferences, interaction style)
- What they are working on (active projects, architecture decisions)
- What decisions they have made (and why)
- Where they left off (session snapshot, open problems)

**PIP does not generate answers. PIP builds the context that makes the LLM's answer
intelligent.**

## 1.3 The Core Mechanism

    Without PIP:
      User: "Why did we choose ChromaDB?"
      LLM:  "I don't have context about your project..."

    With PIP:
      User: "Why did we choose ChromaDB?"
      PIP:  [injects decision log entry into prompt]
      LLM:  "You chose ChromaDB on May 15th because of local-first
             requirements and simple setup. You rejected FAISS as too
             complex and Pinecone as cloud-only."

Same LLM. Same model weights. Completely different output. The difference is entirely the
context PIP assembled from its memory system.

## 1.4 The Core Rule

    PIP recommends → User approves → PIP records.
    Never the other way around. Never silently.

---

# PART 2 — DESIGN PHILOSOPHY AND HARD CONSTRAINTS

These principles govern every design decision. When a choice conflicts with a principle,
the principle wins.

**Personalization Over Raw Model Size**
A smaller model with deep personal context outperforms a larger model that has never met
the user. Context quality is the primary variable in response quality.

**Reliability Over Features**
A half-built system that works correctly on three things delivers more real value than a
fully-designed system that is 40% implemented across everything. Each phase must be
genuinely useful before the next begins.

**Local-First**
Everything runs on the user's machine. Nothing leaves without explicit, per-provider,
per-scope consent. Privacy is a system architecture constraint enforced in code, not
a policy statement.

**Decisions Are First-Class Memory**
The hardest thing to reconstruct is not code. It is the reasoning behind the code. PIP
treats decisions as the most valuable memory type — explicitly recorded, never silently
deleted, queryable by natural language.

**Fail Visibly, Never Silently**
Every failure mode must produce a visible signal. Wrong password produces an error, not
an empty DB. Observer crash leaves profile unchanged, not corrupted. Context overflow
trims lowest-priority content, never corrupts or drops silently.

**The Copilot Principle**
PIP recommends, user approves, PIP records. No autonomous action. No silent writes.
Every consequential action is transparent and user-controlled.

**DB-Level Enforcement Over App-Layer Assumptions**
Where correctness matters, enforce at the DB layer (triggers, CHECK constraints, FK
constraints, single-row guards) not just at the application layer.

**One Writer Per Data Resource**
Every table has exactly one owner module. Every other module is a caller, not a writer.
This is enforced by ADR-025 and a pre-commit hook.

---

# PART 3 — WHAT PIP IS NOT (PERMANENT EXCLUSIONS)

These are permanent design exclusions, not deferred features. Do not suggest them. Do
not implement them under any framing.

| Excluded | Reason |
|---|---|
| Emotion/mood detection | Privacy violation, scope creep, permanently forbidden |
| Psychological profiling | Same as above |
| Mood trend tracking | Same as above |
| Per-message Observer | Noisy, resource-intensive, RAM pressure on 8GB VRAM |
| Scored decision graph | Makes debugging harder, not better |
| Two-pass retrieval | Doubles latency for marginal gain |
| Ephemeral consent tokens | Enterprise solution for wrong scale |
| Four-primitives architecture reframe | Hides complexity, no implementation value |
| Silent cloud fallback | Violates privacy guarantee |
| Autonomous action without approval | Violates Copilot Principle |

**Tool Execution Layer (filesystem, code exec, scheduling)**: DEFERRED to post-v1.0.
Not excluded. Will arrive eventually. When it does, it should use the existing consent
model (extend consent_scope or a sibling tool_consent table), not a new permission
system. PRD Part 1.6 must distinguish non-goals (never) from deferred (later) explicitly.

---

# PART 4 — SUCCESS DEFINITION (TIERED) [FINALIZED]

These two statements are the official success criteria for PIP. Both are locked and must
appear in PRD Part 1.8.

**v0.5 (Academic minimum viable deliverable):**
> PIP correctly enforces constitutional memory rules — it rejects attempts to overwrite
> immutable fields, gates preference updates behind user confirmation, and validates
> Observer candidates against tiered evidence thresholds. `/decide` logs a decision with
> correct confidence scoring. `/profile` shows stored fields with source label and
> confidence.

**v1.0 (Full release target):**
> A user can ask "why did I decide X?" and PIP returns the original decision with
> reasoning, date, and source, retrieved from a searchable persistent log across sessions.

**Why tiered success statements matter:**
The original PRD 1.8 headline claim ("ask why did I decide X six months ago") requires
FTS5 decision search, which does not exist until Phase 6. If the timeline collapses to
v0.5, the original headline cannot be demoed at defense. The tiered statement closes
this risk.

---

# PART 5 — FEATURE PRIORITY ORDER [LOCKED]

```
Priority 1 — Decision Log
Priority 2 — Project Memory
Priority 3 — RAG (Document Retrieval)
Priority 4 — Session Continuity
Priority 5 — Personal Profile
Priority 6 — Observer (Auto-learning)
Priority 7 — Depth Detection (LOW — users can type "briefly" or "in detail")
```

**Tiebreaker rule:** Implementation order prioritizes architectural dependencies and
reliability over feature ranking. If RAG (Priority 3) must be cut for time, that is
a logged conscious decision, not a side effect of running out of weeks.

---

# PART 6 — SYSTEM ARCHITECTURE

## 6.1 High-Level Architecture

```
+-----------+
|   USER    |
+-----+-----+
      |
      v
+-----+------+
| PIP CLIENT |
| CLI (P1-5) |
| Web (P8)   |
| Flutter(P8+|
+-----+------+
      |
      v (WebSocket for chat, REST for CRUD)
+-----+------------------+
|       FASTAPI BACKEND   |
|   (localhost, Phase 2+) |
+-----+------------------+
      |
+-----+-------------------+--------+----------+
|                          |        |          |
v                          v        v          v
14-STAGE PIPELINE    MEMORY/DB   CHROMADB   PROVIDERS
(core intelligence)  (SQLCipher) (RAG only) (Ollama+)
```

## 6.2 Three-Layer Memory Model

```
PERSONAL LAYER
├── identity          (immutable — name, language, timezone)
├── skill_memory      (measurable — performance signals)
├── preference_memory (subjective — explicit + behavioral)
├── goal_memory       (temporal — decays after 14 days inactive)
└── interaction_style (gated — evolves with confirmation)

PROJECT LAYER
├── active_projects       (gated)
├── decision_log          (manual Phase 1, Observer Phase 7)
├── session_snapshot      (JSON — observer-written at session end)
├── topic_interests       (observer-writable, Phase 7+)
└── document_access_patterns (observer-writable, Phase 7+)

KNOWLEDGE LAYER
├── ChromaDB vector store (RAG — derived, rebuildable, NEVER authoritative)
├── preferred_tools       (observer-writable)
└── decision_fts          (FTS5 virtual table for decision search)
```

## 6.3 Hardware Constraints [VERIFIED]

- GPU: RTX 4060, 8GB VRAM
- llama3.1:8b Q4_K_M: ~4.9GB VRAM — main generation model AND Observer (ADR-033, supersedes B1)
- phi3:mini Q4_K_M: ~2.2–2.4GB VRAM — retained only as a candidate model for a future ML-based
  Intent Classifier (B4 currently keeps Intent Classifier as keyword/regex, not generative;
  phi3:mini is not used anywhere in the pipeline today)
- No model-swap orchestration between Observer and generation: both roles run the same
  llama3.1:8b weights, so there is no VRAM-overrun window and no forced cold reload between
  session-end (Observer) and next-session generation
- sentence-transformers (RAG embeddings): CPU-only by default to preserve GPU headroom
- Model-swap benchmark: RETIRED (ADR-033) — no swap exists to benchmark. See ADR-033
  A/B test timing instead (phi3:mini 58.05s vs llama3.1:8b 130.92s, cold-load included,
  n=1 synthetic transcript) for the numbers that replaced it.

---

# PART 7 — 14-STAGE MESSAGE PIPELINE [LOCKED]

```
User Message
     |
     v
[STAGE 0] Gap Detector
  Input:  session_snapshot.json timestamp (Orchestrator must parse the ISO string via datetime.fromisoformat() handling 'Z' suffix before calling gap_detector.run())
  Output: warm_start_level (none|brief|summary|full)
          context_depth_modifier (0-3)
  Gap table:
    < 1 hour        → none, 0
    1 to < 24 hours → brief, 1
    24h to 7 days   → summary, 2  (continuous at 24h, inclusive of exactly 7 days)
    > 7 days        → full, 3
  Failure: none/0, logged, never blocks pipeline
     |
     v
[STAGE 1] Intent Classifier
  Input:  user message, warm_start_level
  Output: category, retrieval_hint, skip_rag (bool)
  Categories: general_knowledge, technical_explanation,
              project_question, personal_question,
              coding_question, research_request,
              external_information, project_continuation
  skip_rag = true when: category = general_knowledge OR
             technical_explanation AND confidence >= 0.9
             AND no project-specific terms detected
  NOTE: Two distinct skip_rag mechanisms:
    Mechanism 1 (skip_rag flag): keyword/token match vs
      active_projects names + decision-log keyword cache.
      This produces the skip_rag bool. Saves ~35ms.
    Mechanism 2 (ADR-002 safety net): lightweight
      title-only embedding pre-check. Runs regardless
      of skip_rag result. These are NOT the same check.
  Failure: category=general_knowledge, skip_rag=false
     |
     v
[STAGE 2] Router
  Input:  category, skip_rag, retrieval_hint, warm_start_level
  Output: ordered retrieval priority list, provider preference
  NOTE: Priority-orderer, not stage-skipper.
        General knowledge still gets ADR-002 pre-check.
  Failure: default LLM-only path, log decision
     |
     +-------+-------+
     |       |       |   (asyncio.gather — parallel)
     v       v       v
  [S3]    [S4]    [S5]
  Dec.    Mem.    RAG+
  Log     Look    Conf
  Look    up      lict
  up              check
     |       |       |
     +-------+-------+
             |
             v
[STAGE 6] Web Search (fires in background thread at Stage 1 detection)
  Trigger keywords: latest, today, current, news, price, who won,
                    recent, weather, right now
  Cache TTL: 3600s
  Failure: return empty, note in response
             |
             v
[STAGE 7] Context Assembly
  Token Budget (6000 total):
    System instructions:   150  (fixed)
    User profile:          400  (selective only)
    Session snapshot:      250  (pre-built by Observer)
    Decision Log entries:  600  (matched entries)
    RAG chunks:            800
    Web results:           800  (top 3)
    Conversation history:  1000 (rolling window)
    User message:          400
    Reserved for response: 2000
  Overflow priority (what gets dropped first):
    1. User message (never drop)
    2. Decision Log entries
    3. Profile fields
    4. RAG chunks
    5. Session snapshot
    6. Conversation history (oldest first)
    7. Web results
  Failure: minimal prompt = system + message only
             |
             v
[STAGE 8] Provider Gate
  if is_cloud AND (NOT user_consented OR revoked) → HARD STOP
  if is_cloud AND consented → check consent_scope
  if not is_cloud → proceed
  Failure: config missing → Ollama local, log warning
             |
             v
[STAGE 9] LLM Streaming
  Streams token by token via BaseLLMProvider.chat()
  stage_hint events sent via WS during processing:
    decision_log_hit, web_search_used, cache_hit, model_loading
  model_loading: true whenever llama3.1:8b must be cold-loaded (e.g. first
    message after Ollama's keep_alive has evicted it) — no longer a two-model
    swap signal post-ADR-033, but still needed: a cold load is still real
    wall-clock time the user would otherwise perceive as a silent hang
  Failure: try next local provider, never cloud without consent
             |
             v
[STAGE 10] Response Delivery
  User receives output. Main pipeline complete.
  All learning happens AFTER this stage.
             |
       [10-min idle OR process exit]
             |
             v
[STAGE 11] Observer (async thread, session-end only)
  Single-pass analysis of full session transcript
  Model: llama3.1:8b (ADR-033, supersedes B1 — always LOCAL, never inherits
    the active generation provider; moot while v1.0 is local-only, but the
    boundary must still be enforced explicitly, not assumed)
  Output (three simultaneously):
    memory_candidates: [{target_table, field_name, proposed_value, label,
                         evidence_count, evidence_text}]
    decision_candidates: [{decision_text, signals_found, raw_quote}]
    session_snapshot: {topic, open_problems, last_decisions,
                       suggested_next_step, snapshot_date}
  session_snapshot → written to data/session_snapshot.json immediately
  memory_candidates + decision_candidates → Stage 12
  Non-negotiable rules:
    NEVER self-scores confidence (labels explicit|inferred only)
    NEVER writes directly to any store
    NEVER runs per-message
    NEVER detects document-decision conflicts (Stage 5 job)
  Failure: profile unchanged, snapshot not updated
             |
          +--+--+
          |     |
          v     v
       Memory  Decision
       Cands   Cands
          |     |
          v     v
[STAGE 12] Validation Layer
  Tier 1 (rule-based, always runs):
    Immutable field violation    → HARD_REJECT
    Forbidden schema key         → HARD_REJECT
    Evidence below threshold     → DISCARD
    Gated field                  → REQUIRES_CONFIRMATION
    Behavioral override trigger  → PROMPT_RECONCILIATION
    High-confidence conflict     → TIER_2_REQUIRED
  Tier 2 (small model, only when Tier 1 returns TIER_2_REQUIRED):
    Same field exists at confidence > 0.7 AND Tier 1 did not reject
  Tiered thresholds by profile age:
    Weeks 1–2:  evidence >= 1, explicit label required
    Weeks 3–4:  evidence >= 2
    Month 2+:   evidence >= 3, confidence >= 0.7
  REQUIRES_CONFIRMATION → written to memory_candidates_pending
  (survives session close, picked up next session)
  Failure: reject all candidates (safe failure)
             |
             v
[STAGE 13] Profile + Decision Log Update (parallel writes)
  Only validated, approved candidates write
  Gated field writes wait for user confirmation
  user_verified writes get maximum confidence
  All writes go through memory/ modules only
  Failure: retry once, then log and discard, never corrupt
```

## 7.0a Pipeline Failure Mode Conventions (Fail-Open vs Fail-Closed)

Two deliberately different failure policies exist in the pipeline. This note records the reasoning so future stages are implemented consistently.

**Stage 0 (Gap Detector) — Fail-Open**
Returns `warm_start_level=none`, `context_depth_modifier=0`, logs the error, and never blocks the pipeline. Rationale: Stage 0's only output is a context-scaling signal — how much session history to inject into the prompt. If it fails (missing `session_snapshot.json`, corrupt timestamp, filesystem error), the pipeline degrades to a cold-start: the user gets a correct answer with slightly less conversational continuity. No security property, no privacy guarantee, and no data integrity invariant depends on Stage 0 succeeding. Blocking the entire pipeline over a missing warm-start signal would trade a recoverable UX degradation for a hard user-visible failure — a strictly worse outcome in every case.

**Stage 8 (Provider Consent Gate) — Fail-Closed**
Hard-stops the pipeline if the provider row is missing, `user_consented = 0`, or `revoked = 1`. Rationale: Stage 8 enforces a privacy guarantee — data must not leave the device and reach a cloud provider without the user's explicit, recorded consent. If Stage 8 has any doubt about consent status, the correct answer is never "proceed anyway." The cost of a false positive (user must grant consent before the call proceeds) is a one-time friction event. The cost of a false negative (a cloud call goes out without consent) is a privacy violation that cannot be undone. The asymmetry of consequences mandates fail-closed. The unknown-provider case (no row at all) is treated identically to unconsented: fail-closed, not fail-open, because allowing an unregistered provider through would silently break the guarantee every time a new provider is added before its consent row is seeded.

**Convention for future stages:**
- A stage's failure mode is **fail-open** if the pipeline can produce a correct, safe result without that stage's output (context, hints, ranking signals, cache hits).
- A stage's failure mode is **fail-closed** if skipping the stage could violate a privacy guarantee, a data integrity invariant, or a constitutional constraint.
- Stages 9–13 default to fail-open unless they enforce a constitutional check (e.g. Stage 12 Validation Layer already uses `HARD_REJECT` for immutable field violations — that is fail-closed behaviour within the stage, but the stage itself runs).

## 7.1 Response Cache

```
Position: Between Stage 2 Router and Stage 7 Context Assembly
Key:      hash(normalized_message + active_project_id)
TTL by category:
  general_knowledge:     86400s
  technical_explanation: 86400s
  web_search:             3600s
  project_question:          0 (never cache)
  personal_question:         0 (never cache)
  decision_lookup:           0 (never cache)
Authority: Lowest in hierarchy. Decision Log always overrides.
```

## 7.2 Stage 3: Decision Log Lookup

```
Input:  retrieval_hint
Output: matching active entries (state=active only)
Search: FTS5 MATCH query (LIKE fallback if FTS5 unavailable)
Failure: return empty, continue
```

## 7.3 Stage 4: Memory Lookup

```
Input:  category, retrieval_hint
Output: relevant profile fields only (NEVER full profile dump)
Access: via profile_store.py only
Failure: return empty profile fields, continue
```

## 7.4 Stage 5: RAG Retrieval + Conflict Check

```
Input:  retrieval_hint, document-paste flag from Router
Output: relevant chunks above threshold
        conflict flag if document vs Decision Log conflict
Threshold: Start 0.6, calibrate from 100 real interactions
Conflict detection: runs HERE, not in Observer
Failure: return empty chunks, continue
```

---

# PART 8 — MEMORY ARCHITECTURE

## 8.1 Three-Way Memory Split [LOCKED — separate validation per type]

```
SKILL MEMORY
  What:    Measurable capability levels (0.0 to 1.0)
  Updates: Demonstrated task performance
  Decay:   None
  Schema:  skill_memory table
  Confidence: GENERATED ALWAYS (formula-derived from evidence_count + source_label)

PREFERENCE MEMORY
  What:    Subjective work and communication preferences
  Updates: Explicit statements OR behavioral patterns (3+ sessions, 14+ days)
  Decay:   None (behavioral override instead)
  Schema:  preference_memory table
  Confidence: GENERATED ALWAYS (same formula)

GOAL MEMORY
  What:    Stated objectives and intentions
  Updates: Conversational commitment language
  Decay:   Automatic — decay_flag=true after 14 days inactive
  Schema:  goal_memory table (NOTE: when reading/writing via candidate APIs, field_name uses the convention "goal:<id>")
  Confidence: STORED MANUALLY (decay adjusts it independently of evidence_count)
```

These three types MUST NOT share validation logic. Separate ConstitutionEnforcer
rule branches for each type.

## 8.2 Confidence Formula [LOCKED]

```
Observer labels candidates as: explicit | inferred

Base scores:
  explicit  → 0.9
  inferred  → 0.4
  (user_verified, user_correction also use 0.9 base when written)

Formula:
  confidence = base_score * min(evidence_count, 5) / 5.0

Examples:
  explicit,  1 session  = 0.9 * 0.20 = 0.18
  explicit,  3 sessions = 0.9 * 0.60 = 0.54
  explicit,  5 sessions = 0.9 * 1.00 = 0.90
  inferred,  5 sessions = 0.4 * 1.00 = 0.40

For skill_memory, preference_memory, interaction_style:
  Implemented as SQLite GENERATED ALWAYS AS ... STORED column.
  Never compute or update manually — the DB recomputes on every write.

For goal_memory:
  confidence is a plain STORED column.
  Reason: decay reduces confidence independently of evidence_count.
  Stage 13 decay logic adjusts it directly.
  A generated column cannot express this pattern.
```

## 8.3 Memory Source Trust Hierarchy [ADR-021, LOCKED]

When sources conflict, this order is absolute:

```
1. User correction           (explicit in-session override)
2. Explicit stated preference ("I prefer X")
3. Repeated behavioral pattern (3+ sessions, 14+ days)
4. Single-session inference   (lowest authority)

Recency alone does not win.
Confidence score alone does not win.
```

## 8.4 Behavioral Override Mechanism

```
Trigger: Behavioral evidence contradicts a stated preference
         for 3+ sessions over 14+ consecutive days.

Result: PROMPT_RECONCILIATION
  "Your behavior suggests X. You stated Y. Which is correct?"

Options:
  User confirms new → user_correction write, maximum confidence
  User confirms old → discard, contradiction logged

Never: silent overwrite of an explicit preference.
Never: automatic update after 3 sessions without user review.
```

## 8.5 Memory Verification Loop

Every 30 sessions (`total_sessions % 30 == 0`):
- Surface 3 randomly sampled profile fields
- User confirms, corrects, or removes each
- `user_verified` writes get maximum confidence, override Observer-derived values
- `/verify` command triggers on demand (for testing and thesis defense demo)
- Production loop fires automatically at the 30-session threshold

## 8.6 Memory Lifecycle

```
Signal detected by Observer
         |
         v
CANDIDATE CREATED (explicit | inferred label)
         |
         v
STAGE 12 VALIDATION
  Immutable?      → HARD_REJECT
  Forbidden key?  → HARD_REJECT
  Below threshold?→ DISCARD
  Gated field?    → REQUIRES_CONFIRMATION (written to memory_candidates_pending)
  Override trigger? → PROMPT_RECONCILIATION
  Conflict >0.7?  → TIER_2_REQUIRED (small model check)
         |
         v
[USER CONFIRMATION if gated]
         |
         v
STAGE 13 WRITE
  source_label: explicit|inferred|user_verified|user_correction
         |
         v
REINFORCEMENT (evidence_count increments on repeat observations)
         |
         v
DECAY CHECK (goal_memory only — 14 days inactive → decay_flag=true)
         |
         v
SOFT DELETE (never hard delete for profile fields or Decision Log)
```

## 8.7 Decision Log Details

```
Phase 1 write path: MANUAL ONLY via /decide command.
Populate 20–30 manual decisions before any automation.

Classification uses OR logic (not AND):
  Signal A: explicit_reasoning_in_conversation
  Signal B: commitment_language
  Signal C: alternative_considered

  A + B + C → confidence 1.0 → auto-logged
  Any two   → confidence 0.7 → auto-logged
  Any one   → confidence 0.4 → auto-logged (manual trigger)
  None      → confidence 0.0 → decision_candidates_pending

Log thresholds by source [LOCKED]:
  manual /decide:           log_threshold = 0.4 (any one signal)
  Observer-detected:        log_threshold_observer = 0.7 (two+ signals)
  Observer single-signal:   → decision_candidates_pending (not auto-logged)
  Reason: avoids noise from casual commitment language in Observer output

Both keys defined in settings.json from Phase 0 with activation comments.
log_threshold_observer is INACTIVE until Phase 7 (Observer ships).

Decision candidates pending surface order [LOCKED]:
  ORDER BY confidence ASC, created_at ASC
  (lowest-evidence oldest candidates first — most likely wrong, most
   worth culling. High-evidence candidates are closest to auto-log
   threshold and need less review. NOT pure oldest-first.)

Pending candidate 60-day aging:
  Surfaced max 3 per session. Prompt shown once.
  "This pending decision is aging. Promote, dismiss, or keep?"
```

---

# PART 9 — CONSTITUTIONAL SYSTEM [LOCKED — file not yet written]

## 9.1 constitutional.json Structure

```json
{
  "version": "1.0",
  "changelog": [
    {"version": "1.0", "date": "2026-06",
     "reason": "Initial constitution — locked before Observer build"}
  ],
  "immutable_fields": {
    "fields": ["name", "language_preference", "timezone"],
    "enforcement": "hard_reject"
  },
  "gated_fields": {
    "fields": ["interaction_style.*", "goal_memory.*",
               "active_projects.*", "skill_memory.*.level"],
    "enforcement": "prompt_confirm"
  },
  "observer_may_write": {
    "fields": ["topic_interests",
               "preferred_tools", "document_access_patterns"]
  },
  "forbidden_categories": {
    "enforcement": "hard_reject",
    "exception": "onboarding_bootstrap"
  },
  "onboarding_bootstrap": {
    "bypasses": ["observer", "validation"],
    "permitted_writes": "any_non_forbidden_field",
    "deactivates": "permanent_after_onboarding_complete"
  },
  "memory_types": {
    "skill_memory":      {"validation": "demonstrated_performance"},
    "preference_memory": {"validation": "explicit_or_behavioral"},
    "goal_memory":       {"validation": "commitment", "decay": true}
  },
  "validation_thresholds": {
    "week_1_2":     {"evidence": 1, "requires": "explicit_label"},
    "week_3_4":     {"evidence": 2},
    "month_2_plus": {"evidence": 3, "confidence": 0.7}
  },
  "confidence_model": {
    "explicit": 0.9,
    "inferred": 0.4,
    "formula":  "base * min(evidence_count, 5) / 5"
  },
  "behavioral_override": {
    "trigger_sessions": 3,
    "trigger_days": 14,
    "action": "prompt_reconciliation"
  },
  "decision_log": {
    "write_path_phase_1": "manual_only",
    "logic": "OR",
    "confidence": {"all_three": 1.0, "any_two": 0.7, "any_one": 0.4},
    "log_threshold_manual": 0.4,
    "log_threshold_observer": 0.7
  },
  "provider_consent": {
    "scope_values": ["full_inference", "web_search_only",
                     "embedding_only", "none"],
    "gate_position": "stage_8_before_network_call",
    "enforcement": "hard_stop"
  },
  "proactive_triggers": {
    "allowed": ["session_gap_exceeds_48h",
                "document_decision_conflict_detected",
                "goal_inactive_14_days"],
    "forbidden": ["model_judgment_of_relevance",
                  "model_judgment_of_urgency"]
  },
  "memory_verification": {
    "frequency_sessions": 30,
    "fields_sampled": 3,
    "authority": "overrides_observer_derived"
  },
  "amendment_process": {
    "on_change": "bump version, add changelog entry",
    "on_startup": "check profile.constitution_version vs current"
  }
}
```

## 9.2 ConstitutionEnforcer Class

```python
class ConstitutionEnforcer:
    def __init__(self, constitution_path: str):
        self.rules = load_json(constitution_path)

    # Note: override check precedes threshold check — this order is deliberate and was the subject of a fixed Phase 1 defect. Do not reorder.
    def validate(
        self,
        candidate: MemoryCandidate,
        existing_field: Optional[ExistingFieldState],
        profile_age_weeks: int
    ) -> ValidationResult:

        field = candidate.field_name  # table-qualified, e.g. "preference_memory.x"

        if field in self.rules["immutable_fields"]["fields"]:
            return ValidationResult.HARD_REJECT("immutable_field")

        if not self._is_writable_field(field) and not onboarding_active():
            return ValidationResult.HARD_REJECT("schema_violation")

        # Override check MUST precede threshold check.
        if self._triggers_override(candidate, existing_field):
            return ValidationResult.PROMPT_RECONCILIATION

        threshold = self._get_threshold(profile_age_weeks)
        confidence = self._compute_confidence(candidate)

        if not threshold.passes(candidate, confidence):
            return ValidationResult.DISCARD

        if self._matches_gated_field(field):
            return ValidationResult.REQUIRES_CONFIRMATION

        if self._conflicts_with_existing(candidate, existing_field):
            return ValidationResult.TIER_2_REQUIRED

        return ValidationResult.APPROVED

    def _compute_confidence(self, candidate: MemoryCandidate) -> float:
        base = 0.9 if candidate.label in (
            "explicit", "user_verified", "user_correction"
        ) else 0.4
        return base * min(candidate.evidence_count, 5) / 5.0
```

ValidationResult values and meanings:
```
HARD_REJECT           — immutable field or schema violation (blocked, never written)
DISCARD               — below threshold (not an error, not written)
REQUIRES_CONFIRMATION — gated field (written to memory_candidates_pending, surfaced next session)
PROMPT_RECONCILIATION — behavioral override triggered (surfaced for user decision)
TIER_2_REQUIRED       — conflict with high-confidence existing field (small model called)
APPROVED              — passes all checks (written to profile)
```

**Constitution must be written and all ConstitutionEnforcer tests must pass BEFORE
Observer is built. This is the one hard technical dependency in the entire project (ADR-011).**

---

# PART 10 — SECURITY ARCHITECTURE (UPDATED — replaces all Fernet references)

## 10.1 Encryption Model [EMPIRICALLY VERIFIED]

**Previous design (OBSOLETE, do not reference):**
~~Fernet symmetric encryption per-file with PBKDF2 key derivation~~

**Current design (FINAL):**

```
User types password at app launch
         |
         v
App-level PBKDF2 derives a 256-bit hex key
  Salt: stored on disk in salt.bin (not secret — salt is never secret)
  Held in process memory only for the session lifetime
  Discarded on exit — re-derived every launch
         |
         v
SQLCipher whole-database transparent encryption
  KDF: PBKDF2_HMAC_SHA512 [EMPIRICALLY VERIFIED: confirmed twice]
  Iterations: 256,000 [EMPIRICALLY VERIFIED]
  All tables encrypted as one unit
  No per-file keys, no per-row keys
         |
         v
Each connection opens with raw-hex key syntax:
  PRAGMA key = "x'<hexkey>'"
  (skips SQLCipher's redundant internal KDF pass on the hot path)
         |
         v
Key discarded on process exit
No recovery if password is forgotten — by design.
```

**No recovery mechanism is a feature, not a limitation.** Forgotten password = permanent
profile loss. This is the privacy guarantee. The onboarding flow warns users explicitly
and prompts them to create a backup within the first week.

## 10.2 Backup Export Mechanism [FINALIZED, EMPIRICALLY VERIFIED]

```
/export command:
  1. PRAGMA wal_checkpoint(TRUNCATE)  — defense-in-depth (proven non-load-bearing
                                        for sqlcipher_export() path, but retained
                                        as free protection for any future raw-copy
                                        backup method)
  2. User types a separate backup password (different from live DB password)
  3. ATTACH DATABASE 'backup.pipbak' AS backup KEY '<user-password>'
     NOTE: Backup key uses passphrase syntax (not raw-hex) because it is a one-time
     operation and the full internal KDF pass is an acceptable cost here.
  4. SELECT sqlcipher_export('backup')
  5. DETACH DATABASE backup
  6. .pipbak file delivered to user

Why sqlcipher_export() via ATTACH, not decrypt-then-Fernet-wrap:
  - One encryption technology end to end
  - No plaintext intermediate state (even in memory)
  - Fernet is not a dependency in this codebase at all
  - Separate backup password means live-key compromise does not
    compromise backups

EMPIRICALLY VERIFIED (sandbox test):
  - Generated columns (GENERATED ALWAYS AS STORED) survive
    sqlcipher_export() correctly [tested, confidence recomputed in backup]
  - WAL-resident data (written but not checkpointed) also survives
    sqlcipher_export() without an explicit checkpoint [tested, WAL file
    was >20KB, backup contained the unckeckpointed row]
  - PRAGMA wal_checkpoint(TRUNCATE) is therefore defense-in-depth,
    not the primary mechanism — sqlcipher_export() reads through the
    SQLite page layer, not raw file bytes
```

## 10.3 Connection Setup [LOCKED — single call site: profile_store.py get_connection()]

```python
def get_connection(db_path: str, db_key: str) -> sqlcipher3.Connection:
    # db_key must be a hex string. Enforced:
    assert re.fullmatch(r'[0-9a-fA-F]+', db_key), \
        "db_key must be hex-encoded"

    conn = sqlcipher3.connect(db_path)
    conn.execute(f"PRAGMA key = \"x'{db_key}'\"")  # 1st — must be first
    conn.execute("PRAGMA foreign_keys = ON")         # 2nd — not default in SQLite
    conn.execute("PRAGMA journal_mode = WAL")         # 3rd — concurrent reads
    conn.execute("PRAGMA busy_timeout = 5000")        # 4th — writer queuing
    return conn
```

**Why each PRAGMA is necessary:**

| PRAGMA | Why |
|---|---|
| key (1st) | SQLCipher unlock. Must be first — wrong order = empty DB |
| foreign_keys (2nd) | SQLite does NOT enforce FK by default. Must be explicit |
| journal_mode WAL (3rd) | Readers don't block writers |
| busy_timeout (4th) | Writer collisions wait 5s instead of throwing SQLITE_BUSY |

WAL mode and busy_timeout together make dropping `asyncio.Lock()` safe:
WAL prevents reader/writer blocking. busy_timeout prevents writer-vs-writer exceptions.
SQLite still serializes writes — busy_timeout makes that safe to ignore at app level.

**Wrong-key behavior (critical to test):** A wrong PRAGMA key does NOT throw an exception.
SQLite silently presents an empty database. Required test: open with wrong key,
`SELECT count(*) FROM sqlite_master` — must fail loudly.

## 10.4 Threat Model (Updated)

**T1 — Encryption Key / Database Compromise [UPDATED for SQLCipher]**
- Threat: Attacker gains filesystem access to the SQLCipher database file
- Mitigations:
  - SQLCipher AES-256, PBKDF2_HMAC_SHA512, 256,000 iterations [verified]
  - PRAGMA key is mandatory first connection statement, single call site
  - Wrong key returns empty DB silently — test explicitly (see Phase 0 tests)
  - Live session hex key held in process memory only, never written to disk
  - Backup export uses separate backup password (live-key compromise ≠ backup compromise)
- Residual: Attacker with both filesystem access AND correct key = full access
  (equivalent to account compromise — outside scope for single-user local app)

**T2 — Prompt Injection**
- Threat: Malicious content in documents or user input influences memory writes
- Mitigations:
  - ConstitutionEnforcer at Validation Layer (not LLM judgment)
  - Memory writes never from LLM output alone — Observer → Validation required
  - Provider Gate enforced in code
- Residual: Session-level influence possible. Memory write without Validation: impossible.

**T3 — Corrupted Embeddings**
- Threat: Malicious document chunks influence retrieval
- Mitigations:
  - Local filesystem ingestion only
  - Similarity threshold gating
  - RAG output is read-only context (cannot write to profile)
- Residual: User deliberately ingesting malicious docs — out of scope

**T4 — Profile Tampering [UPDATED for SQLCipher]**
- Threat: Direct filesystem manipulation of database
- Mitigations:
  - Encrypted at rest — edits without key produce corruption, not valid data
  - PRAGMA foreign_keys = ON — referential violations rejected at DB level
  - constitution_version checked on every startup
  - Append-only contradiction logs provide tamper evidence
  - decision_text immutability enforced at DB level via BEFORE UPDATE trigger
    (`RAISE(ABORT, 'decision_text is write-once and cannot be modified')`)
- Gap closed: decision_text immutability trigger confirmed working in schema test
- Residual: Attacker with key = equivalent to full application access

**T5 — Accidental Cloud Leakage**
- Threat: Data sent to cloud without user knowledge
- Mitigations:
  - Stage 8 Provider Gate: HARD STOP if is_cloud AND (NOT user_consented OR revoked)
  - No silent fallback to cloud
  - Per-provider consent objects with scope control
- Residual: Zero if Provider Gate correctly implemented

**T6 — Observer Profile Corruption**
- Threat: Observer produces incorrect candidates that corrupt profile
- Mitigations:
  - Observer never writes directly
  - Multi-tier Validation Layer
  - Behavioral override requires reconciliation
  - 30-session verification loop provides external ground truth
- Residual: Slow drift if user never engages with verification prompts

---

# PART 11 — STORAGE ARCHITECTURE [FINALIZED after 5 review rounds + empirical testing]

## 11.1 Storage Technology Decisions

| Data | Storage | Reason |
|---|---|---|
| User profile (all memory types) | SQLite via SQLCipher | Encrypted, relational, atomic, auditable |
| Decision log | SQLite via SQLCipher | Same — queryable by state, project, FTS5 |
| Provider consent | SQLite via SQLCipher | Auditable, durable |
| Trace log | SQLite via SQLCipher | Queryable by status, trace_id |
| Pending candidates | SQLite via SQLCipher | Durable across session close |
| Session continuity | JSON (session_snapshot.json) | Single overwritten object, ~5ms load |
| Constitutional rules | JSON (constitutional.json) | Human-readable config, not transactional |
| Application settings | JSON (settings.json) | Human-editable config |
| Document embeddings | ChromaDB | RAG index only — derived, rebuildable |

**ChromaDB is NEVER authoritative.** If ChromaDB drifts from SQLite, rebuild from SQLite
at startup. ChromaDB down = RAG unavailable, system continues normally without it.

## 11.2 Storage Ownership Table [LOCKED]

One module owns each resource. All others are callers, never raw SQL writers.
ADR-025 pre-commit hook enforces this.

| Table(s) | Owner Module | Callers |
|---|---|---|
| `skill_memory`, `skill_contradiction_log` | `memory/profile_store.py` | Stage 13 |
| `preference_memory`, `preference_contradiction_log` | `memory/profile_store.py` | Stage 13 |
| `goal_memory` | `memory/profile_store.py` | Stage 13 |
| `interaction_style`, `interaction_style_history` | `memory/profile_store.py` | Stage 13 |
| `identity`, `profile_meta`, `active_projects` | `memory/profile_store.py` | Onboarding, Stage 13 |
| `decision_log`, `decision_fts` | `memory/decision_log.py` | Stage 3 (read), Stage 13 (write) |
| `decision_candidates_pending` | `memory/candidate_store.py` | Stage 11 Observer (create), decision_log.py (/pending cmds) |
| `memory_candidates_pending` | `memory/candidate_store.py` | Stage 12 (create), Stage 13 (resolve) |
| `provider_consent` | `memory/profile_store.py` | Stage 8 Provider Gate (read) |
| `trace_log` | `core/trace.py` | All stages (write) |
| `topic_interests`, `preferred_tools`, `document_access_patterns` | `memory/profile_store.py` | Stage 11 Observer (write, Phase 7+) |
| ChromaDB | `memory/vector_store.py` | Stage 5 RAG (read), /ingest (write) |
| `documents` | `memory/vector_store.py` | Stage 5 (indirect, via ChromaDB), /ingest /documents /remove (write); source-of-truth registry for ChromaDB rebuild-on-drift |
| `pending_observer` | `memory/pending_observer.py` | Stage 11 Observer (enqueue, Phase 7+), startup drain (before Stage 0) |
| `session_snapshot.json` | `memory/session_snapshot.py` | Stage 0 (read), Stage 11 (write) |
| `constitutional.json` | Read-only after creation | ConstitutionEnforcer |
| `settings.json` | Read-only at runtime | `config/settings.py` canonical loader |

## 11.3 Complete Schema Summary

21 tables, 7 views, 1 trigger (validated against real SQLCipher; `documents` added in Phase 6, `pending_observer` added by ADR-033, see below):

**Profile tables:**
- `profile_meta` — session count, version fields, first/last session dates
- `identity` — name, language, timezone (immutable, single-row via CHECK id=1)
- `skill_memory` — levels + generated confidence
- `skill_contradiction_log` — append-only FK to skill_memory.id
- `preference_memory` — values + generated confidence + behavioral_signal_count
- `preference_contradiction_log` — append-only FK to preference_memory.id
- `goal_memory` — confidence STORED (decay-managed), decay_flag, status
- `interaction_style` — single-row (CHECK id=1), generated confidence
- `interaction_style_history` — previous values on change
- `active_projects` — project_id (UUID4), name, description, status

**Decision tables:**
- `decision_log` — write-once decision_text (trigger enforces), state only mutable field
- `decision_fts` — FTS5 virtual table (decision_text, reasoning, alternatives_considered UNINDEXED decision_id)
- `decision_candidates_pending` — low-confidence candidates awaiting review

**Memory candidate pending:**
- `memory_candidates_pending` — gated memory candidates surviving session close

**System tables:**
- `provider_consent` — per-provider flags (user_consented + revoked separate)
- `trace_log` — status + error_detail columns, 3 indexes
- `pending_observer` (ADR-033) — crash-safety queue for Observer passes that can't
  finish before process exit. status: pending → processing → completed/failed.
  Drain query includes 'processing' rows, not just 'pending' — a row stuck in
  'processing' means a previous drain itself crashed, which must be retried, not
  ignored. Never hard-deleted (ADR-024).

**Knowledge layer:**
- `documents` (Phase 6) — SQLite source-of-truth registry for what's ingested into
  ChromaDB: file_path, content_hash (staleness detection), chunk_count, status.
  Not chunk text — ChromaDB holds that. Unique index on file_path where active.

**Observer-may-write (defined Phase 0, populated Phase 7):**
- `topic_interests`
- `preferred_tools`
- `document_access_patterns`

**Soft-delete views (query through these, never base tables):**
- `active_skills`, `active_preferences`, `active_goals`
- `active_topics`, `active_tools`, `active_document_patterns`, `active_documents`

**Critical schema design decisions:**

| Decision | What | Why |
|---|---|---|
| confidence GENERATED | skill/preference/interaction_style | Prevents sync bugs between evidence_count and confidence |
| goal_memory.confidence STORED | goal_memory only | Decay adjusts confidence independently of evidence_count |
| CHECK(id=1) on identity and interaction_style | Single-row enforcement | DB-level, not convention |
| INSERT OR REPLACE for single-row tables | All writes to identity/interaction_style | The only safe write pattern |
| Surrogate id on skill/preference (not name) | FK targets | String PKs create join drift |
| decision_text BEFORE UPDATE trigger | decision_log | DB-level write-once enforcement |
| alternatives_considered preprocessed to space-separated | FTS5 insert | Raw JSON tokenizes as JSON not content |
| profile_age_weeks NOT stored | profile_meta | Computed from first_session_date at call time |
| FTS5 fallback = LIKE inside encrypted DB | If FTS5 unavailable | Unencrypted shadow index violates T1 |
| decision_candidates_pending ORDER BY confidence ASC, created_at ASC | Surface order | Low-evidence oldest = most likely wrong |
| documents stores metadata only, not chunk text | documents table | ChromaDB is the only place chunk text lives - keeps the split clean (SQLite = registry, Chroma = index) |
| ingest_document() force= param | vector_store.py | Hash-match shortcut would silently no-op during a rebuild-from-drift, which exists specifically to fix cases where the file didn't change but ChromaDB did |

---

# PART 12 — OBSERVER ARCHITECTURE

## 12.1 Non-Negotiable Rules

```
Rule 1: Labels candidates explicit or inferred. NEVER assigns confidence scores.
Rule 2: Produces candidates only. NEVER writes to any store directly.
Rule 3: Runs at session end only (10-min idle OR process exit). NEVER per-message.
Rule 4: Uses llama3.1:8b, same model as generation (ADR-033, supersedes B1).
        MUST be pinned to a LOCAL provider — never inherits the active
        generation provider, even though v1.0 being local-only currently
        makes this structurally moot.
Rule 5: Does NOT detect document-decision conflicts. That is Stage 5's job.
```

## 12.2 Extraction Prompt Structure

```
SYSTEM:
  You are an information extraction assistant. Your only job is to analyze
  a conversation and extract structured signals from it.
  Produce valid JSON only. No commentary. No explanation.

RULES:
  - Label each candidate "explicit" if user directly stated it.
  - Label "inferred" if you observed it from behavior.
  - Do NOT assign confidence scores. Label type only.
  - Do NOT create fields outside the approved list.
  - Do NOT include emotional state, mood, or psychological signals.
  - If uncertain, omit. Never guess.

APPROVED MEMORY FIELDS (target_table: [field_name, ...]):
  skill_memory: [python_level, docker_level, ...]
  preference_memory: [preferred_tools, answer_style, ...]
  goal_memory: [active_goals, project_objectives]
  observer_writable: [topic_interests, preferred_tools, document_access_patterns]  # NOTE: Must exactly match Part 9.1 observer_may_write.fields list

OUTPUT FORMAT:
{
  "memory_candidates": [
    {
      "target_table": "preference_memory",
      "field_name": "preferred_tools",
      "proposed_value": "Neovim",
      "label": "explicit",
      "evidence_count": 1,
      "evidence_text": "the exact quote or paraphrase this was drawn from"
    }
  ],
  "decision_candidates": [
    {
      "decision_text": "one sentence stating the decision",
      "signals_found": ["explicit_reasoning_in_conversation", "commitment_language", "alternative_considered"],
      "raw_quote": "the exact quote this was drawn from"
    }
  ],
  "session_snapshot": {
    "topic": "one sentence",
    "open_problems": [],
    "last_decisions": [],
    "suggested_next_step": "one concrete next action"
  }
}
```

**Found by ADR-033's A/B test, not by inspection:** earlier versions of this spec never told the model to emit `target_table`, matching the exact key names `MemoryCandidate` (Part 9.2/`types.py`) requires. Neither `phi3:mini` nor `llama3.1:8b` produced schema-correct output against the old prompt — `phi3:mini` failed structurally (echoed the field-name list instead of populating candidates), `llama3.1:8b` produced real candidates but with different key names (`field`/`value`/`type` instead of `field_name`/`proposed_value`/`label`). Neither output would have parsed into Stage 12 as written. The `memory_candidates` example above is now explicit about every key Stage 12/13 actually consume.

Refine this prompt after first 50 real sessions with real data. Never fine-tune
Observer speculatively.

---

# PART 13 — PROVIDER ARCHITECTURE

## 13.1 BaseLLMProvider Interface

**Sync vs Async Integration Plan**: The `chat()` generator strictly yields synchronously (`Iterator[str]`). When integrated with the asynchronous FastAPI server layer in Stage 9 (Phase 8), calls to `chat()` will be wrapped inside `asyncio.to_thread` or `run_in_threadpool` at the call site. This isolates blocking HTTP calls from the main event loop while retaining a simpler sync interface for local non-server CLI use.

```python
from abc import ABC, abstractmethod
from typing import Iterator, Optional

class BaseLLMProvider(ABC):

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        context: Optional[str] = None,
        max_tokens: int = 2000,
        timeout_seconds: int = 30
    ) -> Iterator[str]:
        """
        Stream response tokens one by one.
        messages: list of {role: str, content: str}
        Yields: str — one token or word fragment at a time
        Raises: ProviderUnavailableError, ProviderTimeoutError
        Contract: Must yield at least one token or raise.
                  Must not return None.
                  Must not buffer all tokens before yielding.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if provider can accept requests.
        Must complete within 2 seconds. Must not raise."""

    @abstractmethod
    def get_model_info(self) -> dict:
        """Returns: {model_name, context_window, is_local, provider_id}
        Must not make network calls."""

class ProviderUnavailableError(Exception): pass
class ProviderTimeoutError(Exception): pass
```

## 13.2 Provider Consent Schema

```
provider_id    TEXT    (ollama, groq, openai, claude)
is_cloud       INTEGER (0=local, 1=cloud)
user_consented INTEGER (0=never consented, 1=consented)
consent_date   TEXT    (ISO 8601)
revoked        INTEGER (0=not revoked, 1=revoked)
revoked_date   TEXT    (ISO 8601)
consent_scope  TEXT    (full_inference|web_search_only|embedding_only|none)
```

Stage 8 gate logic: `if is_cloud AND (NOT user_consented OR revoked) → HARD STOP`

"Never consented" and "consented then revoked" are distinct states — both blocked by
the gate, but distinguishable in the audit trail and in `/providers` display.

## 13.3 Model Loading (formerly "Model-Swap Constraints" — RETIRED by ADR-033)

Observer and generation both run llama3.1:8b (ADR-033, supersedes B1). There is no
second model to swap to, no VRAM-overrun window, and no forced cold reload at the
Observer/generation boundary — both roles share the same resident weights.

- `model_loading: true` stage_hint still applies, but only for a genuine cold load
  (e.g. Ollama's `keep_alive` evicted the model after enough idle time). Same UX
  problem as before (a silent wait reads as a hang), narrower cause.
- Real timing data (ADR-033 A/B test, 2026-08-16, cold-load included, n=1 transcript):
  phi3:mini 58.05s, llama3.1:8b 130.92s. Both exceed the (never-validated) 30s
  `observer_max_seconds` target — corrected in settings.json.
- `pending_observer` crash-safety mechanism (ADR-033 condition 2) is now required
  before Phase 7 ships: an 8B pass this long cannot block SIGINT/SIGTERM.

---

# PART 14 — FRONTEND AND CLIENT ARCHITECTURE [LOCKED]

## 14.1 Client Build Order

```
Phase 2:  Thin Python CLI client
          Calls local REST API only
          Exercises all /decide, /profile, /pending, /decisions commands
          Proves REST CRUD surface before web client exists

Phase 8:  Web client (HTML/JS first)
          Must be proven before Flutter starts
          Exercises both REST (CRUD) and WebSocket (chat)

Weeks 3-4: Throwaway Flutter spike (2–3 days)
            Connects to fake echo WebSocket server
            Renders streamed tokens in Dart
            Tests async stream handling
            DISCARDED after — de-risks Dart before Phase 8

Phase 8+: Flutter client (second real client)
           Built after web client is proven
           Shares the same API surface
```

## 14.2 Transport Split [LOCKED]

```
WebSocket (/ws/chat):   ALL chat interactions (streaming required)
REST (all other):       CRUD only (/decision, /memory, /provider, /trace, /project)

REST /chat is DROPPED entirely.
Maintaining two streaming code paths (REST + WS) doubles surface area.
One streaming path (WS) proven, then reused for Flutter.
```

## 14.3 WebSocket Message Spec (manual — FastAPI does not auto-document WS)

```
Event types (server → client):
  { "type": "token",       "data": "word or fragment" }
  { "type": "stage_hint",  "data": {
      "decision_log_hit": bool,
      "web_search_used":  bool,
      "cache_hit":        bool,
      "model_loading":    bool   ← true when llama3.1:8b needs a cold load (ADR-033)
  }}
  { "type": "error",       "data": "error message string" }
  { "type": "done",        "data": null }
```

Right sidebar in web/Flutter UI shows stage_hints. Ships as static display (populated
once response completes). Live animated per-stage updates are optional polish, not budgeted.

## 14.4 UI Philosophy

Frontend has zero intelligence. All logic in PIP Core backend.
Client always goes through POST/WS to PIP Core.
Client never talks directly to DB, ChromaDB, or Ollama.

---

# PART 15 — API SPECIFICATION

## 15.1 Base URL

`http://localhost:8765/api/v1` (Phase 2+, local only)

## 15.2 Endpoints

```
CHAT (WebSocket only — no REST /chat)
  WS     /ws/chat

MEMORY
  GET    /memory/profile
  GET    /memory/profile/{field}
  POST   /memory/correct          {field, value}
  DELETE /memory/profile/{field}
  POST   /memory/reset            {confirm, backup_path}
  POST   /memory/verify           {field_id, confirmed, corrected_value?}

DECISION LOG
  POST   /decision/create         {text, reasoning?, alternatives?, project_id?}
  GET    /decision/search         ?q=&state=active&project_id=
  PATCH  /decision/{id}/state     {state, reason, superseded_by?}
  GET    /decision/pending
  POST   /decision/pending/{id}/promote
  POST   /decision/pending/{id}/dismiss

PROJECTS
  GET    /projects
  POST   /projects                {name, description}
  PATCH  /projects/{id}/status    {status}
  POST   /projects/{id}/activate

RAG
  POST   /rag/ingest              {file_path, project_id}
  POST   /rag/query               {query, project_id, threshold?}
  GET    /rag/documents
  DELETE /rag/documents/{ref}

PROVIDERS
  GET    /providers
  POST   /providers/{id}/consent  {consent_scope}
  DELETE /providers/{id}/consent

OBSERVER CANDIDATES
  GET    /observer/candidates
  POST   /observer/candidates/{id}/approve
  POST   /observer/candidates/{id}/reject

TRACE
  GET    /trace/{trace_id}
  GET    /trace/recent            ?limit=20
  DELETE /trace                   ?older_than_days=90

SYSTEM
  GET    /status
```

---

# PART 16 — ALL ARCHITECTURAL DECISION RECORDS (ADRs)

Format: **Decision | Problem | Chosen | Reason | Consequences**

---

**ADR-001 — Gap Detector as Stage 0**
Decision: Gap Detector before Intent Classifier, not inside Stage 7.
Problem: Gap affects entire pipeline behavior, not just context injection. A 10-day gap
changes routing assumptions.
Chosen: Stage 0, non-negotiable.
Consequences: (+) Gap correctly shapes all downstream behavior. (−) Adds 5–10ms.

**ADR-002 — Router as Priority-Orderer, Not Stage-Skipper**
Decision: Router sets retrieval priority order. General knowledge still gets a lightweight
title-only embedding pre-check (separate from skip_rag mechanism).
Problem: Skipping RAG entirely for general knowledge creates project context blind spot.
Consequences: (+) No missed project context. (−) Slight latency increase vs full skip.

**ADR-003 — Observer Fires at Session End Only**
Decision: Single pass at 10-min idle or process exit.
Problem: Per-message Observer burns RAM, produces noisy candidates.
Consequences: (+) Zero impact on response speed. (−) Profile updates at session end only.

**ADR-004 — Observer Never Writes Directly to Memory**
Decision: Candidates only. Validation + user confirmation required.
Consequences: (+) Observer cannot corrupt without Validation approval.

**ADR-005 — Observer Never Self-Scores Confidence**
Decision: Observer labels explicit/inferred only. Validation computes confidence.
Problem: Self-scoring is circular.
Consequences: (+) Confidence reproducible and auditable.

**ADR-006 — Decision Log Write Path is Manual-Only in Phase 1**
Decision: /decide command is the only write path until Phase 7.
Problem: Automating without real examples produces garbage.
Consequences: (+) Log starts with trusted, high-quality entries.

**ADR-007 — Decision Classification Uses OR Logic**
Decision: Any signal qualifies. Confidence weighted by signal count.
Problem: AND logic rejects most real decisions.
Consequences: (+) Captures realistic decision patterns.

**ADR-008 — Provider Gate at Stage 8 (Before LLM, After Assembly)**
Decision: Gate after Context Assembly, before LLM call.
Problem: Gate earlier means Assembly doesn't know target provider.
Consequences: (+) Context assembled correctly for target. (−) Assembly done before gate.

**ADR-009 — Provider Consent is Per-Provider Object**
Decision: Per-provider object with consent_scope, not global boolean.
Problem: Global flag cannot represent nuanced consent.
Consequences: (+) User can grant narrow consent without full exposure.

**ADR-010 — Ephemeral Consent Tokens Rejected**
Decision: Static per-provider flag with revoke command.
Problem: Ephemeral tokens solve multi-user web app problems — wrong scale.
Consequences: (+) Simple, inspectable consent config.

**ADR-011 — Constitutional Rules Built Before Observer**
Decision: constitutional.json + ConstitutionEnforcer tested first.
Problem: Without rules, all downstream components have no boundaries.
Consequences: (+) Everything downstream built against testable rules.
Note: This is the ONE hard technical dependency. Everything else is value-ordered.

**ADR-012 — interaction_style Is Gated, Not Immutable**
Decision: interaction_style in gated_fields, not immutable_fields.
Problem: Immutable prevents adapting to genuine preference evolution.
Consequences: (+) System adapts to real communication style evolution with confirmation.

**ADR-013 — Document-Decision Conflict Detection in Stage 5**
Decision: Conflict check in Stage 5 RAG, not Observer.
Problem: Post-session detection means user learns after moving on.
Consequences: (+) Conflict surfaces during session while context is live.

**ADR-014 — Proactive Triggers Are Deterministic Only**
Decision: Fire ONLY when specific coded conditions are met.
Allowed: session_gap > 48h, conflict_detected, goal_inactive > 14 days.
Forbidden: model judgment of relevance or urgency.
Consequences: (+) Proactive behavior auditable and predictable.

**ADR-015 — Scored Decision Graph Rejected**
Decision: Sequential pipeline with trace IDs.
Problem: Graph makes debugging harder — the very problem it claimed to solve.
Consequences: (+) Fully deterministic and traceable.

**ADR-016 — Two-Pass Retrieval Rejected**
Decision: Single pass with retrieval_hint from Intent Classifier.
Problem: Two-pass doubles latency on RTX 4060.
Consequences: (+) Pre-LLM latency within target.

**ADR-017 — Three-Way Memory Split**
Decision: skill_memory, preference_memory, goal_memory with separate validation.
Problem: One validation model cannot serve all three correctly.
Consequences: (+) Each type validated with appropriate criteria.

**ADR-018 — Validation Thresholds Tiered by Profile Age**
Decision: Thresholds increase as profile matures.
Problem: Fixed thresholds keep profile empty for weeks.
Consequences: (+) Profile accumulates from day one.

**ADR-019 — Intent Classifier Outputs skip_rag Flag**
Decision: skip_rag:bool added to Intent Classifier output.
Note: Two separate mechanisms — Mechanism 1 (keyword cache → skip_rag bool),
Mechanism 2 (ADR-002 embedding pre-check, runs regardless of skip_rag).
Consequences: (+) ~35ms saved per non-project query.

**ADR-020 — Observer Produces session_snapshot as Third Output**
Decision: Observer writes session_snapshot at session end.
Problem: On-demand reconstruction requires heavy work while user waits.
Consequences: (+) Long-gap return latency dramatically reduced (~5ms load).

**ADR-021 — Memory Source Trust Hierarchy**
Decision: User correction > Explicit stated > Repeated behavior > Single inference.
Problem: No rule for which source wins when sources conflict.
Consequences: (+) Explicit preferences always respected. (−) Slow adaptation to silent habit changes.

**ADR-022 — Decision Lifecycle States**
Decision: active | superseded | abandoned. Hard deletion NEVER permitted.
Problem: Old decisions appear equally authoritative without lifecycle state.
Consequences: (+) Log stays accurate as project evolves.

**ADR-023 — Cache Authority Hierarchy**
Decision: User correction > Decision Log > Profile > RAG > Web > Cache.
Problem: Cache silently serves stale content contradicting Decision Log.
Consequences: (+) Clear lookup order for debugging.

**ADR-024 — Memory Deletion Philosophy**
Decision: Profile = soft delete + archive. Decision Log = soft only (never hard delete).
Trace logs = hard delete permitted after 90 days on user request.
Full profile = reset with confirmation (irreversible without prior backup).

**ADR-025 — Dependency Rule (Clean Architecture)**
Decision: Pipeline stages and UI import ONLY interfaces in memory/ and providers/.
Direct imports of sqlite3, chromadb, ollama outside backend/memory and backend/providers
are banned. Enforced by pre-commit hook.
Consequence: One infra swap = update one module, not hunt through 14 stage files.

**ADR-026 — Storage: SQLCipher Whole-Database (supersedes all JSON/Fernet decisions)**
Decision: SQLite via SQLCipher for all structured data. No per-file Fernet. No plaintext
SQLite. ChromaDB is derived index only, never authoritative.
Problem: Plaintext SQLite was a privacy regression against Threat Model T1. Per-file
Fernet creates read-modify-write atomic issues at scale.
Consequences: (+) One encrypted unit. One connection sequence. No plaintext intermediate.

**ADR-027 — Backup Export via sqlcipher_export()**
Decision: /export uses ATTACH DATABASE + sqlcipher_export() with separate backup password.
Problem: Raw file copy misses WAL-resident data. Fernet re-wrap requires Fernet dependency.
Empirically verified: generated columns and WAL-resident data both survive correctly.
Consequences: (+) Encrypted-to-encrypted, no plaintext, separate passwords.

**ADR-028 — REST/WS Transport Split**
Decision: WS for chat only. REST for all CRUD. REST /chat dropped entirely.
Problem: Two streaming implementations for one feature doubles surface area.
Consequences: (+) One streaming implementation, proven twice (web then Flutter).

---

**ADR-032 - TICKET-012 Crash Safety via SQLite/SQLCipher Transactions**
TICKET-012's original 'write-ahead buffer for crash safety' language is superseded. profile_store.py implements no application-level write-ahead buffer. Crash safety is provided by SQLite/SQLCipher transactional atomicity (rollback on interrupted commit) combined with WAL mode, per the locked connection sequence in profile_store.get_connection(). This was proven by test_profile_write_interrupted_before_commit_reopens_with_prewrite_state. Rationale: SQLite's transactional guarantees make an application-level buffer redundant; adding one would be unjustified complexity for a guarantee already provided by the storage engine.

---

**ADR-033 — Observer Collapses Onto llama3.1:8b (Supersedes B1)**

Decision: Observer uses the same llama3.1:8b model as generation. There is no
longer a separate small model (phi3:mini) in the pipeline.

Problem: The original two-model design (phi3:mini for Observer, llama3.1:8b for
generation) required strict sequential VRAM swapping on an 8GB card (combined
~7.1–7.3GB, cannot coexist), an unmeasured model-swap benchmark sitting on the
critical path, and — discovered only by actually running it — a real quality
gap: phi3:mini's extraction output on a real prompt was not just weaker but
structurally broken (it echoed the approved-fields schema back as if it were a
candidate, producing zero usable memory_candidates and missing a decision with
two extractable signals that should have auto-logged per Part 8.7's OR-logic).

Chosen: Single local llama3.1:8b for both roles.

Reason: A/B test run 2026-08-16 (n=1 synthetic transcript — PIP has no real
production sessions yet; extraction prompt per Part 12.2, before this ADR's
prompt-schema fix). phi3:mini: 58.05s, memory_candidates unusable (wrong shape
entirely), decision_candidates empty (missed an extractable decision).
llama3.1:8b: 130.92s, 3 correctly-labeled memory_candidates (explicit/inferred
distinction correct), decision extraction still imperfect (miscategorized a
goal as a decision candidate) but structurally valid and parseable. The gate
rule ("if 8B is not clearly better, kill the decision") was met — the gap is
not marginal. Both timings include cold model load, not isolated inference;
re-benchmark warm once Phase 7 has real usage.

Two conditions carried over from the original proposal, now locked:
  1. Observer is pinned to a LOCAL provider — this is now the operative rule
     ("Observer is always local"), not the retired "Observer is always a small
     model." Currently structurally moot since v1.0 is confirmed local-only
     (no cloud generation provider exists in the call path to accidentally
     inherit), but must still be enforced explicitly at the Stage 8/Observer
     boundary when implemented, not left as an assumption.
  2. A `pending_observer` table + drain-on-startup mechanism is required before
     Phase 7 Observer code ships. An 8B pass (130.92s measured, likely 30-60s+
     even warm) cannot block SIGINT/SIGTERM that long. Transcript persists to
     SQLCipher (never a plain file), process exits immediately, drain runs
     before Stage 0 on next launch. This also closes the existing ADR-003 gap
     (unexpected process death during the Observer pass loses that session's
     learning) — a gap that technically existed under the two-model design too,
     just less urgently.

Consequences: (+) No VRAM-swap orchestration, no swap-window overrun risk on an
8GB card, no guaranteed cold reload at every session boundary, retires the
model-swap benchmark entirely. (−) Slower single Observer pass than phi3:mini
would have been; `observer_max_seconds` raised from an untested 30 to 180
pending a warm-run re-benchmark; `pending_observer` is new scope that must ship
before Phase 7. Also surfaced, independent of which model won: Part 12.2's
extraction prompt never specified the exact `MemoryCandidate` key names
(`target_table`, `field_name`, `proposed_value`) — fixed in this ADR's pass,
see Part 12.2.

Supersedes: B1 (Observer = phi3:mini, "always a small model" principle).

Updated by this ADR: Part 6.3, Part 7 Stage 11, Part 12.1 Rule 4, Part 12.2,
Part 13.3, Part 14.3 WS spec, Part 18 Phase 0 checklist, Part 19 settings.json
(`observer.model`, `observer_max_seconds`), Glossary `model_loading` entry.

---
# PART 17 — FOLDER STRUCTURE [FROZEN]

```
pip/
├── backend/
│   ├── api/
│   │   └── server.py                    (Phase 2)
│   ├── core/
│   │   ├── constitutional.json          ← FIRST FILE CREATED
│   │   ├── constitution_enforcer.py     ← SECOND FILE CREATED
│   │   ├── pipeline.py
│   │   ├── response_cache.py
│   │   ├── trace.py
│   │   ├── schema.sql                   ← FINALIZED (already written)
│   │   └── types.py                     ← STARTED (TIMESTAMP_FORMAT etc.)
│   ├── stages/
│   │   ├── stage_00_gap_detector.py
│   │   ├── stage_01_intent_classifier.py
│   │   ├── stage_02_router.py
│   │   ├── stage_03_decision_log_lookup.py
│   │   ├── stage_04_memory_lookup.py
│   │   ├── stage_05_rag_retrieval.py
│   │   ├── stage_06_web_search.py
│   │   ├── stage_07_context_assembly.py
│   │   ├── stage_08_provider_gate.py
│   │   ├── stage_09_llm_streaming.py
│   │   ├── stage_10_response_delivery.py
│   │   ├── stage_11_observer.py
│   │   ├── stage_12_validation_layer.py
│   │   └── stage_13_profile_update.py
│   ├── memory/
│   │   ├── profile_store.py             ← get_connection() lives here
│   │   ├── decision_log.py
│   │   ├── candidate_store.py           ← owns both pending tables
│   │   ├── vector_store.py
│   │   └── session_snapshot.py
│   ├── providers/
│   │   ├── base_provider.py
│   │   ├── ollama_provider.py
│   │   ├── llamacpp_provider.py
│   │   ├── groq_provider.py
│   │   ├── openai_provider.py
│   │   └── claude_provider.py
│   ├── observer/
│   │   └── extractor.py
│   ├── config/
│   │   ├── settings.json               ← TO BE WRITTEN (Phase 0)
│   │   └── settings.py                 ← canonical loader (Phase 0)
│   ├── logs/
│   │   ├── trace_log.json              (written by trace.py)
│   │   └── startup_log.json            (FTS5 availability cached here)
│   └── tests/
│       ├── test_constitution_enforcer.py
│       ├── test_schema.py              (FTS5 roundtrip, wrong-key)
│       ├── test_stages/
│       ├── test_integration.py
│       └── test_observer_accuracy.py
├── frontend/
│   ├── web/                            (Phase 8 — built first)
│   └── flutter/                        (Phase 8+ — after web proven)
├── shared/
│   ├── models.py                       (Pydantic models)
│   └── ws_spec.py                      (WS message type definitions)
├── data/
│   ├── pip.db                          (SQLCipher database)
│   ├── salt.bin                        (KDF salt — not secret)
│   └── session_snapshot.json           (Observer output, ~5ms load)
├── scripts/
│   └── pre-commit                      (ADR-025 enforcement hook)
├── docs/
├── requirements.txt
└── .env.example                        (PIP_DEV_KEY for dev only)
```

**Rules:**
- No stage file imports sqlite3, chromadb, or ollama directly (pre-commit enforced)
- Each data file has exactly one owner module
- All modules import from config/settings.py, never do their own json.load()
- session_snapshot.json is the only JSON data file (not config)

---

# PART 18 — PHASE ROADMAP

| Phase | What | Time | Git Tag | Notes |
|---|---|---|---|---|
| 0 | Project setup + schema + config skeleton | 2–3 days | v0.0 | No code, only infrastructure |
| 1 | Constitutional Core | 1 week | v0.1 | First real code |
| 2 | Onboarding + Decision Log + Profile | 1 week | v0.2 | First user-facing features |
| 3 | Provider Layer + Provider Gate | 1 week | v0.3 | Privacy guarantee in code |
| 4 | Gap Detector + Session Snapshot | 3–4 days | v0.4 | Session continuity |
| 5 | Validation Layer + Memory Protection | 1 week | v0.5 | ← ACADEMIC MINIMUM |
| 6 | RAG + Parallel Retrieval | 1.5 weeks | v0.6 | |
| 7 | Observer | 2 weeks | v0.7 | Largest single phase |
| 8 | Full Pipeline Integration + Web + Flutter spike | 1.5 weeks | v0.8–v0.9 | |
| 9 | Integration Testing + Debug | 1 week | v1.0 | |
| 10 | Documentation + Final Report | 4 weeks | — | Can overlap Phase 8–9 |
| **Total** | | **~17 weeks** | | |

**Self-imposed target:** v1.0 with both clients by week 20–22. Weeks 22–24+ = genuine buffer.

## Phase 0 Specific Tasks [IMMEDIATE]

```
[ ] git init, create dev and main branches
[ ] Python venv (Python 3.11+)
[ ] Install: sqlcipher3-binary, chromadb, sentence-transformers,
             cryptography, pytest, asyncio, fastapi, ollama
[ ] Create full folder skeleton
[ ] Copy backend/core/schema.sql (already written, finalized)
[ ] Write backend/core/constitutional.json
[ ] Write backend/config/settings.json (ALL keys including
    log_threshold_manual=0.4 and log_threshold_observer=0.7
    with activation comment for Phase 7)
[ ] Write backend/config/settings.py (canonical loader)
[ ] Deploy scripts/pre-commit hook (after git init)
    chmod +x .git/hooks/pre-commit
[ ] Write FTS5-in-SQLCipher roundtrip test:
    open encrypted DB → create FTS5 virtual table → insert →
    MATCH query → assert non-empty result
[ ] Write SQLCipher wrong-key test:
    wrong key → SELECT count(*) FROM sqlite_master → must fail loudly
[x] Verify Ollama running locally, pull phi3:mini and llama3.1:8b — done during
    Phase 5 environment recovery + ADR-033 A/B test (2026-08-16)
[x] requirements.txt committed — done during Phase 5 environment recovery
    (see commit c558893; sqlcipher3-binary is gone from PyPI, corrected to sqlcipher3)
[x] Model-swap benchmark — RETIRED by ADR-033. No swap exists to benchmark since
    Observer and generation now share llama3.1:8b. See ADR-033 for the A/B timing
    data that replaced this item (58.05s vs 130.92s, cold-load included).
[ ] First commit: v0.0 tag (folder skeleton only)
```

**Phase 0 comment skeleton tasks (zero implementation, high architectural value):**
```
[ ] Two-line comment in stage_01_intent_classifier.py distinguishing
    Mechanism 1 (skip_rag flag) from Mechanism 2 (ADR-002 safety net)
[ ] Comment in vector_store.py: startup rebuild-on-mismatch trigger
[ ] Comment in decision_log.py schema:
    active_projects → direct DB query, no cache
    decision_text → write-once, state is only mutable field
```

## Phase 1 Specific Tasks (Constitutional Core)

```
[x] TICKET-001: backend/core/constitutional.json (exact spec from Part 9.1)
[x] TICKET-002: backend/core/constitution_enforcer.py (full class)
[x] TICKET-003: Tests - immutable field HARD_REJECT (name, language, timezone)
[x] TICKET-004: Tests - gated field REQUIRES_CONFIRMATION (all 4 gated fields)
[x] TICKET-005: Tests - tiered thresholds
    Week 1 explicit -> APPROVED
    Week 1 inferred -> DISCARD
    Month 2 evidence=2 -> DISCARD
    Month 2 evidence=3 confidence=0.75 -> APPROVED
[x] TICKET-006: Tests - behavioral override
    explicit/user_verified/user_correction source + behavioral_signal_count >= 3 + first_contradiction_date >= 14 days -> PROMPT_RECONCILIATION
[x] TICKET-007: backend/core/trace.py
    generate_trace_id() works
    stage_log() appends valid JSON to trace_log
    mock pipeline run produces readable full trace
Exit condition: COMPLETE - ConstitutionEnforcer tests pass. Trace ID logged for mock run.
```

---

# PART 19 — SETTINGS.JSON COMPLETE REFERENCE

All tunable values. These are NOT ADRs. Change by measurement, not opinion.

```json
{
  "observer": {
    "idle_timeout_minutes": 10,
    "model": "llama3.1:8b",
    "max_session_tokens": 8000
  },
  "rag": {
    "similarity_threshold": 0.6,
    "chunk_size_tokens": 500,
    "chunk_overlap_tokens": 50,
    "top_k_results": 3,
    "max_document_size_mb": 50,
    "supported_extensions": [".pdf", ".md", ".txt", ".py", ".json", ".html"]
  },
  "cache": {
    "ttl_general_knowledge_seconds": 86400,
    "ttl_technical_explanation_seconds": 86400,
    "ttl_web_search_seconds": 3600,
    "ttl_project_question_seconds": 0,
    "ttl_personal_question_seconds": 0,
    "ttl_decision_lookup_seconds": 0
  },
  "memory": {
    "goal_decay_inactive_days": 14,
    "behavioral_override_sessions": 3,
    "behavioral_override_days": 14,
    "verification_loop_frequency_sessions": 30,
    "verification_loop_sample_size": 3
  },
  "decision_log": {
    "log_threshold_manual": 0.4,
    "log_threshold_observer": 0.7
    // log_threshold_observer is INACTIVE until Phase 7 (Observer ships).
    // Single-signal Observer detections route to decision_candidates_pending
    // rather than auto-logging. Do not activate ad-hoc — it activates
    // automatically when Observer is built in Phase 7.
  },
  "pipeline": {
    "context_token_budget": 6000,
    "system_instructions_tokens": 150,
    "user_profile_tokens": 400,
    "session_snapshot_tokens": 250,
    "decision_log_tokens": 600,
    "rag_chunks_tokens": 800,
    "web_search_tokens": 800,
    "conversation_history_tokens": 1000,
    "user_message_tokens": 400,
    "response_reserved_tokens": 2000
  },
  "proactive": {
    "session_gap_trigger_hours": 48,
    "goal_inactive_trigger_days": 14
  },
  "trace": {
    "hard_delete_after_days": 90,
    "db_table": "trace_log"
  },
  "web_search": {
    "provider": "duckduckgo",
    "result_limit": 3,
    "timeout_seconds": 10
  },
  "database": {
    "kdf_algorithm": "PBKDF2_HMAC_SHA512",
    "kdf_iterations": 256000,
    "fts5_fallback": "LIKE"
  },
  "performance_targets": {
    "stage_0_ms": 10,
    "stage_1_ms": 30,
    "stage_2_ms": 15,
    "stages_3_5_parallel_ms": 80,
    "stage_7_ms": 50,
    "observer_max_seconds": 180,
    "snapshot_load_ms": 5,
    "cache_hit_ms": 100,
    "simple_query_total_seconds": 2,
    "complex_query_total_seconds": 5
  }
}
```

**`observer.model` and `observer_max_seconds` note:** updated by ADR-033 (supersedes B1).
`observer_max_seconds` was raised from the never-validated 30 to 180, based on a measured
130.92s llama3.1:8b pass (ADR-033 A/B test, cold-load included, n=1 transcript) plus headroom.
This should be re-benchmarked warm (model already resident) once Phase 7 has real usage —
180 is a safe starting ceiling, not a tuned steady-state number.

**config/settings.py canonical loader (single source of truth for all config values):**
```python
import json
from pathlib import Path

_settings = None

def get_settings() -> dict:
    global _settings
    if _settings is None:
        settings_path = Path(__file__).parent / "settings.json"
        with open(settings_path) as f:
            _settings = json.load(f)
    return _settings
```

All modules call `get_settings()["section"]["key"]`. No module does its own `json.load()`.

---

# PART 20 — FINALIZATION STATUS

## Locked and Implemented (files exist, tested)

| Item | Status |
|---|---|
| backend/core/schema.sql | DONE — 5 rounds review + empirical SQLCipher test |
| backend/core/types.py | DONE — TIMESTAMP_FORMAT, now_utc(), base TypedDicts |
| sqlcipher_export() + generated columns | EMPIRICALLY VERIFIED (two sandboxes) |
| WAL-resident data + sqlcipher_export() | EMPIRICALLY VERIFIED |
| KDF: PBKDF2_HMAC_SHA512, 256k iterations | EMPIRICALLY VERIFIED (two sandboxes) |
| decision_text immutability trigger | DONE — tested in schema validation |
| ADRs 001–028 | LOCKED |
| All schema design decisions | LOCKED |
| v0.5 / v1.0 success statements | LOCKED |
| Storage ownership table | LOCKED |
| Connection 4-PRAGMA sequence | LOCKED |
| FTS5 fallback decision (LIKE, never shadow index) | LOCKED |
| Backup export mechanism (sqlcipher_export) | LOCKED + EMPIRICALLY VERIFIED |
| master-key-at-rest model | LOCKED |
| Transport split (WS chat, REST CRUD) | LOCKED |
| Phase 2 CLI execution model | LOCKED |
| model_loading WS stage_hint | LOCKED |
| decision_candidates_pending sort order | LOCKED (confidence ASC, created_at ASC) |
| Tool Execution Layer: deferred post-v1.0 | LOCKED |
| Folder structure | FROZEN |
| Pre-commit hook script | DRAFTED (not deployed - git not initialized yet) |
| Phase 1 constitutional core | DONE - TICKET-001 through TICKET-007 accepted |
| backend/core/constitutional.json | DONE - Phase 1 accepted |
| backend/core/constitution_enforcer.py | DONE - validated existing_field contract, table-level observer allowlist, fnmatch gated patterns, behavioral override before thresholds |
| backend/core/trace.py | DONE - trace ID generation and JSON stage logging tested |
| Phase 1 pytest run | PASS - 27 passed, 1 skipped (SQLCipher-dependent wrong-key test skipped because SQLCipher is not installed in current test environment) |
| Phase 2 /decide decision log | DONE - `backend/tests/test_decision_log.py::test_decision_confidence_uses_or_logic` and `backend/tests/test_decision_log.py::test_manual_decide_logs_with_any_one_signal` passing |
| Phase 2 /profile display | DONE - `backend/tests/test_profile_store.py::test_profile_view_includes_confidence_and_source_label` passing |
| Phase 2 decision_text immutability | DONE - `backend/tests/test_decision_log.py::test_decision_text_is_write_once` passing |
| Phase 2 onboarding encrypted profile | NOT COMPLETE - `backend/tests/test_profile_store.py::test_onboarding_writes_identity_profile_and_completion_flag` verifies profile writes, but encrypted-profile behavior is unverified because `backend/tests/test_schema.py::test_wrong_key_behavior` is skipped without SQLCipher |
| Phase 2 crash survival | DONE - `backend/tests/test_profile_store.py::test_profile_write_interrupted_before_commit_reopens_with_prewrite_state` passing; interrupted profile write rolls back to pre-write state on reopen |
| Phase 3 Ticket 1 — BaseLLMProvider ABC | DONE — `backend/providers/base_provider.py`; `ProviderExecutionError`, `ProviderUnavailableError` custom exceptions; tested in `test_base_provider.py` |
| Phase 3 Ticket 2 — OllamaProvider | DONE — `backend/providers/ollama_provider.py`; urllib-only, no extra deps; HTTPError 404 raises descriptive message; tested in `test_ollama_provider.py` |
| Phase 3 Ticket 3 — provider_consent.json seed data | DONE — `config/provider_consent.json` restructured as plain seed array (no JSON Schema wrapper); locked by `test_no_schema_key`, `test_no_examples_key`; ADR-030 web_search row exact-match tested |
| Phase 3 Ticket 4 — seed_provider_consent() + Stage 8 gate | DONE — `memory/profile_store.py::seed_provider_consent()` idempotent; called from `initialize_schema()`; `backend/stages/stage_08_provider_gate.py` fail-closed (unknown provider = hard stop); scope enforcement; revoked overrides consented; 15 tests passing |
| Phase 3 Ticket 4 — DB migration (pre-Phase-3 DBs) | DONE — `scripts/migrate_seed_provider_consent.py`; local dev DB `data/pip.db` migrated: 0→2 rows confirmed; idempotency confirmed; documented in Phase 3 DB Migration Note section |
| Phase 3 Ticket 5 — /providers /consent /revoke | DONE — `api_list_providers`, `api_grant_consent` (scope-validated before DB write), `api_revoke_consent` in `backend/api/server.py`; CLI commands `_providers`, `_consent`, `_revoke` in `frontend/cli/pip_cli.py`; 16 tests passing including 2 end-to-end gate tests |
| Phase 3 full-suite post-merge | PASS — 81 passed, 1 skipped (SQLCipher) on main at `6f1efa5`, tag `v0.3` |

## Phase 3 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.3` |
| Commit (main) | `6f1efa5` |
| Full hash | `6f1efa593b66c5f701f44a942cf62cb953903369` |
| Merge type | Squash merge from `phase-3-provider-layer` into `main` |
| Audit branch | `phase-3-provider-layer` (retained, ticket-by-ticket history: `6685d00` → `5a2aac0` → `3039300` → `90c67f0`) |
| Test result at tag | 81 passed, 1 skipped (pre-existing SQLCipher skip), 0 failed |
| Scope | Provider abstraction layer, OllamaProvider, consent seed data, Stage 8 gate (fail-closed), DB migration script, /providers /consent /revoke CLI+API |
| Phase 4 Tickets 1 & 2 — Gap Detector & session_snapshot.json | DONE — `backend/stages/stage_00_gap_detector.py` continuous boundary logic; fail-open confirmed. `backend/memory/session_snapshot.py` schema and load/write logic; fail-open on missing/corrupt confirmed; 5ms load budget tested. |
| Phase 4 full-suite post-merge | PASS — 97 passed, 1 skipped on main at `2583c4f`, tag `v0.4` |

## Phase 4 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.4` |
| Commit (main) | `2583c4f` |
| Full hash | `2583c4f...` |
| Merge type | Squash merge from `phase-4-gap-detector` into `main` |
| Audit branch | `phase-4-gap-detector` (retained) |
| Test result at tag | 97 passed, 1 skipped (pre-existing SQLCipher skip), 0 failed |
| Scope | Stage 0 Gap Detector, session_snapshot.json read/write helpers, fail-open handling, deterministic continuous boundary resolution |

## Phase 5 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.5` (academic minimum) |
| Commit (main) | `b2fc6df` |
| Test result at tag | 121 passed, 0 skipped, 0 failed — first fully-real run against SQLCipher (previous phases' suites ran against a silent plaintext-SQLite fallback; see environment-fix commit `c558893`) |
| Scope | Stage 12 Validation Layer wired to real DB state; `apply_verified_correction` (verified/corrected writes at max confidence); `memory_candidates_pending` schema fix (added `target_table`, `validation_status`, `state`); Stage 13 write orchestration (APPROVED writes now, gated/conflict/override candidates persist to pending, rejects write nothing) |
| Environment note | Dev environment had never run real SQLCipher before this phase: no `requirements.txt` existed, `sqlcipher3-binary` is gone from PyPI, and Python 3.14 (previously in use) has no compatible SQLCipher wheel at all. Rebuilt on Python 3.12 with the correctly-named `sqlcipher3` package. Two real bugs surfaced only once encryption actually ran: `sqlite3.Row` cannot wrap a `sqlcipher3` cursor, and `get_connection()` silently fell back to plaintext SQLite instead of failing loudly when SQLCipher was unavailable. Both fixed. |

## Phase 6 — NEARLY COMPLETE (RAG + Parallel Retrieval)

| Item | Status |
|---|---|
| `documents` table (schema.sql) | DONE — SQLite source-of-truth registry for ChromaDB ingestion |
| `memory/vector_store.py` | DONE — ingest/query/delete/list/rebuild-from-drift, real ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`, CPU-only), `.pdf`/`.md`/`.txt`/`.py`/`.json`/`.html` extraction, `max_document_size_mb` enforced |
| `backend/stages/stage_05_rag_retrieval.py` | DONE — threshold-filtered retrieval + lexical conflict-check heuristic against active Decision Log (fail-open per Part 7.4) |
| `/ingest`, `/documents`, `/remove` CLI commands | DONE — `frontend/cli/pip_cli.py` |
| `POST /rag/ingest`, `/rag/query`, `GET /rag/documents`, `DELETE /rag/documents/{ref}` REST endpoints | DONE — `backend/api/server.py`, confirmed registered on the real FastAPI app, not just business-logic functions in isolation |
| Known tradeoff | `all-MiniLM-L6-v2` max_seq_length is 256 tokens; `chunk_size_tokens` is 500. Chunks past ~256 tokens are truncated for embedding purposes only — full text is still stored/returned, only mid-chunk semantic search quality degrades. Same class of imprecision as `similarity_threshold` (already documented as "calibrate from real usage") |
| Conflict-check heuristic | Lexical overlap-coefficient between chunk and active decision keywords, not semantic contradiction detection — no LLM call in this stage. Flags "worth a human double-check," not a proven contradiction. Threshold (0.3) needs real-usage calibration same as `similarity_threshold` |
| `/remove`'s REST identifier | file_path itself (percent-encoded), not a separate document id — there is no document id in this schema |
| Test coverage | 21 tests (`test_vector_store.py`, `test_stage_05_rag_retrieval.py`, plus additions to `test_api_server.py`/`test_cli.py`), core engine tested against real ChromaDB + real embedding model, not mocks |
| Router (Stage 2) wiring to actually call Stage 5 during a live pipeline run | NOT DONE — full pipeline integration is Phase 8 per the roadmap, correctly out of scope here |

## Phase 7 Prerequisite — DONE (ADR-033 condition 2)

| Item | Status |
|---|---|
| `pending_observer` table (schema.sql, table 21) | DONE — crash-safety queue, status: pending → processing → completed/failed, never hard-deleted |
| `memory/pending_observer.py` | DONE — `enqueue`, `list_pending`, `mark_processing/completed/failed`, `drain(conn, observer_runner)`. `drain()` takes the extraction function as a parameter rather than importing Stage 11 directly, keeping the queue decoupled from Stage 11's own implementation |
| Crash-recovery detail | `drain()` retries rows stuck in `'processing'`, not just `'pending'` — a stuck `'processing'` row means a previous drain itself crashed mid-run, which is exactly the case this table exists to survive |
| Test coverage | 8 tests, including one-failure-doesn't-block-the-rest and stale-processing-row recovery |
| Not built yet, correctly deferred | Actual SIGINT/SIGTERM signal handling and the "call drain() before Stage 0 at startup" wiring — both need a running server/process lifecycle that doesn't exist until Phase 8. This module is the tested primitive Phase 8 will call, not the process-lifecycle integration itself |

## Phase 7 — Observer (STARTED)

| Item | Status |
|---|---|
| `backend/stages/stage_11_observer.py::run()` | DONE — single-pass extraction against `llama3.1:8b` via `BaseLLMProvider`. Enforces Rule 4 (raises `ObserverLocalProviderError` if given a non-local provider) and Rule 1 (only `explicit`/`inferred` labels survive sanitization; anything else, including a hallucinated confidence-bearing label, is dropped). Fails open on any LLM/parse failure per spec. |
| `run_session_end()` | DONE — full flow: extract → write `session_snapshot.json` immediately → route each memory candidate through Stage 12 (validate) + Stage 13 (write) → route each decision candidate through `decision_log.route_observer_decision()` |
| `decision_log.route_observer_decision()` | DONE (new) — Part 8.7's Observer path: signals come from the LLM's own reading of the conversation (not keyword-matched, unlike the manual `/decide` path), but confidence is still always computed deterministically via `score_confidence()`, never assigned by the model (ADR-005). Unknown/hallucinated signal names are filtered before scoring. |
| `session_snapshot.py` schema fix | Its `SessionSnapshot` TypedDict used `last_topic`/`last_session_timestamp` and had no `last_decisions` key at all — didn't match Part 7/12.2's canonical Observer output shape (`topic`/`snapshot_date`/`last_decisions`). Same bug class as the RAG `target_table` issue; fixed before wiring Stage 11 to it, not after. |
| Live validation against real `llama3.1:8b` | Ran twice, not just against a fake provider: `run()` alone, then the full `run_session_end()` against a real encrypted DB. Found one real bug live: `session_snapshot.last_decisions` came back as a list of full decision objects, not strings — `_sanitize_snapshot` checked "is this a list" but not "is each item a string." Fixed with `_as_string_list()`, re-verified against real output afterward. |
| Empirically confirmed, not just documented | The evidence_count=1 discard problem that motivated the reinforcement fix below actually happened on the live run: both memory candidates came back `DISCARD` because `profile_age_weeks` for the test profile was past month 2 (requires evidence_count >= 3), and a single-session extraction can only ever produce evidence_count=1. The decision candidate (2 signals, confidence 0.7) correctly auto-logged. |
| **Cross-session evidence reinforcement** (Part 8.6) | DONE — `stage_12_validation_layer.reinforce_evidence(conn, candidate)`. Called by `run_session_end()` before `stage_12.run()`; the reinforced candidate (not the original) flows through to `stage_13.run()` so the increment is visible to both the threshold check and the actual write, not just the check. Reinforces only when the existing stored value matches the candidate's `proposed_value` exactly — a *different* value is a conflict, not a repeat observation, and is left alone for the existing TIER_2_REQUIRED/behavioral-override paths to handle. `identity` and `active_projects` have no `evidence_count` column and are returned unchanged. Verified with a simulated two-session test: a fresh evidence_count=1 candidate DISCARDs at week_3_4 on its own, then APPROVEs once reinforced against a prior session's stored row — both the in-memory check and the persisted DB row reflect the reinforced count. |
| `pending_observer.enqueue()` wiring into `run_session_end` | NOT DONE — deliberately: enqueueing happens when the process must exit *before* Observer can run at all (a process-lifecycle decision), not from inside the extraction function itself, which already fails open on its own. That trigger point is Phase 8. |
| Idle-timeout / process-exit triggering (Rule 3) | NOT enforced by this code — there's no process-lifecycle context available to a plain function. Phase 8's job, same boundary as `pending_observer`. |
| Test coverage | 19 new tests total: 13 in the initial Stage 11 pass (`test_stage_11_observer.py`, plus 3 in `test_decision_log.py` for `route_observer_decision`), plus 6 more for reinforcement (5 in `test_stage_12_validation_layer.py`, 1 full-orchestrator integration test in `test_stage_11_observer.py`). All against a fake provider for speed, plus two live smoke-test runs against real `llama3.1:8b` (not part of the permanent suite — too slow to run every time, ~60-130s per call) |

## Decided but Not Yet Written as Files

| Item | What's missing |
|---|---|
| pre-commit hook | Script drafted, not deployed (needs git init first) |
| PRD 1.6 (non-goals vs deferred) | Tool Execution Layer distinction not written (external PRD doc, not this file) |
| PRD 1.8 (tiered success statements) | v0.5/v1.0 claims not in PRD (external PRD doc, not this file) |
| Shared WS message spec | `shared/ws_spec.py` doesn't exist yet at all — planned for Phase 8 per Part 17 folder structure, correctly not started |

**Resolved, removed from this table (verified against the current doc text, not re-claimed as still open):**
SQLCipher test environment (Phase 5 environment-fix commit `c558893` — `sqlcipher3` installed,
wrong-key test passes for real); Threat Model T1/T4 and backup export (Part 10 has described
SQLCipher, not Fernet, since before this session — this table just never got updated to say so);
pending-candidate sort order (Part 8.7/9.2/24 have all said `confidence ASC, created_at ASC`
since before this session, same stale-tracking issue).

## Tracked Technical Debt (not urgent fixes)

| Item | Status |
|---|---|
| ConstitutionEnforcer gated-field helper cleanup | `_matches_gated_field` currently includes a `target_table.field_name` concatenation branch that is dead code once `field_name` is table-qualified per finalized spec. Later cleanup: rely solely on direct `fnmatch(field_name, pattern)`. |
| SQLCipher-dependent local tests | Current local pytest run skips encryption-layer wrong-key behavior because SQLCipher/sqlcipher3 is not installed in the test environment. Encryption-layer behavior remains unverified locally until SQLCipher is installed. |

## Phase 3 DB Migration Note (one-time, RESOLVED for local dev DB)

**Context:** `seed_provider_consent()` was added to `memory/profile_store.py` in Phase 3 (Ticket 4). Any database initialized before this point (Phase 1/2 work) will have the `provider_consent` table but zero rows, which causes Stage 8 to hard-stop on every request (fail-closed policy).

**Confirmed:** The local dev DB at `data/pip.db` was verified to have 0 rows in `provider_consent` before this migration. The migration was run and confirmed 2 rows inserted (ollama, web_search).

**For any future pre-Phase-3 DB** (e.g. a teammate cloning and using an older DB dump): run the migration script once from the repo root:

```
python scripts/migrate_seed_provider_consent.py [--db-path PATH]
```

- Default path: `data/pip.db`
- Idempotent: safe to run multiple times — no-op if rows already exist
- Script location: `scripts/migrate_seed_provider_consent.py`

**New DBs** created after Phase 3 are not affected — `initialize_schema()` now calls `seed_provider_consent()` automatically.

## Genuinely Open (cannot be resolved by architectural reasoning)

| Item | What's needed |
|---|---|
| Submission deadline | Exact calendar date still unset — confirmed as "3+ months, flexible" as of 2026-08-17, so scope decisions aren't currently being made blind, but no hard date exists yet |

**Resolved, removed from this table:** Model-swap benchmark — retired by ADR-033 (no swap exists to benchmark; Observer and generation share llama3.1:8b).

---

# PART 21 — IMPLEMENTATION SEQUENCE FOR PHASE 0

**Exact order. Non-negotiable for items 1–4:**

```
1. backend/core/constitutional.json          (the ground truth for everything)
2. backend/core/constitution_enforcer.py     (class with 6 ValidationResult values)
3. All ConstitutionEnforcer tests            (Tickets 003–006)
4. backend/core/trace.py                     (trace_id generation, stage_log)
5. backend/core/schema.sql                   (ALREADY DONE)
6. backend/config/settings.json             (ALL keys, activation comments)
7. backend/config/settings.py              (canonical loader)
8. backend/tests/test_schema.py            (FTS5 roundtrip + wrong-key tests)
9. scripts/pre-commit                       (ADR-025 enforcement)
10. requirements.txt + venv setup
11. Phase 0 comment skeletons in stage_01, vector_store, decision_log
```

**Exit condition for Phase 0:**
- All ConstitutionEnforcer tests pass
- FTS5 roundtrip test passes against real SQLCipher DB
- Wrong-key test fails loudly (not silently returns empty)
- Pre-commit hook blocks a test commit with a raw sqlite3 import
- Folder skeleton exists on BatMan's machine
- Git initialized, v0.0 tag pushed

---

# PART 22 — ONBOARDING QUESTION SCRIPT

Onboarding bypasses Observer and Validation entirely (onboarding_bootstrap exception).
Writes directly to identity and profile tables. Deactivates permanently after completion.

```
Q1: "What is your name?"
    → identity.name (immutable)
    Skippable: NO

Q2: "What is your primary language for communication?"
    → identity.language_preference (immutable)
    Skippable: NO

Q3: "What timezone are you in?"
    → identity.timezone (immutable)
    Skippable: YES — defaults to system timezone

Q4: "What are you currently working on?"
    → active_projects (name + description)
    Skippable: YES — can add later via /project new

Q5: "What is your primary skill area?"
    → skill_memory[stated_skill] (level 0.5 default, source=explicit)
    Skippable: YES — accepts up to 3 comma-separated skills

Q6: "How do you prefer answers?"
    1. Brief summary first, detail on request
    2. Full detailed answer always
    3. I'll specify each time (adaptive)
    → interaction_style.value (gated, bootstrap exception applies)
    Skippable: YES — defaults to adaptive

Q7: "What tools do you use most?"
    → preferred_tools (evidence_count=1, source=explicit)
    Skippable: YES — accepts up to 5 comma-separated tools

COMPLETION:
  profile_meta.onboarding_complete = 1
  profile_meta.first_session_date = now_utc()
  onboarding_bootstrap permanently deactivated
  "Setup complete. PIP is ready."
```

---

# PART 23 — COMMAND REFERENCE

```
DECISION LOG
/decide                    Start decision log entry workflow
/decisions                 List all active decisions
/decisions search [query]  FTS5 natural language search
/decisions [id] supersede  Mark as superseded
/decisions [id] abandon    Mark as abandoned (reason required)
/pending                   List pending decision candidates
/pending review [id]       Review one candidate
/pending promote [id]      Promote to decision log
/pending dismiss [id]      Dismiss candidate (kept 90 days)

PROFILE
/profile                   View all fields with confidence + source label
/profile edit [field]      Edit a field (user_correction write)
/profile delete [field]    Soft delete (not removed, filtered from retrieval)
/verify                    Manually trigger 30-session memory verification loop
/reset                     Full profile reset (irreversible without prior backup)

PROJECTS
/project new               Create new project (prompts name + description)
/project list              List all projects with status and last_active
/project switch [name]     Set active_project_id for this session

DOCUMENTS / RAG
/ingest [file]             Ingest document into ChromaDB vector store
/documents                 List indexed documents
/remove [document]         Remove document from index

PROVIDERS
/providers                 List all providers with consent status
/consent [provider]        Grant consent (prompts for scope)
/revoke [provider]         Revoke consent

BACKUP
/export                    Export encrypted backup (separate backup password)
/export --readable         Export plain text JSON (warning shown first)
/restore [file]            Restore from backup

SYSTEM
/status                    Ollama status, memory stats, RAG index status
/trace [trace_id]          Full trace for a specific message
/trace recent              Last 20 trace entries
/help                      Command reference
```

---

# PART 24 — GLOSSARY

**behavioral_override:** Reconciliation prompt when behavioral evidence contradicts a
stated preference across 3+ sessions over 14+ days. Never silent overwrite.

**candidate:** Unvalidated observation from Observer. Not written until Validation approves.

**candidate_store.py:** Sole owner of both pending tables (decision_candidates_pending,
memory_candidates_pending). Stages 11, 12, 13 are callers into it.

**confidence:** base_score * min(evidence_count, 5) / 5. Never self-assigned by Observer.
GENERATED ALWAYS AS column for skill/preference/interaction_style. Stored manual for goal.

**constitutional.json:** Immutable rule file. First file created. Everything downstream.

**ConstitutionEnforcer:** Single Python class. One public method: validate(). Tests must
pass before Observer is built (ADR-011).

**context_depth_modifier:** Integer 0–3 from Gap Detector. Scales session_snapshot allocation.

**decay_flag:** True when goal_memory entry inactive > 14 days.

**Decision Log:** Decisions table in SQLCipher. Hard deletion NEVER permitted (ADR-022).

**decision_candidates_pending:** Low-confidence decisions awaiting manual review.
Surfaced ORDER BY confidence ASC, created_at ASC (low-evidence oldest first).

**evidence_count:** Independent sessions in which signal appeared. Primary confidence input.

**explicit:** Observer label. User directly stated something. base_score = 0.9.

**FTS5:** SQLite full-text search extension used for /decisions search. Availability
checked once at startup. Fallback: LIKE inside still-encrypted DB. Shadow index: never.

**gated field:** Observer may detect changes. Requires user confirmation before write.
Pending candidates survive session close in memory_candidates_pending.

**get_connection():** The ONLY function that opens a SQLCipher connection. Lives in
profile_store.py. Executes 4 mandatory PRAGMAs in order.

**inferred:** Observer label. Observed from behavior, not stated. base_score = 0.4.

**model_loading:** WebSocket stage_hint boolean. True whenever llama3.1:8b needs a
cold load (e.g. after Ollama's keep_alive evicts it). No longer a two-model swap
signal (ADR-033 retired the swap entirely) — still needed because a cold load is
still real wall-clock time the user would otherwise perceive as a silent hang.

**onboarding_bootstrap:** Exception mode, first session only. Direct writes, bypasses all
validation. Deactivates permanently after onboarding_complete = 1.

**Provider Gate:** Stage 8. Hard stop if is_cloud AND (NOT user_consented OR revoked).
Per-provider object, not global boolean.

**retrieval_hint:** Short phrase from Intent Classifier. Pre-seeds Stage 3, 4, 5 lookups.

**session_snapshot.json:** Single JSON object written at every session end by Observer.
Loaded by Gap Detector in ~5ms on return. NOT a SQLite table — JSON is correct here.

**skip_rag:** Intent Classifier flag. Two separate mechanisms produce it vs ADR-002.
Mechanism 1 produces the bool via keyword cache. ADR-002 pre-check runs regardless.

**sqlcipher_export():** SQLCipher's native re-keying export via ATTACH DATABASE. Used for
/export. Encrypted-to-encrypted, no plaintext, WAL-safe (empirically verified).

**source_label:** explicit | inferred | user_verified | user_correction

**trace_id:** UUID generated at Stage 0. Propagated through all 14 stages. Written to
trace_log table with status (success|timeout|error) and error_detail per stage.

**warm_start_level:** none | brief | summary | full. Set by Gap Detector based on gap size.

---

# APPENDIX — EMPIRICAL TEST RESULTS

Historical empirical tests ran in sandbox environment against sqlcipher3-binary v0.6.0, SQLCipher 4.12.0.
Current local pytest report after Phase 2 crash-safety test: 28 passed, 1 skipped. The skipped test is SQLCipher-dependent wrong-key behavior; encryption-layer behavior is unverified in the current local test environment until SQLCipher/sqlcipher3 is installed.
Independently re-verified by a second AI sandbox on the same binary version.

| Claim | Test | Result |
|---|---|---|
| KDF: PBKDF2_HMAC_SHA512, 256k iterations | PRAGMA cipher_kdf_algorithm + cipher_default_kdf_iter | VERIFIED ×2 |
| Generated columns survive sqlcipher_export() | ATTACH + export + read back + check confidence | VERIFIED |
| WAL-resident data survives sqlcipher_export() without checkpoint | Write → confirm WAL file >0 bytes → export no checkpoint → restore → read | VERIFIED |
| PRAGMA wal_checkpoint not load-bearing for sqlcipher_export() path | Same test above | CONFIRMED non-load-bearing, kept as defense-in-depth |
| Full schema.sql executes clean | Run against real SQLCipher DB | 19 tables, 6 views, 1 trigger — PASS |
| decision_text_immutable trigger fires correctly | UPDATE decision_text → RAISE(ABORT) | VERIFIED |
| State field remains mutable (only decision_text protected) | UPDATE state → succeeds | VERIFIED |
| Foreign keys enforced (PRAGMA foreign_keys = ON) | Insert contradiction log with nonexistent FK → rejected | CONFIRMED via connection sequence |

---

*End of PIP Master Reference Document v3.0*
*Next action: Write backend/core/constitutional.json*
