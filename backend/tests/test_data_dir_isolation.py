"""
The suite must never read or write the real data/ directory.

Not a hypothetical. Before conftest's isolated_data_dir covered every override,
the production data/startup.jsonl held 240 lines - 120 lock/ready pairs, one
per lifespan the suite had ever started. That instance was harmless. The same
omission on PIP_SALT_PATH would not be: create_salt() overwrites the salt, the
salt is half the key derivation, and Part 10.1 has no recovery path - the
user's database would be permanently unopenable with the correct password.

These assertions exist because the failure is silent by nature. A test that
writes to the real data directory still passes; nothing about the run says it
happened. The only place it can be caught is here, by asking where the paths
actually point.
"""

import os
from pathlib import Path

import pytest

from backend.api import server
from backend.core import db_key, instance_lock, startup_progress
from backend.tests.conftest import _ISOLATED_PATHS

REAL_DATA_DIR = (Path(__file__).parent.parent.parent / "data").resolve()

# Every override, paired with the resolver that reads it, so this checks the
# code path production uses rather than just the environment variable. Any
# override with no resolver here is only half-covered.
_RESOLVERS = {
    "PIP_LOCK_PATH": instance_lock._lock_path,
    "PIP_SALT_PATH": db_key.salt_path,
    "PIP_STARTUP_PROGRESS_PATH": startup_progress.progress_path,
}


@pytest.mark.parametrize("variable", sorted(_ISOLATED_PATHS))
def test_every_override_points_somewhere_other_than_the_real_data_dir(variable):
    value = os.environ.get(variable)

    assert value, f"{variable} is unset, so production code falls back to the real data/ file"
    assert REAL_DATA_DIR not in Path(value).resolve().parents, (
        f"{variable} points inside {REAL_DATA_DIR} - this test run would touch "
        "the developer's own PIP data"
    )


@pytest.mark.parametrize("variable", sorted(_RESOLVERS))
def test_the_resolver_actually_honours_its_override(variable):
    """
    The env var being set is not the same as the code reading it. A resolver
    that stopped consulting its override would leave the variable looking
    correct while every write went to the real file.
    """
    resolved = _RESOLVERS[variable]().resolve()

    assert resolved == Path(os.environ[variable]).resolve()
    assert REAL_DATA_DIR not in resolved.parents


def test_the_database_default_is_only_reached_when_nothing_points_elsewhere():
    """
    open_app_connection() falls back to DEFAULT_DB_PATH and then calls
    initialize_schema() on it - a WRITE to the real database. It is the one
    fallback that is destructive rather than merely noisy, so the guard is that
    PIP_DB_PATH is always set during a test, never that the default is wrong.
    """
    assert server.DEFAULT_DB_PATH.resolve().parent == REAL_DATA_DIR
    assert os.environ.get("PIP_DB_PATH"), "an unset PIP_DB_PATH writes schema to the real database"


def test_the_isolation_table_still_covers_every_override_in_the_backend():
    """
    The omission this whole file guards against is adding an override to the
    backend and forgetting to isolate it - which is exactly how startup
    progress was missed. Read the source rather than trusting a list to have
    been updated by hand.
    """
    import re

    backend_root = Path(__file__).parent.parent
    found = set()
    for source in backend_root.rglob("*.py"):
        if "tests" in source.parts:
            continue
        found |= set(re.findall(r'environ\.get\(\s*"(PIP_[A-Z_]+)"', source.read_text(encoding="utf-8")))

    # Two overrides are not paths, so _ISOLATED_PATHS is the wrong place for
    # them - a table that maps a variable to a filename would give each of
    # these a value that is a path, which is precisely what neither one is.
    #
    #   PIP_DB_KEY is a secret. It has no real file to pollute, and tests that
    #   need it set it themselves.
    #
    #   PIP_PROFILE is a slug - the name of the profile the four real path
    #   variables spell out. Setting it to a path would make active_slug()
    #   return something profiles.get() cannot find. It IS isolated, by its own
    #   line in conftest's fixture, because profiles.activate() writes it
    #   through os.environ and a test that switched profile would otherwise
    #   leave the next one believing it was somebody else.
    not_paths = {"PIP_DB_KEY", "PIP_PROFILE"}
    uncovered = found - set(_ISOLATED_PATHS) - not_paths
    assert not uncovered, (
        f"These backend overrides are not isolated in conftest: {sorted(uncovered)}. "
        "Add them to _ISOLATED_PATHS, or a test run will write to the real data/ file."
    )

    # And the one that is isolated elsewhere is actually isolated, so that this
    # exemption stays an exemption from the TABLE rather than from isolation.
    assert os.environ.get("PIP_PROFILE"), "PIP_PROFILE is unset - conftest no longer pins it"
