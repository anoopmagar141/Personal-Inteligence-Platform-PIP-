"""
Tests for backend/stages/stage_08_provider_gate.py and the seeding function
in backend/memory/profile_store.py (seed_provider_consent).

All tests use an in-memory SQLite DB initialised with the real schema.
The seed_provider_consent function is called with a temp JSON file so tests
are independent of the real config/provider_consent.json on disk.
"""

import json
import sqlite3
import tempfile
import os
import pytest

from backend.memory import profile_store
from backend.stages import stage_08_provider_gate as gate
from backend.stages.stage_08_provider_gate import ProviderConsentError, ConsentRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn() -> sqlite3.Connection:
    """In-memory SQLite connection with schema applied but NOT seeded."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(profile_store.SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def _insert_provider(conn, *, provider_id, is_cloud, user_consented,
                     consent_scope="full_inference", revoked=0):
    conn.execute(
        """INSERT INTO provider_consent
               (provider_id, is_cloud, user_consented, consent_scope, revoked)
           VALUES (?, ?, ?, ?, ?)""",
        (provider_id, 1 if is_cloud else 0, user_consented, consent_scope, revoked),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# seed_provider_consent tests
# ---------------------------------------------------------------------------

def _make_seed_file(providers: list) -> str:
    """Write a temp seed JSON file; caller is responsible for cleanup."""
    data = {"schema_version": 1, "comment": "test", "providers": providers}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    return path


def test_seed_inserts_rows_when_table_empty():
    conn = _make_conn()
    seed_path = _make_seed_file([
        {"provider_id": "ollama", "is_cloud": False,
         "user_consented": 1, "consent_scope": "full_inference", "revoked": 0},
        {"provider_id": "web_search", "is_cloud": True,
         "user_consented": 0, "consent_scope": "web_search_only", "revoked": 0},
    ])
    try:
        from pathlib import Path
        profile_store.seed_provider_consent(conn, seed_path=Path(seed_path))
        rows = conn.execute("SELECT provider_id FROM provider_consent ORDER BY provider_id").fetchall()
        ids = [r["provider_id"] for r in rows]
        assert ids == ["ollama", "web_search"]
    finally:
        os.unlink(seed_path)


def test_seed_is_idempotent_when_table_has_rows():
    """Calling seed twice must not duplicate or overwrite rows."""
    conn = _make_conn()
    seed_path = _make_seed_file([
        {"provider_id": "ollama", "is_cloud": False,
         "user_consented": 1, "consent_scope": "full_inference", "revoked": 0},
    ])
    try:
        from pathlib import Path
        p = Path(seed_path)
        profile_store.seed_provider_consent(conn, seed_path=p)
        # Manually update user_consented to simulate a real user consent grant
        conn.execute("UPDATE provider_consent SET user_consented = 0 WHERE provider_id = 'ollama'")
        conn.commit()
        # Call seed again — must be a no-op, not overwrite the user's value
        profile_store.seed_provider_consent(conn, seed_path=p)
        row = conn.execute("SELECT user_consented FROM provider_consent WHERE provider_id = 'ollama'").fetchone()
        assert row["user_consented"] == 0  # still 0, not overwritten
        count = conn.execute("SELECT COUNT(*) FROM provider_consent").fetchone()[0]
        assert count == 1  # no duplicates
    finally:
        os.unlink(seed_path)


def test_seed_converts_is_cloud_bool_to_int():
    conn = _make_conn()
    seed_path = _make_seed_file([
        {"provider_id": "web_search", "is_cloud": True,
         "user_consented": 0, "consent_scope": "web_search_only", "revoked": 0},
    ])
    try:
        from pathlib import Path
        profile_store.seed_provider_consent(conn, seed_path=Path(seed_path))
        row = conn.execute("SELECT is_cloud FROM provider_consent WHERE provider_id = 'web_search'").fetchone()
        # SQLite stores as integer; must be 1
        assert row["is_cloud"] == 1
    finally:
        os.unlink(seed_path)


# ---------------------------------------------------------------------------
# Stage 8 gate tests
# ---------------------------------------------------------------------------

class TestLocalProviderPassesWithNoConsentNeeded:
    def test_local_provider_passes(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="ollama", is_cloud=False, user_consented=0)
        record = gate.run(conn, "ollama")
        assert isinstance(record, ConsentRecord)
        assert record.provider_id == "ollama"
        assert record.is_cloud is False

    def test_local_provider_passes_even_with_user_consented_0(self):
        """is_cloud=False means the gate never checks user_consented."""
        conn = _make_conn()
        _insert_provider(conn, provider_id="local_embedder", is_cloud=False, user_consented=0)
        record = gate.run(conn, "local_embedder")
        assert isinstance(record, ConsentRecord)

    def test_local_provider_passes_even_with_revoked_1(self):
        """is_cloud=False bypasses ALL cloud checks, including revoked."""
        conn = _make_conn()
        _insert_provider(conn, provider_id="ollama", is_cloud=False,
                         user_consented=1, revoked=1)
        record = gate.run(conn, "ollama")
        assert isinstance(record, ConsentRecord)


class TestCloudProviderBlockedWhenUnconsented:
    def test_cloud_unconsented_raises(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="web_search", is_cloud=True,
                         user_consented=0, consent_scope="web_search_only")
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "web_search")
        assert "not been consented" in str(exc.value)
        assert "web_search" in str(exc.value)


class TestCloudProviderPassesWhenConsented:
    def test_cloud_consented_passes(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="web_search", is_cloud=True,
                         user_consented=1, consent_scope="web_search_only")
        record = gate.run(conn, "web_search", requested_scope="web_search_only")
        assert isinstance(record, ConsentRecord)
        assert record.user_consented is True
        assert record.revoked is False

    def test_full_inference_scope_covers_any_requested_scope(self):
        """full_inference consent_scope grants access regardless of requested_scope."""
        conn = _make_conn()
        _insert_provider(conn, provider_id="openai", is_cloud=True,
                         user_consented=1, consent_scope="full_inference")
        record = gate.run(conn, "openai", requested_scope="web_search_only")
        assert isinstance(record, ConsentRecord)


class TestCloudProviderBlockedWhenRevoked:
    def test_revoked_blocks_even_if_user_consented_1(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="web_search", is_cloud=True,
                         user_consented=1, consent_scope="web_search_only", revoked=1)
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "web_search")
        assert "revoked" in str(exc.value)
        assert "web_search" in str(exc.value)

    def test_revoke_message_mentions_consent_command(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="web_search", is_cloud=True,
                         user_consented=1, consent_scope="web_search_only", revoked=1)
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "web_search")
        assert "/consent" in str(exc.value)


class TestNoRowExistsCaseFailClosed:
    def test_unknown_provider_raises(self):
        """Fail-closed: provider with no row must be hard-stopped."""
        conn = _make_conn()
        # Table is empty — no row for "new_provider"
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "new_provider")
        assert "No consent record found" in str(exc.value)
        assert "new_provider" in str(exc.value)
        assert "Fail-closed" in str(exc.value)

    def test_unknown_provider_even_if_other_rows_exist(self):
        """Fail-closed applies per provider_id, not globally."""
        conn = _make_conn()
        _insert_provider(conn, provider_id="ollama", is_cloud=False, user_consented=1)
        with pytest.raises(ProviderConsentError):
            gate.run(conn, "unknown_cloud_provider")


class TestScopeEnforcement:
    def test_none_scope_blocks_even_if_consented(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="restricted", is_cloud=True,
                         user_consented=1, consent_scope="none")
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "restricted")
        assert "none" in str(exc.value)

    def test_web_search_only_scope_blocks_full_inference_request(self):
        conn = _make_conn()
        _insert_provider(conn, provider_id="web_search", is_cloud=True,
                         user_consented=1, consent_scope="web_search_only")
        with pytest.raises(ProviderConsentError) as exc:
            gate.run(conn, "web_search", requested_scope="full_inference")
        assert "does not cover" in str(exc.value)
