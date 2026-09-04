# Builds something you can hand somebody.
#
#     powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
#
# Produces dist\PIP-Setup.exe when Inno Setup is installed, and dist\PIP.zip
# when it is not. Both install the same thing; they differ in how much the
# person on the other end has to do with it.
#
# WHY THERE IS A FALLBACK AT ALL
#
# Inno Setup is the right tool and this script prefers it: a real installer
# gives a Start menu entry, an uninstaller, and an upgrade path that replaces
# an install rather than sitting beside it. But it is a separate program that
# has to be installed on the build machine, and a build script that simply
# fails when it is missing makes the whole packaging story conditional on
# somebody's tooling.
#
# A zip is not as good and is not pretending to be: it is the portable folder,
# compressed, with no shortcuts and nothing to uninstall. It is what you send
# when you need to send something today.
#
# WHY IT REFUSES TO PACKAGE A STALE BUILD
#
# dist\PIP is a copy, and a copy is exactly as old as the last time it was
# made. Shipping one built before the last few commits is the kind of mistake
# that is invisible until somebody reports a bug that was fixed a week ago, so
# unless -SkipBuild is given this rebuilds first rather than trusting what is
# there.

param(
    # Package whatever is already in dist\PIP instead of rebuilding it. For
    # iterating on the installer itself, where a three-minute copy between
    # attempts is the slowest part of the loop.
    [switch]$SkipBuild,
    # Produce the zip even when Inno Setup is available - for checking that
    # path still works.
    [switch]$ZipOnly
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$payload = Join-Path $dist "PIP"
$iss = Join-Path $root "installer\PIP.iss"

Write-Host ""
Write-Host "  PIP - installer build" -ForegroundColor Cyan
Write-Host "  ====================="
Write-Host ""

# --- the payload -----------------------------------------------------------

if ($SkipBuild) {
    if (-not (Test-Path $payload)) {
        Write-Host "  ERROR: -SkipBuild was given but there is nothing at $payload" -ForegroundColor Red
        exit 1
    }
    $age = (Get-Date) - (Get-Item $payload).LastWriteTime
    Write-Host "  Packaging the existing build, last written $([math]::Round($age.TotalMinutes)) minute(s) ago." -ForegroundColor Yellow
} else {
    & (Join-Path $PSScriptRoot "build_portable.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: the portable build failed; nothing to package." -ForegroundColor Red
        exit 1
    }
}

$sizeMb = [math]::Round((Get-ChildItem $payload -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB)

# --- find Inno Setup -------------------------------------------------------
# The compiler is not on PATH after any of its installers, so this looks in the
# three places it actually lands.
#
# LocalAppData is FIRST because it is where winget puts it, and winget is what
# this script tells people to use. That was found the hard way: `winget install
# JRSoftware.InnoSetup` reported success, `winget list` agreed it was there,
# and a version of this function that only knew about Program Files concluded
# Inno Setup was not installed and quietly produced a zip instead.

function Find-InnoSetup {
    $onPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    $bases = @(
        (Join-Path $env:LOCALAPPDATA "Programs"),
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles
    )
    foreach ($base in $bases) {
        if (-not $base) { continue }
        foreach ($version in @("Inno Setup 6", "Inno Setup 5")) {
            $candidate = Join-Path $base "$version\ISCC.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    }
    return $null
}

$iscc = if ($ZipOnly) { $null } else { Find-InnoSetup }

# --- build -----------------------------------------------------------------

if ($iscc) {
    Write-Host ""
    Write-Host "  Compiling with $iscc" -ForegroundColor DarkGray
    Write-Host "  ($sizeMb MB in, LZMA2 - this takes a few minutes)" -ForegroundColor DarkGray
    Write-Host ""

    & $iscc /Q $iss
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: ISCC failed ($LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }

    $output = Join-Path $dist "PIP-Setup.exe"
    $outMb = [math]::Round((Get-Item $output).Length / 1MB)
    Write-Host ""
    Write-Host "  Built $output  ($outMb MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Installs per-user to %LocalAppData%\Programs\PIP - no admin rights," -ForegroundColor DarkGray
    Write-Host "  because PIP writes its database inside its own folder." -ForegroundColor DarkGray
} else {
    if (-not $ZipOnly) {
        Write-Host ""
        Write-Host "  Inno Setup was not found, so this is the zip." -ForegroundColor Yellow
        Write-Host "  For a real installer - Start menu entry, uninstaller, upgrades:" -ForegroundColor DarkGray
        Write-Host "      winget install JRSoftware.InnoSetup" -ForegroundColor DarkGray
        Write-Host "  then run this script again." -ForegroundColor DarkGray
    }

    $zip = Join-Path $dist "PIP.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }

    Write-Host ""
    Write-Host "  Compressing $sizeMb MB - this takes a few minutes" -ForegroundColor DarkGray
    # ZipFile rather than Compress-Archive. Compress-Archive builds the whole
    # entry list in memory before writing and is measured in tens of minutes on
    # a tree this shape - the interpreter alone is tens of thousands of small
    # files. This is the same class in the same runtime, without that.
    #
    # Optimal rather than Fastest: it is compressed once here and downloaded by
    # everybody, so the minutes are spent where they cost least.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $payload, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)

    $outMb = [math]::Round((Get-Item $zip).Length / 1MB)
    Write-Host ""
    Write-Host "  Built $zip  ($outMb MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "  To install from it: extract anywhere, then run" -ForegroundColor DarkGray
    Write-Host "      powershell -ExecutionPolicy Bypass -File PIP\scripts\install_shortcuts.ps1" -ForegroundColor DarkGray
    Write-Host "  which creates the same Desktop shortcuts the installer would." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Unsigned, so Windows SmartScreen will warn on first run:" -ForegroundColor DarkGray
Write-Host "  More info -> Run anyway. A signing certificate is the only fix." -ForegroundColor DarkGray
Write-Host ""
