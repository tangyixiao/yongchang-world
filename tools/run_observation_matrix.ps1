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

function Write-Utf8NoBom([string]$Path, [string]$Text) {
    # Victoria 3 rejects a UTF-8 BOM in JSON config files and silently falls
    # back to "all DLC enabled, no mods", so every file written for the game
    # must be BOM-free.
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
}

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
$knownDlc = @('dlc010_ep1', 'dlc013_mp1', 'dlc018_ep2')
$contentLoad = [ordered]@{
    enabledMods = @([ordered]@{ path = (Join-Path $projectRoot 'yongchang_world') })
    disabledDLC = @($disabledDlc)
    enabledUGC = @()
}
$contentLoadPath = Join-Path $isolatedUserDataRoot 'content_load.json'
Write-Utf8NoBom -Path $contentLoadPath -Text ($contentLoad | ConvertTo-Json -Depth 4 -Compress)

$launchStatus = 'prepared_no_launch'
$processStatus = 'not_started'
if (-not $NoLaunch) {
    $exe = Join-Path $GameRoot 'binaries\victoria3.exe'
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "Victoria 3 executable does not exist: $exe"
    }
    $process = Start-Process -FilePath $exe -ArgumentList @('-debug_mode', '-userdir', $isolatedUserDataRoot) -WorkingDirectory $GameRoot -WindowStyle Hidden -PassThru
    try {
        Start-Sleep -Seconds 45
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

# Mount evidence comes only from the debug log the game itself wrote into the
# isolated user data root. A missing or unmounted mod is recorded as such and
# never rewritten into a pass. DLC enablement is only observed, not claimed:
# the ownership backend decides which DLCs mount, and disabledDLC entries are
# ignored by the game for directly launched executables.
$modMount = 'not_evaluated_no_launch'
$modMountEvidence = @()
$versionMatchEvidence = @()
$dlcMountEvidence = @()
$observedMountedDlc = @()
$dlcOwnershipBackend = 'not_evaluated_no_launch'
$storeBackendFailureCount = -1
$dlcStateMatchesConfig = 'not_evaluated_no_launch'
$expectedMountedDlc = switch ($Config) {
    'none' { @() }
    'sphere' { @('dlc010_ep1') }
    'charters' { @('dlc013_mp1') }
    'wave' { @('dlc018_ep2') }
    'all' { @('dlc010_ep1', 'dlc013_mp1', 'dlc018_ep2') }
}
$debugLogPath = Join-Path $isolatedUserDataRoot 'logs\debug.log'
if ($launchStatus -ne 'prepared_no_launch') {
    if (Test-Path -LiteralPath $debugLogPath) {
        $mountLines = @(Select-String -LiteralPath $debugLogPath -Pattern 'Mounted Data:' | ForEach-Object { $_.Line })
        $modMountEvidence = @($mountLines | Where-Object { $_ -match 'yongchang_world' })
        $versionMatchEvidence = @(Select-String -LiteralPath $debugLogPath -Pattern 'successfully matched game version' |
            Where-Object { $_.Line -match 'The Yongchang World' } | ForEach-Object { $_.Line })
        if ($modMountEvidence.Count -gt 0) {
            $modMount = 'mounted'
        }
        else {
            $modMount = 'not_mounted'
        }
        $dlcMountEvidence = @($mountLines | Where-Object { $_ -match 'dlc010_ep1|dlc013_mp1|dlc018_ep2' })
        $observedMountedDlc = @($knownDlc | Where-Object { $dlcId = $_; @($dlcMountEvidence | Where-Object { $_ -match $dlcId }).Count -gt 0 })
        $storeBackendFailureCount = @(Select-String -LiteralPath $debugLogPath -Pattern 'Could not find item in store backend').Count
        $dlcOwnershipBackend = if ($storeBackendFailureCount -gt 0) { 'unavailable' } else { 'available' }
        $dlcStateMatchesConfig = if ((@($observedMountedDlc) -join ',') -eq (@($expectedMountedDlc) -join ',')) { 'yes' } else { 'no' }
    }
    else {
        $modMount = 'not_mounted'
        $dlcStateMatchesConfig = 'no'
    }
}

# Keep a run-local smoke summary beside the launch metadata. This is only
# parser/log evidence: it never upgrades a preload into a campaign run.
$smokeSummaryPath = Join-Path $runRoot 'smoke-summary.txt'
$smokeStatus = 'not_collected_no_launch'
$smokeCollector = Join-Path $projectRoot 'tools\collect_smoke_logs.ps1'
if ($launchStatus -ne 'prepared_no_launch') {
    if (Test-Path -LiteralPath $smokeCollector -PathType Leaf) {
        $null = @(& $smokeCollector -NoLaunch -UserDataRoot $isolatedUserDataRoot -SummaryPath $smokeSummaryPath 2>&1)
        $smokeStatus = if ($LASTEXITCODE -eq 0) { 'clean' } else { 'error' }
    }
    else {
        $smokeStatus = 'collector_missing'
    }
}

# The recorder never edits the supplied user-data root. A real observation
# import is placed beside this run metadata as checkpoints.json after a game
# session has been manually or externally exported. A preload run with a
# mounted mod is still not an observation session.
$metadata = [ordered]@{
    config = $Config
    run_id = "run-$Seed"
    requested_seed = $Seed
    observed_seed = $null
    checkpoint_years = $parsedYears
    game_version = '1.13.11 (Matcha)'
    game_root = $GameRoot
    user_data_root = $UserDataRoot
    status = $launchStatus
    process_status = $processStatus
    desktop_interaction = 'none'
    writes_to_user_data = $false
    isolated_user_data_root = $isolatedUserDataRoot
    content_load = $contentLoadPath
    disabled_dlc = @($disabledDlc)
    mod_mount = $modMount
    mod_mount_evidence = $modMountEvidence
    version_match_evidence = $versionMatchEvidence
    dlc_mount_evidence = $dlcMountEvidence
    expected_mounted_dlc = @($expectedMountedDlc)
    observed_mounted_dlc = $observedMountedDlc
    dlc_ownership_backend = $dlcOwnershipBackend
    store_backend_failure_count = $storeBackendFailureCount
    dlc_state_matches_config = $dlcStateMatchesConfig
    smoke_summary = $smokeSummaryPath
    smoke_status = $smokeStatus
    evidence = [ordered]@{
        campaign = 'not_recorded_until_campaign_checkpoint_export'
        logs = $debugLogPath
        smoke_summary = $smokeSummaryPath
    }
    checkpoints = (Join-Path $runRoot 'checkpoints.json')
}
$runJsonPath = Join-Path $runRoot 'run.json'
# A -NoLaunch rerun over a config/seed that already holds live launch
# evidence must not replace that evidence with a not_evaluated stub.
$preservedExistingEvidence = $false
if ($launchStatus -eq 'prepared_no_launch' -and (Test-Path -LiteralPath $runJsonPath)) {
    $existing = $null
    try {
        $existing = Get-Content -LiteralPath $runJsonPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        $existing = $null
    }
    if ($null -ne $existing -and $existing.status -eq 'hidden_preload_only' -and $existing.mod_mount -eq 'mounted') {
        $preservedExistingEvidence = $true
    }
}

if ($preservedExistingEvidence) {
    Write-Output "NoLaunch requested; preserved existing live run evidence: $runJsonPath"
}
else {
    Write-Utf8NoBom -Path $runJsonPath -Text ($metadata | ConvertTo-Json -Depth 4)
    Write-Output "Prepared observation run: $runRoot"
    Write-Output "mod_mount=$modMount dlc_state_matches_config=$dlcStateMatchesConfig"
}
Write-Output 'No save, desktop window, or user-data file was modified.'
