"""
Tests for the password-derived database key (Part 10.1).

The property that matters is not "encryption happens" - that was already true
with a random key on disk - but that NOTHING ON DISK DECRYPTS THE DATABASE.
The salt is written down; the key is not, and cannot be recovered from what is.
"""

import hashlib

import pytest

from backend.core import db_key
from backend.memory import profile_store


@pytest.fixture(autouse=True)
def isolated_salt(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))


def test_derive_produces_a_key_sqlcipher_can_use():
    key = db_key.derive_key("correct horse battery staple", db_key.create_salt())
    # PRAGMA key = "x'<hex>'" wants exactly 32 bytes of hex.
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_same_password_and_salt_always_derive_the_same_key():
    # The whole model rests on this: the key is recomputed every launch rather
    # than stored, so derivation must be reproducible or the database is lost.
    salt = db_key.create_salt()
    assert db_key.derive_key("hunter2hunter2", salt) == db_key.derive_key("hunter2hunter2", salt)


def test_different_password_derives_a_different_key():
    salt = db_key.create_salt()
    assert db_key.derive_key("password-one", salt) != db_key.derive_key("password-two", salt)


def test_different_salt_derives_a_different_key():
    # Why set_db_password.py takes a fresh salt on every change: anyone who
    # captured the old one would otherwise keep a precomputation head start.
    password = "same password both times"
    assert db_key.derive_key(password, db_key.create_salt()) != db_key.derive_key(password, db_key.create_salt())


def test_uses_the_spec_kdf_parameters():
    # Part 10.1, both marked EMPIRICALLY VERIFIED. Pinned because lowering the
    # iteration count to make startup snappier would silently weaken the only
    # work factor protecting the password: the raw-hex PRAGMA form tells
    # SQLCipher the value IS the key, skipping its own KDF pass entirely.
    assert db_key.KDF_HASH == "sha512"
    assert db_key.KDF_ITERATIONS == 256_000
    assert db_key.KEY_BYTES == 32

    salt = db_key.create_salt()
    expected = hashlib.pbkdf2_hmac("sha512", b"a password", salt, 256_000, dklen=32).hex()
    assert db_key.derive_key("a password", salt) == expected


def test_empty_password_is_refused():
    with pytest.raises(ValueError):
        db_key.derive_key("", db_key.create_salt())


def test_missing_salt_is_a_clear_error_not_a_crash():
    with pytest.raises(db_key.NoSaltError):
        db_key.load_salt()


def test_salt_is_random_per_creation():
    assert db_key.create_salt() != db_key.create_salt()


def test_verify_key_accepts_the_right_key_and_rejects_others(tmp_path):
    db_path = str(tmp_path / "pip.db")
    salt = db_key.create_salt()
    key = db_key.derive_key("the real password", salt)

    conn = profile_store.get_connection(db_path, key)
    profile_store.initialize_schema(conn)
    conn.close()

    assert db_key.verify_key(db_path, key) is True
    assert db_key.verify_key(db_path, db_key.derive_key("not the password", salt)) is False


def test_rekey_switches_the_database_to_the_new_key(tmp_path):
    # The migration path in scripts/set_db_password.py: an existing database
    # encrypted under the random key must move to the derived one without
    # losing anything, and must stop opening under the old key.
    db_path = str(tmp_path / "pip.db")
    old_key = "ab" * 32
    conn = profile_store.get_connection(db_path, old_key)
    profile_store.initialize_schema(conn)
    conn.execute(
        "INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'BatMan', 'English', 'Nepal')"
    )
    conn.commit()

    new_key = db_key.derive_key("a password chosen later", db_key.create_salt())
    conn.execute(f"PRAGMA rekey = \"x'{new_key}'\"")
    conn.close()

    assert db_key.verify_key(db_path, new_key) is True
    assert db_key.verify_key(db_path, old_key) is False

    verify = profile_store.get_connection(db_path, new_key)
    assert verify.execute("SELECT name FROM identity").fetchone()["name"] == "BatMan"
    verify.close()


def test_nothing_on_disk_reveals_the_key(tmp_path):
    # The point of the whole change. After setup, data/ holds the salt and the
    # ciphertext; neither contains the key, so a stolen disk yields nothing
    # without the password.
    salt = db_key.create_salt()
    key = db_key.derive_key("the only copy is in my head", salt)

    on_disk = db_key.salt_path().read_bytes()
    assert key.encode() not in on_disk
    assert bytes.fromhex(key) not in on_disk
