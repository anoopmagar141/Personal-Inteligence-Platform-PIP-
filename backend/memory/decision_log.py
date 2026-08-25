import re
from typing import Any

from backend.config.settings import get_settings
from backend.core.types import now_utc
from backend.memory import candidate_store


KNOWN_DECISION_SIGNALS = {
    "explicit_reasoning_in_conversation",
    "commitment_language",
    "alternative_considered",
}

COMMITMENT_TERMS = (
    "decide",
    "decided",
    "choose",
    "chosen",
    "use ",
    "will ",
    "commit",
    "locked",
)


def create_decision(
    conn,
    *,
    text: str,
    reasoning: str | None = None,
    alternatives: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    signals = classify_decision_signals(text, reasoning, alternatives)
    confidence = score_confidence(signals)
    threshold = get_settings()["decision_log"]["log_threshold_manual"]

    if confidence < threshold:
        candidate_id = candidate_store.create_decision_candidate(
            conn,
            decision_text=text,
            signals_found=signals,
            raw_quote=text,
            confidence=confidence,
        )
        return {"status": "pending", "candidate_id": candidate_id, "confidence": confidence, "signals": signals}

    decision_id = insert_decision(
        conn,
        text=text,
        reasoning=reasoning,
        alternatives=alternatives,
        project_id=project_id,
        confidence=confidence,
    )
    return {"status": "logged", "decision_id": decision_id, "confidence": confidence, "signals": signals}


def route_observer_decision(
    conn,
    *,
    text: str,
    signals_found: list[str],
    raw_quote: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """
    Routes an Observer-sourced decision candidate using log_threshold_observer
    (Part 8.7: two-plus signals auto-log; a single signal goes to
    decision_candidates_pending rather than auto-logging, to avoid noise from
    casual commitment language in Observer output).

    Unlike create_decision() (the manual /decide path), signals come from
    Observer's own reading of the full conversation, not keyword matching over
    separate reasoning/alternatives text - that's the value Phase 7 adds over
    Phase 1's manual path (B4 keeps other classifiers keyword/regex-based;
    Observer is the one stage that's deliberately a full LLM). Confidence is
    still always computed deterministically via score_confidence(), never
    assigned by the model itself (ADR-005) - unknown signal strings are
    dropped before scoring so a hallucinated signal name can't inflate it.
    """
    signals = [s for s in signals_found if s in KNOWN_DECISION_SIGNALS]
    confidence = score_confidence(signals)
    threshold = get_settings()["decision_log"]["log_threshold_observer"]

    if confidence < threshold:
        candidate_id = candidate_store.create_decision_candidate(
            conn,
            decision_text=text,
            signals_found=signals,
            raw_quote=raw_quote,
            confidence=confidence,
        )
        return {"status": "pending", "candidate_id": candidate_id, "confidence": confidence, "signals": signals}

    decision_id = insert_decision(
        conn,
        text=text,
        reasoning=None,
        alternatives=None,
        project_id=project_id,
        confidence=confidence,
    )
    return {"status": "logged", "decision_id": decision_id, "confidence": confidence, "signals": signals}


def insert_decision(
    conn,
    *,
    text: str,
    reasoning: str | None = None,
    alternatives: str | None = None,
    project_id: str | None = None,
    confidence: float = 0.4,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO decision_log (
            decision_text, reasoning, alternatives_considered,
            project_id, confidence, state, created_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (text, reasoning, alternatives, project_id, confidence, now_utc()),
    )
    decision_id = int(cur.lastrowid)
    _sync_decision_fts(conn, decision_id, text, reasoning, alternatives)
    conn.commit()
    return decision_id


def list_decisions(conn, *, state: str = "active", project_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM decision_log WHERE state = ?"
    params: list[Any] = [state]
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params)]


def search_decisions(
    conn,
    *,
    query: str,
    state: str = "active",
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if _ensure_decision_fts(conn):
        return _search_decisions_fts(conn, query=query, state=state, project_id=project_id)
    return _search_decisions_like(conn, query=query, state=state, project_id=project_id)


def update_decision_state(
    conn,
    decision_id: int,
    *,
    state: str,
    reason: str,
    superseded_by: int | None = None,
) -> None:
    if state not in {"active", "superseded", "abandoned"}:
        raise ValueError("invalid decision state")
    if state in {"superseded", "abandoned"} and not reason.strip():
        raise ValueError("reason is required")

    # reason is now persisted (schema.sql: decision_log.state_reason). It was
    # required and validated here from the start, then dropped - so the log
    # recorded that a decision had been retracted while losing the one piece
    # of information that makes a retraction interpretable later. Under
    # ADR-022 nothing is ever deleted, which means these rows are read months
    # afterwards by someone who has to tell "this was a fabrication we cleaned
    # up" from "this was real and we changed our mind" - indistinguishable
    # from state alone.
    #
    # Stored verbatim for every state including 'active': re-activating is
    # itself a decision worth explaining, and silently keeping the old
    # retraction reason on a now-active row would be actively misleading.
    conn.execute(
        "UPDATE decision_log SET state = ?, superseded_by = ?, state_reason = ? WHERE id = ?",
        (state, superseded_by, reason, decision_id),
    )
    conn.commit()


def list_pending(conn, *, limit: int | None = None) -> list[dict[str, Any]]:
    return candidate_store.list_decision_candidates(conn, limit=limit)


def promote_pending(conn, candidate_id: int) -> dict[str, Any]:
    candidate = candidate_store.get_decision_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise ValueError("pending decision candidate not found")

    decision_id = insert_decision(
        conn,
        text=candidate["decision_text"],
        reasoning=candidate["raw_quote"],
        alternatives=None,
        project_id=None,
        confidence=max(candidate["confidence"], get_settings()["decision_log"]["log_threshold_manual"]),
    )
    candidate_store.mark_decision_candidate_promoted(conn, candidate_id)
    return {"status": "promoted", "decision_id": decision_id}


def dismiss_pending(conn, candidate_id: int) -> dict[str, Any]:
    candidate = candidate_store.get_decision_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise ValueError("pending decision candidate not found")
    candidate_store.dismiss_decision_candidate(conn, candidate_id)
    return {"status": "dismissed", "candidate_id": candidate_id}


def classify_decision_signals(
    text: str,
    reasoning: str | None,
    alternatives: str | None,
) -> list[str]:
    signals: list[str] = []
    if reasoning and reasoning.strip():
        signals.append("explicit_reasoning_in_conversation")
    lowered = f" {text.lower()} "
    if any(term in lowered for term in COMMITMENT_TERMS):
        signals.append("commitment_language")
    if alternatives and alternatives.strip():
        signals.append("alternative_considered")
    return signals


def score_confidence(signals: list[str]) -> float:
    count = len(set(signals))
    if count >= 3:
        return 1.0
    if count == 2:
        return 0.7
    if count == 1:
        return 0.4
    return 0.0


def _ensure_decision_fts(conn) -> bool:
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS decision_fts
            USING fts5(
                decision_text,
                reasoning,
                alternatives_considered,
                decision_id UNINDEXED
            )
            """
        )
        conn.commit()
        return True
    except Exception:
        return False


def _sync_decision_fts(
    conn,
    decision_id: int,
    text: str,
    reasoning: str | None,
    alternatives: str | None,
) -> None:
    if not _ensure_decision_fts(conn):
        return
    conn.execute(
        """
        INSERT INTO decision_fts (
            decision_text, reasoning, alternatives_considered, decision_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (text, reasoning, alternatives, decision_id),
    )


def _build_fts5_match_query(query: str) -> str | None:
    """
    Converts an arbitrary natural-language string into a safe FTS5 MATCH
    expression. Raw user/retrieval_hint text (question marks, commas, hyphens,
    parens, quotes) is FTS5 query syntax, not literal content, so passing it
    through unescaped throws "fts5: syntax error" on ordinary punctuation -
    e.g. "What did I just ask you about?" never matches anything, silently,
    because Stage 3 fails open around the exception.

    Tokenizing to bareword characters and re-quoting each token sidesteps the
    syntax-error problem, but implicit AND (FTS5's default for multiple bareword
    operands) turns out to be the wrong join for this use case even once it no
    longer crashes: a natural-language question shares few *exact* words with a
    terse logged decision ("What did we decide about ChromaDB?" vs "We decided
    ChromaDB stays rebuildable." - "did"/"decide" isn't literally "decided"), so
    requiring every query word present made real questions match nothing, just
    without throwing. OR instead - relevance-ranked by bm25() at the call site,
    not just created_at - lets a single shared content word (e.g. "chromadb")
    surface the decision, while common words shared with nearly every entry
    ("we", "did") get bm25-penalized for low informativeness rather than needing
    a hand-maintained stopword list.
    """
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        return None
    return " OR ".join(f'"{token}"' for token in tokens)


def _search_decisions_fts(
    conn,
    *,
    query: str,
    state: str,
    project_id: str | None,
) -> list[dict[str, Any]]:
    match_query = _build_fts5_match_query(query)
    if match_query is None:
        return []

    sql = """
        SELECT d.*
        FROM decision_fts
        JOIN decision_log d ON d.id = decision_fts.decision_id
        WHERE decision_fts MATCH ? AND d.state = ?
    """
    params: list[Any] = [match_query, state]
    if project_id:
        sql += " AND d.project_id = ?"
        params.append(project_id)
    # bm25() ranks more relevant (rarer, more concentrated) term matches first;
    # SQLite's bm25 returns lower-is-better scores, and ties fall back to recency.
    sql += " ORDER BY bm25(decision_fts) ASC, d.created_at DESC, d.id DESC"
    return [dict(row) for row in conn.execute(sql, params)]


def _search_decisions_like(
    conn,
    *,
    query: str,
    state: str,
    project_id: str | None,
) -> list[dict[str, Any]]:
    needle = f"%{query}%"
    sql = """
        SELECT * FROM decision_log
        WHERE state = ?
          AND (
            decision_text LIKE ?
            OR reasoning LIKE ?
            OR alternatives_considered LIKE ?
          )
    """
    params: list[Any] = [state, needle, needle, needle]
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params)]
