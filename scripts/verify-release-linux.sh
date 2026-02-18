#!/bin/bash
set -euo pipefail

# Verifies Linux release artifacts produced by Tauri.

TARGET_ROOT="${1:-src-tauri/target}"
EXTRACT_DIR=""

cleanup() {
  if [[ -n "$EXTRACT_DIR" && -d "$EXTRACT_DIR" ]]; then
    rm -rf "$EXTRACT_DIR"
  fi
}
trap cleanup EXIT

find_latest_file() {
  local pattern="$1"
  find "$TARGET_ROOT" -type f -path "$pattern" -print | sort | tail -n 1
}

to_abs_path() {
  local path="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath "$path"
  else
    readlink -f "$path"
  fi
}

APPIMAGE="$(find_latest_file "*/bundle/appimage/*.AppImage" || true)"
DEB="$(find_latest_file "*/bundle/deb/*.deb" || true)"
RPM="$(find_latest_file "*/bundle/rpm/*.rpm" || true)"

if [[ -z "$APPIMAGE" || -z "$DEB" || -z "$RPM" ]]; then
  echo "ERROR: expected AppImage, deb, and rpm artifacts under $TARGET_ROOT"
  echo "AppImage: ${APPIMAGE:-missing}"
  echo "deb: ${DEB:-missing}"
  echo "rpm: ${RPM:-missing}"
  exit 1
fi

APPIMAGE="$(to_abs_path "$APPIMAGE")"
DEB="$(to_abs_path "$DEB")"
RPM="$(to_abs_path "$RPM")"

echo "Verifying AppImage: $APPIMAGE"
chmod +x "$APPIMAGE"
EXTRACT_DIR="$(mktemp -d)"
if ! (
  cd "$EXTRACT_DIR"
  "$APPIMAGE" --appimage-extract >/dev/null
  [[ -x "squashfs-root/AppRun" ]]
  [[ -f "squashfs-root/usr/share/metainfo/com.ytdownloader.app.metainfo.xml" ]]
); then
  echo "ERROR: AppImage extraction failed, AppRun is missing, or metainfo XML is missing"
  exit 1
fi

echo "Verifying deb package metadata: $DEB"
if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "ERROR: dpkg-deb is required but not found; install package 'dpkg' (or equivalent)."
  exit 1
fi
dpkg-deb --info "$DEB" >/dev/null
if ! dpkg-deb --contents "$DEB" | grep -qE '\.?/usr/bin/|\.?/usr/lib/|\.?/opt/'; then
  echo "ERROR: deb package does not contain expected install paths"
  exit 1
fi

echo "Verifying rpm package metadata: $RPM"
if ! command -v rpm >/dev/null 2>&1; then
  echo "ERROR: rpm is required but not found; install package 'rpm'."
  exit 1
fi
rpm -qpi "$RPM" >/dev/null
if ! rpm -qpl "$RPM" | grep -qE '/usr/bin/|/usr/lib/|/opt/'; then
  echo "ERROR: rpm package does not contain expected install paths"
  exit 1
fi

echo "Linux release verification passed."
