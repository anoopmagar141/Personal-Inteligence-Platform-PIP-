# Profile paths for the launcher.
#
# WHY THERE IS NO LONGER A PROMPT HERE
# ------------------------------------
# This file used to print "Which profile?" and read a number, because the
# launcher was the only thing running early enough to make the choice - the
# four path variables below had to be set before uvicorn started.
#
# That stopped being true when the password moved into the application. The
# backend now starts with no key and no opinion, and every consumer of these
# variables reads them at call time rather than capturing them at import, so
# the running process can be re-pointed. backend/core/profiles.py:activate()
# does exactly that, POST /auth/profile exposes it, and the switcher lives on
# the sign-in screen where a person choosing who to sign in as would look for
# it. A numbered menu in a blue PowerShell window was the last thing left in
# the launch that a person had to answer, and it was answering it before they
# had seen the product at all.
#
# What remains here is the non-interactive half: resolve the profile that was
# opened last and point the backend at it, so the common case - the same
# person opening PIP again - needs no interaction anywhere. Choosing anything
# else is the application's job now.
#
# WHY THIS IS SILENT WHEN THERE IS ONE PROFILE
# --------------------------------------------
# An installation that has never created a second profile has no profiles.json,
# and gets no prompt, no menu, and no behaviour change of any kind. That is not
# politeness - it is the property that makes this feature safe to add to a
# working installation. The single-profile path through this file is
# indistinguishable from the code that existed before it.
#
# WHY THE PATHS ARE PASSED AS ENVIRONMENT VARIABLES
# -------------------------------------------------
# PIP_DB_PATH, PIP_SALT_PATH, PIP_CHROMA_PATH and PIP_DOCUMENTS_ROOT are the
# overrides the backend already honours - each one added for test isolation, and
# each one now doing the same job for a real second user. Nothing new had to be
# invented for the backend to open a different profile; it could already be
# pointed at different files, and this points it.

function Get-PipProfiles {
    param([Parameter(Mandatory = $true)][string]$Root)

    $registry = Join-Path $Root "data\profiles.json"
    if (-not (Test-Path $registry)) { return @() }

    try {
        $raw = Get-Content $registry -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
        # A malformed registry must not stop a launch. The database it indexes
        # is perfectly readable; refusing to start over a convenience file would
        # be the wrong failure, and the default profile is reachable regardless.
        Write-Host "  (profiles.json could not be read - using the default profile)" -ForegroundColor DarkGray
        return @()
    }

    return @($raw.profiles)
}

function Resolve-PipProfilePaths {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)]$Profile
    )

    $dataDir = Join-Path $Root "data"
    $profileDir = if ($Profile.data_dir -eq ".") { $dataDir } else { Join-Path $dataDir $Profile.data_dir }

    return @{
        Slug      = $Profile.slug
        Name      = $Profile.name
        Dir       = $profileDir
        Db        = Join-Path $profileDir "pip.db"
        Salt      = Join-Path $profileDir "salt.bin"
        Chroma    = Join-Path $profileDir "chroma"
        Documents = Join-Path $profileDir "documents"
    }
}

function Resolve-PipLastProfile {
    <#
    .SYNOPSIS
    Returns the last-opened profile's paths, or $null to mean "the original
    layout".

    Silent by design, and never wrong in a way that costs anything: the
    application's sign-in screen lists every profile and can switch to any of
    them before a password is typed, so the worst case here is that somebody
    clicks one name on a screen they were already looking at.

    $null with one profile - or none - so the caller behaves exactly as it did
    before profiles existed, and so that data/pip.db is reached by the same code
    path it always was rather than by an override that happens to name it.
    #>
    param([Parameter(Mandatory = $true)][string]$Root)

    $profiles = Get-PipProfiles -Root $Root
    if ($profiles.Count -le 1) { return $null }

    $registry = Join-Path $Root "data\profiles.json"
    $lastUsed = try { (Get-Content $registry -Raw -Encoding utf8 | ConvertFrom-Json).last_used } catch { "default" }

    $chosen = $profiles | Where-Object { $_.slug -eq $lastUsed } | Select-Object -First 1
    if (-not $chosen) { $chosen = $profiles[0] }

    return Resolve-PipProfilePaths -Root $Root -Profile $chosen
}

function Set-PipProfileEnvironment {
    <#
    .SYNOPSIS
    Point the backend at one profile's four files.

    api_token.txt, pip.lock, startup.jsonl and ui_theme.txt are deliberately NOT
    redirected: they belong to the running application rather than to a person,
    and the shared lock is what makes "one profile at a time" true by the same
    mechanism that already made "one PIP at a time" true.
    #>
    param([Parameter(Mandatory = $true)]$Paths)

    $env:PIP_DB_PATH = $Paths.Db
    $env:PIP_SALT_PATH = $Paths.Salt
    $env:PIP_CHROMA_PATH = $Paths.Chroma
    $env:PIP_DOCUMENTS_ROOT = $Paths.Documents
    $env:PIP_PROFILE = $Paths.Slug

    New-Item -ItemType Directory -Force -Path $Paths.Dir | Out-Null
    New-Item -ItemType Directory -Force -Path $Paths.Documents | Out-Null
}
