import pytest
import os
import sqlite3
from backend.config.settings import get_settings

# Note: In production SQLCipher is accessed via profile_store.py get_connection().
# For these tests, we test the schema execution and SQLite features.
# If sqlcipher3 is not available in the test environment, we fallback to sqlite3
# for testing structure and FTS5, but wrong-key logic is validated if sqlcipher3 is active.

try:
    import sqlcipher3
    HAS_SQLCIPHER = True
except ImportError:
    import sqlite3 as sqlcipher3
    HAS_SQLCIPHER = False

DB_PATH = "test_pip.db"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "schema.sql")

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

def get_db_connection(db_key: str = "testkey"):
    if HAS_SQLCIPHER and "sqlcipher3" in globals() and hasattr(sqlcipher3, "connect"):
        conn = sqlcipher3.connect(DB_PATH)
        conn.execute(f"PRAGMA key = \"x'{db_key}'\"")
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def test_schema_execution():
    # Load and execute schema.sql
    conn = get_db_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    
    # Assert tables exist
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        "profile_meta", "identity", "skill_memory", "preference_memory",
        "goal_memory", "interaction_style", "active_projects", "decision_log"
    ]
    for table in expected_tables:
        assert table in tables

    # Assert views exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = [row[0] for row in cursor.fetchall()]
    assert "active_skills" in views
    assert "active_preferences" in views

def test_wrong_key_behavior():
    if not HAS_SQLCIPHER:
        pytest.skip("SQLCipher is not installed, skipping wrong key check")
        
    # Create DB with key1
    conn = get_db_connection(db_key="1111111111111111111111111111111111111111111111111111111111111111")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en', 'UTC')")
    conn.commit()
    conn.close()

    # Reopen with wrong key2
    conn2 = get_db_connection(db_key="2222222222222222222222222222222222222222222222222222222222222222")
    
    # Try reading from identity - must fail loudly (throws database error due to encryption mismatch)
    with pytest.raises(Exception):
        conn2.execute("SELECT count(*) FROM sqlite_master").fetchall()

def test_fts5_roundtrip():
    conn = get_db_connection()
    
    # Test FTS5 creation
    try:
        conn.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content, doc_id UNINDEXED)")
    except sqlite3.OperationalError:
        pytest.skip("FTS5 extension not available in sqlite3")

    conn.execute("INSERT INTO test_fts (content, doc_id) VALUES ('ChromaDB is selected for local-first design', 42)")
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT doc_id FROM test_fts WHERE test_fts MATCH 'ChromaDB'")
    res = cursor.fetchall()
    assert len(res) == 1
    assert res[0][0] == 42
