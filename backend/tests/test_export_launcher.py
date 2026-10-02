"""
The Backup screen's Export backs up the profile that was last opened, with
that profile's own salt, however many profiles there are (docs/FREEZE_LIST.md
§7.16, D-03).

The screen launches scripts/export_pip.ps1, and that wrapper decides two
things for export_backup.py: which database to read (--db-path, or
data/pip.db when it passes nothing) and which salt to derive the key with
(PIP_SALT_PATH, or data/salt.bin when it is unset). It only decided when more
than one profile was registered. A new installation has exactly one, living
in data/profiles/<slug>/, so the export read data/pip.db - a file that does
not exist there - and failed with "no database" for the most common user.

What runs here is the real export_pip.ps1 and its two helpers, copied into a
temporary installation: the real data/ is never in reach, and nothing real is
exported. The interpreter is real too, a throwaway venv the wrapper finds
where it looks for one. Only export_backup.py is replaced, by a stand-in that
records what it was asked to back up and exits. What is asserted is the pair
of files the export would have opened.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# What the stand-in export_backup.py writes beside itself: its arguments, and
# the salt override it inherited - the two inputs that decide what is backed up.
_RECORDER = """\
import json, os, sys
from pathlib import Path
Path(__file__).with_name("called.json").write_text(
    json.dumps({"argv": sys.argv[1:], "salt": os.environ.get("PIP_SALT_PATH")}),
    encoding="utf-8",
)
"""


@pytest.fixture(scope="module")
def interpreter(tmp_path_factory):
    """A real Python, made once, for the wrapper to find in .venv."""
    venv = tmp_path_factory.mktemp("interpreter") / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    return venv


@pytest.fixture
def installation(tmp_path, interpreter):
    root = tmp_path / "PIP"
    (root / "scripts").mkdir(parents=True)
    for name in ("export_pip.ps1", "_python.ps1", "_profiles.ps1"):
        shutil.copyfile(REPO / "scripts" / name, root / "scripts" / name)
    (root / "scripts" / "export_backup.py").write_text(_RECORDER, encoding="utf-8")
    shutil.copytree(interpreter, root / ".venv")
    (root / "data").mkdir()
    return root


def _register(root, *profiles, last_used):
    """profiles.json as the backend writes it, and each profile's two files."""
    entries = []
    for slug, data_dir in profiles:
        folder = root / "data" / data_dir
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "pip.db").write_bytes(b"")
        (folder / "salt.bin").write_bytes(b"0123456789abcdef")
        entries.append({
            "slug": slug, "name": slug.title(), "data_dir": data_dir,
            "created_at": "2026-10-02T00:00:00Z", "last_used": None,
        })
    (root / "data" / "profiles.json").write_text(
        json.dumps({"profiles": entries, "last_used": last_used}), encoding="utf-8"
    )


def _export(root, *args, inherited_salt=None):
    """
    Run the wrapper the way the Backup screen does, and return the pair of
    files export_backup.py would have opened: the database it was given or
    defaults to, and the salt it was pointed at or defaults to.

    The environment is scrubbed of PIP_* first. A launched app inherits
    launch_pip.ps1's profile variables, so a console started from it can carry
    a PIP_SALT_PATH naming whichever profile was opened at launch -
    inherited_salt stands in for that.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("PIP_")}
    if inherited_salt is not None:
        env["PIP_SALT_PATH"] = str(inherited_salt)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(root / "scripts" / "export_pip.ps1"), *args],
        input="\n", capture_output=True, text=True, env=env, timeout=120,
    )
    called = root / "scripts" / "called.json"
    assert called.exists(), f"export_backup.py never ran:\n{result.stdout}\n{result.stderr}"
    call = json.loads(called.read_text(encoding="utf-8"))
    argv = call["argv"]
    database = Path(argv[argv.index("--db-path") + 1]) if "--db-path" in argv else root / "data" / "pip.db"
    salt = Path(call["salt"]) if call["salt"] else root / "data" / "salt.bin"
    return database, salt


@pytest.mark.parametrize("last_used", ["alice", "default"], ids=["recorded", "stale"])
def test_a_sole_profile_is_the_one_exported(installation, last_used):
    """
    D-03. The installation every new user has: one profile, in its own folder.
    The wrapper passed nothing, and the export looked for data/pip.db.

    Also with last_used naming nobody (the registry's value before any sign-in
    has worked): under Windows PowerShell 5.1, which the app launches, a lone
    profile reaches Resolve-PipLastProfile's last_used lookup rather than its
    one-profile branch - a single object returned from a function has no
    .Count there - so the fallback is the path that actually runs.
    """
    _register(installation, ("alice", "profiles/alice"), last_used=last_used)

    database, salt = _export(installation)

    alice = installation / "data" / "profiles" / "alice"
    assert database == alice / "pip.db", f"the export would have read {database}"
    assert salt == alice / "salt.bin", f"the export would have derived its key with {salt}"


def test_the_last_opened_of_several_profiles_is_the_one_exported(installation):
    """The case the wrapper already handled - backing up the wrong person would
    be a quiet and expensive mistake to discover later."""
    _register(
        installation, ("alice", "profiles/alice"), ("bob", "profiles/bob"), last_used="bob"
    )

    database, salt = _export(installation)

    bob = installation / "data" / "profiles" / "bob"
    assert (database, salt) == (bob / "pip.db", bob / "salt.bin")


@pytest.mark.parametrize("registered", [False, True], ids=["no-registry", "registered-default"])
def test_the_original_layout_is_exported_with_its_own_salt(installation, registered):
    """
    An installation from before profiles keeps its database in data/ itself,
    and data/pip.db is then the right file. Its salt must be data/salt.bin
    too, not one inherited from a profile that was open when the app was
    launched - that pairing derives a key the right password cannot produce.

    Two shapes reach it by different paths. With no profiles.json at all the
    resolver finds no profile and the wrapper picks the original layout
    itself; with a registry naming only Default, the resolver returns
    data/'s own paths under PowerShell 5.1.
    """
    if registered:
        _register(installation, ("default", "."), last_used="default")
    else:
        (installation / "data" / "pip.db").write_bytes(b"")
        (installation / "data" / "salt.bin").write_bytes(b"0123456789abcdef")
    elsewhere = installation / "data" / "profiles" / "gone" / "salt.bin"

    database, salt = _export(installation, inherited_salt=elsewhere)

    assert (database, salt) == (installation / "data" / "pip.db", installation / "data" / "salt.bin")


def test_a_database_named_by_the_caller_is_left_alone(installation):
    """--db-path from the command line wins, and with it the caller's own salt."""
    _register(installation, ("alice", "profiles/alice"), last_used="alice")
    chosen = installation / "elsewhere" / "pip.db"
    their_salt = installation / "elsewhere" / "salt.bin"

    database, salt = _export(installation, "--db-path", str(chosen), inherited_salt=their_salt)

    assert (database, salt) == (chosen, their_salt)
