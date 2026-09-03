"""
Tests for backend/core/profiles.py and the seeding script.

The properties that matter here are not "a second profile can be made" but the
two that make profiles worth having at all:

  They are separately encrypted. One profile's password must not open another's
  database, or "profiles" is a display filter over shared plaintext wearing the
  word privacy.

  Adding the feature does not touch the installation that already exists. The
  first profile's data_dir is "." and nothing is relocated - because relocating
  salt.bin is the one operation in this codebase that can permanently destroy a
  database that is otherwise perfectly fine.
"""

import json

import pytest
import sqlcipher3

from backend.core import db_key as db_key_module
from backend.core import profiles
from backend.memory import profile_store


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """PIP_DATA_DIR, so no test can register a profile in the real data/."""
    monkeypatch.setenv("PIP_DATA_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# The installation that already exists
# ---------------------------------------------------------------------------


def test_an_installation_with_no_registry_still_has_a_default_profile():
    """
    Nothing is created by reading. An installation that never adds a second
    profile never grows a profiles.json, and behaves as it did before this
    module existed.
    """
    listed = profiles.list_profiles()

    assert [p.slug for p in listed] == [profiles.DEFAULT_SLUG]
    assert not profiles.registry_path().exists(), "listing profiles wrote a file"


def test_the_default_profile_points_at_the_unmoved_data_directory(isolated_registry):
    """
    data_dir "." is the whole migration story: there isn't one. Moving salt.bin
    is the single most destructive operation available here - the salt is half
    the key derivation and Part 10.1 states there is no recovery - so the
    feature is built to avoid ever needing to.
    """
    default = profiles.get(profiles.DEFAULT_SLUG)

    assert default.data_dir == "."
    assert default.paths()["db"] == isolated_registry / "pip.db"
    assert default.paths()["salt"] == isolated_registry / "salt.bin"


def test_a_corrupt_registry_does_not_hide_the_real_database(isolated_registry):
    """
    Degrade to the default rather than raise. The alternative is an application
    that will not start because a convenience index is malformed, while the
    database holding everything sits there perfectly readable.
    """
    profiles.registry_path().write_text("{ this is not json", encoding="utf-8")

    listed = profiles.list_profiles()

    assert [p.slug for p in listed] == [profiles.DEFAULT_SLUG]


def test_a_registry_that_forgot_the_default_still_lists_it(isolated_registry):
    """The one profile that must never become unreachable is the one with the data in it."""
    profiles.registry_path().write_text(
        json.dumps({
            "profiles": [{
                "slug": "other", "name": "Other", "data_dir": "profiles/other",
                "created_at": "2026-09-03T00:00:00Z",
            }],
            "last_used": "other",
        }),
        encoding="utf-8",
    )

    assert profiles.DEFAULT_SLUG in [p.slug for p in profiles.list_profiles()]


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Priya Sharma", "priya-sharma"),
        ("  Anup  ", "anup"),
        ("Ana-María 42", "ana-mar-a-42"),
    ],
)
def test_names_become_directory_safe_slugs(name, expected):
    assert profiles.slugify(name) == expected


def test_a_slug_cannot_climb_out_of_the_profiles_directory():
    """
    This string becomes a path segment. A name is user input, and user input
    that reaches a filesystem path without constraint is how a profile called
    "../../.." writes over the data directory it lives in.
    """
    assert profiles.slugify("../../etc") == "etc"
    assert "/" not in profiles.slugify("a/b/c")
    assert ".." not in profiles.slugify("a..b")
    # ".." alone survives none of the substitution and is refused outright,
    # which is stronger than sanitising it into some other directory name.
    with pytest.raises(ValueError):
        profiles.slugify("..")


def test_a_name_that_collides_with_the_default_is_renamed():
    assert profiles.slugify("Default") == "default-profile"


def test_a_windows_reserved_name_is_renamed():
    """CON, PRN, AUX and the COM/LPT series cannot be directories on Windows."""
    assert profiles.slugify("con") == "con-profile"
    assert profiles.slugify("LPT1") == "lpt1-profile"


def test_a_name_with_no_usable_characters_is_refused():
    with pytest.raises(ValueError):
        profiles.slugify("!!!")


# ---------------------------------------------------------------------------
# Registering
# ---------------------------------------------------------------------------


def test_registering_creates_a_directory_but_not_a_database(isolated_registry):
    """
    A database needs a password, and a password belongs at a prompt rather than
    in a function signature.
    """
    profile = profiles.register("Priya Sharma")

    assert profile.data_dir == "profiles/priya-sharma"
    assert profile.paths()["db"].parent.is_dir()
    assert not profile.exists()


