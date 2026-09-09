"""
Named profiles, each one its own encrypted database.

WHY SEPARATE DATABASES AND NOT A profile_id COLUMN
--------------------------------------------------
The obvious shape - a profile_id on every table - would have meant dropping the
five `CHECK (id = 1)` constraints that make identity, profile_meta,
interaction_style, session_snapshot and llm_settings singletons, adding a column
to two dozen tables, and revisiting every query in the codebase.

It would also have been the wrong answer regardless of cost. One database means
one SQLCipher key, so one password would decrypt every profile in it: whoever
can open their own could read everyone else's conversations, decisions and
memory. In an application whose entire claim is governed, private, local
personal data, "profiles" that are a display filter over shared plaintext is not
a feature, it is a misleading label on the absence of one.

A profile here is a directory with its own pip.db, its own salt.bin, and
therefore its own key derived from its own password. Two profiles are as
separate as two installations, because that is what they are. The cost is that
switching needs a restart and a password rather than a menu click - which is not
a limitation to apologise for but the honest consequence of the separation being
real.

WHY THE EXISTING INSTALLATION IS NOT MOVED
------------------------------------------
The first profile's data_dir is "." - the data directory itself, exactly where
pip.db and salt.bin already are. Nothing is relocated when this feature arrives.

That is deliberate, and it follows this project's own hardest-won rule. Moving
salt.bin is the single most destructive operation available here: the salt is
half the key derivation, and Part 10.1 states there is no recovery by design, so
a rename that fails partway leaves a database that cannot be opened with the
correct password. Introducing a feature nobody asked for by first performing the
one operation that can permanently destroy the data it is meant to organise
would be an indefensible trade. New profiles go in subdirectories; the original
stays where it is, and keeps working if this file is deleted.

WHAT IS PER-PROFILE AND WHAT IS NOT
-----------------------------------
Per profile: pip.db, salt.bin, chroma/, documents/. Everything that IS the
user's data or is derived from it.

Shared: pip.lock, api_token.txt, startup.jsonl, ui_theme.txt, and this
registry. These belong to the running application rather than to a person, and
the lock being shared is load-bearing - it is what makes "one profile open at a
time" true by the same mechanism that already made "one PIP at a time" true,
rather than by a second rule that could disagree with the first.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from backend.core.types import now_utc

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# The slug of the profile that owns the original, un-relocated data directory.
DEFAULT_SLUG = "default"

# Where new profiles live, relative to data/.
PROFILES_SUBDIR = "profiles"


@dataclass(frozen=True)
class Profile:
    slug: str
    name: str
    data_dir: str  # relative to data/; "." is the original installation
    created_at: str
    last_used: str | None = None

    def paths(self, data_root: Path | None = None) -> dict[str, Path]:
        """
        The four per-profile paths, resolved.

        Named the same as the environment overrides the launcher sets from them,
        so there is one vocabulary for "where this profile's database is" rather
        than a mapping to remember.
        """
        root = (data_root or data_dir()) / self.data_dir
        return {
            "db": root / "pip.db",
            "salt": root / "salt.bin",
            "chroma": root / "chroma",
            "documents": root / "documents",
        }

    def exists(self, data_root: Path | None = None) -> bool:
        """Whether this profile has actually been created, not merely registered."""
        return self.paths(data_root)["db"].exists()


def data_dir() -> Path:
    """PIP_DATA_DIR if set, else the repository's data/. Overridable for tests."""
    override = os.environ.get("PIP_DATA_DIR")
    return Path(override) if override else DATA_DIR


def registry_path() -> Path:
    return data_dir() / "profiles.json"


def slugify(name: str) -> str:
    """
    A directory-safe name.

    Not decorative: this string becomes a path segment, so it is restricted to
    characters that cannot climb out of the profiles directory or collide with a
    Windows reserved name. A caller that passes "../../etc" gets "etc".
    """
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("a profile name must contain at least one letter or digit")
    reserved = {"con", "prn", "aux", "nul", "default"} | {
        f"{p}{i}" for p in ("com", "lpt") for i in range(1, 10)
    }
    if slug in reserved:
        slug = f"{slug}-profile"
    return slug[:64]


