#!/bin/bash
# Script to bundle Python and FFmpeg for Linux builds
# Run this before building the Electron app

echo "Bundling dependencies for Linux..."

# Detect if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "⚠️  WARNING: Running on macOS"
    echo "   The bundled Python/FFmpeg will be macOS binaries that won't work on Linux."
    echo "   For a proper Linux build, you have two options:"
    echo "   1. Use GitHub Actions (recommended) - it builds on Linux"
    echo "   2. Use Docker to bundle Linux binaries, then build"
    echo ""
    echo "   Continuing anyway (electron-builder can create Linux packages, but bundled deps won't work)..."
    echo ""
fi

# Create resources directory structure
mkdir -p resources/python
mkdir -p resources/ffmpeg

echo ""
echo "=== Step 1: Python ==="
echo "Setting up Python environment..."

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "Found Python: $PYTHON_VERSION"
    
    # Create a virtual environment
    # Use --copies to avoid symlinks (better for app bundles)
    python3 -m venv --copies resources/python
    
    # Install yt-dlp in the venv
    echo "Installing yt-dlp..."
    resources/python/bin/pip install --upgrade pip
    resources/python/bin/pip install yt-dlp
    
    # CRITICAL: Fix pyvenv.cfg to use relative paths instead of hardcoded build machine paths
    # This makes the venv portable across different machines
    echo "Making venv portable..."
    PYTHON_VERSION=$(resources/python/bin/python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    
    # Update pyvenv.cfg to use relative paths
    cat > resources/python/pyvenv.cfg <<EOF
home = bin
include-system-site-packages = false
version = $PYTHON_VERSION
executable = bin/python3
EOF
    
    # Fix all shebang lines in Python scripts to use relative paths
    find resources/python/bin -type f -name "*.py" -exec sed -i "1s|^#!.*python.*|#!/usr/bin/env python3|" {} \;
    find resources/python/bin -type f ! -name "*.py" -exec grep -l "^#!.*python" {} \; | while read script; do
        sed -i "1s|^#!.*|#!/usr/bin/env python3|" "$script"
    done
    
    # Ensure Python executable has correct permissions
    chmod +x resources/python/bin/python3
    
    # Make sure all scripts are executable
    find resources/python/bin -type f -exec chmod +x {} \;
    
    echo "✓ Python environment created and made portable"
else
    echo "✗ Python 3 not found. Please install Python 3.11+ first."
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
    echo "  RHEL/CentOS: sudo yum install python3 python3-pip"
    exit 1
fi

# Copy downloader.py
if [ -f "python/downloader.py" ]; then
    cp python/downloader.py resources/python/downloader.py
    echo "✓ Copied downloader.py"
else
    echo "✗ downloader.py not found"
    exit 1
fi

echo ""
echo "=== Step 2: FFmpeg ==="
echo "Setting up FFmpeg..."

# Check if FFmpeg is available
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n1)
    echo "Found FFmpeg: $FFMPEG_VERSION"
    
    # Copy system FFmpeg
    cp $(which ffmpeg) resources/ffmpeg/ffmpeg
    chmod +x resources/ffmpeg/ffmpeg
    echo "✓ FFmpeg copied"
else
    echo "FFmpeg not found. Please install FFmpeg:"
    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "  RHEL/CentOS: sudo yum install ffmpeg"
    echo "  Or download static build from: https://johnvansickle.com/ffmpeg/"
    exit 1
fi

echo ""
echo "=== Summary ==="
if [ -f "resources/python/bin/python3" ] && [ -f "resources/ffmpeg/ffmpeg" ] && [ -f "resources/python/downloader.py" ]; then
    echo "✓ All dependencies ready for bundling!"
    echo "You can now run: pnpm electron:build:linux"
else
    echo "✗ Some dependencies are missing. Please complete the steps above."
    exit 1
fi
