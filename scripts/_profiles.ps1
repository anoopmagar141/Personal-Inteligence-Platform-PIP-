# Profile selection for the launcher.
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

function Select-PipProfile {
    <#
    .SYNOPSIS
    Returns the chosen profile's paths, or $null to mean "the original layout".

    Prompts only when there is something to choose between. With one profile
    registered - or none - this returns $null and the caller behaves exactly as
    it did before profiles existed.
    #>
    param([Parameter(Mandatory = $true)][string]$Root)

    $profiles = Get-PipProfiles -Root $Root
    if ($profiles.Count -le 1) { return $null }

    $registry = Join-Path $Root "data\profiles.json"
    $lastUsed = try { (Get-Content $registry -Raw -Encoding utf8 | ConvertFrom-Json).last_used } catch { "default" }

    Write-Host ""
    Write-Host "  Which profile?" -ForegroundColor Cyan
    Write-Host ""
    for ($i = 0; $i -lt $profiles.Count; $i++) {
        $p = $profiles[$i]
        $paths = Resolve-PipProfilePaths -Root $Root -Profile $p
        $marker = if ($p.slug -eq $lastUsed) { "*" } else { " " }
        $state = if (Test-Path $paths.Db) { "" } else { "   (no database yet - will onboard)" }
        Write-Host ("   {0} [{1}] {2}{3}" -f $marker, ($i + 1), $p.name, $state)
    }
    Write-Host ""
    Write-Host "  * = last opened. Press Enter to take it." -ForegroundColor DarkGray

    $answer = (Read-Host "  Number").Trim()

    if ([string]::IsNullOrWhiteSpace($answer)) {
        $chosen = $profiles | Where-Object { $_.slug -eq $lastUsed } | Select-Object -First 1
        if (-not $chosen) { $chosen = $profiles[0] }
    }
    else {
        $index = 0
        if (-not [int]::TryParse($answer, [ref]$index) -or $index -lt 1 -or $index -gt $profiles.Count) {
            # Not a silent fallback to profile 1: opening the wrong person's
            # profile because a keystroke was mistyped is exactly the confusion
            # this menu exists to prevent.
            Write-Host "  Not one of the listed numbers. Nothing was opened." -ForegroundColor Red
            exit 1
        }
        $chosen = $profiles[$index - 1]
    }

    $paths = Resolve-PipProfilePaths -Root $Root -Profile $chosen
    Write-Host ""
    Write-Host ("  Opening {0}" -f $paths.Name) -ForegroundColor Green
    return $paths
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
