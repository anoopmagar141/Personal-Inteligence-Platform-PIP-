"""
PIP Memory layer - configured OpenAI-compatible endpoints (schema.sql's
llm_endpoints table).

An endpoint is a base URL, a model name and optionally a key. One row here
becomes one OpenAICompatibleProvider in the pipeline's fallback list, which is
the whole reason the table exists: the provider class was written and could
not be constructed, because nothing stored the three facts it needs.

WHY ADDING AN ENDPOINT ALSO WRITES A CONSENT ROW
------------------------------------------------
stage_08 fails closed on a provider_id it has no record for, so an endpoint
saved without one is refused by the gate and silently never used. Two writes
that must happen together, in one place, or the feature looks broken in a way
that points at the wrong file.

They are NOT the same decision though, and the default differs by where the
data goes. A local endpoint is consented by the act of adding it: the user
typed the address of a server on their own machine, and there is no third
party to agree to. A cloud endpoint is stored unconsented and stays inert
until somebody says yes to it by name - which mirrors how config's seed
already treats web_search, and keeps "nothing leaves this machine without
being agreed to" true rather than aspirational.

is_local is carried from the caller rather than sniffed from the URL, for the
reason the provider class documents: a hostname is a bad proxy for where data
travels, and a wrong guess here is a wrong claim in the interface that exists
to describe it.
"""

from datetime import datetime, timezone
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_endpoint(
    conn,
    *,
    provider_id: str,
    label: str,
    base_url: str,
    model_name: str,
    api_key: Optional[str] = None,
    is_local: bool = False,
    supports_response_format: bool = False,
    enabled: bool = True,
    priority: int = 100,
) -> None:
    """
    Save an endpoint and the consent record that lets it actually be used.

    Re-adding an existing provider_id updates it in place. That is deliberate:
    the realistic reason to add the same id twice is fixing a typo in a URL or
    replacing a rotated key, and refusing would leave the user to delete a row
    they cannot see in order to correct one they can.

    The consent row is only INSERTed, never updated, so re-saving an endpoint
    cannot quietly re-grant consent that the user has since revoked - the one
    thing an "upsert everything" would get wrong.
    """
    conn.execute(
        """
        INSERT INTO llm_endpoints (
            provider_id, label, base_url, model_name, api_key,
            is_local, supports_response_format, enabled, priority, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider_id) DO UPDATE SET
            label = excluded.label,
            base_url = excluded.base_url,
            model_name = excluded.model_name,
            api_key = excluded.api_key,
            is_local = excluded.is_local,
            supports_response_format = excluded.supports_response_format,
            enabled = excluded.enabled,
            priority = excluded.priority
        """,
        (
            provider_id,
            label,
            base_url,
            model_name,
            api_key,
            1 if is_local else 0,
            1 if supports_response_format else 0,
            1 if enabled else 0,
            priority,
            _now(),
        ),
    )

    # consent_date is set only where consent is actually being granted. A
    # cloud endpoint is stored unconsented, and stamping it with a date would
    # record an agreement that has not happened - in the column somebody would
    # later read to find out when it did.
    conn.execute(
        """
        INSERT INTO provider_consent (
            provider_id, is_cloud, user_consented, consent_date, consent_scope, revoked
        ) VALUES (?, ?, ?, ?, 'full_inference', 0)
        ON CONFLICT(provider_id) DO NOTHING
        """,
        (
            provider_id,
            0 if is_local else 1,
            1 if is_local else 0,
            _now() if is_local else None,
        ),
    )
    conn.commit()


def list_endpoints(conn, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    """
    Configured endpoints, in the order they should be tried.

    Sorted by priority then provider_id - the second key so that two endpoints
    left on the default priority still come back in a stable order, rather than
    swapping places between calls and making the fallback chain depend on
    SQLite's row layout.
    """
    sql = "SELECT * FROM llm_endpoints"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY priority ASC, provider_id ASC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_endpoint(conn, provider_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM llm_endpoints WHERE provider_id = ?", (provider_id,)
    ).fetchone()
    return dict(row) if row else None


def set_enabled(conn, provider_id: str, enabled: bool) -> bool:
    """
    Turn an endpoint on or off without discarding its configuration.

    Separate from remove_endpoint because the two answer different questions.
    Switching off is "not right now" and keeps the URL and key; removing is
    "not this provider", and should take the key with it.
    """
    cursor = conn.execute(
        "UPDATE llm_endpoints SET enabled = ? WHERE provider_id = ?",
        (1 if enabled else 0, provider_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def remove_endpoint(conn, provider_id: str) -> bool:
    """
    Delete an endpoint and the consent record created alongside it.

    The consent row goes too, which is the point rather than tidiness: leaving
    it behind would mean re-adding the same provider_id later inherits a "yes"
    from a decision the user made about a different URL and a different key.
    stage_08's fail-closed default is only meaningful if a provider that is
    gone is genuinely unknown again.
    """
    cursor = conn.execute(
        "DELETE FROM llm_endpoints WHERE provider_id = ?", (provider_id,)
    )
    conn.execute("DELETE FROM provider_consent WHERE provider_id = ?", (provider_id,))
    conn.commit()
    return cursor.rowcount > 0
