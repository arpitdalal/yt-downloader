#!/bin/bash
# Script to bundle Python and FFmpeg for Windows builds
# Run this before building the Electron app (on Windows or via CI)

echo "Bundling dependencies for Windows..."

# Create resources directory structure
mkdir -p resources/python
mkdir -p resources/ffmpeg

echo ""
echo "=== Step 1: Python ==="
echo "You need to download and extract Python embeddable package:"
echo "1. Download Python embeddable from: https://www.python.org/downloads/windows/"
echo "   - Choose: Windows embeddable package (64-bit) or (32-bit)"
echo "   - Extract to: resources/python/"
echo "2. Install pip:"
echo "   - Download get-pip.py: https://bootstrap.pypa.io/get-pip.py"
echo "   - Run: python.exe get-pip.py"
echo "3. Install yt-dlp:"
echo "   - Run: python.exe -m pip install yt-dlp"
echo "4. Copy downloader.py:"
echo "   - Copy python/downloader.py to resources/python/downloader.py"

if [ -f "resources/python/python.exe" ]; then
    echo "✓ Python found"
else
    echo "✗ Python not found. Please follow instructions above."
fi

echo ""
echo "=== Step 2: FFmpeg ==="
echo "You need to download FFmpeg:"
echo "1. Download from: https://www.gyan.dev/ffmpeg/builds/"
echo "   - Choose: ffmpeg-release-essentials.zip"
echo "2. Extract and copy ffmpeg.exe to: resources/ffmpeg/ffmpeg.exe"

if [ -f "resources/ffmpeg/ffmpeg.exe" ]; then
    echo "✓ FFmpeg found"
else
    echo "✗ FFmpeg not found. Please follow instructions above."
fi

echo ""
echo "=== Step 3: Copy Python Script ==="
if [ -f "python/downloader.py" ]; then
    cp python/downloader.py resources/python/downloader.py
    echo "✓ Copied downloader.py"
else
    echo "✗ downloader.py not found"
fi

echo ""
echo "=== Summary ==="
if [ -f "resources/python/python.exe" ] && [ -f "resources/ffmpeg/ffmpeg.exe" ] && [ -f "resources/python/downloader.py" ]; then
    echo "✓ All dependencies ready for bundling!"
    echo "You can now run: pnpm electron:build:win"
else
    echo "✗ Some dependencies are missing. Please complete the steps above."
fi

