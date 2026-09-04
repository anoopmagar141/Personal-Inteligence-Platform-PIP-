"""
Fail helpfully when a script is run with the wrong Python.

Every script in here needs packages that live in the project's virtual
environment. Run one with the system interpreter and you get either a raw
ModuleNotFoundError traceback, or - worse - advice to run
`pip install -r requirements.txt`, which installs the packages into the wrong
interpreter and leaves the original command failing exactly as before.

That happened: `python scripts/export_backup.py` on a machine where everything
was correctly installed, during a database migration, at the one moment a
confusing error is least welcome.

The distinction the old message missed is that nothing is missing. The
environment is fine; the command named the wrong interpreter. So this reports
which interpreter is running, which one to use, and the exact line to re-run,
rather than prescribing an install that would not help.
"""

import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# An installed copy of PIP ships a standalone interpreter in python\ rather
# than a virtual environment, because a venv records an absolute path back to
# the base install it was made from and so cannot be copied to another machine.
# scripts/_python.ps1 carries the full reasoning; this is the same resolution
# order, for the scripts that are invoked as Python rather than PowerShell.
#
# Portable first, for the reason given there: while a build is being tested
# from inside the source tree both exist, and the copy under test is the one
# whose failures matter.
PORTABLE_PYTHON = REPO_ROOT / "python" / "python.exe"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
VENV_PYTHON_POSIX = REPO_ROOT / ".venv" / "bin" / "python"


def _venv_interpreter() -> pathlib.Path | None:
    for candidate in (PORTABLE_PYTHON, VENV_PYTHON, VENV_PYTHON_POSIX):
        if candidate.exists():
            return candidate
    return None


def require(*modules: str) -> None:
    """
    Exit with a useful message if any of `modules` cannot be imported.

    Exits nonzero, and specifically not 1: sys.exit(message) would print the
    text but always exit 1, and 1 is the code a script here is most likely to
    return for a real answer of its own. A caller must be able to tell "the
    interpreter was wrong" from "the database said no".

    2 is safe for the scripts this guards - none of them returns it, and none
    is invoked by the launchers for its exit code. derive_db_key.py does have
    such a contract (0 ok / 1 no salt / 2 empty password / 3 wrong password,
    read by scripts/_db_key.ps1) and is deliberately left unguarded: the
    launcher always calls it with the venv interpreter by absolute path, so it
    cannot reach this failure in the first place.
    """
    missing = []
    for name in modules:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if not missing:
        return

    venv = _venv_interpreter()
    script = pathlib.Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "this script"
    running = pathlib.Path(sys.executable)

    lines = [
        f"ERROR: {', '.join(missing)} is not available to this interpreter.",
        "",
        f"  running: {running}",
    ]

    if venv is None:
        lines += [
            "",
            "  No interpreter was found at python\\ or .venv, so the dependencies have",
            "  probably never been installed. From the repository root:",
            "",
            "      python -m venv .venv",
            f"      {VENV_PYTHON} -m pip install -r requirements.txt",
        ]
    elif running.resolve() == venv.resolve():
        # Inside the venv and still missing: this genuinely is an install gap.
        lines += [
            "",
            "  That IS the project's virtual environment, so the package really is",
            "  missing rather than out of reach:",
            "",
            f"      {venv} -m pip install -r requirements.txt",
        ]
    else:
        lines += [
            f"  needed:  {venv}",
            "",
            "  Nothing is missing from the project - this command just named the",
            "  wrong interpreter. Re-run it as:",
            "",
            f"      {venv} scripts\\{script}"
            if os.name == "nt"
            else f"      {venv} scripts/{script}",
        ]

    # print + exit(code) rather than sys.exit(message): passing a string to
    # sys.exit prints it but always exits 1, which is the code this is trying
    # not to collide with.
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)
