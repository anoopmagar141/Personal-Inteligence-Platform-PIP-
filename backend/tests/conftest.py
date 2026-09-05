import pytest

# Dev/test-only SQLCipher key. Not a secret - never used outside pytest.
TEST_DB_KEY = "11" * 32


@pytest.fixture
def db_key() -> str:
    return TEST_DB_KEY


# Every path production code can be pointed at, and the file each one lands on
# when nothing points it anywhere. Kept as a table rather than a run of setenv
# calls so that adding an override to the backend without isolating it here is
# a visible omission, not a silent one - which is exactly how the startup
# progress file was missed.
_ISOLATED_PATHS = {
    "PIP_LOCK_PATH": "pip.lock",
    "PIP_DB_PATH": "pip.db",
    "PIP_TOKEN_PATH": "api_token.txt",
    "PIP_SALT_PATH": "salt.bin",
    "PIP_STARTUP_PROGRESS_PATH": "startup.jsonl",
    # Added after a rebuild test wrote a notes.txt into the developer's real
    # data/documents/ - the exact omission the comment below warns about,
    # committed by the change that added the override.
    "PIP_DOCUMENTS_ROOT": "documents",
    # The vector index, per profile. Read through vector_store.chroma_path()
    # at call time precisely so that setting it here isolates something.
    "PIP_CHROMA_PATH": "chroma",
    # The data directory itself, not a file in it - "." resolves to tmp_path.
    # profiles.py builds the registry path and every profile directory from
    # this, so an unisolated test could register profiles in, or write profile
    # directories into, the developer's real data/.
    "PIP_DATA_DIR": ".",
}


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """
    Points every real-file path in the backend at this test's own tmp_path.

    This began as the instance-lock isolation alone, for a reason that turned
    out to apply to all five: a test that spins up server.app's lifespan
    (directly or via TestClient) must not contend with, or write to, a data
    directory that may belong to an actual running backend on the developer's
    own machine. tmp_path is unique per test, so a test's repeated
    TestClient(app) instantiations still share one lock file within it - same
    PID throughout, so instance_lock.acquire()'s "already ours" re-entry path
    is what gets exercised, never a false AlreadyRunningError.

    The other four were each isolated per-test, in the files that happened to
    notice, and missed everywhere else. Measured before this fixture: the real
    data/startup.jsonl held 240 lines - 120 lock/ready pairs, one per lifespan
    the suite had ever started, with none of the launcher-written phases that a
    real launch has. Harmless in that instance (the launcher truncates the file
    and the splash ignores a stale one), but the same omission on a different
    line is not:

      PIP_SALT_PATH is the dangerous one. db_key.create_salt() overwrites the
      salt, and the salt is half the key derivation - replacing it makes the
      user's real database permanently unopenable, with the correct password.
      There is no recovery path by design (Part 10.1).

      PIP_DB_PATH is next. open_app_connection() falls back to the real
      data/pip.db and calls initialize_schema() on it, so an unisolated test
      writes to the production database. It currently fails instead, because
      that file is encrypted and the test has no key - luck, not design.

      PIP_TOKEN_PATH makes a test read or mint the real API token, which
      test_ws_chat.py had already hit once and fixed in one test.

    Per-test setenv calls elsewhere still work and still win; they now override
    a safe default instead of the user's own data directory.
    """
    for variable, filename in _ISOLATED_PATHS.items():
        monkeypatch.setenv(variable, str(tmp_path / filename))

    # Not a path, and isolated for a different reason. profiles.activate() -
    # which POST /auth/profile calls - writes the five variables through
    # os.environ directly, because it re-points a LIVE process rather than
    # configuring a new one. The four above are already on this table so
    # monkeypatch puts them back; PIP_PROFILE was not on any, so a test that
    # switched profile left the next one believing it was somebody else.
    monkeypatch.setenv("PIP_PROFILE", "default")

