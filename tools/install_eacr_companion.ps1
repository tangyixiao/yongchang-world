[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ModDirectory = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Victoria 3\mod'),
    [string]$SourceDirectory = '',
    [string]$VerifiedCache = ''
)

$ErrorActionPreference = 'Stop'
$repositoryUrl = 'https://github.com/1230james/vic3-east-asian-clothes.git'
$pinnedCommit = '8b9083d00ca10c58683664b6d2970ed019899445'
$expectedVersion = '1.0.4'
$metadataRelativePath = '.metadata\metadata.json'
$linkPath = Join-Path $ModDirectory 'east_asian_clothes_redux'
$descriptorPath = Join-Path $ModDirectory 'east_asian_clothes_redux.mod'
$stagingPath = "$SourceDirectory.installing-$([guid]::NewGuid().ToString('N'))"

function Get-GitHead([string]$Path) {
    $head = & git -c "safe.directory=$Path" -C $Path rev-parse HEAD 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    return ([string]$head).Trim()
}

function Assert-ValidSource([string]$Path) {
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) {
        throw "Expected a Git checkout at $Path"
    }
    $head = Get-GitHead $Path
    if ($head -ne $pinnedCommit) { throw "Source HEAD mismatch at $Path (found '$head')" }
    $origin = & git -c "safe.directory=$Path" -C $Path remote get-url origin 2>$null
    if ($LASTEXITCODE -ne 0 -or ([string]$origin).Trim() -notin @($repositoryUrl, 'https://github.com/1230james/vic3-east-asian-clothes')) {
        throw "Unexpected Git origin at $Path"
    }
    $status = & git -c "safe.directory=$Path" -C $Path status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0 -or $status) { throw "Source checkout is not clean at $Path" }
    $metadataFile = Join-Path $Path $metadataRelativePath
    if (-not (Test-Path -LiteralPath $metadataFile -PathType Leaf)) { throw "Missing launcher metadata: $metadataFile" }
    $metadata = Get-Content -LiteralPath $metadataFile -Raw | ConvertFrom-Json
    if ($metadata.version -ne $expectedVersion -or $metadata.name -ne 'East Asian Clothes: Redux') {
        throw "Unexpected source metadata at $metadataFile"
    }
    $modelsPath = Join-Path $Path 'gfx\models'
    $models = @(Get-ChildItem -LiteralPath $modelsPath -Recurse -File)
    if ($models.Count -ne 379) { throw "Expected 379 model assets, found $($models.Count) at $modelsPath" }
    $mingGenes = Join-Path $Path 'common\genes\EAC_genes_clothes.txt'
    $mingAsset = Join-Path $Path 'gfx\models\portraits\attachments\male_outfits\chinese\ming\common_01\male_outfit_chinese_common_ming_01.mesh'
    foreach ($asset in @($mingGenes, $mingAsset)) {
        if (-not (Test-Path -LiteralPath $asset -PathType Leaf) -or (Get-Item -LiteralPath $asset).Length -eq 0) {
            throw "Missing or empty Ming clothing asset: $asset"
        }
        $stream = [System.IO.File]::OpenRead($asset)
        try {
            $prefixBytes = New-Object byte[] 64
            $readCount = $stream.Read($prefixBytes, 0, $prefixBytes.Length)
            $prefix = [System.Text.Encoding]::ASCII.GetString($prefixBytes, 0, $readCount)
        }
        finally { $stream.Dispose() }
        if ($prefix.StartsWith('version https://git-lfs.github.com/spec/v1')) { throw "Git LFS pointer found instead of asset: $asset" }
    }
    return $metadata
}

