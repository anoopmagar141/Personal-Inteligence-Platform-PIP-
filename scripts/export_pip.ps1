# Console wrapper around scripts/export_backup.py.
#
# WHY A WRAPPER AND NOT JUST THE SCRIPT
# -------------------------------------
# This is what the app's Backup screen launches, and what a Desktop shortcut
# can point at. Both need three things the bare `python scripts/export_backup.py`
# invocation does not carry on its own: the venv interpreter rather than
# whatever `python` resolves to, the repo root as the working directory, and a
# window that stays open afterwards so the result is readable.
#
# The last one is not cosmetic. The export prints where the file was written
# and reminds you that a lost backup password is unrecoverable; a console that
# closes on exit would show both for about a frame.
#
# WHY THE APP LAUNCHES THIS INSTEAD OF DOING THE EXPORT ITSELF
# ------------------------------------------------------------
# ADR-027: the export must not be reachable from the API. The live connection
# already holds the real key, so an HTTP route producing a re-encrypted copy
# would hand that capability to anything able to read data/api_token.txt -
# which is any process running as this user - without it ever knowing the live
# key. Launching a console keeps the capability exactly where the ADR put it:
# a shell the user is sitting at, where export_backup.py's authenticate() can
# demand the live password and get an answer from a person.
#
# The app is a launcher here, not a participant. It never sees the password.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "_python.ps1")
$pipPython = Get-PipPython -Root $root

Write-Host ""
Write-Host "  PIP - Export backup" -ForegroundColor Cyan
Write-Host "  ==================="
Write-Host ""

if (-not $pipPython) {
    Show-PipPythonMissing -Root $root
    Read-Host "  Press Enter to close"
    exit 1
}

Write-Host "  You will be asked for two passwords:"
Write-Host ""
Write-Host "    1. Your LIVE password  - proves this is you, and unlocks the database."
Write-Host "    2. A BACKUP password   - encrypts the file itself. Use the same one"
Write-Host "                             every time; it does not need to be new."
Write-Host ""
Write-Host "  They must differ. That separation is the whole point: the backup has to"
Write-Host "  survive the loss or compromise of the live password, and sharing one"
Write-Host "  between them gives up exactly that."
Write-Host ""

# Export the profile that was last opened, not whatever happens to be at
# data/pip.db - backing up the wrong person would be a quiet and expensive
# mistake to discover later. Which profile that is, is Resolve-PipLastProfile's
# answer, the rule launch_pip.ps1 starts the backend by. This used to be a
# second copy of it that chose only when more than one profile was registered,
# on the reasoning that a single profile lives in data/ anyway. A new
# installation's sole profile lives in data/profiles/<slug>/, so the export
# read a data/pip.db that was not there (FREEZE_LIST section 7.16, D-03).
#
# The salt is chosen with the database, never left to the environment: this
# console inherits PIP_SALT_PATH from whatever launched the app, which names
# the profile open at that launch, and a database read under another profile's
# salt is refused for the right password.
. (Join-Path $PSScriptRoot "_profiles.ps1")
$scriptArgs = @($args)
if (-not ($scriptArgs -contains "--db-path")) {
    $paths = Resolve-PipLastProfile -Root $root
    if ($paths) {
        $env:PIP_SALT_PATH = $paths.Salt
        $scriptArgs = @("--db-path", $paths.Db) + $scriptArgs
        Write-Host ("  Profile: {0}" -f $paths.Name) -ForegroundColor Cyan
        Write-Host ""
    } else {
        # The original layout: data/pip.db, and export_backup.py's own default
        # salt beside it.
        Remove-Item Env:PIP_SALT_PATH -ErrorAction SilentlyContinue
    }
}

Push-Location $root
try {
    & $pipPython (Join-Path $root "scripts\export_backup.py") @scriptArgs
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}

Write-Host ""
if ($code -eq 0) {
    Write-Host "  Keep the file somewhere other than this machine." -ForegroundColor Green
    Write-Host "  It holds everything, including your uploaded documents - one file is"
    Write-Host "  all you need to carry."
} else {
    Write-Host "  The export did not complete. Nothing was written." -ForegroundColor Yellow
}
Write-Host ""
Read-Host "  Press Enter to close"
exit $code
