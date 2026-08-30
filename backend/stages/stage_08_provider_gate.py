# PIP Message Pipeline - Stage 8: Provider Consent Gate
#
# ADR-030 / Provider Consent Gate design:
#
# Fail-closed policy (explicit architectural decision):
#   If a provider_id has NO row in the provider_consent table, the gate
#   treats it as NOT consented and raises ProviderConsentError (hard stop).
#   Rationale: This gate exists to enforce a privacy guarantee — that no
#   outbound network call reaches a cloud provider without the user's
#   explicit, recorded consent. Failing open (allowing an unknown provider
#   through) would silently break this guarantee every time a new provider
#   is deployed before its consent row is seeded. Failing closed means the
#   failure is loud and immediate, forcing the developer to add the seed row
#   before the provider can be used. The cost of a false positive (user must
#   consent once) is far lower than the cost of a false negative (data
#   leaves the device without consent).
#
# Gate logic (in evaluation order):
#   1. Look up provider_id in provider_consent table.
#   2. If no row → hard stop (fail-closed, see above).
#   3. If is_cloud = 0 → local provider, no consent needed → pass.
#   4. If revoked = 1 → consent was previously granted but revoked → hard stop.
#   5. If user_consented = 0 → not consented → hard stop.
#   6. If consent_scope does not permit the requested operation → hard stop.
#      (For now, "full_inference" and the operation-specific scope both pass;
#       "none" always blocks regardless of user_consented.)
#   7. All checks pass → return the consent row for Stage 9 downstream use.
#
# This stage is standalone and unit-testable: it receives an open database
# connection and a provider_id string, and either returns cleanly or raises.
#
# conn is deliberately untyped, as it is in every other stage. ADR-025 (Clean
# Architecture / Dependency Rule) forbids backend/stages and backend/api from
# importing sqlite3, chromadb or ollama, and scripts/pre-commit enforces it.
# This file used to import sqlite3 for a single `conn: sqlite3.Connection`
# annotation - the whole coupling the rule exists to prevent, acquired for a
# type hint. The hook never fired because the violation predated it and nothing
# had staged this file since; any commit touching it would have been rejected.

from dataclasses import dataclass


class ProviderConsentError(Exception):
    """Raised when the provider consent gate blocks a request.

    Callers must treat this as a hard stop — the request must not proceed.
    The message describes which check failed.
    """


@dataclass(frozen=True)
class ConsentRecord:
    """Immutable snapshot of a provider_consent row, returned on gate pass."""
    provider_id: str
    is_cloud: bool
    user_consented: bool
    consent_scope: str
    revoked: bool


# Scopes that grant full inference rights.
_FULL_INFERENCE_SCOPES = {"full_inference"}


def run(
    conn,
    provider_id: str,
    requested_scope: str = "full_inference",
) -> ConsentRecord:
    """Run the provider consent gate for *provider_id*.

    Args:
        conn: Open SQLite connection (row_factory = sqlite3.Row expected).
        provider_id: Identifier of the provider being used (e.g. "ollama",
            "web_search").
        requested_scope: The operation scope the caller needs (e.g.
            "full_inference", "web_search_only"). Defaults to "full_inference".

    Returns:
        ConsentRecord if all checks pass.

    Raises:
        ProviderConsentError: Hard stop. The request must not proceed.
    """
    row = conn.execute(
        "SELECT provider_id, is_cloud, user_consented, consent_scope, revoked "
        "FROM provider_consent WHERE provider_id = ?",
        (provider_id,),
    ).fetchone()

    # Check 1 — fail closed: unknown provider treated as not consented.
    if row is None:
        raise ProviderConsentError(
            f"No consent record found for provider '{provider_id}'. "
            "Add a row to config/provider_consent.json and re-initialise the DB. "
            "(Fail-closed policy: unknown providers are blocked.)"
        )

    is_cloud = bool(row["is_cloud"])
    user_consented = bool(row["user_consented"])
    consent_scope = row["consent_scope"]
    revoked = bool(row["revoked"])

    # Check 2 — local providers need no consent gate.
    if not is_cloud:
        return ConsentRecord(
            provider_id=provider_id,
            is_cloud=is_cloud,
            user_consented=user_consented,
            consent_scope=consent_scope,
            revoked=revoked,
        )

    # Remaining checks apply to cloud providers only.

    # Check 3 — consent revoked overrides user_consented=1.
    if revoked:
        raise ProviderConsentError(
            f"Consent for provider '{provider_id}' has been revoked. "
            "Use /consent to re-grant access."
        )

    # Check 4 — explicit consent required.
    if not user_consented:
        raise ProviderConsentError(
            f"Provider '{provider_id}' is a cloud provider and has not been "
            "consented to. Use /consent to grant access."
        )

    # Check 5 — scope must cover the requested operation.
    if consent_scope == "none":
        raise ProviderConsentError(
            f"Provider '{provider_id}' has consent_scope='none'. "
            "No operations are permitted."
        )
    if consent_scope != requested_scope and consent_scope not in _FULL_INFERENCE_SCOPES:
        raise ProviderConsentError(
            f"Provider '{provider_id}' has consent_scope='{consent_scope}' which "
            f"does not cover the requested operation '{requested_scope}'."
        )

    return ConsentRecord(
        provider_id=provider_id,
        is_cloud=is_cloud,
        user_consented=user_consented,
        consent_scope=consent_scope,
        revoked=revoked,
    )
