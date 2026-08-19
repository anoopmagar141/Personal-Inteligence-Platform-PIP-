# PIP Core - Local API token
#
# Security fix: server.py had zero authentication on either transport. The
# threat model explicitly "treats other LOCAL processes as untrusted," and a
# malicious webpage the user's own browser visits can blind-POST to any
# unauthenticated localhost endpoint too - CORS blocks cross-origin *reads*,
# not the request itself. Every REST route and /ws/chat now require a
# shared-secret token.
#
# Deliberately NOT a full session/OAuth system - PIP is a single-user,
# single-machine app (per its own stated threat model), and the realistic
# attacker here is "a process or webpage that doesn't know a locally-stored
# secret," not a multi-tenant scenario. A random token generated on first run
# and persisted to a local file is an appropriately-scoped mitigation for
# that, matching how e.g. Jupyter's own local-server token auth works.
#
# Known limitation, disclosed not hidden: this defends against a DIFFERENT
# process or a malicious webpage, not against another process running as the
# SAME OS user account, which can read this same token file. That's outside
# what a local shared-secret can solve at all - a stronger boundary would
# need OS-level process identity checks, which is a much bigger change than
# this fix. os.chmod(TOKEN_PATH, 0o600) is applied for what it's worth on
# POSIX; it has little effect on Windows ACLs.

import os
import secrets
from pathlib import Path

TOKEN_PATH = Path(__file__).parent.parent.parent / "data" / "api_token.txt"

_cached_token: str | None = None


def get_or_create_token(token_path: Path | None = None) -> str:
    """
    Returns the persisted local API token, generating and storing one on
    first call if none exists yet. Cached in-process after the first real
    (non-override) call so repeated requests don't re-read the file - the
    token_path override (tests) always re-reads, never touches the cache.
    """
    global _cached_token
    path = token_path if token_path is not None else TOKEN_PATH

    if token_path is None and _cached_token is not None:
        return _cached_token

    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
    else:
        token = secrets.token_hex(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # best-effort - not all filesystems/platforms support this

    if token_path is None:
        _cached_token = token
    return token


def verify_token(provided: str | None, token_path: Path | None = None) -> bool:
    if not provided:
        return False
    return secrets.compare_digest(provided, get_or_create_token(token_path))