def _default_profile() -> Profile:
    """
    The installation that existed before profiles did.

    Synthesised rather than written to disk on read, so that merely listing
    profiles never creates a file. An installation that never adds a second
    profile therefore never grows a registry at all, and behaves exactly as it
    did before this module existed.
    """
    return Profile(
        slug=DEFAULT_SLUG,
        name="Default",
        data_dir=".",
        created_at=now_utc(),
    )


def load() -> dict[str, Any]:
    """
    The registry as stored, or a synthetic one describing the original install.

    A corrupt or unreadable registry degrades to the default rather than raising.
    The alternative is an application that will not start because a convenience
    index is malformed, while the actual database sits there perfectly readable.
    """
    path = registry_path()
    if not path.exists():
        return {"profiles": [asdict(_default_profile())], "last_used": DEFAULT_SLUG}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        profiles = [Profile(**p) for p in raw.get("profiles", [])]
    except Exception as e:
        logger.warning(f"profiles.json could not be read ({e}) - falling back to the default profile.")
        return {"profiles": [asdict(_default_profile())], "last_used": DEFAULT_SLUG}

    if not any(p.slug == DEFAULT_SLUG for p in profiles):
        # The original installation is always present, whatever the file says.
        # Losing it from the registry must not make the database it points at
        # unreachable - that database is the one with everything in it.
        profiles.insert(0, _default_profile())

    return {
        "profiles": [asdict(p) for p in profiles],
        # raw is a dict by here: anything else would have failed at raw.get above
        # and been caught, so the isinstance guard an earlier draft had was dead.
        "last_used": raw.get("last_used", DEFAULT_SLUG),
    }


def list_profiles() -> list[Profile]:
    return [Profile(**p) for p in load()["profiles"]]


def get(slug: str) -> Profile:
    for profile in list_profiles():
        if profile.slug == slug:
            return profile
    raise KeyError(f"no profile named {slug!r}")


def last_used() -> str:
    return load().get("last_used") or DEFAULT_SLUG


# --- pointing this process at one profile -----------------------------------
#
# WHY THE CHOICE MOVED OUT OF THE LAUNCHER
# ----------------------------------------
# scripts/_profiles.ps1 used to ask "Which profile?" in the console before
# uvicorn started, and the answer became four environment variables. That is
# the same mistake the password prompt made, for the same reason: PIP is
# something other people install, and a numbered menu in a blue PowerShell
# window is not a sign-in screen. The password moved into the application in
# Part 10.1's rework; the profile follows it here, and for the same cost -
# nothing, because the four variables are read at CALL time by every consumer
# (db_key.salt_path, vector_store.chroma_path, profile_store's documents root,
# server._db_path_or_default), never captured at import.
#
# WHAT DOES NOT CHANGE
# --------------------
# The separation this module's header describes. Two profiles are still two
# databases under two keys derived from two passwords; activate() only points
# at files, and cannot open them. Everything after it still needs the right
# password, so a switch is still exactly as hard to misuse as a fresh launch.


def active_slug() -> str:
    """
    Which profile this process is currently pointed at.

    PIP_PROFILE is the label; the four path variables are what actually take
    effect. They are set together and only together, so a process that has one
    has all five.
    """
    return os.environ.get("PIP_PROFILE") or DEFAULT_SLUG


def environment_for(profile: Profile) -> dict[str, str]:
    """
    The five variables that point a process at one profile.

    Exactly the set scripts/_profiles.ps1 sets, deliberately. A profile opened
    from the launcher and the same profile opened from the sign-in screen have
    to be the same files, and the only way to guarantee that is for both to
    spell out the same list.
    """
    paths = profile.paths()
    return {
        "PIP_DB_PATH": str(paths["db"]),
        "PIP_SALT_PATH": str(paths["salt"]),
        "PIP_CHROMA_PATH": str(paths["chroma"]),
        "PIP_DOCUMENTS_ROOT": str(paths["documents"]),
        "PIP_PROFILE": profile.slug,
    }


