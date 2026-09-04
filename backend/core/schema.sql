-- PIP Database Schema (SQLite/SQLCipher)
-- Version 1.0

-- Ensure foreign keys are enabled (must be executed at connection startup as well)
PRAGMA foreign_keys = ON;

-- 1. profile_meta Table
CREATE TABLE IF NOT EXISTS profile_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    session_count INTEGER DEFAULT 0,
    schema_version TEXT NOT NULL,
    constitution_version TEXT NOT NULL,
    first_session_date TEXT,
    last_session_date TEXT,
    -- When the PREVIOUS session was last active, captured by begin_session()
    -- before it overwrites last_session_date. Stage 0 measures the warm-start
    -- gap from this.
    --
    -- It needs its own column because last_session_date is set on the first
    -- message of the current session, which happens BEFORE the pipeline runs -
    -- so by the time Stage 0 reads anything, last_session_date already says
    -- "now" and every gap would measure zero.
    previous_session_date TEXT,
    onboarding_complete INTEGER DEFAULT 0 CHECK (onboarding_complete IN (0, 1))
);

-- 2. identity Table
CREATE TABLE IF NOT EXISTS identity (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    language_preference TEXT NOT NULL,
    timezone TEXT NOT NULL
);

-- 3. skill_memory Table
CREATE TABLE IF NOT EXISTS skill_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    level REAL NOT NULL CHECK (level >= 0.0 AND level <= 1.0),
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    source_label TEXT NOT NULL CHECK (source_label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    confidence REAL GENERATED ALWAYS AS (
        CASE WHEN source_label IN ('explicit', 'user_verified', 'user_correction') THEN 0.9 ELSE 0.4 END * 
        (CASE WHEN evidence_count > 5 THEN 5 ELSE evidence_count END) / 5.0
    ) STORED,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))
);

-- 4. skill_contradiction_log Table
-- session_no: see preference_contradiction_log below - the behavioral override
-- counts sessions, not rows, and this table feeds the same rule.
CREATE TABLE IF NOT EXISTS skill_contradiction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL,
    contradiction_text TEXT NOT NULL,
    session_no INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (skill_id) REFERENCES skill_memory(id) ON DELETE CASCADE
);

-- 5. preference_memory Table
CREATE TABLE IF NOT EXISTS preference_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    source_label TEXT NOT NULL CHECK (source_label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    behavioral_signal_count INTEGER DEFAULT 0 CHECK (behavioral_signal_count >= 0),
    confidence REAL GENERATED ALWAYS AS (
        CASE WHEN source_label IN ('explicit', 'user_verified', 'user_correction') THEN 0.9 ELSE 0.4 END * 
        (CASE WHEN evidence_count > 5 THEN 5 ELSE evidence_count END) / 5.0
    ) STORED,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))
);

-- 6. preference_contradiction_log Table
-- session_no: profile_meta.session_count at the moment the contradiction was
-- observed. The behavioral override triggers on trigger_sessions (3), and
-- without this the enforcer counted ROWS - so three contradictions inside one
-- session satisfied a rule that asks for three separate ones. NULL on rows
-- written before this column existed, and on any observed before onboarding
-- created profile_meta; the enforcer counts those one-each, which is exactly
-- the behaviour they were written under.
CREATE TABLE IF NOT EXISTS preference_contradiction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preference_id INTEGER NOT NULL,
    contradiction_text TEXT NOT NULL,
    session_no INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (preference_id) REFERENCES preference_memory(id) ON DELETE CASCADE
);

-- 7. goal_memory Table
CREATE TABLE IF NOT EXISTS goal_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_text TEXT NOT NULL,
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    decay_flag INTEGER DEFAULT 0 CHECK (decay_flag IN (0, 1)),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned', 'deleted')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 8. interaction_style Table
CREATE TABLE IF NOT EXISTS interaction_style (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    value TEXT NOT NULL,
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    source_label TEXT NOT NULL CHECK (source_label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    confidence REAL GENERATED ALWAYS AS (
        CASE WHEN source_label IN ('explicit', 'user_verified', 'user_correction') THEN 0.9 ELSE 0.4 END * 
        (CASE WHEN evidence_count > 5 THEN 5 ELSE evidence_count END) / 5.0
    ) STORED
);

-- 9. interaction_style_history Table
CREATE TABLE IF NOT EXISTS interaction_style_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT NOT NULL,
    changed_at TEXT NOT NULL
);

