# Turns every svg\*.svg into png\*.png at 2x size with headless Microsoft Edge.
# Usage: powershell -File notes\report\diagrams\render.ps1 [name-filter]
param([string]$Filter = "*")

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$svgDir = Join-Path $here "svg"
$pngDir = Join-Path $here "png"
New-Item -ItemType Directory -Force $pngDir | Out-Null
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$profileDir = Join-Path $env:TEMP "pip-diagram-edge"

Get-ChildItem $svgDir -Filter "$Filter.svg" | ForEach-Object {
    $head = Get-Content $_.FullName -TotalCount 1
    $w = [regex]::Match($head, 'width="(\d+)"').Groups[1].Value
    $h = [regex]::Match($head, 'height="(\d+)"').Groups[1].Value
    $png = Join-Path $pngDir ($_.BaseName + ".png")
    # Start-Process joins the arguments with spaces and quotes nothing, and this
    # project's folder name has spaces, so the paths are quoted and the URL encoded.
    $url = ([uri]$_.FullName).AbsoluteUri
    Start-Process -FilePath $edge -Wait -WindowStyle Hidden -ArgumentList @(
        "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
        "--window-size=$w,$h", "--user-data-dir=`"$profileDir`"", "--screenshot=`"$png`"", $url)
    Write-Output ("{0}  {1}x{2}" -f $_.BaseName, $w, $h)
}
