# PIP - one-click launcher (production-style, no visible windows).
#
# Unlike run_dev.ps1 (kept as-is for dev work: visible windows, an -NoExit
# terminal for Flutter's hot-reload keys), this script starts Ollama and the
# backend fully hidden, launches the native Windows build, then exits itself
# - "double-click an icon, get a normal app window," not a dev workflow.
#
# Deliberately does NOT wait for the backend to become ready before starting
# the Flutter app - that wait belongs to the app's own splash screen
# (AppRoot in main.dart), which retries against the real backend. Keeping that
# logic in Flutter, not here, matches this project's "frontend has zero
# intelligence... but a frontend is still allowed to wait on its own
# connections" split: this script's only job is starting processes, nothing
# about readiness.
#
# It does, however, REPORT what it is starting. The splash screen used to pick
# between two sentences based on a retry counter, so it said "Still preparing
# things" after eight seconds whether the database was being decrypted or
# nothing was running at all. The phases below are the ones only this script
# can see - Ollama and the password - because they happen before uvicorn
# exists to answer anything. backend/core/startup_progress.py takes over from
# the lock onwards, appending to the same file.
#
# Truncated first, so a launch screen cannot read the last run's phases and
# show a finished checklist before anything has happened.
#
# PIP_DATA_DIR is the one thing the app needs told, not guessed - it reads
# its token from $dataDir\api_token.txt at runtime (not baked in at build
# time, since the token doesn't exist until the backend's first real run
# generates it - see main.dart's docstring for the full reasoning).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root "data"

# Both of these differ between an installed copy and a source checkout, and for
# the same reason: an install ships built artefacts where a checkout has a build
# tree. _python.ps1 explains why the interpreter cannot simply be
# ".venv\Scripts\python.exe" on a machine that is not the one it was made on.
. (Join-Path $PSScriptRoot "_python.ps1")
$pipPython = Get-PipPython -Root $root
if (-not $pipPython) { Show-PipPythonMissing -Root $root; exit 1 }

$flutterExe = Join-Path $root "app\pip_flutter_client.exe"
if (-not (Test-Path $flutterExe)) {
    $flutterExe = Join-Path $root "frontend\flutter\build\windows\x64\runner\Release\pip_flutter_client.exe"
}

function Test-PortOpen($portNum) {
    return Test-NetConnection -ComputerName 127.0.0.1 -Port $portNum -InformationLevel Quiet -WarningAction SilentlyContinue
}

$progressFile = Join-Path $dataDir "startup.jsonl"

# Appends one phase for the splash screen to read. Silent on failure for the
# same reason the Python side is: a launch screen is a courtesy, and failing a
# launch because the courtesy could not be written inverts the priority.
function Write-Phase($phase, $detail) {
    try {
        $entry = @{ phase = $phase; detail = $detail; at = (Get-Date).ToUniversalTime().ToString("s") + "Z" }
        Add-Content -Path $progressFile -Value ($entry | ConvertTo-Json -Compress) -Encoding utf8
    } catch { }
}

New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
try { Set-Content -Path $progressFile -Value "" -Encoding utf8 } catch { }

# Ollama, in every state a machine is actually ever in.
#
# WHY A MISSING OLLAMA DOES NOT STOP THE LAUNCH
# ---------------------------------------------
# This was one Start-Process with no check, under the $ErrorActionPreference =
# "Stop" set at the top of the file. On a machine without Ollama installed that
# throws, so the script died HERE - several lines before the one that starts
# the application. And the Desktop shortcut runs this hidden, so the entire
# failure presented as a double-clicked icon doing nothing: no window, no
# error, and nothing in a log anybody in that situation would think to open.
#
# Continuing is not a concession. PIP without Ollama is an installation with no
# model yet, which is exactly the state the model browser and /llm/catalog were
# built for - the catalogue is deliberately fail-open so that choosing
# something to pull is possible on a machine where nothing is set up. Refusing
# to open the app is refusing to show the one screen that fixes the problem.
#
# A start that FAILS is reported the same way as one that was never possible.
# The distinction between "absent" and "installed but broken" is real, and it
# is not this script's to draw: both leave the same machine in the same state,
# and neither is worth trading the application window for.
if (Test-PortOpen 11434) {
    # Reported rather than skipped. A phase the splash never receives would sit
    # unresolved on screen, and "already running" is a true and useful thing to
    # be told - it is the difference between a fast launch and a broken one.
    Write-Phase "ollama" "already running"
} elseif (Get-Command ollama -ErrorAction SilentlyContinue) {
    try {
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Write-Phase "ollama" "started"
    } catch {
        Write-Phase "ollama" "could not be started"
    }
} else {
    # The detail, not the phase id, carries this. A new phase would add a row
    # to a checklist that is meant to be the same list every launch, and would
    # describe the machine rather than a step - the step here genuinely is
    # "local model service", and "not installed" is its outcome.
    Write-Phase "ollama" "not installed"
}

