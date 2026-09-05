[CmdletBinding()]
param(
    [string]$GameRoot = 'E:\SteamLibrary\steamapps\common\Victoria 3',
    [string]$UserDataRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Victoria 3'),
    [ValidateSet('none', 'sphere', 'charters', 'wave', 'all')]
    [string]$Config = 'none',
    [int]$Seed = 11,
    [string]$CheckpointYears = '1846,1866,1900',
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runRoot = Join-Path $projectRoot (Join-Path 'artifacts\observe' (Join-Path $Config ([string]$Seed)))
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

$expectedYears = @(1846, 1866, 1900)
$parsedYears = @($CheckpointYears -split ',' | ForEach-Object { [int]$_.Trim() })
if ((@($parsedYears | Sort-Object) -join ',') -ne (@($expectedYears | Sort-Object) -join ',')) {
    throw 'CheckpointYears must contain exactly 1846, 1866, and 1900.'
}

# The recorder never edits the supplied user-data root. A real observation
# import is placed beside this run metadata as checkpoints.json after a game
# session has been manually or externally exported.
$metadata = [ordered]@{
    config = $Config
    seed = $Seed
    checkpoint_years = $parsedYears
    game_root = $GameRoot
    user_data_root = $UserDataRoot
    status = if ($NoLaunch) { 'prepared_no_launch' } else { 'prepared_checkpoint_import_required' }
    desktop_interaction = 'none'
    writes_to_user_data = $false
    checkpoints = (Join-Path $runRoot 'checkpoints.json')
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'run.json') -Encoding UTF8
Write-Output "Prepared observation run: $runRoot"
Write-Output 'No save, desktop window, or user-data file was modified.'
