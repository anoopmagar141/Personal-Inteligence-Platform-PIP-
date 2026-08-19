from backend.core import auth


def test_get_or_create_token_generates_and_persists(tmp_path):
    token_path = tmp_path / "api_token"
    assert not token_path.exists()

    token = auth.get_or_create_token(token_path)
    assert len(token) == 64  # secrets.token_hex(32)
    assert token_path.read_text(encoding="utf-8").strip() == token


def test_get_or_create_token_is_stable_across_calls(tmp_path):
    token_path = tmp_path / "api_token"
    first = auth.get_or_create_token(token_path)
    second = auth.get_or_create_token(token_path)
    assert first == second


def test_get_or_create_token_generates_different_tokens_for_different_paths(tmp_path):
    token_a = auth.get_or_create_token(tmp_path / "a" / "api_token")
    token_b = auth.get_or_create_token(tmp_path / "b" / "api_token")
    assert token_a != token_b


def test_verify_token_accepts_correct_token(tmp_path):
    token_path = tmp_path / "api_token"
    token = auth.get_or_create_token(token_path)
    assert auth.verify_token(token, token_path) is True


def test_verify_token_rejects_wrong_token(tmp_path):
    token_path = tmp_path / "api_token"
    auth.get_or_create_token(token_path)
    assert auth.verify_token("wrong-token", token_path) is False


def test_verify_token_rejects_none_and_empty(tmp_path):
    token_path = tmp_path / "api_token"
    auth.get_or_create_token(token_path)
    assert auth.verify_token(None, token_path) is False
    assert auth.verify_token("", token_path) is False
