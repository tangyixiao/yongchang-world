[CmdletBinding()]
param(
    [string]$ModDirectory = (Join-Path $env:USERPROFILE 'Documents\Paradox Interactive\Victoria 3\mod')
)

$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$modRoot = Join-Path $sourceRoot 'yongchang_world'
$descriptorPath = Join-Path $ModDirectory 'yongchang_world.mod'

if (-not (Test-Path -LiteralPath $modRoot -PathType Container)) {
    throw "Mod root does not exist: $modRoot"
}

New-Item -ItemType Directory -Force -Path $ModDirectory | Out-Null

$descriptor = @(
    'name="The Yongchang World"'
    'path="E:/Victoria3 Mod/yongchang_world"'
    'supported_version="1.13.*"'
) -join [Environment]::NewLine

Set-Content -LiteralPath $descriptorPath -Value $descriptor -Encoding utf8NoBOM
Write-Output "Installed development descriptor: $descriptorPath"
