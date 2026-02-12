# Bundle Python + FFmpeg for Tauri (Windows)

$ErrorActionPreference = "Stop"

Write-Host "Bundling dependencies for Windows (Tauri resources)..." -ForegroundColor Green

$resourcesRoot = "src-tauri/resources"
$pythonDir = Join-Path $resourcesRoot "python"
$ffmpegDir = Join-Path $resourcesRoot "ffmpeg"

if (Test-Path $pythonDir) { Remove-Item -Recurse -Force $pythonDir }
if (Test-Path $ffmpegDir) { Remove-Item -Recurse -Force $ffmpegDir }

New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null

Write-Host "`n=== Step 1: Python ===" -ForegroundColor Yellow

$pythonVersion = "3.12.0"
$pythonArch = "amd64"
$pythonZipUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-$pythonArch.zip"

Write-Host "Downloading Python embeddable package..."
Invoke-WebRequest -Uri $pythonZipUrl -OutFile python-embed.zip
Expand-Archive -Path python-embed.zip -DestinationPath $pythonDir -Force
Remove-Item python-embed.zip

$pthFile = Get-ChildItem $pythonDir -Filter "python*._pth" | Select-Object -First 1
if ($null -ne $pthFile) {
    $content = Get-Content $pthFile.FullName
    $content = $content | ForEach-Object { $_ -replace '^#import site$', 'import site' }
    Set-Content -Path $pthFile.FullName -Value $content
}

Write-Host "Installing pip + requirements..."
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile get-pip.py
& (Join-Path $pythonDir "python.exe") get-pip.py
Remove-Item get-pip.py

& (Join-Path $pythonDir "python.exe") -m pip install --upgrade pip
& (Join-Path $pythonDir "python.exe") -m pip install -r python/requirements.txt

Copy-Item "python/downloader.py" (Join-Path $pythonDir "downloader.py") -Force
Write-Host "OK: Python bundled at $pythonDir" -ForegroundColor Green

Write-Host "`n=== Step 2: FFmpeg ===" -ForegroundColor Yellow

$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
Write-Host "Downloading FFmpeg..."
Invoke-WebRequest -Uri $ffmpegUrl -OutFile ffmpeg.zip
Expand-Archive -Path ffmpeg.zip -DestinationPath ffmpeg-temp -Force

$ffmpegSource = Get-ChildItem ffmpeg-temp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if ($null -eq $ffmpegSource) {
    throw "Failed to locate ffmpeg.exe in archive"
}
Copy-Item $ffmpegSource.FullName (Join-Path $ffmpegDir "ffmpeg.exe") -Force
Remove-Item -Recurse -Force ffmpeg-temp
Remove-Item ffmpeg.zip

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
