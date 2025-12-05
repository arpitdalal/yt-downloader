#!/bin/bash
# Script to bundle Python and FFmpeg for macOS builds
# Run this before building the Electron app

echo "Bundling dependencies for macOS..."

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
    PYTHON_BIN_DIR=$(cd resources/python/bin && pwd)
    PYTHON_EXECUTABLE=$(ls "$PYTHON_BIN_DIR"/python3.* 2>/dev/null | head -1 || echo "$PYTHON_BIN_DIR/python3")
    PYTHON_VERSION=$(resources/python/bin/python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    
    # Update pyvenv.cfg to use relative paths
    cat > resources/python/pyvenv.cfg <<EOF
home = bin
include-system-site-packages = false
version = $PYTHON_VERSION
executable = bin/python3
EOF
    
    # Fix all shebang lines in Python scripts to use relative paths
    find resources/python/bin -type f -name "*.py" -exec sed -i '' "1s|^#!.*python.*|#!/usr/bin/env python3|" {} \;
    find resources/python/bin -type f ! -name "*.py" -exec grep -l "^#!.*python" {} \; | while read script; do
        # Get the script name
        script_name=$(basename "$script")
        # Update shebang to use the script's own directory
        sed -i '' "1s|^#!.*|#!/usr/bin/env python3|" "$script"
    done
    
    # Ensure Python executable has correct permissions
    chmod +x resources/python/bin/python3
    
    # Make sure all scripts are executable
    find resources/python/bin -type f -exec chmod +x {} \;
    
    echo "✓ Python environment created and made portable"
else
    echo "✗ Python 3 not found. Please install Python 3.11+ first."
    echo "  Install via Homebrew: brew install python@3.12"
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
    
    # Copy system FFmpeg (or create symlink)
    cp $(which ffmpeg) resources/ffmpeg/ffmpeg
    chmod +x resources/ffmpeg/ffmpeg
    echo "✓ FFmpeg copied"
else
    echo "FFmpeg not found in PATH. Installing via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
        cp $(which ffmpeg) resources/ffmpeg/ffmpeg
        chmod +x resources/ffmpeg/ffmpeg
        echo "✓ FFmpeg installed and copied"
    else
        echo "✗ Homebrew not found. Please install FFmpeg manually:"
        echo "  1. Install Homebrew: https://brew.sh"
        echo "  2. Run: brew install ffmpeg"
        echo "  3. Or download from: https://evermeet.cx/ffmpeg/"
        exit 1
    fi
fi

echo ""
echo "=== Step 3: Verify Python venv ==="
# Ensure the venv is properly activated and yt-dlp is installed
if [ -f "resources/python/bin/python3" ]; then
    echo "Testing Python installation..."
    resources/python/bin/python3 -c "import yt_dlp; print('✓ yt-dlp is installed')" || {
        echo "✗ yt-dlp not found in venv, reinstalling..."
        resources/python/bin/pip install yt-dlp
    }
else
    echo "✗ Python venv not properly created"
    exit 1
fi

echo ""
echo "=== Summary ==="
if [ -f "resources/python/bin/python3" ] && [ -f "resources/ffmpeg/ffmpeg" ] && [ -f "resources/python/downloader.py" ]; then
    echo "✓ All dependencies ready for bundling!"
    echo "  Python: resources/python/bin/python3"
    echo "  FFmpeg: resources/ffmpeg/ffmpeg"
    echo "  Script: resources/python/downloader.py"
    echo ""
    echo "You can now run: pnpm electron:build:mac"
else
    echo "✗ Some dependencies are missing. Please complete the steps above."
    exit 1
fi
