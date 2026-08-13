#!/bin/bash
set -euo pipefail

# Bundle Python + FFmpeg for Tauri (Linux)

RESOURCES_ROOT="src-tauri/resources"
PYTHON_DIR="$RESOURCES_ROOT/python"
FFMPEG_DIR="$RESOURCES_ROOT/ffmpeg"
JSRUNTIME_DIR="$RESOURCES_ROOT/jsruntime"

printf '%s\n' "Bundling dependencies for Linux (Tauri resources)..."

if [[ "$OSTYPE" == darwin* ]]; then
  echo "WARNING: running Linux bundling script on macOS."
  echo "Generated Python/FFmpeg binaries will be macOS binaries."
  echo "Use a Linux runner for release artifacts. Exiting on macOS to avoid BSD/GNU tool incompatibilities."
  exit 1
fi

rm -rf "$PYTHON_DIR" "$FFMPEG_DIR" "$JSRUNTIME_DIR"
mkdir -p "$PYTHON_DIR" "$FFMPEG_DIR" "$JSRUNTIME_DIR"

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

# Remove unused GUI stdlib/extensions (Tk/IDLE) to avoid linuxdeploy
# resolving optional Tcl/Tk runtime dependencies that are irrelevant for yt-dlp.
PYTHON_STDLIB_TAG="$("$PYTHON_DIR/bin/python3" -c 'import sys; print("python%d.%d" % (sys.version_info.major, sys.version_info.minor))')"
PYTHON_STDLIB_DIR="$PYTHON_DIR/lib/$PYTHON_STDLIB_TAG"
for candidate in \
  "$PYTHON_STDLIB_DIR/tkinter" \
  "$PYTHON_STDLIB_DIR/idlelib"; do
  if [[ -e "$candidate" ]]; then
    rm -rf "$candidate"
  fi
done

find "$PYTHON_DIR/lib" -maxdepth 1 -type d \( -name "tcl[0-9]*" -o -name "tk[0-9]*" -o -name "itcl*" \) -exec rm -rf {} +
find "$PYTHON_DIR/lib" -type f \( -name "_tkinter*.so" -o -name "libtcl*.so*" -o -name "libtk*.so*" \) -delete
# python-build-standalone may include broken symlinks (for example, terminfo aliases);
# remove them so downstream packaging/tools don't fail on missing targets.
find -L "$PYTHON_DIR" -type l -delete

echo "OK: Python bundled at $PYTHON_DIR"

printf '\n=== Step 2: JS Runtime (Node.js) ===\n'
NODE_VERSION="v24.14.0"
case "$PYTHON_ARCH" in
  x86_64)
    NODE_ARCHIVE_NAME="node-${NODE_VERSION}-linux-x64.tar.xz"
    NODE_SHA256="41cd79bb7877c81605a9e68ec4c91547774f46a40c67a17e34d7179ef11729df"
    ;;
  aarch64 | arm64)
    NODE_ARCHIVE_NAME="node-${NODE_VERSION}-linux-arm64.tar.xz"
    NODE_SHA256="e7adfca03d9173276114a6f2219df1a7d25e1bfd6bbd771d3f839118a2053094"
    ;;
  *)
    echo "Unsupported Linux architecture for bundled Node.js: $PYTHON_ARCH"
    exit 1
    ;;
esac
NODE_URL="https://nodejs.org/dist/${NODE_VERSION}/${NODE_ARCHIVE_NAME}"
curl -fSL -o node.tar.xz "$NODE_URL"
echo "$NODE_SHA256  node.tar.xz" | sha256sum -c -
tar -xf node.tar.xz -C "$JSRUNTIME_DIR" --strip-components=2 "${NODE_ARCHIVE_NAME%.tar.xz}/bin/node"
chmod +x "$JSRUNTIME_DIR/node"
rm -f node.tar.xz

"$JSRUNTIME_DIR/node" --version >/dev/null 2>&1 || { echo "ERROR: bundled node binary does not execute"; exit 1; }
echo "OK: JS runtime bundled at $JSRUNTIME_DIR"

printf '\n=== Step 3: FFmpeg ===\n'
# Pinned release (yt-dlp/FFmpeg-Builds). Upgrade by choosing a newer autobuild-* tag and updating SHA + archive base.
FFMPEG_RELEASE_TAG="autobuild-2026-08-11-18-08"
case "$PYTHON_ARCH" in
  x86_64)
    FFMPEG_ARCHIVE_BASE="ffmpeg-N-126061-g844e10e1a7-linux64-gpl"
    FFMPEG_SHA256="722f3ccb2c9a63c4583aaf6300f6243562cfc5028ef88992c676afff45442c7e"
    ;;
  aarch64 | arm64)
    FFMPEG_ARCHIVE_BASE="ffmpeg-N-126061-g844e10e1a7-linuxarm64-gpl"
    FFMPEG_SHA256="2c88e67ab64618c3ed870a14cf29f0771230afb1352700062b9484ec33bdfe2a"
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
if [[ -f "$PYTHON_DIR/bin/python3" && -f "$PYTHON_DIR/downloader.py" && -f "$FFMPEG_DIR/ffmpeg" && -f "$JSRUNTIME_DIR/node" ]]; then
  echo "All dependencies bundled for Tauri."
  echo "Python: $PYTHON_DIR/bin/python3"
  echo "Script: $PYTHON_DIR/downloader.py"
  echo "JS runtime: $JSRUNTIME_DIR/node"
  echo "FFmpeg: $FFMPEG_DIR/ffmpeg"
  echo "Next: pnpm tauri:build:linux"
else
  echo "Dependency bundling failed."
  exit 1
fi
