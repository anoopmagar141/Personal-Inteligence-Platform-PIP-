"""
The governance audit log: an append-only record of every governance decision
on a memory or decision candidate (BLUEPRINT G-7, A-3; issue #20; owner
decision DEC-5: the thesis keeps "auditable").

What was wrong: a rejected Observer candidate left no permanent record - Stage
13's reject branch called logger.info and nothing else, and trace_log is a
diagnostic table purged after 90 days. So "an auditable enforcement mechanism"
could not show what the guard refused, or why, a month later.

Built in four parts, each with its tests here:
  1. the table, its append-only triggers, and the per-profile salt;
  2. a row at every terminal outcome of a candidate (Stages 11 to 13);
  3. a row at every user resolution of a pending question;
  4. reading it back, and its survival of backup, restore and a password change.

What it is, stated rather than implied (the thesis wording): append-only
within the trust boundary, logged, not tamper-evident. The triggers stop an
UPDATE or DELETE through PIP; someone holding the profile key can drop them.
No candidate text is stored, only a keyed fingerprint (HMAC) of table, field
and value - a correlation key, not secrecy: anyone who can read the table
already holds the key that decrypts the rest of the profile.
"""

import pytest

from backend.memory import governance_audit, profile_store
from backend.memory.profile_store import get_connection, initialize_schema


@pytest.fixture
def conn(tmp_path, db_key):
    c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(c)
    yield c
    c.close()


def _rows(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM governance_audit_log ORDER BY id")]


def _record(conn, **overrides):
    fields = dict(candidate_id="c-1", actor="system", stage=13, outcome="accepted", reason_code="written",
                  target_table="preference_memory", field_name="preferred_tools", value="Neovim",
                  evidence_count=1, confidence=0.18)
    fields.update(overrides)
    return governance_audit.record(conn, **fields)


# --- part 1: the table, the triggers, the salt ---------------------------------


def test_a_fresh_profile_has_the_log_and_its_salt_table(conn):
    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"governance_audit_log", "governance_audit_salt"} <= tables


def test_a_row_holds_a_fingerprint_and_no_candidate_text(conn):
    _record(conn, value="Neovim")

    (row,) = _rows(conn)
    assert row["candidate_hmac"] and "neovim" not in str(row).lower()
    assert row["target_table"] == "preference_memory" and row["field_name"] == "preferred_tools"
    assert row["actor"] == "system" and row["stage"] == 13 and row["outcome"] == "accepted"


@pytest.mark.parametrize("statement", [
    "UPDATE governance_audit_log SET outcome = 'rejected'",
    "DELETE FROM governance_audit_log",
])
def test_a_row_cannot_be_changed_or_removed(conn, statement):
    _record(conn)

    with pytest.raises(Exception, match="append-only"):
        conn.execute(statement)
    conn.rollback()
    assert len(_rows(conn)) == 1


def test_the_salt_is_made_once_and_cannot_be_changed_or_removed(conn):
    first = governance_audit.salt(conn)
    assert governance_audit.salt(conn) == first and len(first) >= 32

    for statement in ("UPDATE governance_audit_salt SET salt = 'ab'", "DELETE FROM governance_audit_salt"):
        with pytest.raises(Exception, match="never"):
            conn.execute(statement)
        conn.rollback()
    assert governance_audit.salt(conn) == first


def test_the_fingerprint_is_stable_per_profile_and_differs_between_profiles(conn, tmp_path, db_key):
    same = governance_audit.fingerprint(conn, "preference_memory", "preferred_tools", "Neovim")
    assert governance_audit.fingerprint(conn, "preference_memory", "preferred_tools", "Neovim") == same
    assert governance_audit.fingerprint(conn, "preference_memory", "preferred_tools", "Emacs") != same

    other = get_connection(str(tmp_path / "other.db"), db_key=db_key)
    try:
        initialize_schema(other)
        assert governance_audit.fingerprint(other, "preference_memory", "preferred_tools", "Neovim") != same
    finally:
        other.close()


@pytest.mark.parametrize("overrides, message", [
    ({"reason_code": "made_up_reason"}, "reason"),
    ({"outcome": "maybe"}, "outcome"),
    ({"actor": "observer"}, "actor"),
    ({"actor": "user", "stage": 13}, "stage"),
    ({"stage": 9}, "stage"),
])
def test_the_writer_refuses_what_the_log_does_not_define(conn, overrides, message):
    with pytest.raises(ValueError, match=message):
        _record(conn, **overrides)
    assert _rows(conn) == []


