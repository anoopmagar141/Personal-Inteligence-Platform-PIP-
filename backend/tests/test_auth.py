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


# --- Token must never reach a log file ---
#
# Found live in data/backend.err.log: uvicorn's access logger writes the full
# request path, and /ws/chat carries the token as a query parameter because
# browsers cannot set headers on a WebSocket handshake. auth.py says the token
# file is "the only place this value is meant to be read from"; the access log
# was a second place, on disk, in plaintext.

import logging

from backend.api import server


def _record(msg, args=()):
    return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, msg, args, None)


def test_redacts_token_from_a_websocket_access_line():
    # Obviously-synthetic value. The first draft of this test pasted in the
    # REAL token that had leaked - which would have committed a live secret to
    # a public repo in the very change that stops it being logged. Test data
    # for a redaction test must never be a real secret.
    token = "0123456789abcdef" * 4
    # uvicorn logs lazily: the path arrives as an ARG, not inside msg. A filter
    # that only rewrote record.msg would miss every real access-log line.
    record = _record('%s - "WebSocket %s" [accepted]', ("127.0.0.1:1", f"/ws/chat?token={token}"))
    server.RedactTokenFilter().filter(record)
    assert token not in str(record.args)
    assert "[REDACTED]" in str(record.args)


def test_redacts_token_from_the_message_body_too():
    token = "deadbeef" * 8
    record = _record(f"connecting to /ws/chat?token={token}")
    server.RedactTokenFilter().filter(record)
    assert token not in record.msg
    assert "[REDACTED]" in record.msg


def test_redaction_keeps_the_rest_of_the_line_intact():
    record = _record('%s - "GET %s" %d', ("127.0.0.1:2", "/api/v1/status?token=abc123&x=1", 200))
    server.RedactTokenFilter().filter(record)
    rendered = str(record.args)
    assert "abc123" not in rendered
    assert "/api/v1/status" in rendered
    assert "x=1" in rendered  # only the token value is removed, not the whole query


def test_filter_never_drops_a_record():
    record = _record("nothing sensitive here")
    assert server.RedactTokenFilter().filter(record) is True


def test_install_log_redaction_is_idempotent():
    # Runs once per lifespan, and the test suite enters the lifespan repeatedly.
    server.install_log_redaction()
    server.install_log_redaction()
    access = logging.getLogger("uvicorn.access")
    assert sum(isinstance(f, server.RedactTokenFilter) for f in access.filters) == 1