-- 10. active_projects Table
CREATE TABLE IF NOT EXISTS active_projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    -- 'deleted' is a retraction, not an erasure: ADR-022's rule for every other
    -- memory table applies here too, and the row survives so that a decision or
    -- a conversation still pointing at this project does not dangle.
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'completed', 'deleted')),
    last_active TEXT NOT NULL
);

-- 11. decision_log Table
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_text TEXT NOT NULL,
    reasoning TEXT,
    alternatives_considered TEXT,
    project_id TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    state TEXT DEFAULT 'active' CHECK (state IN ('active', 'superseded', 'abandoned')),
    superseded_by INTEGER,
    -- Why this decision left 'active'. update_decision_state() has always
    -- REQUIRED a reason for superseded/abandoned and validated it non-empty,
    -- then discarded it for want of anywhere to put it - so the log recorded
    -- that six decisions were retracted but not why, in a project whose
    -- entire premise is an auditable record. NULL for decisions still active,
    -- and for any retracted before this column existed.
    state_reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES active_projects(project_id) ON DELETE SET NULL,
    FOREIGN KEY (superseded_by) REFERENCES decision_log(id) ON DELETE SET NULL
);

-- 12. decision_candidates_pending Table
CREATE TABLE IF NOT EXISTS decision_candidates_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_text TEXT NOT NULL,
    signals_found TEXT,
    raw_quote TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    state TEXT DEFAULT 'pending' CHECK (state IN ('pending', 'promoted', 'dismissed')),
    dismissed_at TEXT,
    created_at TEXT NOT NULL
);

-- 13. memory_candidates_pending Table
CREATE TABLE IF NOT EXISTS memory_candidates_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_table TEXT NOT NULL,
    field_name TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    evidence_text TEXT,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('REQUIRES_CONFIRMATION', 'TIER_2_REQUIRED', 'PROMPT_RECONCILIATION')),
    -- Why this row is in the queue. 'observer' is a candidate Stage 12 could not
    -- decide alone; 'verification' is the periodic memory check-in asking the
    -- user to confirm something already stored. Both need a human answer, but a
    -- client has to word them very differently - "should I remember this?" is
    -- not the same question as "do I still have this right?" - and inferring
    -- the difference from prose in evidence_text would be guesswork. NULL on
    -- rows written before this column existed; those were all observer rows,
    -- which is what the backfill records.
    origin TEXT DEFAULT 'observer',
    state TEXT DEFAULT 'pending' CHECK (state IN ('pending', 'resolved', 'dismissed')),
    resolved_at TEXT,
    created_at TEXT NOT NULL
);

-- 14. provider_consent Table
CREATE TABLE IF NOT EXISTS provider_consent (
    provider_id TEXT PRIMARY KEY,
    is_cloud INTEGER NOT NULL CHECK (is_cloud IN (0, 1)),
    user_consented INTEGER NOT NULL CHECK (user_consented IN (0, 1)),
    consent_date TEXT,
    revoked INTEGER NOT NULL CHECK (revoked IN (0, 1)),
    revoked_date TEXT,
    consent_scope TEXT NOT NULL CHECK (consent_scope IN ('full_inference', 'web_search_only', 'embedding_only', 'none'))
);

-- 15. trace_log Table
-- Where pipeline traces actually live now. This table was declared from the
-- start and never written to: core/trace.py wrote to a plain JSON file at
-- backend/logs/trace_log.json instead, which put pipeline diagnostics outside
-- the SQLCipher boundary everything else gets. pipeline.py already carries a
-- security fix that had to STOP recording message text for that exact reason.
-- Same finding, same resolution as session_snapshot a few tables down.
--
-- Keyed by an autoincrement id, not by (trace_id, stage) as it was originally
-- declared. A trace is an event stream, and several stages legitimately log
-- more than once per run - stage_08_provider_gate logs once per blocked
-- provider, again if web_search is blocked, and again if nothing consented is
-- left. Under the composite key the second entry would collide with the first,
-- so the trace would lose events precisely on the error paths it exists to
-- explain. Ordering within a trace comes from the id: now_utc() has
-- second resolution and a whole pipeline run fits inside one second.
CREATE TABLE IF NOT EXISTS trace_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    error_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_trace_log_trace_id ON trace_log(trace_id);
-- Supports the retention sweep (trace.hard_delete_after_days).
CREATE INDEX IF NOT EXISTS idx_trace_log_timestamp ON trace_log(timestamp);

