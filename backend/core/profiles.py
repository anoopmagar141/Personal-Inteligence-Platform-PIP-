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