def activate(slug: str) -> Profile:
    """
    Point this process at *slug*'s files. Only ever call this while locked.

    That condition is not a style note. The key held in session_key belongs to
    the profile that was open when it was derived, and it is also in
    PIP_DB_KEY, which vector_store reads to decrypt chunk text. Re-pointing the
    paths while a key is still held would leave one profile's key aimed at
    another profile's files: SQLCipher would refuse the database, but the
    Chroma directory would be opened and written under the wrong key's HMAC,
    which fails silently and permanently. The caller that enforces this is the
    /auth/profile route, which refuses while unlocked.

    Creates the directories rather than requiring them, because a profile that
    has been registered but never opened has nothing on disk yet - that is the
    state new_profile.py leaves behind, and the state a first sign-in resolves.
    """
    profile = get(slug)
    paths = profile.paths()
    paths["db"].parent.mkdir(parents=True, exist_ok=True)
    paths["documents"].mkdir(parents=True, exist_ok=True)
    os.environ.update(environment_for(profile))

    # The one cache that outlives a lock. Everything else reads its path per
    # call; Chroma's client is held for the life of the module and would keep
    # the previous profile's directory open. Lazily imported and best-effort:
    # this module is imported by scripts that have no reason to pull in
    # chromadb and sentence-transformers, and a switch must not fail because a
    # vector index could not be dropped.
    try:
        from backend.memory import vector_store

        vector_store.reset_client()
    except Exception as e:
        logger.warning(f"Could not reset the vector store while switching profile: {e}")

    return profile


def _save(profiles: list[Profile], last: str) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"profiles": [asdict(p) for p in profiles], "last_used": last}
    # Written whole and replaced, not appended to: a half-written registry is a
    # file that cannot be parsed, and the fallback above would then silently
    # hide every profile but the default.
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def register(name: str, *, slug: str | None = None) -> Profile:
    """
    Add a profile to the registry and create its directory.

    Does NOT create the database - that needs a password, which belongs at a
    prompt and not in a function signature. scripts/new_profile.py does both
    halves in the right order.
    """
    chosen = slug or slugify(name)
    existing = list_profiles()
    if any(p.slug == chosen for p in existing):
        raise ValueError(f"a profile named {chosen!r} already exists")

    profile = Profile(
        slug=chosen,
        name=name.strip(),
        data_dir=f"{PROFILES_SUBDIR}/{chosen}",
        created_at=now_utc(),
    )
    profile.paths()["db"].parent.mkdir(parents=True, exist_ok=True)
    _save(existing + [profile], last_used())
    return profile


def record_last_used(slug: str) -> None:
    """Remember which profile was opened, so the next launch offers it first."""
    profiles = list_profiles()
    if not any(p.slug == slug for p in profiles):
        raise KeyError(f"no profile named {slug!r}")
    stamped = [
        Profile(**{**asdict(p), "last_used": now_utc()}) if p.slug == slug else p
        for p in profiles
    ]
    _save(stamped, slug)


def remove(slug: str) -> Profile:
    """
    Forget a profile, leaving its files entirely alone.

    Deliberately not a delete. The directory holds somebody's whole profile
    under a password this function does not have and cannot check, and ADR-024's
    posture on every other memory class is that removal is a retraction rather
    than an erasure. Unregistering makes it stop appearing; the data stays until
    a person deletes the directory themselves, having decided to.
    """
    if slug == DEFAULT_SLUG:
        raise ValueError("the default profile cannot be unregistered")
    profiles = list_profiles()
    remaining = [p for p in profiles if p.slug != slug]
    if len(remaining) == len(profiles):
        raise KeyError(f"no profile named {slug!r}")
    removed = next(p for p in profiles if p.slug == slug)
    _save(remaining, DEFAULT_SLUG if last_used() == slug else last_used())
    return removed


