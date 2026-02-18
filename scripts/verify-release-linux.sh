#!/bin/bash
set -euo pipefail

# Verifies Linux release artifacts produced by Tauri.

TARGET_ROOT="${1:-src-tauri/target}"
REQUIRE_RPM="${REQUIRE_RPM:-false}"
EXTRACT_DIR=""
DEB_CONTENTS_FILE=""
RPM_CONTENTS_FILE=""
PACKAGE_PATH_REGEX='(^|[[:space:]])(\.?/)?(usr/bin/|usr/lib/|opt/)'

cleanup() {
  if [[ -n "$EXTRACT_DIR" && -d "$EXTRACT_DIR" ]]; then
    rm -rf "$EXTRACT_DIR"
  fi
  if [[ -n "$DEB_CONTENTS_FILE" && -f "$DEB_CONTENTS_FILE" ]]; then
    rm -f "$DEB_CONTENTS_FILE"
  fi
  if [[ -n "$RPM_CONTENTS_FILE" && -f "$RPM_CONTENTS_FILE" ]]; then
    rm -f "$RPM_CONTENTS_FILE"
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

if [[ -z "$APPIMAGE" || -z "$DEB" ]]; then
  echo "ERROR: expected AppImage and deb artifacts under $TARGET_ROOT"
  echo "AppImage: ${APPIMAGE:-missing}"
  echo "deb: ${DEB:-missing}"
  if [[ "$REQUIRE_RPM" == "true" ]]; then
    echo "rpm: ${RPM:-missing}"
  fi
  exit 1
fi

if [[ "$REQUIRE_RPM" == "true" && -z "$RPM" ]]; then
  echo "ERROR: expected rpm artifact under $TARGET_ROOT"
  echo "rpm: missing"
  exit 1
fi

APPIMAGE="$(to_abs_path "$APPIMAGE")"
DEB="$(to_abs_path "$DEB")"
if [[ -n "$RPM" ]]; then
  RPM="$(to_abs_path "$RPM")"
fi

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
DEB_CONTENTS_FILE="$(mktemp)"
dpkg-deb --contents "$DEB" >"$DEB_CONTENTS_FILE"
if ! grep -qE "$PACKAGE_PATH_REGEX" "$DEB_CONTENTS_FILE"; then
  echo "ERROR: deb package does not contain expected install paths"
  echo "First 200 deb entries for debugging:"
  sed -n '1,200p' "$DEB_CONTENTS_FILE"
  exit 1
fi

if [[ "$REQUIRE_RPM" == "true" ]]; then
  echo "Verifying rpm package metadata: $RPM"
  if ! command -v rpm >/dev/null 2>&1; then
    echo "ERROR: rpm is required but not found; install package 'rpm'."
    exit 1
  fi
  rpm -qpi "$RPM" >/dev/null
  RPM_CONTENTS_FILE="$(mktemp)"
  rpm -qpl "$RPM" >"$RPM_CONTENTS_FILE"
  if ! grep -qE "$PACKAGE_PATH_REGEX" "$RPM_CONTENTS_FILE"; then
    echo "ERROR: rpm package does not contain expected install paths"
    echo "First 200 rpm entries for debugging:"
    sed -n '1,200p' "$RPM_CONTENTS_FILE"
    exit 1
  fi
else
  echo "Skipping rpm verification (REQUIRE_RPM=$REQUIRE_RPM)."
fi

echo "Linux release verification passed."
