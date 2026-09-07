[CmdletBinding()]
param(
    [string]$GameRoot = 'E:\SteamLibrary\steamapps\common\Victoria 3',
    [string]$UserDataRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Victoria 3'),
    [switch]$NoLaunch,
    [switch]$RequireScriptedTests
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$artifactRoot = Join-Path $projectRoot 'artifacts\smoke'
$logRoot = Join-Path $UserDataRoot 'logs'
$logPaths = @(
    (Join-Path $logRoot 'error.log'),
    (Join-Path $logRoot 'game.log')
)
$debugLogPath = Join-Path $logRoot 'debug.log'
$markers = @(
    'ywc_',
    'yongchang_world',
    'Unknown trigger',
    'Unknown effect',
    'Invalid database object'
)

if (-not $NoLaunch) {
    $executable = Join-Path $GameRoot 'binaries\victoria3.exe'
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Victoria 3 executable does not exist: $executable"
    }
    $process = Start-Process -FilePath $executable -ArgumentList '-debug_mode' -PassThru
    Write-Output "Started Victoria 3 with PID $($process.Id)"
}

$findings = New-Object System.Collections.Generic.List[string]
foreach ($logPath in $logPaths) {
    if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
        $findings.Add("${logPath}:1: missing log")
        continue
    }
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $logPath) {
        $lineNumber++
        foreach ($marker in $markers) {
            if ($line -like "*$marker*") {
                $findings.Add("${logPath}:${lineNumber}: $line")
                break
            }
        }
    }
}

# debug.log is optional in non-debug launches. When present, only scan for
# parser/runtime failures; normal mount lines contain the mod name and ywc IDs.
if (Test-Path -LiteralPath $debugLogPath -PathType Leaf) {
    $lineNumber = 0
    $debugMarkers = @(
        'Unknown trigger',
        'Unknown effect',
        'Invalid database object',
        'missing localization',
        'Duplicate localization key',
        'Failed to parse'
    )
    foreach ($line in Get-Content -LiteralPath $debugLogPath) {
        $lineNumber++
        foreach ($marker in $debugMarkers) {
            if ($line -like "*$marker*") {
                $findings.Add("${debugLogPath}:${lineNumber}: $line")
                break
            }
        }
    }
}

# Scripted-test output is written beside the isolated user data when the game
# is launched with -userdir.  A file containing only the header means that the
# engine's test mode was enabled but no suite completed; it is not a pass.
$scriptedTestStatus = 'not_requested'
$scriptedTestResultsPath = Join-Path $UserDataRoot 'tests.txt'
if (Test-Path -LiteralPath $scriptedTestResultsPath -PathType Leaf) {
    $scriptedTestText = (Get-Content -LiteralPath $scriptedTestResultsPath -Raw) -replace '^\uFEFF', ''
    $scriptedTestPayload = $scriptedTestText -replace '^\s*Tests:\s*', ''
    $scriptedTestStatus = if ([string]::IsNullOrWhiteSpace($scriptedTestPayload)) { 'empty' } else { 'present' }
} elseif ($RequireScriptedTests) {
    $scriptedTestStatus = 'missing'
}
if ($RequireScriptedTests -and $scriptedTestStatus -ne 'present') {
    $findings.Add("$scriptedTestResultsPath:1: scripted test results are $scriptedTestStatus")
}

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
$status = if ($findings.Count -eq 0) { 'clean' } else { 'error' }

# The summary reports whether the mod actually mounted, taken only from the
# game's own debug log. This is recorded information: it does not change the
# clean/error verdict, and a missing mount is reported as-is.
$modMount = 'unknown_no_debug_log'
$modMountEvidence = @()
if (Test-Path -LiteralPath $debugLogPath -PathType Leaf) {
    $modMountEvidence = @(Get-Content -LiteralPath $debugLogPath |
        Where-Object { $_ -like '*Mounted Data:*yongchang_world*' })
    $modMount = if ($modMountEvidence.Count -gt 0) { 'mounted' } else { 'not_mounted' }
}

$summary = @(
    "status=$status"
    "user_data_root=$UserDataRoot"
    "checked_logs=$($logPaths -join ';');$debugLogPath (optional)"
    "finding_count=$($findings.Count)"
    "mod_mount=$modMount"
    "scripted_tests=$scriptedTestStatus"
)
$summary += "scripted_test_results_path=$scriptedTestResultsPath"
$summary += @($modMountEvidence | ForEach-Object { "mount_evidence: $_" })
if ($findings.Count -gt 0) {
    $summary += 'findings:'
    $summary += $findings
}
Set-Content -LiteralPath (Join-Path $artifactRoot 'latest-summary.txt') -Value $summary -Encoding UTF8

foreach ($finding in $findings) {
    Write-Output $finding
}
if ($findings.Count -eq 0) {
    Write-Output "Smoke logs are clean. Summary: $(Join-Path $artifactRoot 'latest-summary.txt')"
    exit 0
}
exit 1