$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path.TrimEnd('\', '/')
if ([string]::IsNullOrWhiteSpace($SourceDirectory)) { $SourceDirectory = Join-Path $RepositoryRoot 'refs\eacr-companion' }
$SourceDirectory = [System.IO.Path]::GetFullPath($SourceDirectory)
$ModDirectory = [System.IO.Path]::GetFullPath($ModDirectory)
if (-not $SourceDirectory.StartsWith($RepositoryRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Persistent source must stay under repository root: $SourceDirectory"
}
$ignoredCheck = & git -C $RepositoryRoot check-ignore -q -- $SourceDirectory
if ($LASTEXITCODE -ne 0) { throw "Persistent source is not ignored by Git; refusing to place large third-party assets there: $SourceDirectory" }

if (Test-Path -LiteralPath $SourceDirectory) {
    $null = Assert-ValidSource $SourceDirectory
}
else {
    if (Test-Path -LiteralPath $stagingPath) { throw "Install staging path already exists; inspect it manually: $stagingPath" }
    if (-not $stagingPath.StartsWith($RepositoryRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Staging path must stay under repository root: $stagingPath"
    }
    if (Test-Path -LiteralPath $VerifiedCache) {
        $null = Assert-ValidSource $VerifiedCache
        Copy-Item -LiteralPath $VerifiedCache -Destination $stagingPath -Recurse -Force
    }
    else {
        & git clone --filter=blob:none --no-checkout $repositoryUrl $stagingPath
        if ($LASTEXITCODE -ne 0) { throw "git clone failed for $repositoryUrl" }
        & git -c "safe.directory=$stagingPath" -C $stagingPath checkout --detach $pinnedCommit
        if ($LASTEXITCODE -ne 0) { throw "Could not check out pinned commit $pinnedCommit" }
    }
    $null = Assert-ValidSource $stagingPath
    if (-not $SourceDirectory.StartsWith($RepositoryRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Final source path escaped repository root: $SourceDirectory"
    }
    Move-Item -LiteralPath $stagingPath -Destination $SourceDirectory
}

$metadata = Assert-ValidSource $SourceDirectory
New-Item -ItemType Directory -Force -Path $ModDirectory | Out-Null

if (Test-Path -LiteralPath $linkPath) {
    $existing = Get-Item -LiteralPath $linkPath -Force
    if (($existing.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) {
        throw "Mod target exists and is not a junction; leaving it untouched: $linkPath"
    }
    $resolvedTarget = [System.IO.Path]::GetFullPath($existing.Target)
    if ($resolvedTarget -ne $SourceDirectory) { throw "Mod junction points elsewhere; leaving it untouched: $linkPath -> $resolvedTarget" }
}
else {
    New-Item -ItemType Junction -Path $linkPath -Target $SourceDirectory | Out-Null
}

$descriptor = @(
    'name="East Asian Clothes Redux"'
    "path=`"$($SourceDirectory -replace '\\','/')`""
    'version="1.0.4"'
    'supported_version="1.13.*"'
) -join [Environment]::NewLine
if (Test-Path -LiteralPath $descriptorPath) {
    $existingDescriptor = [System.IO.File]::ReadAllText($descriptorPath)
    if ($existingDescriptor.Trim() -ne $descriptor.Trim()) {
        throw "Descriptor exists with different content; leaving it untouched: $descriptorPath"
    }
}
else {
    [System.IO.File]::WriteAllText($descriptorPath, $descriptor, (New-Object System.Text.UTF8Encoding($false)))
}

$models = @(Get-ChildItem -LiteralPath (Join-Path $SourceDirectory 'gfx\models') -Recurse -File)
$modelBytes = ($models | Measure-Object -Property Length -Sum).Sum
Write-Output "Installed source: $SourceDirectory"
Write-Output "Pinned HEAD: $(Get-GitHead $SourceDirectory)"
Write-Output "Source metadata: $($metadata.name), version $($metadata.version), game $($metadata.game_id)"
Write-Output "Model assets: $($models.Count) files, $modelBytes bytes"
Write-Output "Ming genes: $(Join-Path $SourceDirectory 'common\genes\EAC_genes_clothes.txt')"
Write-Output "Mod junction: $linkPath -> $SourceDirectory"
Write-Output "Local descriptor: $descriptorPath"
