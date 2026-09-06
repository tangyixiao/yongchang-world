[CmdletBinding()]
param(
    [string]$ModDirectory = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Victoria 3\mod')
)

$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$modRoot = Join-Path $sourceRoot 'yongchang_world'
$descriptorPath = Join-Path $ModDirectory 'yongchang_world.mod'
$modLinkPath = Join-Path $ModDirectory 'yongchang_world'

if (-not (Test-Path -LiteralPath $modRoot -PathType Container)) {
    throw "Mod root does not exist: $modRoot"
}

New-Item -ItemType Directory -Force -Path $ModDirectory | Out-Null

# Current Paradox Launcher versions reliably discover loose local mods when
# the mod folder itself is present below the game's mod directory. A junction
# keeps the repository as the single source of truth without copying files.
if (-not (Test-Path -LiteralPath $modLinkPath)) {
    New-Item -ItemType Junction -Path $modLinkPath -Target $modRoot | Out-Null
}
else {
    $existingLink = Get-Item -LiteralPath $modLinkPath -Force
    if (($existingLink.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
        Write-Output "Mod directory already exists; leaving it unchanged: $modLinkPath"
    }
}

$descriptor = @(
    'name="The Yongchang World"'
    'path="E:/Victoria3 Mod/yongchang_world"'
    'supported_version="1.13.*"'
) -join [Environment]::NewLine

# Windows PowerShell 5.1 rejects the PS6+ utf8NoBOM encoding switch; write
# BOM-free UTF-8 directly instead.
[System.IO.File]::WriteAllText($descriptorPath, $descriptor, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "Installed development descriptor: $descriptorPath"
