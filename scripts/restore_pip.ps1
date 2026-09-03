# Console wrapper around scripts/restore_backup.py, for a Desktop shortcut.
#
# WHY THIS IS A SHORTCUT AND NOT A BUTTON IN THE APP
# --------------------------------------------------
# A restore replaces the database file the running backend has open, and
# restore_backup.py refuses outright while PIP holds the lock. So there is no
# arrangement in which a button inside the running app can do this - the app
# being open is the thing that stops it.
#
# That is not a limitation to work around, it is the shape of the operation.
# The moment a restore actually happens is a machine where PIP is not running:
# a fresh install with no data yet, or one whose database is gone. Neither has
# an app window to put a button in.
#
# WHAT IT DOES NOT DO
# -------------------
# Pick the backup for you when you name one explicitly. With no arguments,
# restore_backup.py takes the newest .pipbak in data/ - which is right on the
# machine that wrote them and wrong on a fresh one, where the file you carried
# over is probably somewhere else. So this prompts for a path when data/ has
# nothing in it, rather than failing with "no .pipbak files in data".

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$dataDir = Join-Path $root "data"

Write-Host ""
Write-Host "  PIP - Restore from backup" -ForegroundColor Cyan
Write-Host "  ========================="
Write-Host ""

if (-not (Test-Path $venvPython)) {
    Write-Host "  ERROR: no virtual environment at $venvPython" -ForegroundColor Red
    Write-Host "         Create it with:  python -m venv .venv"
    Write-Host "         then:            .venv\Scripts\python.exe -m pip install -r requirements.txt"
    Write-Host ""
    Read-Host "  Press Enter to close"
    exit 1
}

Write-Host "  Close PIP first if it is open - this replaces the database it has open,"
Write-Host "  and the restore will refuse to run while it is."
Write-Host ""
Write-Host "  You will be asked for:"
Write-Host ""
Write-Host "    1. The BACKUP password - the one you chose when the .pipbak was written."
Write-Host "    2. A NEW live password - what you will type to open PIP on THIS machine."
Write-Host ""
Write-Host "  The old live password is not recovered, because there is nothing to"
Write-Host "  recover it from. A .pipbak carries the data, never the live secret."
Write-Host ""

$scriptArgs = @($args)

# On a fresh machine data/ is empty, and restore_backup.py's default - the
# newest .pipbak in data/ - names a file that is not there. Ask instead of
# failing on a default that only makes sense on the machine that wrote them.
$haveBackupArg = $scriptArgs -contains "--from"
if (-not $haveBackupArg) {
    $local = @()
    if (Test-Path $dataDir) { $local = @(Get-ChildItem -Path $dataDir -Filter *.pipbak -ErrorAction SilentlyContinue) }

    if ($local.Count -eq 0) {
        Write-Host "  No .pipbak files in $dataDir - name the one you carried over."
        Write-Host ""
        $picked = Read-Host "  Path to your .pipbak file"
        $picked = $picked.Trim().Trim('"')
        if ([string]::IsNullOrWhiteSpace($picked)) {
            Write-Host ""
            Write-Host "  Nothing entered. Nothing was changed." -ForegroundColor Yellow
            Read-Host "  Press Enter to close"
            exit 1
        }
        if (-not (Test-Path $picked)) {
            Write-Host ""
            Write-Host "  ERROR: no file at $picked" -ForegroundColor Red
            Write-Host "         Nothing was changed."
            Read-Host "  Press Enter to close"
            exit 1
        }
        $scriptArgs = @("--from", $picked) + $scriptArgs
    }
    else {
        Write-Host "  Found $($local.Count) backup(s) in data\ - the newest will be used:"
        foreach ($file in $local | Sort-Object LastWriteTime -Descending) {
            Write-Host ("    {0}  {1:N0} bytes  {2}" -f $file.Name, $file.Length, $file.LastWriteTime)
        }
        Write-Host ""
        Write-Host "  Pass --from <path> to this shortcut if you want a different one."
        Write-Host ""
    }
}

Push-Location $root
try {
    & $venvPython (Join-Path $root "scripts\restore_backup.py") @scriptArgs
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-Host ""
if ($code -eq 0) {
    Write-Host "  Restored. Launch PIP and enter the NEW password." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Your documents were written back into data\documents\ and re-indexed."
    Write-Host "  Nothing needs re-uploading. Install Ollama and pull the model if this"
    Write-Host "  machine does not have it - that is the one thing a backup cannot carry."
} else {
    Write-Host "  The restore did not complete. Nothing was replaced." -ForegroundColor Yellow
}
Write-Host ""
Read-Host "  Press Enter to close"
exit $code
