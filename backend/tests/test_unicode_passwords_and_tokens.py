"""
A password in any script, and a token that is not ASCII (FREEZE_LIST 7.29).

  - a password in any script (accents, Devanagari, Chinese, emoji) can be chosen at the export
    prompt and at the shortcut restore's prompt. Both compared it with hmac.compare_digest on
    strings, which raises TypeError for any non-ASCII str, so the export died with a traceback
    after the person had typed it twice - and every earlier test used an ASCII password;
  - a request whose bearer token is not ASCII is refused (401). It reached the same comparison and
    raised, so an unauthenticated request could produce a server error.
"""

import pytest

from backend.core import auth
from backend.tests.test_first_run_import import (  # noqa: F401  (fixtures)
    LIVE_KEY, _empty, _load, fresh, forget_the_key,
)
from backend.tests._import_export_helpers import NEW, OLD, NON_ASCII_PASSWORDS, _backup, _import


# ---------------------------------------------------------------------------
# Passwords in any script
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("password", NON_ASCII_PASSWORDS)
def test_the_export_prompt_accepts_a_backup_password_in_any_script(password):
    export = _load("export_backup")
    # Not the live secret, so it must be accepted - and above all it must not raise.
    assert export._is_live_secret(password, LIVE_KEY) is False


@pytest.mark.parametrize("password", NON_ASCII_PASSWORDS)
def test_a_backup_made_under_a_password_in_any_script_comes_back_with_it(fresh, tmp_path, monkeypatch, password):
    client, headers, data = fresh
    backup = _backup(tmp_path, monkeypatch, password=password)

    response = _import(client, headers, backup, backup_password=password, new_password=password + "!")

    assert response.status_code == 200, response.text
    opened = client.post(
        "/api/v1/auth/unlock",
        json={"password": password + "!", "profile": response.json()["slug"]},
        headers=headers,
    )
    assert opened.status_code == 200, opened.text


@pytest.mark.parametrize("password", NON_ASCII_PASSWORDS)
def test_the_shortcut_restore_accepts_a_new_password_in_any_script(monkeypatch, password):
    restore_script = _load("restore_backup")
    monkeypatch.setattr(restore_script.getpass, "getpass", lambda prompt="": password)

    assert restore_script.prompt_new_live_password(OLD) == password


def test_the_shortcut_restore_still_refuses_a_new_password_equal_to_the_backup_one(monkeypatch):
    restore_script = _load("restore_backup")
    same = "密码密码密码密码"
    monkeypatch.setattr(restore_script.getpass, "getpass", lambda prompt="": same)

    with pytest.raises(SystemExit) as stopped:
        restore_script.prompt_new_live_password(same)

    assert "backup password" in str(stopped.value)


# ---------------------------------------------------------------------------
# A token that is not ASCII
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["é", "密码", "😀"])
def test_a_token_that_is_not_ascii_is_not_a_match(bad):
    assert auth.verify_token(bad) is False


def test_a_request_with_a_non_ascii_bearer_token_is_refused_not_an_error(fresh):
    client, _, _ = fresh
    for bad in ("Bearer é", "Bearer 密码"):
        response = client.get("/api/v1/auth/profiles", headers=[(b"authorization", bad.encode("utf-8"))])
        assert response.status_code == 401, f"{bad!r} -> {response.status_code}"
