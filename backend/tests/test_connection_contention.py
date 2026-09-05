"""
Opening a connection while another one is writing.

Every connection in the backend is short-lived and per-request, and both the
Observer and the startup catch-up write from background threads, so two
connections wanting the database at once is the normal case rather than an edge
one.

WHAT WENT WRONG, AND WHAT DID NOT

Found by installing PIP and choosing a password, not here: /auth/setup starts
the catch-up, the catch-up opens the brand-new database and writes, the
application asks for /status milliseconds later, and that second connection
raised "database is locked" from inside get_connection - before the caller had
run a single query. The first thing a new user saw after setting their password
was "PIP could not read your data".

The obvious diagnosis was that PRAGMA busy_timeout was set after
PRAGMA journal_mode, leaving the statement most likely to block with no timeout
in force. That diagnosis was wrong, and was measured to be wrong: SQLite refuses
to change into or out of WAL while another connection holds a write
transaction, and returns SQLITE_BUSY for it WITHOUT invoking the busy handler.
The switch fails identically at a 5000ms timeout and at 0.

So the fix is not a timeout. journal_mode is a property of the database FILE
rather than of a connection, so the switch is allowed to fail: whoever holds
the lock is setting WAL themselves, and the file ends up in the mode this
wanted anyway.

The window is the first run and only the first run. Once the file is in WAL the
pragma is a no-op that takes no lock - which is also why a test built on an
already-WAL database cannot reproduce any of this, as the first version of this
file found out by passing against the bug.
"""

import sqlite3
import threading
import time

import pytest

from backend.memory import profile_store


@pytest.fixture
def wal_db(tmp_path):
    """A normal, established database - already in WAL."""
    path = str(tmp_path / "pip.db")
    conn = profile_store.get_connection(path)
    profile_store.initialize_schema(conn)
    conn.close()
    return path


@pytest.fixture
def fresh_db(tmp_path):
    """
    A database that has NOT been switched to WAL yet, which is the only state
    in which this race exists and exactly the state a first run is in.
    """
    path = str(tmp_path / "fresh.db")
    plain = sqlite3.connect(path)
    plain.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    plain.commit()
    plain.close()
    return path


def test_a_connection_opens_while_a_new_database_is_being_written(fresh_db):
    """
    The regression. Another connection holds an exclusive write on a database
    that is not yet WAL - which is what the startup catch-up is doing at the
    moment the application asks for /status.

    Before the fix this raised OperationalError from inside get_connection.
    """
    holder = sqlite3.connect(fresh_db, check_same_thread=False)
    holder.execute("BEGIN EXCLUSIVE")
    holder.execute("INSERT INTO identity (id, name) VALUES (1, 'BatMan')")

    try:
        conn = profile_store.get_connection(fresh_db)
    except Exception as e:  # noqa: BLE001 - the point is that nothing escapes
        holder.rollback()
        holder.close()
        pytest.fail(f"get_connection raised while another connection was writing: {e!r}")

    try:
        # Alive and configured, checked with a connection-level pragma rather
        # than a query. Nothing can READ through an exclusive lock, and
        # asserting otherwise would be asserting that SQLite does not work -
        # the claim here is only that get_connection hands back a connection
        # instead of raising. The next test covers reading, after the writer
        # commits.
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    finally:
        conn.close()
        holder.rollback()
        holder.close()


def test_the_data_is_readable_once_the_writer_commits(fresh_db):
    """
    And the connection handed back during the overlap keeps working afterwards,
    rather than being wedged in whatever state it was opened in.
    """
    holder = sqlite3.connect(fresh_db, check_same_thread=False)
    holder.execute("BEGIN EXCLUSIVE")
    holder.execute("INSERT INTO identity (id, name) VALUES (1, 'BatMan')")

    conn = profile_store.get_connection(fresh_db)

    def commit_shortly():
        time.sleep(0.3)
        holder.commit()
        holder.close()

    threading.Thread(target=commit_shortly, daemon=True).start()
    time.sleep(0.8)

    try:
        row = conn.execute("SELECT name FROM identity WHERE id = 1").fetchone()
        assert row["name"] == "BatMan"
    finally:
        conn.close()


def test_an_established_database_still_ends_up_in_wal(wal_db):
    """
    The switch is allowed to fail, which must not mean it stopped happening.
    Every uncontended open still gets WAL - it is only the contended first run
    that is permitted to skip it and let the other connection do it.
    """
    conn = profile_store.get_connection(wal_db)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()


def test_foreign_keys_are_not_allowed_to_fail(wal_db):
    """
    The distinction the fix rests on. journal_mode belongs to the file and may
    be left to another connection; foreign_keys belongs to THIS connection, so
    nothing may swallow it - a connection without it silently stops enforcing
    every ON DELETE CASCADE in schema.sql.
    """
    conn = profile_store.get_connection(wal_db)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_a_busy_timeout_is_in_force_for_ordinary_queries(wal_db):
    """
    Not what fixed the bug above - measured not to be - but still what keeps a
    normal query waiting on the Observer's write rather than failing on it.
    """
    conn = profile_store.get_connection(wal_db)
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
    finally:
        conn.close()


def test_the_driver_specific_error_class_is_covered():
    """
    sqlcipher3's OperationalError is not a subclass of sqlite3's, so a handler
    written against only the standard one would catch nothing on the encrypted
    path - which is the only path a real installation uses.
    """
    names = {e.__module__.split(".")[0] for e in profile_store.OPERATIONAL_ERRORS}
    assert "sqlite3" in names
    if profile_store.sqlcipher3 is not None:
        assert "sqlcipher3" in names
