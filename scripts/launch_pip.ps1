# PIP - one-click launcher (production-style, no visible windows).
#
# Unlike run_dev.ps1 (kept as-is for dev work: visible windows, an -NoExit
# terminal for Flutter's hot-reload keys), this script starts Ollama and the
# backend fully hidden, launches the native Windows build, then exits itself
# - "double-click an icon, get a normal app window," not a dev workflow.
#
# Deliberately does NOT wait for the backend to become ready before starting
# the Flutter app - that wait belongs to the app's own splash screen
# (AppRoot in main.dart), which already retries against the real backend
# with its own "please wait" messaging. Keeping that logic in Flutter, not
# here, matches this project's "frontend has zero intelligence... but a
# frontend is still allowed to wait on its own connections" split: this
# script's only job is starting processes, nothing about readiness.
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

if (-not (Test-PortOpen 11434)) {
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
}

if (-not (Test-PortOpen 8765)) {
    New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

    # Security fix: nothing previously set PIP_DB_KEY on the actual startup
    # path, so get_connection() (backend/memory/profile_store.py) always took
    # its unencrypted sqlite3 fallback despite SQLCipher support existing -
    # ADR-026's "encrypted at rest" guarantee was dead code in every real
    # launch. Same persisted-local-secret pattern as backend/core/auth.py's
    # API token: a random hex key generated once and reused on every
    # subsequent start.
    $dbKeyPath = Join-Path $dataDir "db_key.txt"
    if (Test-Path $dbKeyPath) {
        $dbKey = (Get-Content $dbKeyPath -Raw).Trim()
    } else {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $dbKey = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
        Set-Content -Path $dbKeyPath -Value $dbKey -NoNewline -Encoding utf8
    }
    $env:PIP_DB_KEY = $dbKey

    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    $stdoutLog = Join-Path $dataDir "backend.log"
    $stderrLog = Join-Path $dataDir "backend.err.log"
    Start-Process $venvPython `
        -ArgumentList "-m", "uvicorn", "backend.api.server:app", "--host", "127.0.0.1", "--port", "8765" `
        -WorkingDirectory $root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
}

if (-not (Test-Path $flutterExe)) {
    Write-Host "Flutter build not found at $flutterExe" -ForegroundColor Red
    Write-Host "Run this first: cd frontend\flutter; flutter build windows" -ForegroundColor Yellow
    exit 1
}

$env:PIP_DATA_DIR = $dataDir
Start-Process $flutterExe -WorkingDirectory (Split-Path $flutterExe)
