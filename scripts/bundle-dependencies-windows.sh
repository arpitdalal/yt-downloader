#!/bin/bash
set -euo pipefail

# Bundle Python + FFmpeg for Tauri (Windows via Git Bash)

RESOURCES_ROOT="src-tauri/resources"
PYTHON_DIR="$RESOURCES_ROOT/python"
FFMPEG_DIR="$RESOURCES_ROOT/ffmpeg"

echo "Bundling dependencies for Windows (Tauri resources)..."
rm -rf "$PYTHON_DIR" "$FFMPEG_DIR"
mkdir -p "$PYTHON_DIR" "$FFMPEG_DIR"

echo ""
echo "Use PowerShell script for full automation:"
echo "  ./scripts/bundle-dependencies-windows.ps1"
echo ""
echo "If bundling manually, place files here:"
echo "  $PYTHON_DIR/python.exe"
echo "  $PYTHON_DIR/downloader.py"
echo "  $FFMPEG_DIR/ffmpeg.exe"

echo ""
echo "Summary"
if [[ -f "$PYTHON_DIR/python.exe" && -f "$PYTHON_DIR/downloader.py" && -f "$FFMPEG_DIR/ffmpeg.exe" ]]; then
  echo "All dependencies ready for Tauri build."
  echo "Next: pnpm tauri:build:win"
else
  echo "Dependencies are not fully bundled yet."
fi
