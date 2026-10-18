"""
The Constitution's version is bumped when its rules change, and checked when a
profile signs in (BLUEPRINT G-5; owner decision DEC-6, 2026-10-18: warn loudly
and keep running).

What was wrong: `backend/core/constitutional.json` says "version 1.0, locked
before Observer build", and was edited twice after that with no bump - gated
fields became table-and-field patterns (2026-07-04) and session_continuity
left observer_may_write (2026-08-16). Its own amendment_process says
"on_startup: check profile.constitution_version vs current"; nothing did, and
every profile stored the literal "1.0" whatever rules it ran under. So "which
rules decided this?" had no answer.

Each released version is registered with a fingerprint of its exact text (the
same LF-normalised sha256 the S-1 run stamp records), so an edit without a
bump is caught; a profile records the version it last ran under, so a change
between runs is reported. Neither stops PIP: a mismatch is normal after an
update, and refusing would lock the user out of their own data.
"""

import json
import sys
from pathlib import Path

import pytest

from backend.api import server
from backend.core import constitution_version
from backend.memory import profile_store
from backend.memory.profile_store import get_connection, initialize_schema

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def conn(tmp_path, db_key):
    c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(c)
    yield c
    c.close()


def _profile_version(conn):
    row = conn.execute("SELECT constitution_version FROM profile_meta WHERE id = 1").fetchone()
    return row["constitution_version"] if row else None


def test_the_rules_in_force_are_a_registered_version_with_this_exact_text():
    current = constitution_version.current()

    assert current["version"] == "1.1"
    assert constitution_version.KNOWN_VERSIONS[current["version"]] == current["sha256"]
    rules = json.loads((ROOT / "backend" / "core" / "constitutional.json").read_text(encoding="utf-8"))
    assert rules["changelog"][-1]["version"] == rules["version"], "the bump has no changelog entry"


def test_the_run_stamp_records_the_same_fingerprint():
    # S-1's stamp and this check must agree on what "these rules" means.
    sys.path.insert(0, str(ROOT / "scripts"))
    import _stamp

    stamp = _stamp.run_stamp(None)["constitution"]
    assert constitution_version.KNOWN_VERSIONS[stamp["version"]] == stamp["sha256"]


def test_rules_edited_without_a_bump_are_reported(conn, tmp_path, monkeypatch):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    rules = json.loads(constitution_version.CONSTITUTION_PATH.read_text(encoding="utf-8"))
    rules["immutable_fields"]["fields"].append("preferred_name")  # a rule change, version left alone
    edited = tmp_path / "constitutional.json"
    edited.write_text(json.dumps(rules, indent=2), encoding="utf-8")
    monkeypatch.setattr(constitution_version, "CONSTITUTION_PATH", edited)

    result = constitution_version.check(conn)

    assert any("without a version bump" in w for w in result["warnings"]), result


def test_a_profile_that_last_ran_older_rules_is_warned_once_and_then_recorded(conn, caplog):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    conn.execute("UPDATE profile_meta SET constitution_version = '1.0' WHERE id = 1")
    conn.commit()

    with caplog.at_level("WARNING"):
        first = constitution_version.check_and_record(conn)

    assert any("1.0" in w and "1.1" in w for w in first["warnings"]), first
    assert any("1.0" in r.getMessage() and r.levelname == "WARNING" for r in caplog.records)
    assert _profile_version(conn) == "1.1"
    trace = [r["message"] for r in conn.execute("SELECT message FROM trace_log WHERE stage = 'constitution'")]
    assert any("1.0" in m for m in trace), "the warning is not in the trace"
    assert constitution_version.check_and_record(conn)["warnings"] == []


def test_a_new_profile_records_the_rules_it_starts_under(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")

    assert _profile_version(conn) == constitution_version.current()["version"]
    assert constitution_version.check(conn)["warnings"] == []


def test_an_unreadable_rules_file_is_a_warning_not_a_failed_start(conn, tmp_path, monkeypatch):
    broken = tmp_path / "constitutional.json"
    broken.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(constitution_version, "CONSTITUTION_PATH", broken)

    result = constitution_version.check_and_record(conn)

    assert result["warnings"], "a broken rules file must be reported"


def test_status_reports_the_rules_version_and_any_warning(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    conn.execute("UPDATE profile_meta SET constitution_version = '1.0' WHERE id = 1")
    conn.commit()

    status = server.api_status(conn)

    assert status["constitution"]["version"] == "1.1"
    assert status["constitution"]["profile_version"] == "1.0"
    assert status["constitution"]["warnings"]


def test_signing_in_runs_the_check_and_records_the_version(monkeypatch, tmp_path):
    # Through the app's own start-up catch-up, the path every sign-in takes,
    # rather than calling the check by hand.
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "pip.db")
    monkeypatch.setenv("PIP_DB_PATH", db_path)
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))
    seed = server.open_app_connection(db_path, None)
    profile_store.complete_onboarding(seed, name="Asha Rai", language_preference="English")
    seed.execute("UPDATE profile_meta SET constitution_version = '1.0' WHERE id = 1")
    seed.commit()
    seed.close()
    monkeypatch.setattr(server, "_default_observer_provider", lambda *a, **k: None)

    with TestClient(server.app):  # __enter__ runs the lifespan start-up, catch-up included
        pass

    conn = server.open_app_connection(db_path, None)
    try:
        assert _profile_version(conn) == "1.1"
        trace = [r["message"] for r in conn.execute("SELECT message FROM trace_log WHERE stage = 'constitution'")]
        assert any("1.0 -> 1.1" in m for m in trace), trace
    finally:
        conn.close()
