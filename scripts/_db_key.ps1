# Shared by run_dev.ps1 and launch_pip.ps1: works out the database key and puts
# it in $env:PIP_DB_KEY for the backend process.
#
# Three states, deliberately distinguished rather than collapsed:
#
#   salt.bin exists      -> a password has been set. Prompt for it, derive, verify.
#   db_key.txt exists    -> the random-key era. Use it, and say clearly that the
#                           key is sitting on disk next to the database it
#                           decrypts, which is the thing a password fixes.
#   neither              -> nothing encrypted yet. Say so; the caller decides.
#
# Derivation is delegated to Python (scripts/derive_db_key.py), never
# reimplemented here. PBKDF2 only reproduces if hash, iteration count, output
# length and salt handling all match exactly, and a PowerShell version differing
# in any one would produce a different key silently - presenting as "wrong
# password" against a database the user had typed the right password for.
#
# Residual weakness, stated rather than hidden: the key reaches the backend
# through an environment variable, and a process environment is readable by
# other processes running as the same user. Part 10.1's "held in process memory
# only" is not fully achieved by this. What it does achieve is the part that
# matters for the threats in Part 10.4 - nothing on disk decrypts the database,
# so a stolen disk, a disk image, or a backup of data/ is useless without the
# password.

function Get-PipPasswordPlaintext {
    param([string]$Prompt)
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        # Zero the unmanaged copy rather than waiting for GC.
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Set-PipDbKey {
    param([Parameter(Mandatory = $true)][string]$Root)

    $dataDir = Join-Path $Root "data"

    # PIP_SALT_PATH wins when the launcher has selected a profile. Every entry
    # point in this project already honours that variable - it was added for
    # test isolation and does the identical job here, pointing the derivation
    # at one profile's salt instead of the installation's. Unset, this is the
    # path it always was.
    $saltPath = if ($env:PIP_SALT_PATH) { $env:PIP_SALT_PATH } else { Join-Path $dataDir "salt.bin" }

    # The legacy random-key file is deliberately NOT per-profile. It only
    # exists on installations that never migrated to a password, and a profile
    # created after profiles existed is always on the password model - so a
    # per-profile db_key.txt would be a path that can never be occupied.
    $legacyPath = Join-Path $dataDir "db_key.txt"
    . (Join-Path $PSScriptRoot "_python.ps1")
    $pipPython = Get-PipPython -Root $Root
    if (-not $pipPython) { Show-PipPythonMissing -Root $Root; return $false }
    $deriveScript = Join-Path $Root "scripts\derive_db_key.py"

    if (Test-Path $saltPath) {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            $password = Get-PipPasswordPlaintext "PIP database password"
            $key = $password | & $pipPython $deriveScript
            $code = $LASTEXITCODE
            $password = $null

            if ($code -eq 0) {
                $env:PIP_DB_KEY = $key.Trim()
                return $true
            }
            if ($code -eq 3) {
                $remaining = 3 - $attempt
                if ($remaining -gt 0) {
                    Write-Host "  Wrong password - $remaining attempt(s) left." -ForegroundColor Yellow
                } else {
                    Write-Host "  Wrong password." -ForegroundColor Red
                }
                continue
            }
            Write-Host "  Could not derive the key (exit $code)." -ForegroundColor Red
            return $false
        }
        Write-Host ""
        Write-Host "Too many failed attempts. The database was not opened." -ForegroundColor Red
        Write-Host "If you have genuinely forgotten it, there is no recovery - that is by" -ForegroundColor Red
        Write-Host "design (Part 10.1). Check with:" -ForegroundColor Red
        Write-Host "    .venv\Scripts\python.exe scripts\set_db_password.py --check" -ForegroundColor DarkGray
        return $false
    }

    if (Test-Path $legacyPath) {
        $env:PIP_DB_KEY = (Get-Content $legacyPath -Raw).Trim()
        Write-Host "Note: the database key is stored in data\db_key.txt, beside the database" -ForegroundColor Yellow
        Write-Host "      it decrypts - so anything that copies data\ gets both. Set a password:" -ForegroundColor Yellow
        Write-Host "      .venv\Scripts\python.exe scripts\set_db_password.py" -ForegroundColor DarkGray
        return $true
    }

    # No salt, no legacy key: nothing has been encrypted yet. Left to the caller
    # rather than silently generating a random key here - quietly recreating the
    # weaker model is exactly what a password is meant to replace.
    return $true
}
