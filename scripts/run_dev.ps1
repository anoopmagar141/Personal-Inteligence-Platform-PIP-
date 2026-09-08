# One-command dev launcher: starts Ollama (if it isn't already running) and
# the backend (with --reload, so backend edits apply automatically without a
# manual restart), each in its own window, waits for the backend to come up,
# then runs the Flutter client in debug mode against it - hot reload (r) /
# hot restart (R) both work from the Flutter terminal this opens.
#
# Native desktop only (-d windows default) - main.dart reads its config via
# dart:io's Platform.environment now, not --dart-define, and dart:io isn't
# available on the web target at all ("Unsupported operation:
# Platform._environment" is exactly this mismatch, not a real app bug) -
# see main.dart's docstring for why. Passing PIP_DATA_DIR as a real
# environment variable (not --dart-define) is what lets this script and
# launch_pip.ps1 share the exact same config-reading path in the app.
#
# Usage:
#   .\scripts\run_dev.ps1
#   .\scripts\run_dev.ps1 -Device windows   # equivalent, windows is already the default

param(
    [string]$Device = "windows"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $root "data"
$tokenPath = Join-Path $dataDir "api_token.txt"

# Database key. Originally nothing set PIP_DB_KEY on the real startup path at
# all, so get_connection() always took its unencrypted fallback and ADR-026's
# "encrypted at rest" guarantee was dead code in every launch. That was first
# fixed with a random key persisted to data/db_key.txt - which encrypts, but
# leaves the key beside the database it decrypts, so anything copying data/ gets
# both. Part 10.1 specifies the model now used instead: a password typed here,
# PBKDF2-derived, never written to disk. See scripts/_db_key.ps1.
. (Join-Path $PSScriptRoot "_db_key.ps1")
if (-not (Set-PipDbKey -Root $root)) { exit 1 }

# Ollama listens on 11434 by default (see backend/providers/ollama_provider.py's
# OllamaProvider host default) - a TCP probe is enough to tell "already
# running" from "needs starting," no API call needed.
$ollamaRunning = (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet -WarningAction SilentlyContinue)
if (-not $ollamaRunning) {
    Write-Host "Starting Ollama..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", "ollama serve")
    for ($i = 0; $i -lt 15; $i++) {
        if (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet -WarningAction SilentlyContinue) { break }
        Start-Sleep -Seconds 1
    }
} else {
    Write-Host "Ollama already running." -ForegroundColor DarkGray
}

Write-Host "Starting PIP backend (--reload: edits apply automatically)..." -ForegroundColor Cyan
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; Set-Location '$root'; & '$venvActivate'; python -m uvicorn backend.api.server:app --host 127.0.0.1 --port 8765 --reload --reload-dir backend"
)

Write-Host "Waiting for backend on http://127.0.0.1:8765 ..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/v1/status" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch {
        # A 401 (missing/invalid token) still means the server answered - only
        # a connection failure means it isn't up yet.
        #
        # Catches everything and then ASKS THE EXCEPTION whether a response
        # exists, rather than filtering on a type. The type filter here used to
        # be [System.Net.WebException], which is what Windows PowerShell 5.1
        # throws - but PowerShell 7's Invoke-WebRequest is built on HttpClient
        # and throws Microsoft.PowerShell.Commands.HttpResponseException for an
        # HTTP status and TaskCanceledException for a timeout. Neither matches,
        # so under pwsh the catch never fired, $ErrorActionPreference = "Stop"
        # made the unhandled error terminating, and the script aborted on the
        # FIRST probe - taking the whole launch down while leaving the backend
        # window it had just spawned running.
        #
        # That is worse than a plain failure, because the abandoned backend
        # keeps the port and the instance lock, so the next run_dev.ps1 dies on
        # AlreadyRunningError and the cause looks like a stale lock rather than
        # a launcher bug. Measured: three consecutive failed launches, three
        # different error messages, none of them the real one.
        #
        # .Response is present on WebException (5.1) and on
        # HttpResponseException (7), and absent on the timeout/connection
        # exceptions of both - so it answers the question the comment above
        # actually asks, on either edition.
        if ($_.Exception.Response) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Host "Backend did not come up in time - check the backend window for errors." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $tokenPath)) {
    Write-Host "No token file yet at $tokenPath - backend may still be initializing. Waiting a bit longer..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

Write-Host "Launching Flutter client (device: $Device)..." -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend\flutter")
$env:PIP_DATA_DIR = Join-Path $root "data"
$env:PIP_API_BASE = "http://127.0.0.1:8765/api/v1"
$env:PIP_WS_URL = "ws://127.0.0.1:8765/ws/chat"
flutter run -d $Device
