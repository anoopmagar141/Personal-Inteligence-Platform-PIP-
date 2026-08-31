"""
Tests for config/provider_consent.json

This file is SEED DATA only — it is loaded into the SQLite provider_consent
table on first run by memory/profile_store.py. It is NOT a JSON Schema
meta-document. These tests confirm its shape and content directly.

Coverage:
- File is valid JSON with no JSON-Schema wrapper ($schema / examples keys absent)
- Top-level keys: schema_version (int), comment (str), providers (list)
- Each provider row has required fields: provider_id, is_cloud, user_consented,
  consent_scope, revoked
- consent_scope enum matches constitutional.json scope_values exactly
- user_consented and revoked only accept 0 or 1
- ADR-030 web_search row matches exactly
- Ollama local provider row matches exactly
- is_cloud is a native JSON boolean (not 0/1) in all rows
"""

import json
import os
import pytest

SEED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "provider_consent.json"
)

# The constitution's scope_values. Kept as a literal on purpose: this list is
# what server.VALID_CONSENT_SCOPES is checked AGAINST, so importing that set
# here would make the test agree with itself no matter what either one said.
# See backend/core/constitutional.json for the constitutional side.
CONSTITUTIONAL_SCOPE_VALUES = ["full_inference", "web_search_only", "embedding_only", "none"]


@pytest.fixture(scope="module")
def data():
    with open(SEED_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def providers(data):
    return data["providers"]


# ---------------------------------------------------------------------------
# 1. File shape — seed-data-only, no JSON Schema wrapper
# ---------------------------------------------------------------------------

def test_no_schema_key(data):
    """Lock: this must never have a $schema key (JSON Schema wrapper forbidden)."""
    assert "$schema" not in data


def test_no_examples_key(data):
    """Lock: this must never have an examples key (JSON Schema wrapper forbidden)."""
    assert "examples" not in data


def test_no_properties_key(data):
    """Lock: this must never have a properties key (JSON Schema wrapper forbidden)."""
    assert "properties" not in data


def test_top_level_schema_version(data):
    assert data["schema_version"] == 1


def test_top_level_comment_present(data):
    assert "comment" in data
    assert isinstance(data["comment"], str)


def test_top_level_providers_is_list(data):
    assert isinstance(data["providers"], list)
    assert len(data["providers"]) >= 1


# ---------------------------------------------------------------------------
# 2. Required fields present in every row
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"provider_id", "is_cloud", "user_consented", "consent_scope", "revoked"}


def test_all_rows_have_required_fields(providers):
    for row in providers:
        missing = REQUIRED_FIELDS - set(row.keys())
        assert not missing, f"Row {row.get('provider_id', '?')} missing: {missing}"


# ---------------------------------------------------------------------------
# 3. consent_scope enum matches constitutional.json scope_values exactly
# ---------------------------------------------------------------------------

def test_consent_scope_enum_matches_constitutional(providers):
    for row in providers:
        assert row["consent_scope"] in CONSTITUTIONAL_SCOPE_VALUES, (
            f"provider_id='{row['provider_id']}' has consent_scope='{row['consent_scope']}' "
            f"which is not in {CONSTITUTIONAL_SCOPE_VALUES}"
        )


# ---------------------------------------------------------------------------
# 4. user_consented and revoked only 0 or 1 (SQLite int-boolean)
# ---------------------------------------------------------------------------

def test_user_consented_is_int_boolean(providers):
    for row in providers:
        assert row["user_consented"] in (0, 1), (
            f"provider_id='{row['provider_id']}' has user_consented={row['user_consented']!r}"
        )


def test_revoked_is_int_boolean(providers):
    for row in providers:
        assert row["revoked"] in (0, 1), (
            f"provider_id='{row['provider_id']}' has revoked={row['revoked']!r}"
        )


# ---------------------------------------------------------------------------
# 5. is_cloud is a native JSON boolean (not 0/1) in all rows
# ---------------------------------------------------------------------------

def test_is_cloud_is_native_boolean(providers):
    for row in providers:
        assert isinstance(row["is_cloud"], bool), (
            f"provider_id='{row['provider_id']}' has is_cloud={row['is_cloud']!r} "
            f"(expected bool, got {type(row['is_cloud']).__name__})"
        )


# ---------------------------------------------------------------------------
# 6. ADR-030 web_search row — exact match
# ---------------------------------------------------------------------------

def test_adr030_web_search_row(providers):
    """
    ADR-030: provider_id='web_search', is_cloud=True,
    user_consented=0 (default off), consent_scope='web_search_only', revoked=0.
    """
    ws = next((p for p in providers if p["provider_id"] == "web_search"), None)
    assert ws is not None, "web_search provider row missing from seed data"
    assert ws["is_cloud"] is True
    assert ws["user_consented"] == 0
    assert ws["consent_scope"] == "web_search_only"
    assert ws["revoked"] == 0


# ---------------------------------------------------------------------------
# 7. Ollama local provider row — exact match
# ---------------------------------------------------------------------------

def test_ollama_row(providers):
    """
    Local model: is_cloud=False, user_consented=1, consent_scope='full_inference', revoked=0.
    """
    ollama = next((p for p in providers if p["provider_id"] == "ollama"), None)
    assert ollama is not None, "ollama provider row missing from seed data"
    assert ollama["is_cloud"] is False
    assert ollama["user_consented"] == 1
    assert ollama["consent_scope"] == "full_inference"
    assert ollama["revoked"] == 0
