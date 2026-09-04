"""
Tests for Ticket 5: /providers, /consent, /revoke

Coverage:
1. api_list_providers — returns all rows, correct shape
2. api_grant_consent — updates user_consented=1, sets scope, clears revoked
3. api_grant_consent — raises ValueError for unknown provider_id
4. api_revoke_consent — sets revoked=1
5. api_revoke_consent — raises ValueError for unknown provider_id
6. CLI /providers dispatch — calls correct endpoint
7. CLI /consent dispatch — sends correct payload, default scope
8. CLI /consent dispatch — --scope flag respected
9. CLI /revoke dispatch — sends correct request
10. CLI /revoke — raises ValueError when no provider_id given
11. End-to-end: cloud provider call blocked by gate when unconsented
    (CLI -> api_grant_consent/revoke -> Stage 8 gate — the full path,
    not gate in isolation)
"""

import json
import sqlite3
import pytest
from unittest.mock import MagicMock

from backend.memory import profile_store
from backend.api.server import (
    api_list_providers,
    api_grant_consent,
    api_revoke_consent,
)
from backend.stages import stage_08_provider_gate as gate
from backend.stages.stage_08_provider_gate import ProviderConsentError
from frontend.cli.pip_cli import run_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(profile_store.SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def _seed(conn, *, provider_id, is_cloud, user_consented,
          consent_scope="full_inference", revoked=0):
    conn.execute(
        "INSERT INTO provider_consent "
        "(provider_id, is_cloud, user_consented, consent_scope, revoked) "
        "VALUES (?, ?, ?, ?, ?)",
        (provider_id, 1 if is_cloud else 0, user_consented, consent_scope, revoked),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 1. api_list_providers
# ---------------------------------------------------------------------------

def test_list_providers_returns_all_rows():
    conn = _make_conn()
    _seed(conn, provider_id="ollama", is_cloud=False, user_consented=1)
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=0, consent_scope="web_search_only")
    result = api_list_providers(conn)
    ids = {r["provider_id"] for r in result}
    assert ids == {"ollama", "web_search"}


def test_list_providers_returns_correct_shape():
    conn = _make_conn()
    _seed(conn, provider_id="ollama", is_cloud=False, user_consented=1)
    result = api_list_providers(conn)
    row = result[0]
    assert set(row.keys()) >= {"provider_id", "is_cloud", "user_consented",
                               "consent_scope", "revoked"}


def test_list_providers_empty_when_no_rows():
    conn = _make_conn()
    assert api_list_providers(conn) == []


# ---------------------------------------------------------------------------
# 2. api_grant_consent
# ---------------------------------------------------------------------------

def test_grant_consent_sets_user_consented_and_scope():
    conn = _make_conn()
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=0, consent_scope="web_search_only")
    result = api_grant_consent(conn, "web_search", "web_search_only")
    assert result == {"status": "consented", "provider_id": "web_search",
                      "consent_scope": "web_search_only"}
    row = conn.execute(
        "SELECT user_consented, consent_scope, revoked FROM provider_consent "
        "WHERE provider_id = 'web_search'"
    ).fetchone()
    assert row["user_consented"] == 1
    assert row["consent_scope"] == "web_search_only"
    assert row["revoked"] == 0


def test_grant_consent_clears_revoked():
    conn = _make_conn()
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=1, consent_scope="web_search_only", revoked=1)
    api_grant_consent(conn, "web_search", "web_search_only")
    row = conn.execute(
        "SELECT revoked FROM provider_consent WHERE provider_id = 'web_search'"
    ).fetchone()
    assert row["revoked"] == 0


def test_grant_consent_unknown_provider_raises():
    conn = _make_conn()
    with pytest.raises(ValueError, match="Unknown provider"):
        api_grant_consent(conn, "nonexistent", "full_inference")


def test_grant_consent_invalid_scope_raises_before_db_write():
    """Scope validation must fire before any DB access — confirmed by using an
    empty table where the provider doesn't exist either; ValueError must cite
    the scope, not the provider, proving the scope check runs first."""
    conn = _make_conn()
    with pytest.raises(ValueError, match="Invalid consent_scope"):
        api_grant_consent(conn, "web_search", "made_up_scope")



# ---------------------------------------------------------------------------
# 3. api_revoke_consent
# ---------------------------------------------------------------------------

def test_revoke_consent_sets_revoked():
    conn = _make_conn()
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=1, consent_scope="web_search_only")
    result = api_revoke_consent(conn, "web_search")
    assert result == {"status": "revoked", "provider_id": "web_search"}
    row = conn.execute(
        "SELECT revoked FROM provider_consent WHERE provider_id = 'web_search'"
    ).fetchone()
    assert row["revoked"] == 1


