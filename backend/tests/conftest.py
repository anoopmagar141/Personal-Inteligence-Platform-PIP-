import pytest

# Dev/test-only SQLCipher key. Not a secret - never used outside pytest.
TEST_DB_KEY = "11" * 32


@pytest.fixture
def db_key() -> str:
    return TEST_DB_KEY
