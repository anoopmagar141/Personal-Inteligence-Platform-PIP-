# One-command dev launcher: starts Ollama (if it isn't already running) and
# the backend, each in its own window, waits for the backend to come up,
# reads the current token from data/api_token.txt (avoids the manual
# copy/paste step that kept going stale across restarts), and runs the
# Flutter client with the right --dart-define flags already wired up.
#
# Usage:
#   .\scripts\run_dev.ps1            # launches the Edge (web) build
#   .\scripts\run_dev.ps1 -Device windows

param(
    [string]$Device = "edge"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tokenPath = Join-Path $root "data\api_token.txt"

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

Write-Host "Starting PIP backend..." -ForegroundColor Cyan
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned; Set-Location '$root'; & '$venvActivate'; python -m uvicorn backend.api.server:app --host 127.0.0.1 --port 8765"
)

Write-Host "Waiting for backend on http://127.0.0.1:8765 ..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/v1/status" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch [System.Net.WebException] {
        # A 401 (missing/invalid token) still means the server answered - only
        # a connection failure means it isn't up yet.
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
$token = (Get-Content $tokenPath -Raw).Trim()

Write-Host "Launching Flutter client (device: $Device)..." -ForegroundColor Cyan
Set-Location (Join-Path $root "frontend\flutter")
flutter run -d $Device `
    --dart-define=PIP_API_BASE=http://127.0.0.1:8765/api/v1 `
    --dart-define=PIP_WS_URL=ws://127.0.0.1:8765/ws/chat `
    --dart-define=PIP_API_TOKEN=$token