def test_a_duplicate_name_is_refused(isolated_registry):
    profiles.register("Priya")
    with pytest.raises(ValueError, match="already exists"):
        profiles.register("Priya")


def test_the_last_used_profile_is_remembered(isolated_registry):
    profiles.register("Priya")
    profiles.record_last_used("priya")

    assert profiles.last_used() == "priya"
    assert profiles.get("priya").last_used is not None


def test_the_default_profile_cannot_be_unregistered(isolated_registry):
    profiles.register("Priya")
    with pytest.raises(ValueError, match="cannot be unregistered"):
        profiles.remove(profiles.DEFAULT_SLUG)


def test_unregistering_leaves_the_files_alone(isolated_registry):
    """
    Not a delete. The directory holds somebody's whole profile under a password
    this function does not have, and ADR-024's posture everywhere else in this
    codebase is that removal is a retraction rather than an erasure.
    """
    profile = profiles.register("Priya")
    marker = profile.paths()["db"].parent / "evidence.txt"
    marker.write_text("still here", encoding="utf-8")

    profiles.remove("priya")

    assert "priya" not in [p.slug for p in profiles.list_profiles()]
    assert marker.read_text(encoding="utf-8") == "still here"


def test_unregistering_the_active_profile_falls_back_to_the_default(isolated_registry):
    profiles.register("Priya")
    profiles.record_last_used("priya")

    profiles.remove("priya")

    assert profiles.last_used() == profiles.DEFAULT_SLUG


# ---------------------------------------------------------------------------
# The separation is cryptographic, not cosmetic
# ---------------------------------------------------------------------------


def _make_profile(name: str, password: str):
    profile = profiles.register(name)
    paths = profile.paths()
    paths["db"].parent.mkdir(parents=True, exist_ok=True)
    key = db_key_module.derive_key(password, db_key_module.create_salt(paths["salt"]))
    conn = profile_store.get_connection(str(paths["db"]), db_key=key)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(
        conn, name=name, language_preference="English", skills=["Python"]
    )
    conn.commit()
    conn.close()
    return profile, key


def test_one_profiles_password_does_not_open_another(isolated_registry):
    """
    The property that makes these profiles rather than a filter. A profile_id
    column in one database could not have provided it at any price: one database
    means one key, and one key means every profile readable by whoever holds it.
    """
    _, key_a = _make_profile("Anup", "anup-password")
    profile_b, _ = _make_profile("Priya", "priya-password")

    conn = sqlcipher3.connect(str(profile_b.paths()["db"]))
    try:
        conn.execute(f"PRAGMA key = \"x'{key_a}'\"")
        with pytest.raises(sqlcipher3.DatabaseError):
            conn.execute("SELECT COUNT(*) FROM identity").fetchone()
    finally:
        conn.close()


def test_each_profile_has_its_own_salt(isolated_registry):
    """
    Same password, different salt, different key. Without separate salts two
    people who happened to choose the same password would share a key.
    """
    profile_a, _ = _make_profile("Anup", "same-password")
    profile_b, _ = _make_profile("Priya", "same-password")

    salt_a = profile_a.paths()["salt"].read_bytes()
    salt_b = profile_b.paths()["salt"].read_bytes()

    assert salt_a != salt_b
    assert db_key_module.derive_key("same-password", salt_a) != db_key_module.derive_key(
        "same-password", salt_b
    )


def test_profiles_do_not_share_a_database_file(isolated_registry):
    profile_a, _ = _make_profile("Anup", "a")
    profile_b, _ = _make_profile("Priya", "b")

    assert profile_a.paths()["db"] != profile_b.paths()["db"]
    for key in ("db", "salt", "chroma", "documents"):
        assert profile_a.paths()[key] != profile_b.paths()[key]


def test_a_profiles_memory_is_its_own(isolated_registry):
    """The observable point of the whole feature: PIP knows a different person."""
    profile_a, key_a = _make_profile("Anup", "a")
    profile_b, key_b = _make_profile("Priya", "b")

    def name_in(profile, key):
        conn = profile_store.get_connection(str(profile.paths()["db"]), db_key=key)
        try:
            return conn.execute("SELECT name FROM identity WHERE id = 1").fetchone()["name"]
        finally:
            conn.close()

    assert name_in(profile_a, key_a) == "Anup"
    assert name_in(profile_b, key_b) == "Priya"
