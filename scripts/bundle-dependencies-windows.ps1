# Bundle Python + FFmpeg for Tauri (Windows)

$ErrorActionPreference = "Stop"

Write-Host "Bundling dependencies for Windows (Tauri resources)..." -ForegroundColor Green

$resourcesRoot = "src-tauri/resources"
$pythonDir = Join-Path $resourcesRoot "python"
$ffmpegDir = Join-Path $resourcesRoot "ffmpeg"

function Assert-Sha256 {
    param (
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedHash,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $actualHash = (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $expected = $ExpectedHash.ToLowerInvariant()
    if ($actualHash -ne $expected) {
        if (Test-Path $Path) { Remove-Item -Force $Path }
        throw "$Label checksum mismatch. Expected $expected but got $actualHash."
    }
}

if (Test-Path $pythonDir) { Remove-Item -Recurse -Force $pythonDir }
if (Test-Path $ffmpegDir) { Remove-Item -Recurse -Force $ffmpegDir }

New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null

Write-Host "`n=== Step 1: Python ===" -ForegroundColor Yellow

$pythonVersion = "3.12.0"
$pythonArch = "amd64"
$pythonZipUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-$pythonArch.zip"
$getPipUrl = "https://raw.githubusercontent.com/pypa/get-pip/69fd2a8ffdc323a975d2f15eb4c2766cf28daaf7/public/get-pip.py"
$expectedPythonZipHash = "c87f000e3dae1a572e98e81daeb622f8bc6f22664093fc9c70989b5f0018d49b"
$expectedGetPipHash = "feba1c697df45be1b539b40d93c102c9ee9dde1d966303323b830b06f3fbca3c"

Write-Host "Downloading Python embeddable package..."
try {
    Invoke-WebRequest -Uri $pythonZipUrl -OutFile python-embed.zip
    Assert-Sha256 -Path "python-embed.zip" -ExpectedHash $expectedPythonZipHash -Label "python-embed.zip"
    Expand-Archive -Path python-embed.zip -DestinationPath $pythonDir -Force
    Remove-Item python-embed.zip
} catch {
    if (Test-Path "python-embed.zip") { Remove-Item -Force "python-embed.zip" }
    throw
}

$pthFile = Get-ChildItem $pythonDir -Filter "python*._pth" | Select-Object -First 1
if ($null -ne $pthFile) {
    $content = Get-Content $pthFile.FullName
    $content = $content | ForEach-Object { $_ -replace '^#import site$', 'import site' }
    Set-Content -Path $pthFile.FullName -Value $content
}

Write-Host "Installing pip + requirements..."
try {
    Invoke-WebRequest -Uri $getPipUrl -OutFile get-pip.py
    Assert-Sha256 -Path "get-pip.py" -ExpectedHash $expectedGetPipHash -Label "get-pip.py"
    & (Join-Path $pythonDir "python.exe") get-pip.py
    Remove-Item get-pip.py
} catch {
    if (Test-Path "get-pip.py") { Remove-Item -Force "get-pip.py" }
    throw
}

& (Join-Path $pythonDir "python.exe") -m pip install --upgrade pip
& (Join-Path $pythonDir "python.exe") -m pip install -r python/requirements.txt

Copy-Item "python/downloader.py" (Join-Path $pythonDir "downloader.py") -Force
Write-Host "OK: Python bundled at $pythonDir" -ForegroundColor Green

Write-Host "`n=== Step 2: FFmpeg ===" -ForegroundColor Yellow

$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-7.1.1-essentials_build.zip"
$expectedFfmpegZipHash = "04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4"
Write-Host "Downloading FFmpeg..."
try {
    Invoke-WebRequest -Uri $ffmpegUrl -OutFile ffmpeg.zip
    Assert-Sha256 -Path "ffmpeg.zip" -ExpectedHash $expectedFfmpegZipHash -Label "ffmpeg.zip"
    Expand-Archive -Path ffmpeg.zip -DestinationPath ffmpeg-temp -Force

    $ffmpegSource = Get-ChildItem ffmpeg-temp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if ($null -eq $ffmpegSource) {
        throw "Failed to locate ffmpeg.exe in archive"
    }
    Copy-Item $ffmpegSource.FullName (Join-Path $ffmpegDir "ffmpeg.exe") -Force
    Remove-Item -Recurse -Force ffmpeg-temp
    Remove-Item ffmpeg.zip
} catch {
    if (Test-Path "ffmpeg-temp") { Remove-Item -Recurse -Force "ffmpeg-temp" }
    if (Test-Path "ffmpeg.zip") { Remove-Item -Force "ffmpeg.zip" }
    throw
}

Write-Host "OK: FFmpeg bundled at $ffmpegDir" -ForegroundColor Green

Write-Host "`n=== Summary ===" -ForegroundColor Yellow
$pythonExe = Join-Path $pythonDir "python.exe"
$pythonScript = Join-Path $pythonDir "downloader.py"
$ffmpegExe = Join-Path $ffmpegDir "ffmpeg.exe"

if ((Test-Path $pythonExe) -and (Test-Path $pythonScript) -and (Test-Path $ffmpegExe)) {
    Write-Host "All dependencies bundled for Tauri." -ForegroundColor Green
    Write-Host "Python: $pythonExe"
    Write-Host "Script: $pythonScript"
    Write-Host "FFmpeg: $ffmpegExe"
    Write-Host "Next: pnpm tauri:build:win"
} else {
    throw "Dependency bundling failed"
}