def rename(slug: str, name: str) -> Profile:
    """
    Change a profile's display name, leaving its slug and directory alone.

    The slug is a path segment - data/profiles/<slug> - so renaming it would
    mean moving a directory that holds pip.db and salt.bin, and this module's
    header is one long argument for never doing that. The name is what a person
    reads on the sign-in screen; the slug is where the bytes live, and only one
    of those is safe to change after the fact.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("a profile name cannot be empty")
    # Same ceiling the registry has always implied: the name is drawn in a
    # switcher, not stored as a document.
    if len(cleaned) > 64:
        raise ValueError("a profile name must be 64 characters or fewer")

    existing = list_profiles()
    if not any(p.slug == slug for p in existing):
        raise KeyError(f"no profile named {slug!r}")

    renamed = [
        Profile(**{**asdict(p), "name": cleaned}) if p.slug == slug else p
        for p in existing
    ]
    _save(renamed, last_used())
    return next(p for p in renamed if p.slug == slug)


# --- destroying one ---------------------------------------------------------
#
# WHY THIS IS AN ERASURE AND remove() IS NOT
# ------------------------------------------
# remove() above unregisters and deliberately leaves the files, because it is
# reachable by somebody who does not have the profile's password and therefore
# cannot be shown to own what they are discarding. ADR-024's posture - removal
# is a retraction, not an erasure - is the right one for that caller.
#
# delete() is the other caller, and the difference is authorisation. It is only
# reachable from inside an unlocked profile, which means the person asking has
# just proved they can derive its key. That proof is the only ownership claim
# this application has: there is no account server, no recovery, nothing else
# that could distinguish the owner from anyone with the disk. When it has been
# made, "delete my account" has to mean the bytes are gone, because a control
# labelled that way which merely hides a directory is the misleading label this
# module's header warns about, pointed the other way.
#
# There is no undo. That is the same sentence db_key.py writes about a
# forgotten password, and it is true here for the same reason.


def erasable_paths(slug: str, data_root: Path | None = None) -> list[Path]:
    """
    Exactly what deleting *slug* would destroy, listed before anything is.

    The list is this profile's own files and nothing else, which matters most
    for the default profile: its data_dir is "." - the data directory itself -
    which also holds profiles.json, pip.lock, api_token.txt, startup.jsonl and
    ui_theme.txt. Those belong to the running application rather than to a
    person, and three of them describe the OTHER profiles. A delete implemented
    as "remove the profile's directory" would therefore be correct for every
    profile except the original one, where it would take every other profile's
    registry entry with it.

    So the unit of deletion is the paths this module already names as
    per-profile, for every profile equally. Everything that is the user's data
    goes; the application's own plumbing stays.
    """
    profile = get(slug)
    paths = profile.paths(data_root)
    return [
        paths["db"],
        paths["salt"],
        paths["chroma"],
        paths["documents"],
        # The unencrypted copy of the profile picture, if one was published to
        # the sign-in screen. Not one of the four env-mapped paths, but it is
        # the user's data by any reading - and a delete that left a photograph
        # of the account holder in the directory it had just emptied would be
        # the most visible possible way to get this wrong.
        signin_picture_path(slug, data_root),
    ]


def _remove_path(path: Path) -> bool:
    """Delete a file or a directory tree. Returns whether anything was there."""
    if path.is_dir():
        shutil.rmtree(path)
        return True
    if path.exists():
        path.unlink()
        return True
    return False


def delete(slug: str) -> Profile:
    """
    Erase a profile's data and unregister it. Only ever call this while the
    caller has proved they can open it.

    ORDERING
    --------
    Files first, registry second. A crash between the two leaves a registered
    profile whose database is gone, which the sign-in screen already draws
    correctly - `exists` is False, so it reads as "not created yet". The
    reverse order would leave orphaned encrypted data with nothing pointing at
    it, which nobody would ever find to delete again.

    THE DEFAULT PROFILE IS NOT EXEMPT
    ---------------------------------
    Its data is erased like anyone else's. What survives is its registry entry,
    because load() synthesises it whenever it is missing - the original
    installation is always listed, and that invariant exists so that losing the
    entry can never make the database it points at unreachable. The consequence
    after a delete is that the slot remains and reads as a fresh profile, which
    is what it now is: there is nothing behind it.
    """
    profile = get(slug)

    for path in erasable_paths(slug):
        _remove_path(path)
        # SQLite leaves -wal and -shm beside a database it did not close
        # cleanly, holding pages that have not landed in the main file yet.
        # They are named after pip.db rather than living under it, so the
        # four-path list does not cover them - and leaving them behind would
        # leave fragments of the erased profile's content in a directory it
        # was just deleted from.
        if path.suffix == ".db":
            for sidecar in (f"{path}-wal", f"{path}-shm", f"{path}-journal"):
                _remove_path(Path(sidecar))

    if slug != DEFAULT_SLUG:
        # The directory itself, now that everything PIP put in it is gone.
        # Best-effort: anything else in there was not put there by PIP, and
        # deleting a directory that is not empty is not this function's call.
        try:
            profile.paths()["db"].parent.rmdir()
        except OSError:
            logger.info(f"{profile.data_dir} was not empty after erasing - leaving the directory.")

        remaining = [p for p in list_profiles() if p.slug != slug]
        _save(remaining, DEFAULT_SLUG if last_used() == slug else last_used())

    return profile


# --- the picture on the sign-in screen --------------------------------------
#
# WHY THIS IS A SEPARATE FILE AND NOT THE AVATAR
# ----------------------------------------------
# The profile picture lives in identity_avatar, inside the encrypted database.
# That is the right place for it and it stays there. But the sign-in screen
# draws profiles that are LOCKED - if it could read that table it would not be
# a sign-in screen - so a picture shown there cannot come from inside the
# database. There is no clever way around this: anything the screen can render
# before a password is typed is, by definition, readable without one.
#
# So the trade is stated rather than hidden. Turning this on writes a SECOND
# copy of the picture, unencrypted, beside the profile's database, and that
# copy is readable by anyone who can read the disk - which is the threat model
# (a stolen laptop, a disk image, a backup tool) that the encryption exists
# for. A face is not a conversation, and plenty of people will think a
# recognisable switcher is worth it; that is their call to make, which is why
# it is off until somebody makes it and why removing it deletes the file.
#
# It is erased with the profile. erasable_paths() includes it, because a
# "delete my account" that leaves a photograph of the account holder in the
# directory it just emptied would be the most visible possible way to get this
# wrong.

SIGNIN_PICTURE_NAME = "signin-picture"


def signin_picture_path(slug: str, data_root: Path | None = None) -> Path:
    """
    Where *slug*'s sign-in picture is, whether or not one has been published.

    One fixed filename with no extension, because the format is detected from
    the bytes when it is served (avatar_store.detect_media_type), exactly as it
    is on upload. An extension would be a second, weaker claim about the same
    thing, and the two could disagree.
    """
    profile = get(slug)
    root = (data_root or data_dir()) / profile.data_dir
    return root / SIGNIN_PICTURE_NAME


def publish_signin_picture(slug: str, image: bytes) -> Path:
    """Write the unencrypted copy the sign-in screen can read."""
    path = signin_picture_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)
    return path


def unpublish_signin_picture(slug: str) -> bool:
    """Remove it. Returns whether there was one."""
    return _remove_path(signin_picture_path(slug))


def has_signin_picture(slug: str) -> bool:
    return signin_picture_path(slug).exists()
