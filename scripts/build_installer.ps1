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
    # Package whatever is already staged instead of rebuilding it. For
    # iterating on the installer itself, where a three-minute copy between
    # attempts is the slowest part of the loop.
    [switch]$SkipBuild,
    # Produce the zip even when Inno Setup is available - for checking that
    # path still works.
    [switch]$ZipOnly,
    # Where to build the payload. Short on purpose, and NOT inside the project:
    # Windows limits a path to 260 characters for most callers, the Inno
    # compiler included, and torch ships license files nested deep enough that
    # this project's own directory name is the difference between building and
    # failing with "the system cannot find the path specified".
    #
    # Defaults to the root of whichever drive the project is on, so the payload
    # stays on the same disk - copying a gigabyte across drives is minutes, and
    # across a network drive is worse.
    [string]$Payload
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$iss = Join-Path $root "installer\PIP.iss"

if (-not $Payload) {
    $drive = (Split-Path -Qualifier $root)     # "D:" for D:\...
    $Payload = Join-Path "$drive\" "pip-build\PIP"
}
$payload = $Payload

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
    # build_portable.ps1 runs under ErrorActionPreference = "Stop", so a real
    # failure throws rather than returning a code. What is checked afterwards is
    # that the payload is actually there.
    #
    # NOT $LASTEXITCODE. That is the exit code of the last NATIVE command the
    # script ran, which is robocopy - whose success codes are 1 and 3, not 0.
    # Reading it here declared every successful build a failure.
    & (Join-Path $PSScriptRoot "build_portable.ps1") $payload
    if (-not (Test-Path (Join-Path $payload "python\python.exe"))) {
        Write-Host "  ERROR: the portable build did not produce a payload." -ForegroundColor Red
        exit 1
    }
}

# --- refuse to compile an incomplete payload -------------------------------
#
# WHY THIS EXISTS
#
# A 76 MB PIP-Setup.exe was found in dist\, built from a payload that had not
# finished assembling: the installer's timestamp was 22 minutes earlier than
# the payload's last step, and its version resource was empty, so it was not
# even a build of this .iss. Nothing caught it. -SkipBuild only warned how old
# the payload was, and ISCC will happily compile whatever subset of the tree it
# can see - a partial payload is not an error to it, it is a smaller install.
#
# Size alone does not settle it either: a payload can be the right size and
# hold the wrong application binary, which is the failure this project has
# actually had. So the check is per-file, and the one that matters most is
# app\data\app.so - the Dart code. pip_flutter_client.exe is a runner shell
# that does not change between builds of the same Flutter version, so an
# unchanged .exe proves nothing at all about which code is inside.

function Assert-PayloadComplete {
    param([string]$Path, [string]$FlutterRelease)

    $required = @(
        "python\python.exe",
        "app\pip_flutter_client.exe",
        "app\data\app.so",
        "app\flutter_windows.dll",
        # The VC++ runtime the application links against. Absent from a clean
        # Windows install and absent from the payload until it was noticed, so
        # it is checked here rather than trusted to keep being copied.
        "app\MSVCP140.dll",
        "app\VCRUNTIME140.dll",
        "app\VCRUNTIME140_1.dll",
        "backend\api\server.py",
        "backend\core\profiles.py",
        "config\provider_consent.json",
        "scripts\launch_pip.ps1",
        "shared\ws_spec.py"
    )
    $missing = @($required | Where-Object { -not (Test-Path (Join-Path $Path $_)) })
    if ($missing.Count -gt 0) {
        Write-Host "  ERROR: the payload is incomplete - refusing to compile." -ForegroundColor Red
        foreach ($m in $missing) { Write-Host "         missing $m" -ForegroundColor DarkGray }
        Write-Host "         Rebuild it: scripts\build_portable.ps1 `"$Path`"" -ForegroundColor DarkGray
        exit 1
    }

    # data\ ships empty. A payload carrying a database is one built over
    # somebody's real installation, and it would hand every user the
    # developer's memory and a salt their password will not match.
    if (Test-Path (Join-Path $Path "data")) {
        $stray = @(Get-ChildItem (Join-Path $Path "data") -Recurse -Force -ErrorAction SilentlyContinue)
        if ($stray.Count -gt 0) {
            Write-Host "  ERROR: payload data\ is not empty ($($stray.Count) item(s)) - refusing." -ForegroundColor Red
            foreach ($f in $stray | Select-Object -First 8) { Write-Host "         $($f.Name)" -ForegroundColor DarkGray }
            exit 1
        }
    }

    # The staleness check the whole release gate turns on. Only possible when
    # the build tree is present - an installer built on a machine without the
    # Flutter output is packaging a payload it cannot compare against, and says
    # so rather than pretending it verified something.
    $built = Join-Path $FlutterRelease "data\app.so"
    if (Test-Path $built) {
        $a = (Get-FileHash $built -Algorithm SHA256).Hash
        $b = (Get-FileHash (Join-Path $Path "app\data\app.so") -Algorithm SHA256).Hash
        if ($a -ne $b) {
            Write-Host "  ERROR: the payload's Flutter build is NOT the one in the build tree." -ForegroundColor Red
            Write-Host "         build tree : $a" -ForegroundColor DarkGray
            Write-Host "         payload    : $b" -ForegroundColor DarkGray
            Write-Host "         Rebuild the payload after `"flutter build windows`"." -ForegroundColor DarkGray
            exit 1
        }
        Write-Host "  app.so      : matches the current Flutter build" -ForegroundColor DarkGray
    } else {
        Write-Host "  app.so      : no Flutter build tree here - staleness NOT verified" -ForegroundColor Yellow
    }
}

Assert-PayloadComplete -Path $payload -FlutterRelease (Join-Path $root "frontend\flutter\build\windows\x64\runner\Release")

$sizeMb = [math]::Round((Get-ChildItem $payload -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB)
Write-Host "  payload     : $payload  ($sizeMb MB)" -ForegroundColor DarkGray

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

    # The payload is not where the .iss defaults to, so it is passed in.
    & $iscc /Q "/DDistDir=$payload" $iss
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: ISCC failed ($LASTEXITCODE)." -ForegroundColor Red
        exit 1
    }

    $output = Join-Path $dist "PIP-Setup.exe"
    $outMb = [math]::Round((Get-Item $output).Length / 1MB)

    # "ISCC completed successfully" is not the same claim as "the installer
    # holds the payload". The 76 MB artefact that prompted this check was 6.8%
    # of its payload; a real LZMA2 build of this tree lands near 17%. The floor
    # is deliberately well below that - it is an anomaly detector, not a
    # compression model - and it fails the build rather than printing a warning
    # nobody reads at the end of a five-minute compile.
    $ratio = $outMb / $sizeMb
    Write-Host ""
    Write-Host ("  compressed  : {0} MB from {1} MB ({2:P1} of payload)" -f $outMb, $sizeMb, $ratio) -ForegroundColor DarkGray
    if ($ratio -lt 0.10) {
        Write-Host ""
        Write-Host "  ERROR: the installer is far smaller than this payload can compress to." -ForegroundColor Red
        Write-Host "         That is what a compile against a half-written payload looks like." -ForegroundColor DarkGray
        Write-Host "         Treat $output as untrusted and rebuild." -ForegroundColor DarkGray
        exit 1
    }

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