def test_a_row_records_the_session_it_was_decided_in(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    session = profile_store.current_session_no(conn)

    _record(conn)

    assert _rows(conn)[0]["session_no"] == session


def test_before_onboarding_the_session_is_zero_not_missing(conn):
    _record(conn)
    assert _rows(conn)[0]["session_no"] == 0


def test_an_old_database_gains_the_candidate_id_columns(conn):
    for table in ("memory_candidates_pending", "decision_candidates_pending"):
        conn.execute(f"ALTER TABLE {table} DROP COLUMN candidate_id")
    conn.commit()

    added = set(profile_store.apply_column_migrations(conn))

    assert {"memory_candidates_pending.candidate_id", "decision_candidates_pending.candidate_id"} <= added


def test_a_pending_row_from_before_candidate_ids_gets_its_own_legacy_id():
    assert governance_audit.legacy_candidate_id("memory_candidates_pending", 7) == "legacy:memory_candidates_pending:7"
    assert governance_audit.legacy_candidate_id("memory_candidates_pending", 8) != \
        governance_audit.legacy_candidate_id("memory_candidates_pending", 7)


# --- part 2: a row at every terminal outcome (Stages 11 to 13) ------------------

import json  # noqa: E402

from backend.core.evidence_gate import REJECTION_STATES, _STATUS_FOR_STATE  # noqa: E402
from backend.core.types import ValidationResult  # noqa: E402
from backend.providers.base_provider import BaseLLMProvider  # noqa: E402
from backend.stages import stage_11_observer as observer  # noqa: E402
from backend.stages import stage_13_profile_update as stage_13  # noqa: E402


def _candidate(**overrides):
    candidate = {"target_table": "preference_memory", "field_name": "preferred_tools", "proposed_value": "Neovim",
                 "label": "explicit", "evidence_count": 1, "evidence_text": "I use Neovim",
                 "candidate_id": "cand-1"}
    candidate.update(overrides)
    return candidate


STAGE_13_CASES = [
    # (status, reason, expected stage, outcome, reason_code)
    ("APPROVED", None, 13, "accepted", "written"),
    ("DISCARD", "threshold_violation_week_1_2", 12, "rejected", "threshold_violation_week_1_2"),
    ("DISCARD", "threshold_violation_month_2_plus_evidence", 12, "rejected", "threshold_violation_month_2_plus_evidence"),
    ("HARD_REJECT", "immutable_field", 12, "rejected", "immutable_field"),
    ("HARD_REJECT", "schema_violation", 12, "rejected", "schema_violation"),
    ("REQUIRES_CONFIRMATION", "gated_field", 12, "deferred", "gated_field"),
    ("TIER_2_REQUIRED", "high_confidence_conflict", 12, "deferred", "high_confidence_conflict"),
    ("PROMPT_RECONCILIATION", "behavioral_override", 12, "deferred", "behavioral_override"),
] + [
    (_STATUS_FOR_STATE[state], state, 11, "rejected", state) for state in sorted(REJECTION_STATES)
]


@pytest.mark.parametrize("status, reason, stage, outcome, reason_code", STAGE_13_CASES)
def test_every_status_leaves_exactly_one_row_with_its_stage_and_reason(conn, status, reason, stage, outcome,
                                                                       reason_code):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")

    stage_13.run(conn, _candidate(), ValidationResult(status, reason))

    (row,) = _rows(conn)
    assert (row["candidate_id"], row["stage"], row["actor"], row["outcome"], row["reason_code"]) == \
        ("cand-1", stage, "system", outcome, reason_code)


def test_a_question_already_queued_is_recorded_as_already_queued(conn):
    for candidate_id in ("cand-1", "cand-2"):
        stage_13.run(conn, _candidate(candidate_id=candidate_id),
                     ValidationResult("REQUIRES_CONFIRMATION", "gated_field"))

    assert [(r["candidate_id"], r["stage"], r["reason_code"]) for r in _rows(conn)] == [
        ("cand-1", 12, "gated_field"), ("cand-2", 13, "already_queued")]
    pending = conn.execute("SELECT candidate_id FROM memory_candidates_pending").fetchall()
    assert [p["candidate_id"] for p in pending] == ["cand-1"], "the queued row must carry the candidate id"


def test_a_write_that_fails_twice_is_recorded_as_failed(conn, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(profile_store, "write_approved_candidate", broken)

    assert stage_13.run(conn, _candidate(), ValidationResult("APPROVED")) == "failed"

    assert [(r["stage"], r["outcome"], r["reason_code"]) for r in _rows(conn)] == [(13, "rejected", "write_failed")]


def test_the_month_2_threshold_names_which_rule_refused(conn):
    from backend.core.constitution_enforcer import ConstitutionEnforcer

    enforcer = ConstitutionEnforcer(observer.CONSTITUTION_PATH)
    short_evidence = enforcer.validate(_candidate(evidence_count=1), None, 9)
    low_confidence = enforcer.validate(_candidate(evidence_count=3, label="inferred"), None, 9)

    assert short_evidence.reason == "threshold_violation_month_2_plus_evidence"
    assert low_confidence.reason == "threshold_violation_month_2_plus_confidence"


TRANSCRIPT = (
    "User: I use Neovim for all my coding.\n"
    "Assistant: Nice. Since you love Emacs too, want config tips?\n"
    "User: We decided to use Postgres for the database because SQLite could not take the writes.\n"
)
POSTGRES_QUOTE = "We decided to use Postgres for the database because SQLite could not take the writes"


class _Model(BaseLLMProvider):
    def __init__(self, answer):
        self.answer = answer

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield json.dumps(self.answer)

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


def _answer(memory=(), decisions=()):
    return {"memory_candidates": list(memory), "decision_candidates": list(decisions),
            "session_snapshot": {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""}}


NEOVIM = {"target_table": "preference_memory", "field_name": "preferred_tools", "proposed_value": "Neovim",
          "label": "explicit", "evidence_text": "I use Neovim for all my coding"}


def _seeded_session(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    answer = _answer(
        memory=[
            NEOVIM,                                                                            # written
            {"target_table": "preference_memory", "field_name": "preferred_tools", "proposed_value": "Vim",
             "label": "explicit", "evidence_text": "I adore Vim"},                             # not in transcript
            {"target_table": "preference_memory", "field_name": "preferred_tools", "proposed_value": "Nano",
             "label": "certain", "evidence_text": "I use Neovim"},                            # label not allowed
            {"target_table": "skill_memory", "field_name": "Python", "proposed_value": "expert",
             "label": "explicit", "evidence_text": "I use Neovim"},                           # skill not a number
            {"field_name": "x"},                                                              # malformed
        ],
        decisions=[
            {"decision_text": "Use Postgres for the database",
             "signals_found": ["commitment_language", "explicit_reasoning_in_conversation"],
             "raw_quote": POSTGRES_QUOTE},                                                    # logged
            {"decision_text": "Use Redis", "signals_found": ["commitment_language"],
             "raw_quote": "we will use Redis everywhere"},                                    # quote not said
            {"decision_text": "Since you love Emacs too, want config tips?", "signals_found": [],
             "raw_quote": "We decided to use Postgres for the database"},                     # assistant echo
            {"signals_found": []},                                                            # malformed
        ],
    )
    observer.run_session_end(conn, TRANSCRIPT, _Model(answer), conversation_id="chat-1")


def test_every_candidate_the_observer_drops_or_routes_leaves_one_row(conn):
    _seeded_session(conn)

    rows = _rows(conn)
    assert sorted(r["reason_code"] for r in rows) == sorted([
        "written", "evidence_not_in_transcript", "label_not_allowed", "skill_level_not_a_number",
        "malformed_candidate", "decision_logged", "decision_quote_not_in_transcript", "decision_assistant_echo",
        "decision_malformed"])
    assert all(r["stage"] == 11 for r in rows if r["reason_code"] != "written")
    assert {r["conversation_id"] for r in rows} == {"chat-1"}
    assert len({r["candidate_id"] for r in rows}) == len(rows), "one id per candidate"


def test_a_queued_and_a_duplicate_decision_are_recorded(conn):
    weak = {"decision_text": "Use Postgres for the database", "signals_found": ["commitment_language"],
            "raw_quote": POSTGRES_QUOTE}
    strong = dict(weak, signals_found=["commitment_language", "explicit_reasoning_in_conversation"])
    for decision in (weak, strong, strong):
        observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(decisions=[decision])))

    assert [r["reason_code"] for r in _rows(conn)] == ["decision_queued", "decision_logged", "decision_duplicate"]
    queued = conn.execute("SELECT candidate_id FROM decision_candidates_pending").fetchone()["candidate_id"]
    assert queued == _rows(conn)[0]["candidate_id"]


def test_a_candidate_that_raises_leaves_one_error_row(conn, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(stage_13, "run", broken)

    observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(memory=[NEOVIM])))

    assert [(r["stage"], r["outcome"], r["reason_code"]) for r in _rows(conn)] == [(11, "rejected", "candidate_error")]