-- 16. topic_interests Table
CREATE TABLE IF NOT EXISTS topic_interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT UNIQUE NOT NULL,
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    last_observed TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'deleted'))
);

-- 17. preferred_tools Table
CREATE TABLE IF NOT EXISTS preferred_tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT UNIQUE NOT NULL,
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    last_observed TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'deleted'))
);

-- 18. document_access_patterns Table
CREATE TABLE IF NOT EXISTS document_access_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_path TEXT NOT NULL,
    access_count INTEGER DEFAULT 1 CHECK (access_count >= 1),
    last_accessed TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'deleted'))
);

-- 19. documents Table
-- SQLite is the source of truth for what's been ingested into ChromaDB (Part 11.1:
-- ChromaDB is NEVER authoritative). content_hash lets a startup rebuild-on-mismatch
-- trigger detect drift (file changed on disk since last ingest) without re-reading
-- every file. chunk_count is stored so a mismatch against the actual ChromaDB
-- collection count is detectable without querying every chunk's metadata.
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    chunk_count INTEGER NOT NULL CHECK (chunk_count >= 0),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'removed')),
    ingested_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES active_projects(project_id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_file_path_active
ON documents(file_path) WHERE status = 'active';

-- 20. session_snapshot Table
-- Observer's (Stage 11) end-of-session summary, used to warm-start future
-- sessions (Stage 0/7). Singleton row (id=1), same pattern as profile_meta/
-- identity/interaction_style. Previously a plain JSON file at
-- data/session_snapshot.json - moved into the encrypted DB (security review
-- finding: topic/decisions/open-problems sat in plaintext outside the
-- SQLCipher boundary the rest of "structured data" gets, unlike
-- pending_observer's session_transcript a few tables down, which was always
-- SQLCipher-encrypted). open_problems/last_decisions are JSON-encoded TEXT -
-- SQLite has no native array type - same pattern already used for
-- decision_candidates_pending.signals_found.
CREATE TABLE IF NOT EXISTS session_snapshot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    topic TEXT NOT NULL DEFAULT '',
    open_problems TEXT NOT NULL DEFAULT '[]',
    last_decisions TEXT NOT NULL DEFAULT '[]',
    suggested_next_step TEXT NOT NULL DEFAULT '',
    snapshot_date TEXT
);

-- 21. pending_observer Table
-- ADR-033 condition 2. An Observer pass (llama3.1:8b, ~130s cold / an unmeasured but
-- likely still substantial warm time per the ADR-033 A/B test) cannot block
-- SIGINT/SIGTERM that long. When the pipeline must exit before Observer completes,
-- the session transcript is persisted here (SQLCipher-encrypted, never a plain file)
-- instead of being lost, and drained before Stage 0 on next launch. Also closes the
-- pre-existing ADR-003 gap: unexpected process death during the Observer pass no
-- longer loses that session's learning.
-- 'processing' rows are included in drain queries, not just 'pending': a row left in
-- 'processing' means a previous drain attempt was itself interrupted mid-run, which is
-- exactly the crash case this table exists to survive - it must be retried, not ignored.
CREATE TABLE IF NOT EXISTS pending_observer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_transcript TEXT NOT NULL,
    session_started_at TEXT,
    session_ended_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_detail TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT
);

-- llm_settings Table (added after the original numbered sequence below - not
-- renumbering table 22's existing decision_fts note to avoid touching every
-- other comment in this codebase that already cites it by number).
-- Which locally-pulled Ollama model pipeline.py's _default_providers() uses -
-- previously hardcoded to "llama3.1:8b" everywhere. Its own table, not a
-- column on profile_meta/identity, following the session_snapshot precedent
-- above: a distinct app-level concern gets its own singleton row rather than
-- being bolted onto an unrelated existing one. A missing row (fresh DB, or
-- an existing DB from before this table existed) means "use the hardcoded
-- default" - api_get_active_model()/get_default_model_name() in server.py
-- fall back to that, so this table is optional state, never required.
CREATE TABLE IF NOT EXISTS llm_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    model_name TEXT NOT NULL
);

