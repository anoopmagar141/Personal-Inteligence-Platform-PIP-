# Creates the Desktop shortcuts for PIP.
#
# Run once, per machine:
#     powershell -ExecutionPolicy Bypass -File scripts\install_shortcuts.ps1
#
# The PIP shortcut existed already on the development machine, made by hand and
# recorded nowhere - which is fine until it is a second machine, and then the
# documented "double-click the PIP shortcut on the Desktop" refers to something
# that was never created. This makes both reproducible.
#
# "Restore PIP from backup" is the one that earns its place. A restore happens
# on a machine where PIP is not running - a fresh install, or one whose database
# is gone - so there is no app window to reach it from, and asking somebody in
# that situation to remember a python invocation is asking at the worst moment.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

function New-PipShortcut {
    param(
        [string]$Name,
        [string]$Target,
        [string]$Arguments,
        [string]$Description,
        [string]$IconIndex = "0"
    )

    $path = Join-Path $desktop "$Name.lnk"
    $shortcut = $shell.CreateShortcut($path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $Description
    $shortcut.Save()
    Write-Host "  created  $path" -ForegroundColor Green
}

$powershell = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

Write-Host ""
Write-Host "  Installing PIP shortcuts to $desktop" -ForegroundColor Cyan
Write-Host ""

# -WindowStyle Hidden: the launcher's whole job is starting things without
# console windows, and a shortcut that flashes one up undoes that.
New-PipShortcut -Name "PIP" `
    -Target $powershell `
    -Arguments "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$root\scripts\launch_pip.ps1`"" `
    -Description "Start PIP"

# Deliberately NOT hidden. This one is a conversation - it asks for two
# passwords and prints what it is about to replace.
New-PipShortcut -Name "Restore PIP from backup" `
    -Target $powershell `
    -Arguments "-ExecutionPolicy Bypass -NoProfile -File `"$root\scripts\restore_pip.ps1`"" `
    -Description "Rebuild PIP's database from a .pipbak backup file"

Write-Host ""
Write-Host "  Done. Export is available from the Backup screen inside PIP;"
Write-Host "  restore is here because it cannot run while PIP is open."
Write-Host ""
