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
CREATE TABLE IF NOT EXISTS skill_contradiction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL,
    contradiction_text TEXT NOT NULL,
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
CREATE TABLE IF NOT EXISTS preference_contradiction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preference_id INTEGER NOT NULL,
    contradiction_text TEXT NOT NULL,
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
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'completed')),
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
    created_at TEXT NOT NULL
);

-- 13. memory_candidates_pending Table
CREATE TABLE IF NOT EXISTS memory_candidates_pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_name TEXT NOT NULL,
    proposed_value TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('explicit', 'inferred', 'user_verified', 'user_correction')),
    evidence_count INTEGER DEFAULT 1 CHECK (evidence_count >= 1),
    evidence_text TEXT,
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
CREATE TABLE IF NOT EXISTS trace_log (
    trace_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    error_detail TEXT,
    PRIMARY KEY (trace_id, stage)
);

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

-- Note: Table 19 (decision_fts) is created at application level if FTS5 is available
-- as virtual table:
-- CREATE VIRTUAL TABLE IF NOT EXISTS decision_fts USING fts5(decision_text, reasoning, alternatives_considered, decision_id UNINDEXED);

-- 6 Views
CREATE VIEW IF NOT EXISTS active_skills AS 
SELECT * FROM skill_memory WHERE status = 'active';

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

-- Immutability Trigger on decision_log decision_text
CREATE TRIGGER IF NOT EXISTS decision_text_immutable 
BEFORE UPDATE OF decision_text ON decision_log
BEGIN
    SELECT RAISE(ABORT, 'decision_text is write-once and cannot be modified');
END;
