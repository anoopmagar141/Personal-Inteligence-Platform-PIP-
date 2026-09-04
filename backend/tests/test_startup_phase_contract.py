"""
The launch checklist spans three files that nothing else makes agree.

  * scripts/launch_pip.ps1 writes the phases that happen before uvicorn exists
  * backend/core/startup_progress.py (via server.py) writes the rest
  * frontend/flutter/lib/startup_progress.dart turns phase ids into sentences

Running the app is what exposed why this needs a test. The two phases the
BACKEND writes land in the same second:

    14:03:34  lock
    14:03:34  ready

and the server answers immediately after, so the client reads the file and
succeeds at /status in the same poll - the checklist never paints. What
actually covers the wait is the launcher writing 'backend' BEFORE python
starts, ten seconds before the backend can report anything:

    14:03:24  backend   uvicorn launched      <- launch_pip.ps1
       ... ten seconds of imports ...
    14:03:34  lock                            <- server.py

So the launcher's phases are not a nice-to-have decorating the backend's:
they are the entire visible life of the feature. Delete them and the launch
screen degrades to the spinner-and-a-guess it replaced, every test still
passes, and nobody finds out until someone watches a cold start.

These are text assertions rather than behavioural ones, which is a real
limitation: they prove the calls are written, not that they run. That is the
most a Python suite can say about a PowerShell script it does not execute,
and it is enough for the failure that actually threatens this - a phase being
dropped in a refactor.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
LAUNCHER = REPO / "scripts" / "launch_pip.ps1"
SERVER = REPO / "backend" / "api" / "server.py"
DART_LABELS = REPO / "frontend" / "flutter" / "lib" / "startup_progress.dart"

# The phases only the launcher can report, because they happen before there is
# a backend to ask. These are the ones that cover the multi-second wait.
PRE_BACKEND_PHASES = {"ollama", "key", "backend"}

# The phases only the backend can report, from inside its own lifespan.
BACKEND_PHASES = {"lock", "ready"}


def launcher_phases() -> list[str]:
    """Every phase id the launcher writes, in file order, with duplicates."""
    # The function DEFINITION is `function Write-Phase($phase, $detail)`, which
    # this does not match - only the call sites, which pass a literal.
    return re.findall(r'Write-Phase\s+"([a-z_]+)"', LAUNCHER.read_text(encoding="utf-8"))


def backend_phases() -> list[str]:
    return re.findall(
        r'startup_progress\.report\(\s*"([a-z_]+)"', SERVER.read_text(encoding="utf-8")
    )


def dart_labelled_phases() -> set[str]:
    source = DART_LABELS.read_text(encoding="utf-8")
    block = re.search(r"startupPhaseLabels\s*=\s*<String,\s*String>\{(.*?)\};", source, re.S)
    assert block, "startupPhaseLabels is no longer a map literal this test can read"
    return set(re.findall(r"'([a-z_]+)'\s*:", block.group(1)))


def test_the_launcher_still_reports_the_phases_only_it_can_see():
    """
    The regression this file exists for. Without these three the checklist has
    nothing to show during the ten seconds that actually elapse, and the launch
    screen quietly reverts to a spinner.
    """
    written = set(launcher_phases())
    missing = PRE_BACKEND_PHASES - written
    assert not missing, (
        f"scripts/launch_pip.ps1 no longer reports {sorted(missing)}. "
        "Those phases cover the wait before uvicorn exists - without them the "
        "launch screen shows a spinner and a guess again."
    )


# The two phases the launcher reports from inside an if/else: Ollama is either
# started or already up, and so is the backend. Both branches report,
# deliberately - a phase the splash never receives sits unresolved on screen,
# and "already running" is the difference between a fast launch and a broken
# one.
BRANCHED_PHASES = ["ollama", "backend"]


@pytest.mark.parametrize("phase", BRANCHED_PHASES)
def test_the_launcher_reports_a_branched_phase_on_both_paths(phase):
    """
    Counting, not set membership, and the distinction is the whole point.

    This test first shipped checking only that 'backend' appeared SOMEWHERE in
    the launcher - which it does twice, so deleting the started-path write left
    the suite green while the checklist stalled on every cold launch. That is
    the exact failure this file was written to catch, and the first version of
    it did not.
    """
    assert launcher_phases().count(phase) >= 2, (
        f"The launcher reports {phase!r} on only one branch. Both the started "
        "and the already-running paths must report it, or one of them leaves "
        "that row spinning for a step that will never arrive."
    )


def ollama_block() -> str:
    """
    The launcher's Ollama block, from its guard comment to the bare closing
    brace that ends the last branch. Read out of the file rather than restated
    here, so these assertions cannot pass against code that is not shipping.
    """
    source = LAUNCHER.read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(source) if "# Ollama, in every state" in line),
        None,
    )
    assert start is not None, (
        "The launcher's Ollama block has been rewritten past recognition. "
        "These tests are now blind to it - re-anchor them before trusting them."
    )
    end = next((i for i in range(start, len(source)) if source[i].rstrip() == "}"), None)
    assert end is not None, "The Ollama block has no closing brace this test can find"
    return "\n".join(source[start : end + 1])
def ollama_code() -> str:
    """
    The same block with its comment lines removed.

    The comments there explain the bug by naming it - "this was one
    Start-Process with no check" - so a test searching the raw text finds
    Start-Process in the prose before it finds it in the code, and concludes
    the guard is on the wrong side of it. Every assertion below is a claim
    about what RUNS, so every one of them reads this instead.
    """
    return "\n".join(
        line for line in ollama_block().splitlines() if not line.lstrip().startswith("#")
    )


def test_the_launcher_checks_for_ollama_before_starting_it():
    """
    The regression: `Start-Process ollama` with no check, under the
    $ErrorActionPreference = "Stop" set at the top of the file. On a machine
    without Ollama that throws, and it throws SEVERAL LINES BEFORE the
    Start-Process that opens the application - so the launch ended here, having
    started nothing.

    What made it invisible rather than merely broken is the Desktop shortcut,
    which runs the launcher with -WindowStyle Hidden. There was no console for
    the error to land in. The whole failure presented as double-clicking the
    PIP icon and having nothing happen.

    This is the machine PIP is now packaged for: scripts/build_portable.ps1
    produces a copy that carries its own Python but cannot carry Ollama.
    """
    block = ollama_code()
    guard = block.index("Get-Command")
    start = block.index("Start-Process")
    assert guard < start, (
        "scripts/launch_pip.ps1 starts Ollama without first checking it exists. "
        "Under ErrorActionPreference Stop that terminates the launch before the "
        "application is started, and the shortcut runs hidden, so the user sees "
        "nothing at all."
    )


def test_a_machine_without_ollama_still_reaches_the_application():
    """
    The guard is only half the fix. A check that reports the problem and then
    exits leaves the same user with the same nothing - and exiting would be the
    wrong call regardless, because PIP with no Ollama is an installation with
    no model YET. That is the exact state the model browser and the fail-open
    /llm/catalog exist to serve. Refusing to open is refusing to show the
    screen that fixes the problem.
    """
    assert "exit" not in ollama_code(), (
        "A branch of the launcher's Ollama block now exits. Whatever Ollama's "
        "state, the application still has to start: choosing and pulling a "
        "model is done from inside it."
    )


def test_every_ollama_branch_reports_its_outcome():
    """
    Four states - listening, started, failed to start, not installed - and the
    splash draws one row for all of them. A branch that reports nothing leaves
    that row unresolved on screen for a step that has already finished.

    The count is DERIVED from the block rather than written down here, and that
    is the whole design of this test. The first version asserted `>= 3` against
    four branches, so deleting one report left the suite green - which is the
    same bug, in the same file, that the branched-phase test above was rewritten
    to fix. A number restated in a test is a number that stops matching the code.
    """
    code = ollama_code()

    # Every path that can be taken: the three top-level branches, plus the catch
    # that splits the middle one into started and failed-to-start. `\bif` does
    # not match inside `elseif`, so the two are counted separately rather than
    # twice.
    outcomes = (
        len(re.findall(r"\bif\s*\(", code))
        + len(re.findall(r"\belseif\s*\(", code))
        + len(re.findall(r"\belse\s*\{", code))
        + len(re.findall(r"\bcatch\s*\{", code))
    )
    written = re.findall(r'Write-Phase\s+"ollama"\s+"([^"]+)"', code)

    assert len(written) >= outcomes, (
        f"The launcher's Ollama block has {outcomes} outcomes but only "
        f"{len(written)} of them report a phase ({written}). The branch that "
        "stays quiet leaves the launch screen waiting on a step that already "
        "happened."
    )
    assert len(set(written)) == len(written), (
        f"Two Ollama branches report the same detail ({written}), so the launch "
        "screen cannot tell apart the states they exist to distinguish."
    )


def test_the_already_running_path_still_completes_the_list():
    """
    When the backend is already listening the launcher skips the block that
    starts it - so it reports 'ready' itself, or the checklist stops halfway
    with the app about to connect anyway.
    """
    assert "ready" in launcher_phases(), (
        "The launcher no longer reports 'ready' on the already-running path, so "
        "that launch leaves the checklist unfinished."
    )


def test_the_backend_still_reports_its_own_phases():
    written = set(backend_phases())
    missing = BACKEND_PHASES - written
    assert not missing, f"backend/api/server.py no longer reports {sorted(missing)}"


def test_the_backgrounded_catch_up_is_still_not_reported():
    """
    The Observer drain runs in the background so nobody waits on it - server.py
    records that having it inline hung launch for over two minutes. Reporting it
    would put the thing that was moved OFF the launch path back onto the launch
    screen.
    """
    assert not [p for p in backend_phases() if "catch" in p or "observer" in p]


def test_every_phase_written_has_something_to_display():
    """
    A phase with no label still renders, under its raw id - deliberately, so a
    version skew is visible rather than hidden. This catches it at build time
    instead, where it is cheaper than on a user's launch screen.
    """
    written = set(launcher_phases()) | set(backend_phases())
    unlabelled = written - dart_labelled_phases()
    assert not unlabelled, (
        f"These phases are written but have no label in startup_progress.dart: "
        f"{sorted(unlabelled)}. They will render as their raw id."
    )


def test_every_label_has_something_that_writes_it():
    """
    The other direction. A label nobody writes is a row that can never report,
    so it either sits pending forever or gets silently marked done by a later
    phase - which is a claim about a step that never happened.
    """
    written = set(launcher_phases()) | set(backend_phases())
    orphans = dart_labelled_phases() - written
    assert not orphans, (
        f"These phases have a label but nothing writes them: {sorted(orphans)}."
    )


@pytest.mark.parametrize("path", [LAUNCHER, SERVER, DART_LABELS])
def test_the_files_this_contract_reads_still_exist(path):
    """
    Guards the guard. Every assertion above is a regex over a file, so a moved
    or renamed file would make them all vacuous rather than failing.
    """
    assert path.exists(), f"{path} has moved; the phase contract tests are now blind"