-- llm_endpoints Table
--
-- Every OpenAI-compatible endpoint the user has configured: llama.cpp, LM
-- Studio, Jan, vLLM, or a cloud API. One row becomes one
-- OpenAICompatibleProvider in the pipeline's fallback list.
--
-- WHY THE KEY LIVES HERE AND NOT IN A CONFIG FILE
--
-- config/ is read at startup and sits in plaintext beside the application, and
-- an api_key is a credential that can spend the user's money. This database is
-- SQLCipher-encrypted under a key derived from a password that is never
-- written down (ADR-026, Part 10.1), which makes it the only place in the
-- project where a secret can be kept at rest. A settings file would undo that
-- for the sake of being easier to edit by hand.
--
-- WHY provider_id IS THE PRIMARY KEY
--
-- It is the same id stage_08 looks up in provider_consent, and the gate fails
-- closed on an id with no row. Making it the primary key here means one
-- endpoint is one consent decision - you cannot end up with two endpoints
-- sharing an id where consenting to one silently consents to the other.
--
-- priority orders the fallback chain, ascending, against OLLAMA_PRIORITY in
-- pipeline.py. A lower number than that runs before the local model, which is
-- how somebody deliberately makes a cloud endpoint their primary; the default
-- of 100 leaves it behind Ollama, so adding an endpoint never silently
-- redirects a conversation off the machine.
CREATE TABLE IF NOT EXISTS llm_endpoints (
    provider_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    base_url TEXT NOT NULL,
    model_name TEXT NOT NULL,
    api_key TEXT,
    is_local INTEGER NOT NULL DEFAULT 0 CHECK (is_local IN (0, 1)),
    supports_response_format INTEGER NOT NULL DEFAULT 0 CHECK (supports_response_format IN (0, 1)),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL
);

-- conversations / messages Tables (added after the original numbered
-- sequence, same reasoning as llm_settings above). Part 7's pipeline.py
-- comment "there is no message-history table - the caller owns that state"
-- was true until now: conversation_history lived only in one WS
-- connection's memory, discarded on disconnect. These two tables give chat
-- history the same "Claude/ChatGPT sidebar" persistence real users expect -
-- every turn is written here as it happens, and /ws/chat can resume a past
-- conversation_id by replaying its messages back into a fresh connection's
-- in-memory conversation_history.
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New chat',
    project_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    -- When the Observer last took a pass over this conversation. NULL means it
    -- never has, which is how a session killed without a clean disconnect or
    -- shutdown is found again at startup: the messages were persisted per turn,
    -- but the extraction that turns them into memory never ran, and nothing
    -- previously noticed. See session_lifecycle.recover_unobserved_conversations.
    observed_at TEXT,
    FOREIGN KEY (project_id) REFERENCES active_projects(project_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

-- Note: Table 22 (decision_fts) is created at application level if FTS5 is available
-- as virtual table:
-- CREATE VIRTUAL TABLE IF NOT EXISTS decision_fts USING fts5(decision_text, reasoning, alternatives_considered, decision_id UNINDEXED);

-- 6 Views
CREATE VIEW IF NOT EXISTS active_skills AS 
SELECT * FROM skill_memory WHERE status = 'active';

-- memory_observation_log Table (added after the original numbered sequence,
-- same reasoning as llm_settings and conversations above).
--
-- Part 8.6's REINFORCEMENT step needed somewhere to accumulate. Before this
-- table, stage_12.reinforce_evidence() could only raise evidence_count for a
-- field that was ALREADY stored - and storing it is what the thresholds were
-- blocking. From week 3 onward (evidence >= 2) that is a deadlock: the write
-- needs two observations, the second observation cannot know about the first,
-- so a value PIP had never stored could never be stored, no matter how many
-- times it was observed. Verified before the fix: the same explicit user
-- statement, made in six separate sessions, was DISCARDed all six times with
-- evidence_count stuck at 1.
--
-- One row per observation, counted by DISTINCT session - deliberately the same
-- shape as preference_contradiction_log, which is the mirror image of this
-- (that one accumulates evidence AGAINST a stored value, this one accumulates
-- evidence FOR a proposed one). session_no is NULL for observations made
-- before onboarding created profile_meta; those count one-each, matching the
-- rule used for contradictions.
--
-- Not pruned. An Observer pass writes a handful of rows per session against an
-- indexed integer-keyed table, so this grows far slower than the conversation
-- history sitting beside it.
CREATE TABLE IF NOT EXISTS memory_observation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_table TEXT NOT NULL,
    field_name TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    session_no INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_observation_signal
ON memory_observation_log(target_table, field_name, proposed_value);

-- document_decision_conflicts Table
--
-- constitutional.json allows document_decision_conflict_detected as a proactive
-- trigger, and the name is precise: it fires on a DETECTION, which is an event
-- rather than a standing fact. Stage 5 is the only thing that detects one - it
-- compares retrieved chunks against active decisions on every query - and it
-- was throwing the answer away into a trace log line. This is where it goes now.
--
-- Recording rather than recomputing matters for cost. Answering the trigger
-- from scratch would mean pulling every active document's chunks out of
-- ChromaDB and comparing them against every active decision on each poll;
-- Stage 5 has already done the comparison, for free, on chunks it had to fetch
-- anyway.
--
-- UNIQUE(document_path, decision_id) because the same pair will be detected
-- again on every query that retrieves that document - the row is refreshed, not
-- duplicated.
CREATE TABLE IF NOT EXISTS document_decision_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_path TEXT NOT NULL,
    decision_id INTEGER NOT NULL,
    detected_at TEXT NOT NULL,
    UNIQUE (document_path, decision_id)
);

