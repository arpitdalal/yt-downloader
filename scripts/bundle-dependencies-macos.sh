#!/bin/bash
set -euo pipefail

# Bundle Python + FFmpeg for Tauri (macOS)

RESOURCES_ROOT="src-tauri/resources"
PYTHON_DIR="$RESOURCES_ROOT/python"
FFMPEG_DIR="$RESOURCES_ROOT/ffmpeg"

printf '%s\n' "Bundling dependencies for macOS (Tauri resources)..."

rm -rf "$PYTHON_DIR" "$FFMPEG_DIR"
mkdir -p "$PYTHON_DIR" "$FFMPEG_DIR"

printf '\n=== Step 1: Python ===\n'
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install Python 3.11+ first."
  echo "Homebrew: brew install python@3.12"
  exit 1
fi

python3 -m venv --copies "$PYTHON_DIR"
"$PYTHON_DIR/bin/pip" install --upgrade pip
"$PYTHON_DIR/bin/pip" install -r python/requirements.txt

PYTHON_VERSION=$($PYTHON_DIR/bin/python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
cat > "$PYTHON_DIR/pyvenv.cfg" <<PYVENV
home = bin
include-system-site-packages = false
version = $PYTHON_VERSION
executable = bin/python3
PYVENV

find "$PYTHON_DIR/bin" -type f -name "*.py" -exec sed -i '' "1s|^#!.*python.*|#!/usr/bin/env python3|" {} \;
find "$PYTHON_DIR/bin" -type f ! -name "*.py" -exec grep -l "^#!.*python" {} \; | while read -r script; do
  sed -i '' "1s|^#!.*|#!/usr/bin/env python3|" "$script"
done

chmod +x "$PYTHON_DIR/bin/python3"
find "$PYTHON_DIR/bin" -type f -exec chmod +x {} \;
cp python/downloader.py "$PYTHON_DIR/downloader.py"

echo "OK: Python bundled at $PYTHON_DIR"

printf '\n=== Step 2: FFmpeg ===\n'
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "FFmpeg not found and Homebrew unavailable."
    exit 1
  fi
fi

cp "$(which ffmpeg)" "$FFMPEG_DIR/ffmpeg"
chmod +x "$FFMPEG_DIR/ffmpeg"

echo "OK: FFmpeg bundled at $FFMPEG_DIR"

printf '\n=== Summary ===\n'
if [[ -f "$PYTHON_DIR/bin/python3" && -f "$PYTHON_DIR/downloader.py" && -f "$FFMPEG_DIR/ffmpeg" ]]; then
  echo "All dependencies bundled for Tauri."
  echo "Python: $PYTHON_DIR/bin/python3"
  echo "Script: $PYTHON_DIR/downloader.py"
  echo "FFmpeg: $FFMPEG_DIR/ffmpeg"
  echo "Next: pnpm tauri:build:mac"
else
  echo "Dependency bundling failed."
  exit 1
fi
