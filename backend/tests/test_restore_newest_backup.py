"""
"The newest will be used" has to be true (FREEZE_LIST D-21).

restore_pip.ps1 lists the .pipbak files in data/ newest first by modification
time and says "the newest will be used"; restore_backup.newest_backup() then
took the last NAME in sorted(). A second export on the same day is written as
pip_backup_20261003-2.pipbak, and "-" sorts before ".", so the first export of
the day beat the second: the shortcut printed the right list and restored the
older file. -9 beat -10 the same way, and any name sorting after the dated ones
beat them whatever its age.

The outcome checked is which file the restore is pointed at, with the age of
the files set explicitly - a test that relied on the order files happened to be
created in would pass on the machine whose clock hid the bug.
"""

import importlib.util
import os
import pathlib
import sys

import pytest


def _load():
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("restore_backup", root / "scripts" / "restore_backup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(tmp_path, monkeypatch):
    module = _load()
    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    return module


def _backup(directory, name, age_seconds):
    """A file whose modification time is *age_seconds* before a fixed instant."""
    path = directory / name
    path.write_bytes(b"x")
    stamp = 1_800_000_000 - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def test_a_same_day_retry_beats_the_first_export_of_the_day(script, tmp_path):
    _backup(tmp_path, "pip_backup_20261003.pipbak", age_seconds=60)
    retry = _backup(tmp_path, "pip_backup_20261003-2.pipbak", age_seconds=10)

    assert script.newest_backup() == retry


def test_the_tenth_export_of_a_day_beats_the_ninth(script, tmp_path):
    _backup(tmp_path, "pip_backup_20261003-9.pipbak", age_seconds=60)
    tenth = _backup(tmp_path, "pip_backup_20261003-10.pipbak", age_seconds=10)

    assert script.newest_backup() == tenth


def test_an_older_file_with_a_later_name_does_not_win(script, tmp_path):
    """The age of the file decides, not where its name falls in the alphabet."""
    _backup(tmp_path, "pip_backup_zzz.pipbak", age_seconds=500)
    newer = _backup(tmp_path, "pip_backup_20261003.pipbak", age_seconds=5)

    assert script.newest_backup() == newer


def test_files_of_the_same_age_fall_back_to_date_then_number(script, tmp_path):
    """A copy that reset every modification time still has a defensible answer."""
    _backup(tmp_path, "pip_backup_20261002-3.pipbak", age_seconds=30)
    _backup(tmp_path, "pip_backup_20261003.pipbak", age_seconds=30)
    _backup(tmp_path, "pip_backup_20261003-2.pipbak", age_seconds=30)
    last = _backup(tmp_path, "pip_backup_20261003-10.pipbak", age_seconds=30)

    assert script.newest_backup() == last


def test_with_no_backup_it_still_says_so(script, tmp_path):
    with pytest.raises(SystemExit):
        script.newest_backup()


def test_the_file_written_last_wins_even_when_its_name_is_an_earlier_date(script, tmp_path):
    """
    What the listing shows is modification time, so that is what has to pick:
    a backup copied onto this machine today is the newest thing here, whatever
    day its name says it was exported.
    """
    _backup(tmp_path, "pip_backup_20261003-2.pipbak", age_seconds=500)
    copied_today = _backup(tmp_path, "pip_backup_20261001.pipbak", age_seconds=5)

    assert script.newest_backup() == copied_today
