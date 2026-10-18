# PIP Core - which Constitution is in force (BLUEPRINT G-5)
#
# constitutional.json declared "version 1.0, locked before Observer build" and
# was then edited twice without a bump (2026-07-04: gated fields became
# table-and-field patterns; 2026-08-16: session_continuity left
# observer_may_write). Its own amendment_process says "on_startup: check
# profile.constitution_version vs current", and nothing did: every profile
# stored the literal "1.0" whatever rules it ran under, so "which rules decided
# this?" had no answer.
#
# Two checks, both at sign-in:
#   - the file's text matches the fingerprint registered for its version, or
#     the rules were edited without a bump;
#   - the version matches the one this profile last ran under, or the rules
#     changed between runs.
# Owner decision DEC-6 (2026-10-18): warn loudly and keep running. A changed
# version is normal after an update, and refusing to start would lock the user
# out of their own data; the warning goes to the log, the trace and /status,
# and the profile then records the version it now runs under.
#
# The fingerprint is the sha256 of the file's text with LF line endings, the
# same one scripts/_stamp.py writes into every evaluation result, so a result
# and a profile can be matched to the rules that produced them.

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONSTITUTION_PATH = Path(__file__).parent / "constitutional.json"

# Every released version and the fingerprint of its exact text. Changing a rule
# means a new version, a changelog entry and a new line here; editing the file
# without that is what the check below reports. 1.0 is not listed: its text was
# edited after it was released, so no single fingerprint was ever "1.0".
KNOWN_VERSIONS = {
    "1.1": "75363e5af8e00985f27d4b0c161e505e8e2d293b86c59dc7908ef125de048d83",
}


def current() -> dict[str, Any]:
    """The version and fingerprint of the rules file on disk. Raises if unreadable."""
    text = CONSTITUTION_PATH.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return {
        "version": json.loads(text).get("version"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def check(conn) -> dict[str, Any]:
    """
    Read-only: the rules in force, the version this profile last ran under, and
    a warning for each mismatch. Never raises; an unreadable rules file is
    itself a warning.
    """
    warnings: list[str] = []
    try:
        rules = current()
    except Exception as e:
        rules = {"version": None, "sha256": None}
        warnings.append(f"The Constitution file could not be read ({e}); the rules in force are unknown.")
    version = rules["version"]

    if version is not None:
        registered = KNOWN_VERSIONS.get(version)
        if registered is None:
            warnings.append(f"Constitution version {version} is not a registered version; "
                            f"its rules may have been edited without a version bump.")
        elif registered != rules["sha256"]:
            warnings.append(f"The Constitution's rules were edited without a version bump: "
                            f"version {version} no longer has the text it was released with.")

    profile_version = None
    try:
        row = conn.execute("SELECT constitution_version FROM profile_meta WHERE id = 1").fetchone()
        profile_version = row["constitution_version"] if row else None
    except Exception as e:
        warnings.append(f"This profile's Constitution version could not be read ({e}).")
    if profile_version is not None and version is not None and profile_version != version:
        warnings.append(f"The Constitution changed since this profile last ran: {profile_version} -> {version}. "
                        f"Rules apply from now on; what was learned before was checked under {profile_version}.")

    return {"version": version, "sha256": rules["sha256"], "profile_version": profile_version, "warnings": warnings}


def check_and_record(conn) -> dict[str, Any]:
    """
    The sign-in check: warn loudly (log at WARNING, a trace row) for each
    mismatch, then record the version this profile now runs under, so the
    same change is reported once. Never raises: it must not stop PIP (DEC-6).
    """
    result = check(conn)
    if result["warnings"]:
        from backend.core import trace

        trace_id = trace.generate_trace_id()
        for warning in result["warnings"]:
            logger.warning(f"Constitution: {warning}")
            trace.stage_log(conn, trace_id, "constitution", "warn", warning)
    if result["version"] is not None and result["profile_version"] not in (None, result["version"]):
        try:
            conn.execute("UPDATE profile_meta SET constitution_version = ? WHERE id = 1", (result["version"],))
            conn.commit()
        except Exception as e:
            logger.error(f"Constitution: could not record version {result['version']} for this profile: {e}")
    return result
