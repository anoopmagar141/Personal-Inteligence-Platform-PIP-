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
