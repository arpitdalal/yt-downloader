#!/bin/bash
set -euo pipefail

# Bundle Python + FFmpeg for Tauri (Linux)

RESOURCES_ROOT="src-tauri/resources"
PYTHON_DIR="$RESOURCES_ROOT/python"
FFMPEG_DIR="$RESOURCES_ROOT/ffmpeg"

printf '%s\n' "Bundling dependencies for Linux (Tauri resources)..."

if [[ "$OSTYPE" == darwin* ]]; then
  echo "WARNING: running Linux bundling script on macOS."
  echo "Generated Python/FFmpeg binaries will be macOS binaries."
  echo "Use a Linux runner for release artifacts. Exiting on macOS to avoid BSD/GNU tool incompatibilities."
  exit 1
fi

rm -rf "$PYTHON_DIR" "$FFMPEG_DIR"
mkdir -p "$PYTHON_DIR" "$FFMPEG_DIR"

printf '\n=== Step 1: Python ===\n'
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 not found. Install python3 python3-pip python3-venv."
  exit 1
fi

python3 -m venv --copies "$PYTHON_DIR"
"$PYTHON_DIR/bin/pip" install --upgrade pip
"$PYTHON_DIR/bin/pip" install -r python/requirements.txt

PYTHON_VERSION=$($PYTHON_DIR/bin/python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
PYTHON_DIR_ABS="$(cd "$PYTHON_DIR" && pwd)"
cat > "$PYTHON_DIR/pyvenv.cfg" <<PYVENV
home = $PYTHON_DIR_ABS/bin
include-system-site-packages = false
version = $PYTHON_VERSION
executable = bin/python3
PYVENV

find "$PYTHON_DIR/bin" -type f -name "*.py" -exec sed -i "1s|^#!.*python.*|#!/usr/bin/env python3|" {} \;
while IFS= read -r script; do
  sed -i "1s|^#!.*|#!/usr/bin/env python3|" "$script"
done < <(find "$PYTHON_DIR/bin" -type f ! -name "*.py" -exec grep -l "^#!.*python" {} + || true)

find "$PYTHON_DIR/bin" -type f \( -name "python*" -o -name "pip*" -o -name "*.py" \) -exec chmod +x {} \;
cp python/downloader.py "$PYTHON_DIR/downloader.py"

echo "OK: Python bundled at $PYTHON_DIR"

printf '\n=== Step 2: FFmpeg ===\n'
# Pinned release (yt-dlp/FFmpeg-Builds). Upgrade by choosing a newer autobuild-* tag and updating SHA + archive base.
FFMPEG_RELEASE_TAG="autobuild-2026-02-13-14-51"
FFMPEG_ARCHIVE_BASE="ffmpeg-N-122740-g0a629df0a8-linux64-gpl"
FFMPEG_SHA256="2b32e14dd5c79e69d4f932e4c5800910a25aa948416dcd7ea33c60d4926b595e"
FFMPEG_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/${FFMPEG_RELEASE_TAG}/${FFMPEG_ARCHIVE_BASE}.tar.xz"

curl -fSL -o ffmpeg.tar.xz "$FFMPEG_URL"
echo "$FFMPEG_SHA256  ffmpeg.tar.xz" | sha256sum -c -
tar -xf ffmpeg.tar.xz -C "$FFMPEG_DIR" --strip-components=2 "${FFMPEG_ARCHIVE_BASE}/bin/ffmpeg"
chmod +x "$FFMPEG_DIR/ffmpeg"
rm -f ffmpeg.tar.xz

"$FFMPEG_DIR/ffmpeg" -version >/dev/null 2>&1 || { echo "ERROR: bundled ffmpeg binary does not execute"; exit 1; }
echo "OK: FFmpeg bundled at $FFMPEG_DIR"

printf '\n=== Summary ===\n'
if [[ -f "$PYTHON_DIR/bin/python3" && -f "$PYTHON_DIR/downloader.py" && -f "$FFMPEG_DIR/ffmpeg" ]]; then
  echo "All dependencies bundled for Tauri."
  echo "Python: $PYTHON_DIR/bin/python3"
  echo "Script: $PYTHON_DIR/downloader.py"
  echo "FFmpeg: $FFMPEG_DIR/ffmpeg"
  echo "Next: pnpm tauri:build:linux"
else
  echo "Dependency bundling failed."
  exit 1
fi