def test_a_resumed_chat_records_what_it_did_not_count_again(conn):
    decision = {"decision_text": "Use Postgres for the database",
                "signals_found": ["commitment_language", "explicit_reasoning_in_conversation"],
                "raw_quote": POSTGRES_QUOTE}
    new_turns = "User: thanks, that is all for today.\n"

    observer.run_session_end(conn, TRANSCRIPT + new_turns, _Model(_answer([NEOVIM], [decision])),
                             unobserved_transcript=new_turns)

    assert sorted(r["reason_code"] for r in _rows(conn)) == [
        "decision_quote_only_in_earlier_turns", "evidence_only_in_earlier_turns"]


def test_only_the_writer_inserts_into_the_log():
    # The Promise 1 pattern: outside tests, one module writes this table, and
    # nothing at all updates or deletes from it.
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    writers, changers = [], []
    for path in backend.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "INSERT INTO governance_audit_log" in text:
            writers.append(path.name)
        if "UPDATE governance_audit_log" in text or "DELETE FROM governance_audit_log" in text:
            changers.append(path.name)
    assert writers == ["governance_audit.py"] and changers == []


def test_every_stored_reason_is_a_known_one(conn):
    _seeded_session(conn)
    assert {r["reason_code"] for r in _rows(conn)} <= governance_audit.KNOWN_REASON_CODES


