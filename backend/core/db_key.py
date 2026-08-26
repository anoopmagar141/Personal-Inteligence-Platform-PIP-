"""
PIP Core - password-derived database key (Part 10.1).

Closes the gap between the specified encryption model and the implemented one.
Encryption at rest was switched on by generating a random key and persisting it
to data/db_key.txt, which works but sits in the same directory as the database
it decrypts - so anything capturing data/ captures both. A stolen disk, a disk
image, or a backup tool pointed at that folder defeats it entirely, and those
are precisely the threats Part 10.4 claims.

Part 10.1 specifies the stronger model implemented here: the user types a
password at launch, PBKDF2 derives the key, and the key exists only for the
lifetime of the process. What lands on disk is the salt, which is not secret -
salts never are. An attacker with the disk gets ciphertext and a salt, and needs
the password, which exists only in the user's head.

Parameters are the spec's, not invented here:
  KDF        PBKDF2-HMAC-SHA512   [Part 10.1, EMPIRICALLY VERIFIED]
  Iterations 256,000              [Part 10.1, EMPIRICALLY VERIFIED]
  Output     32 bytes -> 64 hex chars, matching PRAGMA key = "x'<hex>'"

The raw-hex PRAGMA form matters for why the iteration count is load-bearing:
it tells SQLCipher the value IS the key and skips its own internal KDF pass, so
the work factor protecting the password is entirely the PBKDF2 below. Lowering
it to make startup snappier would silently weaken the only thing standing
between a stolen database and its contents.

No recovery mechanism, by design (Part 10.1): a forgotten password means
permanent profile loss. The wrapper scripts say so before setting one, rather
than leaving the user to discover it.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

# Part 10.1, both EMPIRICALLY VERIFIED in the original spec work.
KDF_HASH = "sha512"
KDF_ITERATIONS = 256_000
KEY_BYTES = 32  # 256-bit, the width SQLCipher's raw-hex key syntax expects
SALT_BYTES = 16

# Lives here rather than in whichever script happens to ask for a password:
# two entry points now set one (scripts/set_db_password.py for an existing
# database, scripts/derive_db_key.py --init for a first run), and a minimum
# that differs between them is the kind of drift nobody notices until the
# weaker path is the one someone used.
MIN_PASSWORD_LENGTH = 8

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SALT_PATH = DATA_DIR / "salt.bin"


class NoSaltError(Exception):
    """Raised when no salt exists yet - i.e. no password has ever been set."""


def salt_path() -> Path:
    """Test isolation, same pattern as PIP_DB_PATH / PIP_TOKEN_PATH."""
    override = os.environ.get("PIP_SALT_PATH")
    return Path(override) if override else SALT_PATH


def create_salt(path: Path | None = None) -> bytes:
    """
    Generates and persists a new random salt, overwriting any existing one.

    Overwriting is destructive in a way worth being explicit about: the salt is
    half of the derivation, so replacing it changes the key that any given
    password produces, and a database encrypted under the old salt can no
    longer be opened even with the correct password. Only ever call this when
    setting a password for the first time, or as part of a rekey that re-encrypts
    the database in the same operation.
    """
    target = path or salt_path()
    salt = secrets.token_bytes(SALT_BYTES)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(salt)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass  # best-effort; little effect on Windows ACLs, same as auth.py
    return salt


def load_salt(path: Path | None = None) -> bytes:
    target = path or salt_path()
    if not target.exists():
        raise NoSaltError(
            f"No salt at {target} - no database password has been set yet. "
            f"Run scripts/set_db_password.py first."
        )
    salt = target.read_bytes()
    if len(salt) != SALT_BYTES:
        raise ValueError(f"Salt at {target} is {len(salt)} bytes, expected {SALT_BYTES}.")
    return salt


def derive_key(password: str, salt: bytes) -> str:
    """
    Returns the 64-char hex key for PRAGMA key = "x'<hex>'".

    Deterministic given (password, salt) - that is the whole point: the key is
    recomputed on every launch and never stored, so there is nothing on disk to
    steal beyond the salt.
    """
    if not password:
        raise ValueError("password must not be empty")
    if len(salt) != SALT_BYTES:
        raise ValueError(f"salt must be {SALT_BYTES} bytes, got {len(salt)}")
    return hashlib.pbkdf2_hmac(
        KDF_HASH, password.encode("utf-8"), salt, KDF_ITERATIONS, dklen=KEY_BYTES
    ).hex()


def derive_key_from_stored_salt(password: str, path: Path | None = None) -> str:
    """Convenience for the normal launch path: load the salt, derive the key."""
    return derive_key(password, load_salt(path))


def verify_key(db_path: str, hex_key: str) -> bool:
    """
    Whether hex_key actually opens db_path.

    Used to tell "wrong password" from "corrupt database" before either matters,
    and - more importantly - to prove a newly derived key works BEFORE anything
    irreversible is done with the old one. SQLCipher only fails on first real
    page access, not on connect or on PRAGMA key, so this has to run a query
    that touches the schema rather than merely opening the file.
    """
    from backend.memory import profile_store

    try:
        conn = profile_store.get_connection(db_path, hex_key)
    except Exception:
        return False
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return True
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
