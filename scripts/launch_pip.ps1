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
$flutterExe = Join-Path $root "frontend\flutter\build\windows\x64\runner\Release\pip_flutter_client.exe"

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

if (-not (Test-PortOpen 11434)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Write-Phase "ollama" "started"
} else {
    # Reported rather than skipped. A phase the splash never receives would sit
    # unresolved on screen, and "already running" is a true and useful thing to
    # be told - it is the difference between a fast launch and a broken one.
    Write-Phase "ollama" "already running"
}

if (-not (Test-PortOpen 8765)) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

    # Database key. Originally nothing set PIP_DB_KEY on the real startup path,
    # so get_connection() always took its unencrypted fallback and ADR-026's
    # "encrypted at rest" guarantee was dead code in every launch. First fixed
    # with a random key in data/db_key.txt - which encrypts, but leaves the key
    # beside the database it decrypts. Part 10.1's model is used instead now:
    # a password, PBKDF2-derived, never written to disk.
    #
    # This is the one place this script is not silent. Its whole premise is
    # "double-click an icon, get a normal app window" with no console - and a
    # password prompt is a console. That cost is deliberate and is the spec's
    # own choice ("User types password at app launch"): a key that never
    # touches disk cannot be obtained without asking. The window closes once
    # the app starts.
    . (Join-Path $PSScriptRoot "_db_key.ps1")
    if (-not (Set-PipDbKey -Root $root)) { exit 1 }
    Write-Phase "key" "database key derived"

    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    $stdoutLog = Join-Path $dataDir "backend.log"
    $stderrLog = Join-Path $dataDir "backend.err.log"
    Start-Process $venvPython `
        -ArgumentList "-m", "uvicorn", "backend.api.server:app", "--host", "127.0.0.1", "--port", "8765" `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
    Write-Phase "backend" "starting PIP Core"
} else {
    # Already listening - every phase this script would have reported happened
    # on an earlier launch, and the backend will not report its own again
    # either. Saying so keeps the splash honest about why it is about to
    # finish immediately.
    Write-Phase "backend" "already running"
    Write-Phase "ready" "backend listening"
}

if (-not (Test-Path $flutterExe)) {
    Write-Host "Flutter build not found at $flutterExe" -ForegroundColor Red
    Write-Host "Run this first: cd frontend\flutter; flutter build windows" -ForegroundColor Yellow
    exit 1
}

$env:PIP_DATA_DIR = $dataDir
Start-Process $flutterExe -WorkingDirectory (Split-Path $flutterExe)
