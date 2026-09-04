# Which Python runs PIP - resolved, not assumed.
#
# WHY THIS EXISTS
# ---------------
# Every script here needs the interpreter that has PIP's dependencies, and
# each one used to spell that out as ".venv\Scripts\python.exe". That is true
# on a development machine and false on an installed one: a portable install
# ships a standalone interpreter in python\, because a venv cannot be copied
# between machines - pyvenv.cfg records an absolute `home` pointing at the
# base install it was created from, and Scripts\python.exe is a shim back to
# that same path. Neither exists on somebody else's computer.
#
# So the two layouts differ in exactly one fact, and hardcoding it in five
# scripts meant five places to get it wrong. This is the one place that knows.
#
# WHY PORTABLE WINS WHEN BOTH ARE PRESENT
# ---------------------------------------
# A development checkout has .venv and no python\, and an install has python\
# and no .venv, so the ordering is usually moot. It stops being moot while
# testing a build from inside the source tree, and there the portable copy is
# the thing under test - checking it first means what runs is what shipped,
# rather than the dev environment silently standing in for it and hiding a
# packaging bug until a user finds it.

function Get-PipPython {
    param([Parameter(Mandatory)][string]$Root)

    $candidates = @(
        (Join-Path $Root "python\python.exe"),          # portable install
        (Join-Path $Root ".venv\Scripts\python.exe")    # development checkout
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }

    return $null
}

# Reports the failure the same way every caller would have to, so the advice
# stays identical everywhere rather than drifting per script. Deliberately
# says what to do for BOTH layouts: a missing interpreter looks the same from
# here whether somebody has an incomplete checkout or an extraction that did
# not finish, and guessing which would send half of them down the wrong path.
function Show-PipPythonMissing {
    param([Parameter(Mandatory)][string]$Root)

    Write-Host ""
    Write-Host "  ERROR: no Python interpreter for PIP was found." -ForegroundColor Red
    Write-Host "         Looked for:" -ForegroundColor DarkGray
    Write-Host "           $Root\python\python.exe        (installed copy)" -ForegroundColor DarkGray
    Write-Host "           $Root\.venv\Scripts\python.exe (source checkout)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  If this is an installed copy of PIP, the extraction is incomplete -"
    Write-Host "  unpack the download again into an empty folder."
    Write-Host ""
    Write-Host "  If this is a source checkout, create the environment with:"
    Write-Host "      python -m venv .venv" -ForegroundColor DarkGray
    Write-Host "      .venv\Scripts\python.exe -m pip install -r requirements.txt" -ForegroundColor DarkGray
    Write-Host ""
}
