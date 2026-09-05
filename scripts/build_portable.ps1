# Assembles the portable, copy-and-run layout of PIP.
#
#     powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1
#
# Output is a single self-contained folder that runs on a machine with no
# Python, no virtual environment and no PIP source tree:
#
#     PIP\
#       python\   standalone interpreter + every dependency
#       app\      the built Windows application
#       backend\  config\  scripts\  shared\
#       data\     empty - created on first run, never shipped
#
# WHY A COPIED INTERPRETER RATHER THAN THE .venv
# ----------------------------------------------
# A virtual environment cannot be moved between machines. pyvenv.cfg records
# an absolute `home` pointing at the base install it was created from, and
# .venv\Scripts\python.exe is a shim that defers to that path - neither of
# which exists on somebody else's computer. A full CPython install, by
# contrast, locates its own prefix relative to the executable, so copying the
# directory is all it takes. That is what this does: copy the interpreter,
# then drop .venv's site-packages into it.
#
# WHY NOT FREEZE IT INSTEAD
# -------------------------
# PyInstaller would produce something smaller, and would also have to be told,
# by hand and forever, about every dynamic import in torch, chromadb and
# transformers. Copying has no such failure mode: what ships is byte-for-byte
# what was tested here. The cost is size, and size is the cheapest thing to
# spend on a local-first application that is about to download a 4.7 GB model
# anyway.
#
# WHAT IS DELIBERATELY NOT COPIED
# -------------------------------
# data\ is per-machine state - the database, the salt, the API token, the
# profiles. Shipping it would hand every user a copy of the developer's
# memory, and a salt that no longer matches the password they are about to
# choose. It is created empty; the backend populates it on first run, and
# somebody bringing an existing profile across restores a .pipbak into it.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$out = if ($args.Count -gt 0) { $args[0] } else { Join-Path $root "dist\PIP" }

$venv = Join-Path $root ".venv"
$sitePackages = Join-Path $venv "Lib\site-packages"
$flutterRelease = Join-Path $root "frontend\flutter\build\windows\x64\runner\Release"

Write-Host ""
Write-Host "  PIP - portable build" -ForegroundColor Cyan
Write-Host "  ===================="
Write-Host ""

# --- checks, before anything is copied -------------------------------------
# All of them up front. A build that copies 1.2 GB and then discovers the app
# was never built has wasted three minutes to tell you something it knew at
# the start.

if (-not (Test-Path $sitePackages)) {
    Write-Host "  ERROR: no site-packages at $sitePackages" -ForegroundColor Red
    Write-Host "         Create the environment first:" -ForegroundColor DarkGray
    Write-Host "           python -m venv .venv" -ForegroundColor DarkGray
    Write-Host "           .venv\Scripts\python.exe -m pip install -r requirements.txt" -ForegroundColor DarkGray
    exit 1
}

if (-not (Test-Path (Join-Path $flutterRelease "pip_flutter_client.exe"))) {
    Write-Host "  ERROR: no Windows build at $flutterRelease" -ForegroundColor Red
    Write-Host "         Build it first:  cd frontend\flutter; flutter build windows" -ForegroundColor DarkGray
    exit 1
}

# The base install is read out of pyvenv.cfg rather than guessed. Hardcoding
# a path under AppData would work on exactly one machine, which is the bug
# this whole script exists to avoid.
$pyvenvCfg = Join-Path $venv "pyvenv.cfg"
$baseHome = (Get-Content $pyvenvCfg | Where-Object { $_ -match "^home\s*=" }) -replace "^home\s*=\s*", ""
if (-not $baseHome -or -not (Test-Path (Join-Path $baseHome "python.exe"))) {
    Write-Host "  ERROR: could not locate the base Python install." -ForegroundColor Red
    Write-Host "         pyvenv.cfg says home = $baseHome" -ForegroundColor DarkGray
    exit 1
}

$baseVersion = (& (Join-Path $baseHome "python.exe") -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
Write-Host "  interpreter : $baseHome  (Python $baseVersion)"
Write-Host "  packages    : $sitePackages"
Write-Host "  application : $flutterRelease"
Write-Host "  output      : $out"
Write-Host ""

if (Test-Path $out) {
    Write-Host "  Removing previous build at $out" -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $out
}
New-Item -ItemType Directory -Force -Path $out | Out-Null

# robocopy's exit codes are a bitmask where anything under 8 means success.
# Treating nonzero as failure - the reflex everywhere else - fails every build
# that actually copied a file.
function Invoke-Robocopy {
    param([string]$Source, [string]$Destination, [string[]]$ExtraArgs = @())
    $arguments = @($Source, $Destination, "/E", "/MT:16", "/NFL", "/NDL", "/NJH", "/NJS", "/NP") + $ExtraArgs
    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed ($LASTEXITCODE) copying $Source -> $Destination"
    }
}

# --- interpreter -----------------------------------------------------------
# Doc, tcl, include and libs are excluded: documentation, the Tk GUI toolkit,
# and the headers and import libraries used to COMPILE extensions. PIP ships
# extensions already built, and draws no Tk windows.
Write-Host "  [1/5] interpreter" -ForegroundColor DarkGray
Invoke-Robocopy $baseHome (Join-Path $out "python") @("/XD", "Doc", "tcl", "include", "libs", "__pycache__")

Write-Host "  [2/5] dependencies (this is the slow one)" -ForegroundColor DarkGray
Invoke-Robocopy $sitePackages (Join-Path $out "python\Lib\site-packages") @("/XD", "__pycache__")

# --- application and source ------------------------------------------------
Write-Host "  [3/5] application" -ForegroundColor DarkGray
Invoke-Robocopy $flutterRelease (Join-Path $out "app")

Write-Host "  [4/5] backend" -ForegroundColor DarkGray
foreach ($dir in @("backend", "config", "shared", "scripts")) {
    # tests are excluded for the same reason Doc is: they are for developing
    # PIP, not running it, and pytest is not shipped to run them with.
    Invoke-Robocopy (Join-Path $root $dir) (Join-Path $out $dir) @("/XD", "__pycache__", "tests", ".pytest_cache")
}

Write-Host "  [5/5] finishing" -ForegroundColor DarkGray
New-Item -ItemType Directory -Force -Path (Join-Path $out "data") | Out-Null

$sizeMb = [math]::Round((Get-ChildItem $out -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB)

Write-Host ""
Write-Host "  Built $out  ($sizeMb MB)" -ForegroundColor Green
Write-Host ""
Write-Host "  Verify it, from that folder, with:" -ForegroundColor DarkGray
Write-Host "    .\python\python.exe -c `"import sqlcipher3, chromadb, torch; print('ok')`"" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Then compress it for distribution - scripts\build_installer.ps1" -ForegroundColor DarkGray
Write-Host "  turns this folder into PIP-Setup.exe." -ForegroundColor DarkGray
Write-Host ""

# Explicit, because without it $LASTEXITCODE is whatever the last NATIVE command
# left behind - and the last one here is robocopy, whose success codes are 1
# and 3 rather than 0. A caller checking $LASTEXITCODE after running this script
# would read a completed build as a failed one, which is exactly what
# build_installer.ps1 did.
exit 0