# --- part 3: the user's answers to queued questions ------------------------------

from backend.memory import candidate_store, decision_log  # noqa: E402


def _queue_memory(conn, candidate_id="cand-q", conversation_id="chat-9"):
    stage_13.run(conn, _candidate(candidate_id=candidate_id, conversation_id=conversation_id),
                 ValidationResult("REQUIRES_CONFIRMATION", "gated_field"))
    return conn.execute("SELECT id FROM memory_candidates_pending WHERE candidate_id = ?",
                        (candidate_id,)).fetchone()["id"]


def _user_rows(conn):
    return [r for r in _rows(conn) if r["actor"] == "user"]


def test_confirming_a_queued_memory_joins_the_systems_row(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    row_id = _queue_memory(conn)

    stage_13.resolve_pending(conn, row_id)

    system, user = _rows(conn)
    assert (user["actor"], user["stage"], user["outcome"], user["reason_code"]) == \
        ("user", None, "accepted", "user_confirmed")
    assert user["candidate_id"] == system["candidate_id"] == "cand-q"
    assert user["candidate_hmac"] == system["candidate_hmac"]
    assert user["conversation_id"] == "chat-9", "the user's answer keeps the chat the question came from"


def test_dismissing_a_queued_memory_is_recorded(conn):
    row_id = _queue_memory(conn)

    stage_13.dismiss_pending(conn, row_id)

    assert [(r["outcome"], r["reason_code"]) for r in _user_rows(conn)] == [("dismissed", "user_dismissed")]


def test_saying_no_to_a_check_in_question_is_recorded_as_retiring_the_value(conn):
    from backend.memory import verification

    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    stage_13.run(conn, _candidate(candidate_id="stored"), ValidationResult("APPROVED"))
    row_id = candidate_store.create_memory_candidate(
        conn, target_table="preference_memory", field_name="preferred_tools", proposed_value="Neovim",
        label="explicit", evidence_count=1, evidence_text="I use Neovim",
        validation_status="REQUIRES_CONFIRMATION", origin=verification.ORIGIN)

    assert stage_13.dismiss_pending(conn, row_id)["retired"] is True

    assert [(r["outcome"], r["reason_code"]) for r in _user_rows(conn)] == [("dismissed", "user_retired_field")]


def test_promoting_and_dismissing_queued_decisions_are_recorded(conn):
    weak = {"decision_text": "Use Postgres for the database", "signals_found": ["commitment_language"],
            "raw_quote": POSTGRES_QUOTE}
    observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(decisions=[weak])), conversation_id="chat-2")
    other = dict(weak, decision_text="Use Postgres for the analytics database")
    observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(decisions=[other])))
    first, second = decision_log.list_pending(conn)

    decision_log.promote_pending(conn, first["id"])
    decision_log.dismiss_pending(conn, second["id"])

    users = _user_rows(conn)
    assert [(r["outcome"], r["reason_code"]) for r in users] == [
        ("accepted", "user_promoted_decision"), ("dismissed", "user_dismissed_decision")]
    assert users[0]["candidate_id"] == first["candidate_id"] and users[0]["conversation_id"] == "chat-2"
    assert users[1]["candidate_id"] == second["candidate_id"]