if (-not (Test-PortOpen 8765)) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

    # THE PASSWORD IS NO LONGER ASKED FOR HERE
    #
    # This script used to derive the database key before starting uvicorn, via
    # _db_key.ps1, and the comment that stood here called that the one place
    # this script is not silent: its whole premise is "double-click an icon,
    # get a normal app window" with no console, and a password prompt is a
    # console. The cost was called deliberate.
    #
    # It stopped being worth paying once PIP became something other people
    # install. A first-time user's first sight of the product was a blue
    # PowerShell window asking for a password - for a database that, on a
    # fresh machine, does not exist yet.
    #
    # So the order inverts. The backend starts with no key and serves three
    # routes; the application window opens; the password is typed into PIP.
    # backend/core/session_key.py holds it from there, and still never writes
    # it down - Part 10.1's model is unchanged, only the prompt moved.
    #
    # An older copy of this script that still exports PIP_DB_KEY keeps working:
    # the backend adopts a key it finds in the environment rather than asking
    # for one it already has.
    # AND THE PROFILE IS NO LONGER ASKED FOR HERE EITHER
    #
    # This used to print "Which profile?" and wait for a number, which was the
    # same mistake as the password prompt above and outlived it by one change:
    # a console menu, before any window had opened, asking a question about a
    # product the person had not yet seen. The launch is silent or it is not,
    # and one remaining prompt made it not.
    #
    # So this now only RESOLVES - the profile opened last, with no interaction
    # - and the choosing moved to the sign-in screen, which lists every profile
    # and switches between them through POST /auth/profile. That route works
    # because the backend re-points itself: the four variables below are read
    # at call time by everything that consumes them, never captured at import,
    # so a running process can be aimed somewhere else as long as it holds no
    # key. It refuses while unlocked, which is why signing out is the first
    # half of switching.
    #
    # record_last_used moved with it, to the unlock route. It used to be
    # written here, at selection, and therefore recorded what somebody typed
    # at this menu rather than what actually opened - the password came much
    # later, into an application this script had already exited before. It is
    # now written after a key has been proven to open the database, so the
    # field means what it is called.
    . (Join-Path $PSScriptRoot "_profiles.ps1")
    $profilePaths = Resolve-PipLastProfile -Root $root
    if ($profilePaths) {
        Set-PipProfileEnvironment -Paths $profilePaths
        Write-Phase "profile" $profilePaths.Name
    }

    $stdoutLog = Join-Path $dataDir "backend.log"
    $stderrLog = Join-Path $dataDir "backend.err.log"
    Start-Process $pipPython `
        -ArgumentList "-m", "uvicorn", "backend.api.server:app", "--host", "127.0.0.1", "--port", "8765" `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
    Write-Phase "backend" "uvicorn launched"
} else {
    # Already listening - every phase this script would have reported happened
    # on an earlier launch, and the backend will not report its own again
    # either. Saying so keeps the splash honest about why it is about to
    # finish immediately.
    Write-Phase "backend" "already running"
    Write-Phase "ready" "already listening"
}

if (-not (Test-Path $flutterExe)) {
    Write-Host "PIP's application window was not found at $flutterExe" -ForegroundColor Red
    Write-Host "In an installed copy, that means the extraction did not finish -" -ForegroundColor Yellow
    Write-Host "unpack the download again into an empty folder." -ForegroundColor Yellow
    Write-Host "In a source checkout: cd frontend\flutter; flutter build windows" -ForegroundColor Yellow
    exit 1
}

$env:PIP_DATA_DIR = $dataDir
Start-Process $flutterExe -WorkingDirectory (Split-Path $flutterExe)
