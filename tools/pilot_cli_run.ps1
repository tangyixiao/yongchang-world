[CmdletBinding()]
param(
    [string]$GameRoot = 'E:\SteamLibrary\steamapps\common\Victoria 3',
    [string]$IsoRoot,
    [string]$StartTag = 'SHU',
    [string]$RunUntil = '1846.1.1',
    [int]$Seconds = 90,
    [switch]$NoHandsoff
)

# Bounded pilot: does the game accept the hands-off command line and start a
# campaign without any desktop interaction? Hidden window only - nothing is
# injected into the user's foreground.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $IsoRoot) {
    $IsoRoot = Join-Path $projectRoot 'artifacts/observe/_pilot/userdata'
}
New-Item -ItemType Directory -Force -Path $IsoRoot | Out-Null

$modPath = Join-Path $projectRoot 'yongchang_world'
$contentLoad = [ordered]@{
    enabledMods = @([ordered]@{ path = $modPath })
    disabledDLC = @()
    enabledUGC = @()
}
$contentLoadPath = Join-Path $IsoRoot 'content_load.json'
[System.IO.File]::WriteAllText($contentLoadPath, ($contentLoad | ConvertTo-Json -Depth 4 -Compress), (New-Object System.Text.UTF8Encoding($false)))

$args = @('-debug_mode', '-no_notifications', "-start_tag=$StartTag", '-run_until', $RunUntil, '-userdir', $IsoRoot)
if (-not $NoHandsoff) { $args = @('-handsoff') + $args }

$exe = Join-Path $GameRoot 'binaries/victoria3.exe'
$process = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $GameRoot -WindowStyle Hidden -PassThru
Write-Output "launched pid=$($process.Id) args=$($args -join ' ')"
try {
    Start-Sleep -Seconds $Seconds
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        Write-Output "stopped pid=$($process.Id)"
    }
    else {
        Write-Output "exited on its own pid=$($process.Id)"
    }
}
$logs = Join-Path $IsoRoot 'logs'
if (Test-Path -LiteralPath $logs) {
    Get-ChildItem -LiteralPath $logs -File | ForEach-Object { Write-Output ("log: " + $_.FullName + " (" + $_.Length + " bytes)") }
}
$saves = Join-Path $IsoRoot 'save games'
if (Test-Path -LiteralPath $saves) {
    Get-ChildItem -LiteralPath $saves -File | ForEach-Object { Write-Output ("save: " + $_.FullName + " (" + $_.Length + " bytes)") }
}
