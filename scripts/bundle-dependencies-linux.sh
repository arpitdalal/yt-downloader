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
PYTHON_RELEASE_TAG="20260211"
PYTHON_BUILD_VERSION="3.10.19+20260211"
PYTHON_ARCH="$(uname -m)"

case "$PYTHON_ARCH" in
  x86_64)
    PYTHON_ARCHIVE_URL_NAME="cpython-${PYTHON_BUILD_VERSION//+/%2B}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    PYTHON_SHA256="0e16ab6f0f966475ae907e739dbc2001e97b9bdd6c9e3ee9233b76c0fcf34c2c"
    ;;
  aarch64 | arm64)
    PYTHON_ARCHIVE_URL_NAME="cpython-${PYTHON_BUILD_VERSION//+/%2B}-aarch64-unknown-linux-gnu-install_only.tar.gz"
    PYTHON_SHA256="9e54900384bbd516e45ade18885735126d0f2f4de4be35558969eb17f37ecd72"
    ;;
  *)
    echo "Unsupported Linux architecture for bundled Python: $PYTHON_ARCH"
    exit 1
    ;;
esac

PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE_TAG}/${PYTHON_ARCHIVE_URL_NAME}"
curl -fSL -o python.tar.gz "$PYTHON_URL"
echo "$PYTHON_SHA256  python.tar.gz" | sha256sum -c -
tar -xzf python.tar.gz -C "$RESOURCES_ROOT"
rm -f python.tar.gz

if [[ ! -x "$PYTHON_DIR/bin/python3" ]]; then
  echo "ERROR: bundled Python executable missing at $PYTHON_DIR/bin/python3"
  exit 1
fi

echo "Using bundled Python: $("$PYTHON_DIR/bin/python3" --version 2>&1)"
"$PYTHON_DIR/bin/python3" -m pip install --upgrade pip
"$PYTHON_DIR/bin/python3" -m pip install -r python/requirements.txt

cp python/downloader.py "$PYTHON_DIR/downloader.py"

echo "OK: Python bundled at $PYTHON_DIR"

printf '\n=== Step 2: FFmpeg ===\n'
# Pinned release (yt-dlp/FFmpeg-Builds). Upgrade by choosing a newer autobuild-* tag and updating SHA + archive base.
FFMPEG_RELEASE_TAG="autobuild-2026-02-13-14-51"
case "$PYTHON_ARCH" in
  x86_64)
    FFMPEG_ARCHIVE_BASE="ffmpeg-N-122740-g0a629df0a8-linux64-gpl"
    FFMPEG_SHA256="2b32e14dd5c79e69d4f932e4c5800910a25aa948416dcd7ea33c60d4926b595e"
    ;;
  aarch64 | arm64)
    FFMPEG_ARCHIVE_BASE="ffmpeg-N-122740-g0a629df0a8-linuxarm64-gpl"
    FFMPEG_SHA256="79c3dec8f707e59a0be469dbd2ba6967a1bd63ff91a38d210a4e169d81a1eae3"
    ;;
  *)
    echo "Unsupported Linux architecture for bundled FFmpeg: $PYTHON_ARCH"
    exit 1
    ;;
esac
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
