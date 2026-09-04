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
# data/pip.db. On a single-profile installation those are the same file and
# this changes nothing; on a multi-profile one, backing up the wrong person
# would be a quiet and expensive mistake to discover later.
. (Join-Path $PSScriptRoot "_profiles.ps1")
$profiles = Get-PipProfiles -Root $root
$scriptArgs = @($args)
if ($profiles.Count -gt 1 -and -not ($scriptArgs -contains "--db-path")) {
    $registry = Join-Path $root "data\profiles.json"
    $lastUsed = try { (Get-Content $registry -Raw -Encoding utf8 | ConvertFrom-Json).last_used } catch { "default" }
    $chosen = $profiles | Where-Object { $_.slug -eq $lastUsed } | Select-Object -First 1
    if ($chosen) {
        $paths = Resolve-PipProfilePaths -Root $root -Profile $chosen
        $env:PIP_SALT_PATH = $paths.Salt
        $scriptArgs = @("--db-path", $paths.Db) + $scriptArgs
        Write-Host ("  Profile: {0}" -f $paths.Name) -ForegroundColor Cyan
        Write-Host ""
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
