"""
A backup imports whatever its owner is called (FREEZE_LIST 7.29).

The profile's folder name comes from the person's name, and a name with no a-z or 0-9 (all of
Devanagari, Chinese, Arabic) produced no folder name at all, so the first-run import was refused
with "A profile with that name already exists" - false, with no way round it for the person the
import was meant for.
"""

import pytest

from backend.core import profiles
from backend.tests.test_first_run_import import (  # noqa: F401  (fixtures)
    LIVE_KEY, _empty, _load, fresh, forget_the_key,
)
from backend.tests._import_export_helpers import NEW, OLD, NON_ASCII_PASSWORDS, _backup, _import


# ---------------------------------------------------------------------------
# A name that makes no folder name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["अनुप मगर", "张伟", "Ünal"],
)
def test_a_name_in_any_script_still_makes_a_distinct_usable_folder_name(name):
    slug = profiles.slugify(name)
    assert slug and all(c.isascii() and (c.isalnum() or c == "-") for c in slug)
    assert slug == profiles.slugify(name), "the same name must always give the same folder"


def test_different_names_in_the_same_script_do_not_share_a_folder():
    assert profiles.slugify("अनुप मगर") != profiles.slugify("सुनिता श्रेष्ठ")


@pytest.mark.parametrize("name", ["!!!", "...", "..", "😀😀"])
def test_a_name_with_no_letters_or_digits_at_all_is_still_refused_when_creating_a_profile(name):
    # An emoji is not a letter or a digit, so the sentence "must contain at least one letter or
    # digit" is true of it; only the import, which must take anybody's backup, works around that.
    with pytest.raises(ValueError):
        profiles.slugify(name)


@pytest.mark.parametrize(
    "name",
    ["अनुप मगर", "张伟", "😀😀", "...", "!!!", "Zoë", "O'Brien", "CON", "a" * 64],
)
def test_a_backup_imports_whatever_its_owner_is_called(fresh, tmp_path, monkeypatch, name):
    client, headers, data = fresh
    backup = _backup(tmp_path, monkeypatch, name=name)

    response = _import(client, headers, backup)

    assert response.status_code == 200, f"{name!r}: {response.status_code} {response.text}"
    opened = client.post(
        "/api/v1/auth/unlock", json={"password": NEW, "profile": response.json()["slug"]}, headers=headers
    )
    assert opened.status_code == 200, opened.text
