import pytest

# Dev/test-only SQLCipher key. Not a secret - never used outside pytest.
TEST_DB_KEY = "11" * 32


@pytest.fixture
def db_key() -> str:
    return TEST_DB_KEY


@pytest.fixture(autouse=True)
def isolated_instance_lock(tmp_path, monkeypatch):
    # Every test that spins up server.app's lifespan (directly or via
    # TestClient) must not contend with, or leave behind, a lock file at the
    # real data/pip.lock path - that path may belong to an actual running
    # backend on the developer's own machine. tmp_path is unique per test, so
    # this also means each test's own repeated TestClient(app) instantiations
    # share one lock file within that test - same PID throughout, so
    # instance_lock.acquire()'s "already ours" re-entry path is what's
    # exercised, never a false AlreadyRunningError.
    monkeypatch.setenv("PIP_LOCK_PATH", str(tmp_path / "pip.lock"))
