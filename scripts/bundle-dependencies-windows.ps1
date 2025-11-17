# Script to bundle Python and FFmpeg for Windows builds
# Run this before building the Electron app

Write-Host "Bundling dependencies for Windows..." -ForegroundColor Green

# Create resources directory structure
$resourcesDir = "resources"
$pythonDir = Join-Path $resourcesDir "python"
$ffmpegDir = Join-Path $resourcesDir "ffmpeg"

New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null

Write-Host "`n=== Step 1: Python ===" -ForegroundColor Yellow
Write-Host "You need to download and extract Python embeddable package:"
Write-Host "1. Download Python embeddable from: https://www.python.org/downloads/windows/"
Write-Host "   - Choose: Windows embeddable package (64-bit) or (32-bit)"
Write-Host "   - Extract to: $pythonDir"
Write-Host "2. Install pip:"
Write-Host "   - Download get-pip.py: https://bootstrap.pypa.io/get-pip.py"
Write-Host "   - Run: python.exe get-pip.py"
Write-Host "3. Install yt-dlp:"
Write-Host "   - Run: python.exe -m pip install yt-dlp"
Write-Host "4. Copy downloader.py:"
Write-Host "   - Copy python/downloader.py to $pythonDir/downloader.py"

$pythonExe = Join-Path $pythonDir "python.exe"
if (Test-Path $pythonExe) {
    Write-Host "✓ Python found at: $pythonExe" -ForegroundColor Green
} else {
    Write-Host "✗ Python not found. Please follow instructions above." -ForegroundColor Red
}

Write-Host "`n=== Step 2: FFmpeg ===" -ForegroundColor Yellow
Write-Host "You need to download FFmpeg:"
Write-Host "1. Download from: https://www.gyan.dev/ffmpeg/builds/"
Write-Host "   - Choose: ffmpeg-release-essentials.zip"
Write-Host "2. Extract and copy ffmpeg.exe to: $ffmpegDir/ffmpeg.exe"

$ffmpegExe = Join-Path $ffmpegDir "ffmpeg.exe"
if (Test-Path $ffmpegExe) {
    Write-Host "✓ FFmpeg found at: $ffmpegExe" -ForegroundColor Green
} else {
    Write-Host "✗ FFmpeg not found. Please follow instructions above." -ForegroundColor Red
}

Write-Host "`n=== Step 3: Copy Python Script ===" -ForegroundColor Yellow
$downloaderScript = "python/downloader.py"
$targetScript = Join-Path $pythonDir "downloader.py"
if (Test-Path $downloaderScript) {
    Copy-Item $downloaderScript $targetScript -Force
    Write-Host "✓ Copied downloader.py" -ForegroundColor Green
} else {
    Write-Host "✗ downloader.py not found at: $downloaderScript" -ForegroundColor Red
}

Write-Host "`n=== Summary ===" -ForegroundColor Yellow
if ((Test-Path $pythonExe) -and (Test-Path $ffmpegExe) -and (Test-Path $targetScript)) {
    Write-Host "✓ All dependencies ready for bundling!" -ForegroundColor Green
    Write-Host "You can now run: pnpm electron:build:win" -ForegroundColor Cyan
} else {
    Write-Host "✗ Some dependencies are missing. Please complete the steps above." -ForegroundColor Red
}

