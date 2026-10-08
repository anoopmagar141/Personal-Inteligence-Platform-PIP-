"""
Closing PIP and opening it again applies a staged restore, and the restore
shortcut can get PIP out of its way (FREEZE_LIST D-09).

Nothing stops the backend when the window closes. launch_pip.ps1 starts it
hidden, the Flutter app has no exit hook and the backend no shutdown route, so
"close PIP" closes a window and leaves the process, its lock and its open
database exactly where they were. Two things followed, and the second was never
seen because the migration harness stopped the backend itself:

  The in-app restore says "Close PIP and open it again". Opening it again found
  the port already listening, said "already running", and started nothing: the
  staged restore is installed by the lifespan of a NEW backend, so it waited for
  a reboot or a crash, possibly days, with D-18 and D-19's windows open all the
  while.

  The first-run "Import existing PIP" tells the person to close PIP and use the
  "Restore PIP from backup" shortcut. restore_backup.py refuses while the lock is
  held, and the lock is held by the backend nobody was told to stop. On the one
  machine the welcome screen is shown on - where PIP has just been launched -
  the import could not start without Task Manager.

What runs here is the real launch_pip.ps1, restore_pip.ps1 and _backend.ps1
copied into a throwaway installation, against a stand-in "backend": a process
whose command line carries `backend.api.server` and which listens on a free
port. Nothing real is stopped - the helper identifies PIP's backend by that
command line and refuses anything else, which is the test most worth having
here: a script that kills whatever owns port 8765 is a script that kills
somebody's other program.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SYSTEM_PATH = os.pathsep.join([
    str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"),
    str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0"),
])

_LISTENER = (
    "import socket, sys, time\n"
    "s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
    "s.bind(('127.0.0.1', int(sys.argv[1]))); s.listen(5)\n"
    "time.sleep(600)\n"
)

_RECORDER = """\
import json, sys
from pathlib import Path
Path(__file__).with_name("restore_called.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
"""


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_until(predicate, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


@pytest.fixture(scope="module")
def interpreter(tmp_path_factory):
    venv = tmp_path_factory.mktemp("interpreter") / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    return venv


@pytest.fixture
def installation(tmp_path, interpreter):
    root = tmp_path / "PIP"
    (root / "scripts").mkdir(parents=True)
    for name in ("launch_pip.ps1", "restore_pip.ps1", "_backend.ps1", "_python.ps1", "_profiles.ps1"):
        source = REPO / "scripts" / name
        if source.exists():
            shutil.copyfile(source, root / "scripts" / name)
    (root / "scripts" / "restore_backup.py").write_text(_RECORDER, encoding="utf-8")
    shutil.copytree(interpreter, root / ".venv")
    (root / "data").mkdir()
    return root


@pytest.fixture
def spawned():
    started = []
    yield started
    for proc in started:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)


def _fake(spawned, port, *, pip: bool):
    """A process listening on *port*. With pip=True its command line is the one
    launch_pip.ps1 gives the real backend's module; otherwise it is some other
    program that happens to own a port."""
    args = [sys.executable, "-c", _LISTENER, str(port)]
    if pip:
        args.append("backend.api.server:app")
    proc = subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    spawned.append(proc)
    assert _wait_until(lambda: _listening(port)), "the stand-in did not start listening"
    return proc


def _env(port):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PIP_")}
    env["PIP_PORT"] = str(port)
    env["PATH"] = SYSTEM_PATH  # no ollama: the launcher must not start one here
    return env


def _helper(root, port, command):
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         f". '{root / 'scripts' / '_backend.ps1'}'; {command}"],
        capture_output=True, text=True, env=_env(port), timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def _mark_restore_pending(root):
    (root / "data" / "pending-restore.json").write_text(json.dumps({"db": "x"}), encoding="utf-8")


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


def test_the_helper_finds_pips_backend_by_what_it_is(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)

    found = _helper(
        installation, port,
        f"$p = Get-PipBackendProcess -Port {port}; \"$($p.ProcessId),$($p.ParentProcessId)\"",
    )

    # The venv's python.exe is a launcher that starts the interpreter as a
    # child, and the child is what listens: the stand-in is found either way.
    pid, parent = (int(x) for x in found.split(","))
    assert proc.pid in (pid, parent)


def test_the_helper_does_not_mistake_another_program_for_pip(installation, spawned):
    port = _free_port()
    _fake(spawned, port, pip=False)

    found = _helper(installation, port, f"Get-PipBackendProcess -Port {port}")

    assert found == ""


def test_stopping_pips_backend_frees_the_port(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)

    outcome = _helper(installation, port, f"Stop-PipBackend -Port {port}")

    assert outcome == "stopped"
    assert _wait_until(lambda: proc.poll() is not None)
    assert not _listening(port)


def test_stopping_never_touches_a_program_that_is_not_pip(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=False)

    outcome = _helper(installation, port, f"Stop-PipBackend -Port {port}")

    assert outcome == "not-pip"
    assert proc.poll() is None and _listening(port), "somebody else's program was killed"


def test_stopping_with_nothing_running_says_so(installation):
    port = _free_port()

    assert _helper(installation, port, f"Stop-PipBackend -Port {port}") == "not-running"


def test_a_backend_is_restarted_only_when_a_restore_is_waiting(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)
    data = installation / "data"

    untouched = _helper(installation, port, f"Restart-PipBackendIfRestorePending -DataDir '{data}' -Port {port}")
    assert untouched == "no-restore-pending"
    assert proc.poll() is None and _listening(port), "a backend with nothing to apply was stopped"

    _mark_restore_pending(installation)
    restarted = _helper(installation, port, f"Restart-PipBackendIfRestorePending -DataDir '{data}' -Port {port}")
    assert restarted == "stopped"
    assert _wait_until(lambda: proc.poll() is not None)


# ---------------------------------------------------------------------------
# launch_pip.ps1: "close PIP and open it again"
# ---------------------------------------------------------------------------


def _launch(root, port):
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "scripts" / "launch_pip.ps1")],
        capture_output=True, text=True, env=_env(port), timeout=240, input="\n",
    )


def _phases(root):
    path = root / "data" / "startup.jsonl"
    if not path.exists():
        return []
    # utf-8-sig: Windows PowerShell's -Encoding utf8 writes a BOM.
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def test_opening_pip_again_replaces_the_backend_a_restore_is_waiting_for(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)
    _mark_restore_pending(installation)

    _launch(installation, port)

    assert proc.poll() is not None or _wait_until(lambda: proc.poll() is not None, 5), (
        "the old backend was left running, so the staged restore would wait for a reboot"
    )
    backend = [p for p in _phases(installation) if p["phase"] == "backend"]
    assert backend and backend[-1]["detail"] == "uvicorn launched", "no new backend was started"


def test_opening_pip_again_leaves_a_running_backend_alone_when_nothing_is_waiting(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)

    _launch(installation, port)

    assert proc.poll() is None and _listening(port)
    assert any(p["phase"] == "backend" and p["detail"] == "already running" for p in _phases(installation))


# ---------------------------------------------------------------------------
# restore_pip.ps1: the shortcut can get PIP out of its way
# ---------------------------------------------------------------------------


def _restore(root, port, answers):
    backup = root / "data" / "carried.pipbak"
    backup.write_bytes(b"x")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "scripts" / "restore_pip.ps1"),
         "--from", str(backup), "--yes"],
        capture_output=True, text=True, env=_env(port), timeout=240, input=answers,
    )
    called = root / "scripts" / "restore_called.json"
    return result, (json.loads(called.read_text(encoding="utf-8")) if called.exists() else None)


def test_the_shortcut_closes_pip_when_asked_and_then_restores(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)

    result, called = _restore(installation, port, "yes\n\n")

    assert _wait_until(lambda: proc.poll() is not None), result.stdout
    assert called is not None, "the restore never ran after PIP was closed:\n" + result.stdout


def test_the_shortcut_changes_nothing_when_the_answer_is_no(installation, spawned):
    port = _free_port()
    proc = _fake(spawned, port, pip=True)

    result, called = _restore(installation, port, "no\n\n")

    assert proc.poll() is None and _listening(port)
    assert called is None, "the restore ran although PIP was left running"
    assert result.returncode != 0


def test_the_shortcut_does_not_ask_when_pip_is_not_running(installation):
    result, called = _restore(installation, _free_port(), "\n")

    assert called is not None
    assert "still running" not in result.stdout.lower()
