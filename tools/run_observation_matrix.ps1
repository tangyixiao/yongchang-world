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
$isolatedUserDataRoot = Join-Path $runRoot 'userdata'
New-Item -ItemType Directory -Force -Path $isolatedUserDataRoot | Out-Null

$expectedYears = @(1846, 1866, 1900)
$parsedYears = @($CheckpointYears -split ',' | ForEach-Object { [int]$_.Trim() })
if ((@($parsedYears | Sort-Object) -join ',') -ne (@($expectedYears | Sort-Object) -join ',')) {
    throw 'CheckpointYears must contain exactly 1846, 1866, and 1900.'
}

$disabledDlc = switch ($Config) {
    'none' { @('dlc010_ep1', 'dlc013_mp1', 'dlc018_ep2') }
    'sphere' { @('dlc013_mp1', 'dlc018_ep2') }
    'charters' { @('dlc010_ep1', 'dlc018_ep2') }
    'wave' { @('dlc010_ep1', 'dlc013_mp1') }
    'all' { @() }
}
$contentLoad = [ordered]@{
    enabledMods = @([ordered]@{ path = (Join-Path $projectRoot 'yongchang_world') })
    disabledDLC = @($disabledDlc)
    enabledUGC = @()
}
$contentLoad | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $isolatedUserDataRoot 'content_load.json') -Encoding UTF8

$launchStatus = 'prepared_no_launch'
$processStatus = 'not_started'
if (-not $NoLaunch) {
    $exe = Join-Path $GameRoot 'binaries\victoria3.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Victoria 3 executable does not exist: $exe"
    }
    $process = Start-Process -FilePath $exe -ArgumentList @('-debug_mode', '-userdir', $isolatedUserDataRoot) -WorkingDirectory $GameRoot -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 20
        $launchStatus = 'hidden_preload_only'
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $processStatus = 'stopped_after_preload'
        }
        else {
            $processStatus = 'exited_after_preload'
        }
    }
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
    status = $launchStatus
    process_status = $processStatus
    desktop_interaction = 'none'
    writes_to_user_data = $false
    isolated_user_data_root = $isolatedUserDataRoot
    content_load = (Join-Path $isolatedUserDataRoot 'content_load.json')
    checkpoints = (Join-Path $runRoot 'checkpoints.json')
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runRoot 'run.json') -Encoding UTF8
Write-Output "Prepared observation run: $runRoot"
Write-Output 'No save, desktop window, or user-data file was modified.'
