"""
The wrong-interpreter guard in scripts/_venv.py.

This code only ever runs on a machine where something is already wrong, which
is exactly why it needs tests: nobody exercises it by accident, and its whole
job is to be correct on the one bad day it fires.

The bug it exists to prevent was real. `python scripts/export_backup.py` on a
fully-installed machine printed "sqlcipher3 is not installed" and advised
`pip install -r requirements.txt` - an instruction that installs into the wrong
interpreter and leaves the original command failing identically. Nothing was
missing; the command named the wrong Python.
"""

import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).parent.parent.parent
SCRIPTS = ROOT / "scripts"


def _load_venv_module():
    spec = importlib.util.spec_from_file_location("_venv_under_test", SCRIPTS / "_venv.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def venv():
    return _load_venv_module()


def test_an_importable_module_does_not_trip_the_guard(venv):
    venv.require("pathlib", "sys")  # must not raise SystemExit


def test_the_guard_exits_2_not_1(venv, monkeypatch, tmp_path):
    """
    sys.exit(message) would print the text but always exit 1 - the code a
    script here is most likely to return for a real answer of its own. A caller
    must be able to tell "wrong interpreter" from "the database said no".
    """
    fake_venv = tmp_path / ".venv" / "Scripts" / "python.exe"
    fake_venv.parent.mkdir(parents=True)
    fake_venv.write_text("")
    monkeypatch.setattr(venv, "_venv_interpreter", lambda: fake_venv)
    monkeypatch.setattr(sys, "executable", r"C:\Python312\python.exe")

    with pytest.raises(SystemExit) as exc:
        venv.require("a_module_that_is_definitely_not_installed")

    assert exc.value.code == 2


def test_the_wrong_interpreter_message_points_at_the_venv(venv, monkeypatch, tmp_path, capsys):
    fake_venv = tmp_path / ".venv" / "Scripts" / "python.exe"
    fake_venv.parent.mkdir(parents=True)
    fake_venv.write_text("")
    monkeypatch.setattr(venv, "_venv_interpreter", lambda: fake_venv)
    monkeypatch.setattr(sys, "executable", r"C:\Python312\python.exe")

    with pytest.raises(SystemExit):
        venv.require("a_module_that_is_definitely_not_installed")

    err = capsys.readouterr().err
    assert str(fake_venv) in err, "must name the interpreter to use"
    assert "pip install" not in err, (
        "this is the branch where nothing is missing - advising an install is "
        "the exact bug this guard replaced"
    )


def test_inside_the_venv_a_missing_package_is_reported_as_missing(venv, monkeypatch, tmp_path, capsys):
    """The opposite case: same interpreter, so the package really is absent."""
    fake_venv = tmp_path / ".venv" / "Scripts" / "python.exe"
    fake_venv.parent.mkdir(parents=True)
    fake_venv.write_text("")
    monkeypatch.setattr(venv, "_venv_interpreter", lambda: fake_venv)
    monkeypatch.setattr(sys, "executable", str(fake_venv))

    with pytest.raises(SystemExit):
        venv.require("a_module_that_is_definitely_not_installed")

    err = capsys.readouterr().err
    assert "pip install" in err, "here the install advice is the correct advice"


def test_no_venv_at_all_explains_how_to_create_one(venv, monkeypatch, capsys):
    monkeypatch.setattr(venv, "_venv_interpreter", lambda: None)

    with pytest.raises(SystemExit):
        venv.require("a_module_that_is_definitely_not_installed")

    err = capsys.readouterr().err
    assert "python -m venv" in err


def test_every_script_needing_the_venv_carries_the_guard():
    """
    A script that needs a venv package and lacks the guard fails with a raw
    traceback, which is the state this change existed to end. Catching that
    here is cheaper than rediscovering it mid-migration.

    Importing backend counts, and is in fact the common case: only two scripts
    name sqlcipher3 themselves, while the rest reach it through
    backend.memory.profile_store. A check that looked for sqlcipher3 alone
    would pass trivially - the guard call itself contains that string - and
    would miss exactly the scripts most likely to be added next.

    derive_db_key.py is exempt: the launcher invokes it with the venv
    interpreter by absolute path, so it cannot reach the failure, and its exit
    codes are a contract scripts/_db_key.ps1 reads.
    """
    exempt = {"derive_db_key.py", "_venv.py"}
    needs_venv = re.compile(r"^\s*(?:from|import)\s+(?:backend|sqlcipher3)\b", re.MULTILINE)

    unguarded = []
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name in exempt:
            continue
        source = path.read_text(encoding="utf-8")
        if needs_venv.search(source) and "_venv.require" not in source:
            unguarded.append(path.name)
    assert not unguarded, f"these need _venv.require(): {unguarded}"


def test_scripts_stay_ascii_so_windows_consoles_can_print_them():
    """
    A non-ASCII character in a script's output or docstring crashes with
    UnicodeEncodeError under the Windows console's cp1252 codec. This was not
    hypothetical: an arrow in migrate_seed_provider_consent.py crashed both its
    --help and its "already seeded, no-op" path.
    """
    offenders = []
    for path in sorted(SCRIPTS.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if any(ord(ch) > 127 for ch in line):
                offenders.append(f"{path.name}:{lineno}")
    assert not offenders, f"non-ASCII will crash a cp1252 console: {offenders}"
