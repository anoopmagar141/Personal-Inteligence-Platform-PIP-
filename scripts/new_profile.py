"""
Create a new PIP profile: its own directory, its own password, its own database.

    python scripts/new_profile.py "Priya"
    python scripts/new_profile.py --list

WHAT A PROFILE IS
-----------------
A directory under data/profiles/ holding pip.db, salt.bin, chroma/ and
documents/ - the same four things the original installation has at the top of
data/, and nothing else. Two profiles are as separate as two installations,
because that is exactly what they are.

The separation is cryptographic, not cosmetic. Each profile's key is derived
from its own password against its own salt, so opening one tells you nothing
about the others and gives you no way to read them. That is the property a
profile_id column could not have provided at any price: one database means one
key, and one key means every profile readable by whoever holds it.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
Onboard the person. It writes an empty, initialised database and stops.
complete_onboarding() takes a name, a language and a set of skills - answers
that belong to whoever is going to use the profile, given in the app's own
onboarding flow, not typed by whoever ran a script on their behalf. A profile
seeded with somebody's guesses about someone else starts its life with memory
that was never observed, which is the exact failure this project has already had
to clean up once.

seed_test_profile.py is the deliberate exception, and says so.
"""

import _venv

_venv.require("sqlcipher3")

import argparse
import getpass
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import db_key as db_key_module  # noqa: E402
from backend.core import profiles  # noqa: E402
from backend.memory import profile_store  # noqa: E402


def prompt_password(name: str) -> str:
    """
    The password this profile's database is encrypted under.

    Entered twice, never echoed, and never recoverable: Part 10.1's "a forgotten
    password means permanent profile loss" applies to each profile separately,
    which is the point of them having separate passwords at all.
    """
    first = getpass.getpass(f"New password for {name}: ")
    if not first:
        sys.exit("ERROR: an empty password would leave this profile unencrypted in practice.")
    second = getpass.getpass("Repeat it: ")
    if first != second:
        sys.exit("ERROR: the two entries do not match. Nothing was created.")
    return first


def show_profiles() -> int:
    registry = profiles.load()
    current = registry["last_used"]
    print(f"{len(registry['profiles'])} profile(s):\n")
    for profile in profiles.list_profiles():
        marker = "*" if profile.slug == current else " "
        state = "ready" if profile.exists() else "registered, no database yet"
        print(f" {marker} {profile.slug:<20} {profile.name:<24} {state}")
        print(f"   {profile.paths()['db']}")
    print("\n* = last opened")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new PIP profile.")
    parser.add_argument("name", nargs="?", help="display name for the profile")
    parser.add_argument("--list", action="store_true", help="show existing profiles and exit")
    args = parser.parse_args(argv)

    if args.list or not args.name:
        return show_profiles()

    slug = profiles.slugify(args.name)
    profile = profiles.register(args.name, slug=slug)
    paths = profile.paths()

    print(f"Creating profile {profile.name!r} ({profile.slug})")
    print(f"  {paths['db'].parent}")
    print()

    password = prompt_password(profile.name)

    # Salt first, then key, then database - the same order set_db_password.py
    # uses, so a failure at any step leaves nothing half-made that a later run
    # would mistake for a working profile.
    salt = db_key_module.create_salt(paths["salt"])
    key = db_key_module.derive_key(password, salt)

    conn = profile_store.get_connection(str(paths["db"]), db_key=key)
    try:
        profile_store.initialize_schema(conn)
    finally:
        conn.close()

    paths["documents"].mkdir(parents=True, exist_ok=True)

    print()
    print(f"Created. Launch PIP, choose {profile.name!r}, and enter that password.")
    print("It will ask the onboarding questions the first time - deliberately, so the")
    print("answers come from the person using it rather than from whoever ran this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