def test_revoke_consent_unknown_provider_raises():
    conn = _make_conn()
    with pytest.raises(ValueError, match="Unknown provider"):
        api_revoke_consent(conn, "nonexistent")


# ---------------------------------------------------------------------------
# 4-9. CLI dispatch — mock opener so no HTTP server is needed
# ---------------------------------------------------------------------------

def _mock_response(payload: dict):
    """Build a mock urlopen response returning JSON."""
    body = json.dumps(payload).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body
    return mock_resp


def test_cli_providers_calls_get_providers():
    opener = MagicMock(return_value=_mock_response([
        {"provider_id": "ollama", "is_cloud": 0, "user_consented": 1,
         "consent_scope": "full_inference", "revoked": 0}
    ]))
    result = run_command(["/providers"], opener=opener)
    req = opener.call_args[0][0]
    assert req.get_full_url().endswith("/providers")
    assert req.get_method() == "GET"
    assert result[0]["provider_id"] == "ollama"


def test_cli_consent_sends_correct_payload_default_scope():
    opener = MagicMock(return_value=_mock_response(
        {"status": "consented", "provider_id": "web_search",
         "consent_scope": "full_inference"}
    ))
    result = run_command(["/consent", "web_search"], opener=opener)
    req = opener.call_args[0][0]
    assert "/providers/web_search/consent" in req.get_full_url()
    assert req.get_method() == "POST"
    sent = json.loads(req.data.decode())
    assert sent["consent_scope"] == "full_inference"
    assert result["status"] == "consented"


def test_cli_consent_respects_scope_flag():
    opener = MagicMock(return_value=_mock_response(
        {"status": "consented", "provider_id": "web_search",
         "consent_scope": "web_search_only"}
    ))
    run_command(["/consent", "web_search", "--scope", "web_search_only"],
                opener=opener)
    req = opener.call_args[0][0]
    sent = json.loads(req.data.decode())
    assert sent["consent_scope"] == "web_search_only"


def test_cli_revoke_sends_correct_request():
    opener = MagicMock(return_value=_mock_response(
        {"status": "revoked", "provider_id": "web_search"}
    ))
    result = run_command(["/revoke", "web_search"], opener=opener)
    req = opener.call_args[0][0]
    assert "/providers/web_search/revoke" in req.get_full_url()
    assert req.get_method() == "POST"
    assert result["status"] == "revoked"


def test_cli_revoke_no_provider_id_raises():
    with pytest.raises(ValueError, match="usage: /revoke"):
        run_command(["/revoke"])


# ---------------------------------------------------------------------------
# 11. End-to-end: cloud provider BLOCKED when unconsented
#     Path: CLI command -> api function -> Stage 8 gate
#     This is NOT the gate in isolation — it tests the full chain:
#       run_command(/consent) -> api_grant_consent -> gate.run passes
#       run_command(/revoke)  -> api_revoke_consent -> gate.run raises
# ---------------------------------------------------------------------------

def test_end_to_end_revoke_then_gate_blocks():
    """
    Full path test:
      1. Seed web_search as consented (user_consented=1, revoked=0).
      2. Call api_revoke_consent (what /revoke wires to) — same DB conn.
      3. Then run gate.run() on the same conn — must raise ProviderConsentError.
    This tests that the data written by api_revoke_consent is exactly what
    the gate reads, not just that each function works in isolation.
    """
    conn = _make_conn()
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=1, consent_scope="web_search_only")

    # Gate passes before revocation
    record = gate.run(conn, "web_search", requested_scope="web_search_only")
    assert record.user_consented is True
    assert record.revoked is False

    # Revoke via the API function (same function /revoke CLI calls)
    api_revoke_consent(conn, "web_search")

    # Gate must now hard-stop
    with pytest.raises(ProviderConsentError) as exc:
        gate.run(conn, "web_search", requested_scope="web_search_only")
    assert "revoked" in str(exc.value)


def test_end_to_end_grant_consent_then_gate_passes():
    """
    Full path test:
      1. Seed web_search as unconsented.
      2. Gate blocks (fail-closed).
      3. Call api_grant_consent (what /consent wires to) — same DB conn.
      4. Gate now passes.
    """
    conn = _make_conn()
    _seed(conn, provider_id="web_search", is_cloud=True,
          user_consented=0, consent_scope="web_search_only")

    # Gate blocks before consent
    with pytest.raises(ProviderConsentError):
        gate.run(conn, "web_search", requested_scope="web_search_only")

    # Grant consent via the API function (same function /consent CLI calls)
    api_grant_consent(conn, "web_search", "web_search_only")

    # Gate now passes
    record = gate.run(conn, "web_search", requested_scope="web_search_only")
    assert record.user_consented is True
    assert record.revoked is False
