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
PYTHON_RELEASE_TAG="20260211"
PYTHON_BUILD_VERSION="3.10.19+20260211"
PYTHON_ARCH="$(uname -m)"

case "$PYTHON_ARCH" in
  arm64 | aarch64)
    PYTHON_ARCHIVE_URL_NAME="cpython-${PYTHON_BUILD_VERSION//+/%2B}-aarch64-apple-darwin-install_only.tar.gz"
    PYTHON_SHA256="bd04a9a4e01142a16f6e471af8472d9253a558043af277039f0312c5876bcda2"
    ;;
  x86_64)
    PYTHON_ARCHIVE_URL_NAME="cpython-${PYTHON_BUILD_VERSION//+/%2B}-x86_64-apple-darwin-install_only.tar.gz"
    PYTHON_SHA256="ed919dd9b55e4f31e7e10ec0c56fa03d1438de2e97cf241431fcab9f2db557c7"
    ;;
  *)
    echo "Unsupported macOS architecture for bundled Python: $PYTHON_ARCH"
    exit 1
    ;;
esac

PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE_TAG}/${PYTHON_ARCHIVE_URL_NAME}"
curl -fSL -o python.tar.gz "$PYTHON_URL"
echo "$PYTHON_SHA256  python.tar.gz" | shasum -a 256 -c -
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
case "$PYTHON_ARCH" in
  arm64 | aarch64)
    FFMPEG_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/1766430132_8.0.1/ffmpeg.zip"
    FFMPEG_SHA256="c56f4e2b2ce26a61becf890d8da3415347a1d7d4418cb514915f21612358b790"
    ;;
  x86_64)
    FFMPEG_URL="https://ffmpeg.martin-riedl.de/download/macos/amd64/1766437297_8.0.1/ffmpeg.zip"
    FFMPEG_SHA256="a6c41c69e829697e408308f1ecd6acdfd0d0a84973ff3a6bf782beba83885ed6"
    ;;
  *)
    echo "Unsupported macOS architecture for bundled FFmpeg: $PYTHON_ARCH"
    exit 1
    ;;
esac

curl -fSL -o ffmpeg.zip "$FFMPEG_URL"
echo "$FFMPEG_SHA256  ffmpeg.zip" | shasum -a 256 -c -
unzip -o ffmpeg.zip -d "$FFMPEG_DIR"
chmod +x "$FFMPEG_DIR/ffmpeg"
rm -f ffmpeg.zip

"$FFMPEG_DIR/ffmpeg" -version >/dev/null 2>&1 || { echo "ERROR: bundled ffmpeg binary does not execute"; exit 1; }
echo "OK: FFmpeg bundled at $FFMPEG_DIR"

printf '\n=== Step 3: macOS code signing for bundled runtimes ===\n'
SIGNING_IDENTITY="${APPLE_SIGNING_IDENTITY:-}"
REQUIRE_SIGNED_BUNDLED_RUNTIMES="${REQUIRE_SIGNED_BUNDLED_RUNTIMES:-false}"
if [[ -z "$SIGNING_IDENTITY" ]]; then
  SIGNING_IDENTITY="$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:.*\)"/\1/p' | head -n 1 || true)"
fi

if [[ -n "$SIGNING_IDENTITY" ]]; then
  echo "Signing bundled runtime binaries with identity: $SIGNING_IDENTITY"
  while IFS= read -r candidate; do
    if file -b "$candidate" | grep -q "Mach-O"; then
      codesign --force --sign "$SIGNING_IDENTITY" --timestamp --options runtime "$candidate"
    fi
  done < <(find "$PYTHON_DIR" "$FFMPEG_DIR" -type f \( -perm -111 -o -name "*.dylib" -o -name "*.so" \) -print)
  echo "OK: bundled runtime binaries signed"
else
  if [[ "$REQUIRE_SIGNED_BUNDLED_RUNTIMES" == "true" ]]; then
    echo "ERROR: no Developer ID identity found; refusing unsigned bundled runtime binaries."
    exit 1
  fi
  echo "WARNING: no Developer ID identity found; bundled runtime binaries left unsigned"
fi

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