def test_a_question_queued_before_candidate_ids_gets_its_own_legacy_id(conn):
    ids = []
    for value in ("Neovim", "Helix"):
        conn.execute(
            "INSERT INTO memory_candidates_pending (target_table, field_name, proposed_value, label, evidence_count, "
            "evidence_text, validation_status, origin, state, created_at) VALUES ('preference_memory', "
            "'preferred_tools', ?, 'explicit', 1, 'x', 'REQUIRES_CONFIRMATION', 'observer', 'pending', "
            "'2026-10-01T00:00:00Z')", (value,))
        ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.commit()

    for row_id in ids:
        stage_13.dismiss_pending(conn, row_id)

    assert [r["candidate_id"] for r in _user_rows(conn)] == [
        f"legacy:memory_candidates_pending:{ids[0]}", f"legacy:memory_candidates_pending:{ids[1]}"]


def test_an_answer_that_fails_leaves_no_row(conn, monkeypatch):
    row_id = _queue_memory(conn)

    def broken(*args, **kwargs):
        raise ValueError("cannot apply")

    monkeypatch.setattr(profile_store, "apply_verified_correction", broken)
    with pytest.raises(ValueError):
        stage_13.resolve_pending(conn, row_id)

    assert _user_rows(conn) == []


# --- part 4: reading it back; backup, restore and a password change -------------

import importlib.util  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

from backend.core import db_key, restore, session_key  # noqa: E402


def test_the_reader_counts_a_session_by_outcome_and_by_reason(conn):
    _seeded_session(conn)

    summary = governance_audit.summary(conn)

    assert summary["rows"] == 9
    assert summary["by_outcome"] == {"accepted": 2, "rejected": 7}
    assert summary["by_reason"]["written"] == 1 and summary["by_reason"]["decision_assistant_echo"] == 1
    assert sum(summary["by_reason"].values()) == 9
    assert summary["by_actor"] == {"system": 9}


def test_the_reader_follows_one_candidate_from_question_to_answer(conn):
    profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English")
    stage_13.run(conn, _candidate(candidate_id="cand-q"), ValidationResult("REQUIRES_CONFIRMATION", "gated_field"))
    row_id = conn.execute("SELECT id FROM memory_candidates_pending").fetchone()["id"]
    stage_13.dismiss_pending(conn, row_id)

    history = governance_audit.history(conn, "cand-q")

    assert [(h["actor"], h["outcome"], h["reason_code"]) for h in history] == [
        ("system", "deferred", "gated_field"), ("user", "dismissed", "user_dismissed")]


def test_deleting_a_chat_keeps_its_rows_and_they_hold_no_text(tmp_path, db_key):
    from backend.api import server
    from backend.memory import conversation_store

    c = get_connection(str(tmp_path / "chat.db"), db_key=db_key)
    try:
        initialize_schema(c)
        chat = conversation_store.create_conversation(c)
        observer.run_session_end(c, TRANSCRIPT, _Model(_answer(memory=[NEOVIM])), conversation_id=chat)
        before = _rows(c)

        server.api_delete_conversation(c, chat)

        assert _rows(c) == before, "an audit row outlives the chat it came from"
        assert before[0]["conversation_id"] == chat and not conversation_store.conversation_exists(c, chat)
        assert "neovim" not in str(before).lower()
    finally:
        c.close()


OLD_PASSWORD, NEW_PASSWORD, BACKUP_PASSWORD = "old-live-password", "new-live-password", "backup-password"


