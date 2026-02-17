#!/bin/bash
set -euo pipefail

# Verifies Linux release artifacts produced by Tauri.

TARGET_ROOT="${1:-src-tauri/target}"

find_latest_file() {
  local pattern="$1"
  find "$TARGET_ROOT" -type f -path "$pattern" -print | sort | tail -n 1
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

echo "Verifying AppImage: $APPIMAGE"
chmod +x "$APPIMAGE"
TMPDIR="$(mktemp -d)"
if ! (
  cd "$TMPDIR"
  "$APPIMAGE" --appimage-extract >/dev/null
  [[ -x "squashfs-root/AppRun" ]]
); then
  echo "ERROR: AppImage extraction failed or AppRun is missing"
  rm -rf "$TMPDIR"
  exit 1
fi
rm -rf "$TMPDIR"

echo "Verifying deb package metadata: $DEB"
dpkg-deb --info "$DEB" >/dev/null
if ! dpkg-deb --contents "$DEB" | grep -qE '\.*/usr/bin/|\.*/opt/'; then
  echo "ERROR: deb package does not contain expected install paths"
  exit 1
fi

echo "Verifying rpm package metadata: $RPM"
rpm -qpi "$RPM" >/dev/null
if ! rpm -qpl "$RPM" | grep -qE '/usr/bin/|/opt/'; then
  echo "ERROR: rpm package does not contain expected install paths"
  exit 1
fi

echo "Linux release verification passed."