CREATE VIEW IF NOT EXISTS active_preferences AS 
SELECT * FROM preference_memory WHERE status = 'active';

CREATE VIEW IF NOT EXISTS active_goals AS 
SELECT * FROM goal_memory WHERE status = 'active';

CREATE VIEW IF NOT EXISTS active_topics AS 
SELECT * FROM topic_interests WHERE status = 'active';

CREATE VIEW IF NOT EXISTS active_tools AS 
SELECT * FROM preferred_tools WHERE status = 'active';

CREATE VIEW IF NOT EXISTS active_document_patterns AS
SELECT * FROM document_access_patterns WHERE status = 'active';

CREATE VIEW IF NOT EXISTS active_documents AS
SELECT * FROM documents WHERE status = 'active';

-- Immutability Trigger on decision_log decision_text
CREATE TRIGGER IF NOT EXISTS decision_text_immutable 
BEFORE UPDATE OF decision_text ON decision_log
BEGIN
    SELECT RAISE(ABORT, 'decision_text is write-once and cannot be modified');
END;

-- document_blobs Table
--
-- The bytes of every ingested document, so that a .pipbak is a complete copy of
-- what PIP holds rather than a copy of everything except the source material.
--
-- Before this table, `documents` recorded that a file had been ingested - its
-- path, its content hash, how many chunks it produced - and nothing anywhere
-- held the file itself. Restoring onto a second machine therefore brought back
-- the registry with no way to satisfy it: rebuild_from_sqlite() looked for each
-- recorded path, found nothing, and reported every document missing. The
-- profile, projects, decisions and conversations all arrived; RAG arrived
-- empty, and the only repair was remembering to copy data/documents/ by hand on
-- the day you were already restoring from a backup.
--
-- A separate table rather than a column on `documents`, because list_documents()
-- does SELECT * and is called on every Documents screen load - putting a BLOB in
-- that row would drag the whole corpus through a query that wants five columns.
--
-- This also closes the one place ADR-026's "no plaintext, one encrypted unit"
-- does not hold. Ingested files sit in data/documents/ as ordinary readable
-- files while every other byte PIP owns is inside SQLCipher; storing the content
-- here puts it under the same encryption as the decisions and conversations that
-- discuss it. The files on disk are not deleted - ingestion reads from them and
-- the user put them there - but they are no longer the only copy.
--
-- Bounded by rag.max_document_size_mb (50MB), which ingest_document() already
-- enforces before anything reaches here.
CREATE TABLE IF NOT EXISTS document_blobs (
    document_id INTEGER PRIMARY KEY,
    content BLOB NOT NULL,
    byte_size INTEGER NOT NULL,
    stored_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