@pytest.fixture
def keyed_profile(tmp_path, monkeypatch):
    """A profile keyed from a password, as the app makes one, with an audited session in it."""
    monkeypatch.setenv("PIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    key = db_key.derive_key(OLD_PASSWORD, db_key.create_salt(tmp_path / "salt.bin"))
    c = profile_store.get_connection(str(tmp_path / "pip.db"), key)
    profile_store.initialize_schema(c)
    _seeded_session(c)
    facts = {"rows": len(_rows(c)), "salt": governance_audit.salt(c),
             "neovim": governance_audit.fingerprint(c, "preference_memory", "preferred_tools", "Neovim")}
    c.close()
    return tmp_path, key, facts


def _open(path, password):
    key = db_key.derive_key(password, db_key.load_salt(path / "salt.bin"))
    return profile_store.get_connection(str(path / "pip.db"), key)


def _triggers(c):
    return {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}


def test_a_backup_and_restore_keep_every_row_the_triggers_and_the_salt(keyed_profile, monkeypatch):
    path, key, facts = keyed_profile
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("export_backup", root / "scripts" / "export_backup.py")
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    backup = path / "audit.pipbak"
    monkeypatch.setenv("PIP_DB_KEY", key)
    # The live database is keyed from a password here, as the app keys it, so
    # the script asks for that first and then for the backup's own.
    monkeypatch.setattr(export.getpass, "getpass",
                        lambda prompt="": OLD_PASSWORD if "database password" in prompt else BACKUP_PASSWORD)
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", str(path / "pip.db"), "--out", str(backup)])
    export.main()

    restore.stage_restore(backup, BACKUP_PASSWORD, NEW_PASSWORD, db_path=path / "pip.db", salt_path=path / "salt.bin")
    assert restore.drain_pending_restore() is not None

    restored = _open(path, NEW_PASSWORD)
    try:
        assert len(_rows(restored)) == facts["rows"]
        assert {"governance_audit_log_no_update", "governance_audit_log_no_delete",
                "governance_audit_salt_no_update", "governance_audit_salt_no_delete"} <= _triggers(restored)
        assert governance_audit.salt(restored) == facts["salt"]
        with pytest.raises(Exception, match="append-only"):
            restored.execute("DELETE FROM governance_audit_log")
    finally:
        restored.close()


def test_a_password_change_keeps_the_same_fingerprint_for_the_same_candidate(keyed_profile):
    path, _, facts = keyed_profile

    session_key.change_password(OLD_PASSWORD, NEW_PASSWORD, str(path / "pip.db"))

    rekeyed = _open(path, NEW_PASSWORD)
    try:
        assert governance_audit.salt(rekeyed) == facts["salt"]
        assert governance_audit.fingerprint(rekeyed, "preference_memory", "preferred_tools", "Neovim") == facts["neovim"]
        assert len(_rows(rekeyed)) == facts["rows"]
    finally:
        rekeyed.close()


def test_a_candidate_that_fails_after_its_row_was_written_gets_no_second_row(conn, monkeypatch):
    real_audit = stage_13._audit

    def audit_then_fail(*args, **kwargs):
        real_audit(*args, **kwargs)
        raise RuntimeError("failed after the row was written")

    monkeypatch.setattr(stage_13, "_audit", audit_then_fail)

    observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(memory=[NEOVIM])))

    assert [r["reason_code"] for r in _rows(conn)] == ["written"], "exactly one row per candidate"


def test_a_candidate_saved_when_its_audit_row_cannot_be_written_is_not_recorded_as_rejected(conn, monkeypatch):
    # Found while recording G-7: Stage 13 wrote the memory, its audit row then
    # failed, the error reached Stage 11's per-candidate isolation, and that
    # recorded the candidate as rejected (candidate_error) although it was saved.
    # A missing row is a gap the log admits (the failure is logged); a row that
    # says the opposite of what happened is not.
    real_record = governance_audit.record

    def the_written_row_fails(conn, **fields):
        if fields["reason_code"] == "written":
            raise RuntimeError("database is locked")
        return real_record(conn, **fields)

    monkeypatch.setattr(governance_audit, "record", the_written_row_fails)

    observer.run_session_end(conn, TRANSCRIPT, _Model(_answer(memory=[NEOVIM])))

    assert conn.execute("SELECT value FROM preference_memory WHERE name = 'preferred_tools'").fetchone() is not None
    assert _rows(conn) == [], "no row may say a saved candidate was rejected"


def test_every_reason_the_constitution_can_give_is_a_known_one():
    # Stage 13 logs an audit row it cannot write rather than raising, so a new
    # Constitution reason missing from the known set would cost its rows
    # quietly; this makes that loud instead.
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "core" / "constitution_enforcer.py").read_text(encoding="utf-8")
    reasons = set(re.findall(r'ValidationResult\.[A-Z_0-9]+\("([^"]+)"\)', source))

    assert len(reasons) >= 9
    assert reasons <= governance_audit.CONSTITUTION_REASONS, reasons - governance_audit.CONSTITUTION_REASONS
