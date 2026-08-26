# Shared by run_dev.ps1 and launch_pip.ps1: works out the database key and puts
# it in $env:PIP_DB_KEY for the backend process.
#
# Three states, deliberately distinguished rather than collapsed:
#
#   salt.bin exists      -> a password has been set. Prompt for it, derive, verify.
#   db_key.txt exists    -> the random-key era. Use it, and say clearly that the
#                           key is sitting on disk next to the database it
#                           decrypts, which is the thing a password fixes.
#   neither, no pip.db   -> first run. Offer to set a password now, so the
#                           database is created encrypted rather than created
#                           plaintext and re-keyed later.
#   neither, pip.db here -> an existing PLAINTEXT database. Do not touch it;
#                           say plainly that it is unencrypted and point at
#                           set_db_password.py, which rekeys it safely.
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
    $saltPath = Join-Path $dataDir "salt.bin"
    $legacyPath = Join-Path $dataDir "db_key.txt"
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    $deriveScript = Join-Path $Root "scripts\derive_db_key.py"

    if (Test-Path $saltPath) {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            $password = Get-PipPasswordPlaintext "PIP database password"
            $key = $password | & $venvPython $deriveScript
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

    # No salt, no legacy key: nothing has been encrypted yet.
    #
    # This branch used to `return $true` on the reasoning that the decision was
    # "left to the caller." Neither caller decided anything - run_dev.ps1 and
    # launch_pip.ps1 both just check the boolean and carry on - so PIP_DB_KEY
    # stayed unset, get_connection() took its unencrypted sqlite3 fallback,
    # vector_store._get_db_key() returned $null into plaintext passthrough, and
    # a fresh install ran entirely in the clear without ever saying so. That is
    # the same bug 8414e44 fixed, surviving in the one path that hadn't run yet
    # - and a first run is exactly when a demo machine or a fresh clone starts.
    #
    # The decision is made here now, out loud, in the only place that can ask.
    $dbPath = Join-Path $dataDir "pip.db"

    if (Test-Path $dbPath) {
        # A database but no salt and no key file means it was created
        # unencrypted. Deliberately NOT offering to create a salt: a key
        # derived here would be handed to SQLCipher against a plaintext file
        # and die on "file is not a database" some seconds later, in a hidden
        # window. set_db_password.py rekeys it properly, with verification and
        # row counts, and rebuilds the vector index to match.
        Write-Host ""
        Write-Host "WARNING: this database is NOT encrypted." -ForegroundColor Red
        Write-Host "         Anything that copies data\ reads your profile, decision log" -ForegroundColor Red
        Write-Host "         and conversation history in plain text. Encrypt it with:" -ForegroundColor Red
        Write-Host "         .venv\Scripts\python.exe scripts\set_db_password.py" -ForegroundColor DarkGray
        Write-Host ""
        return $true
    }

    Write-Host ""
    Write-Host "No database password is set yet." -ForegroundColor Cyan
    Write-Host "PIP stores your profile, decisions and full conversation history. With a" -ForegroundColor Cyan
    Write-Host "password, all of it is encrypted at rest and the key is never written to" -ForegroundColor Cyan
    Write-Host "disk - only a salt is, and a salt is not secret. Without one, everything" -ForegroundColor Cyan
    Write-Host "in data\ is readable by anything that can read the folder." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "THERE IS NO PASSWORD RECOVERY. Forgetting it means permanent profile" -ForegroundColor Yellow
    Write-Host "loss - that is the design (Part 10.1). Write it down somewhere that is" -ForegroundColor Yellow
    Write-Host "not this machine." -ForegroundColor Yellow
    Write-Host ""

    $answer = Read-Host "Set a database password now? [Y/n]"
    if ($answer -match '^\s*(n|no)\s*$') {
        Write-Host ""
        Write-Host "Continuing WITHOUT encryption - data\ will be stored in plain text." -ForegroundColor Red
        Write-Host "Set one later with: .venv\Scripts\python.exe scripts\set_db_password.py" -ForegroundColor DarkGray
        Write-Host ""
        return $true
    }

    # Same three-attempt shape as the unlock path above. Typed twice because
    # there is no recovery from a typo in a value nothing else on the machine
    # will ever be able to check it against.
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $first = Get-PipPasswordPlaintext "New database password (8+ characters)"
        $second = Get-PipPasswordPlaintext "Type it again"

        if ($first -cne $second) {
            $first = $null
            $second = $null
            Write-Host "  They don't match." -ForegroundColor Yellow
            continue
        }
        $second = $null

        $key = $first | & $venvPython $deriveScript --init
        $code = $LASTEXITCODE
        $first = $null

        if ($code -eq 0) {
            $env:PIP_DB_KEY = $key.Trim()
            Write-Host "  Password set. The database will be created encrypted." -ForegroundColor Green
            return $true
        }
        if ($code -eq 2) {
            Write-Host "  Too short - at least 8 characters." -ForegroundColor Yellow
            continue
        }
        # 4 (salt appeared) and 5 (database appeared) both mean the state
        # changed under us, and neither is retryable by typing again.
        Write-Host "  Could not set the password (exit $code)." -ForegroundColor Red
        return $false
    }

    Write-Host ""
    Write-Host "Password not set after 3 attempts. Not starting - rerun and try again," -ForegroundColor Red
    Write-Host "or answer 'n' at the prompt to run unencrypted." -ForegroundColor Red
    return $false
}
