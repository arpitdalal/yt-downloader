#!/bin/bash
set -euo pipefail

# Verifies macOS release artifacts produced by Tauri.
# Fails if code signature, Gatekeeper policy, or notarization is invalid.

TARGET_ROOT="${1:-src-tauri/target}"
APP_PATH="${APP_PATH:-}"
DMG_PATH="${DMG_PATH:-}"
REQUIRE_DEVELOPER_ID_SIGNATURE="${REQUIRE_DEVELOPER_ID_SIGNATURE:-true}"
REQUIRE_NOTARIZATION="${REQUIRE_NOTARIZATION:-true}"
MOUNT_DIR=""

cleanup() {
  if [[ -n "$MOUNT_DIR" && -d "$MOUNT_DIR" ]]; then
    hdiutil detach "$MOUNT_DIR" -force >/dev/null 2>&1 || true
    rmdir "$MOUNT_DIR" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ -z "$APP_PATH" ]]; then
  APP_PATH="$(find "$TARGET_ROOT" -type d -path "*/bundle/macos/*.app" -print | sort | tail -n 1 || true)"
fi

if [[ -z "$APP_PATH" || ! -d "$APP_PATH" ]]; then
  if [[ -z "$DMG_PATH" ]]; then
    DMG_PATH="$(find "$TARGET_ROOT" -type f -path "*/bundle/dmg/*.dmg" -print | sort | tail -n 1 || true)"
  fi

  if [[ -n "$DMG_PATH" && -f "$DMG_PATH" ]]; then
    MOUNT_DIR="$(mktemp -d /tmp/ytdmg.XXXXXX)"
    if hdiutil attach "$DMG_PATH" -nobrowse -readonly -mountpoint "$MOUNT_DIR" >/dev/null 2>&1; then
      APP_PATH="$(find "$MOUNT_DIR" -maxdepth 2 -type d -name "*.app" -print | sort | tail -n 1 || true)"
    else
      echo "WARNING: failed to mount DMG: $DMG_PATH"
    fi
  fi
fi

if [[ -z "$APP_PATH" || ! -d "$APP_PATH" ]]; then
  echo "ERROR: macOS app bundle not found under $TARGET_ROOT"
  echo "App path checked: ${APP_PATH:-missing}"
  echo "DMG path checked: ${DMG_PATH:-missing}"
  exit 1
fi

UPDATER_ARCHIVE="$(find "$TARGET_ROOT" -type f -path "*/bundle/macos/*.app.tar.gz" -print | sort | tail -n 1 || true)"
if [[ -z "$UPDATER_ARCHIVE" || ! -s "$UPDATER_ARCHIVE" ]]; then
  echo "ERROR: macOS updater archive not found under $TARGET_ROOT"
  echo "Expected a non-empty */bundle/macos/*.app.tar.gz (requires --bundles app)"
  exit 1
fi
if [[ ! -s "${UPDATER_ARCHIVE}.sig" ]]; then
  echo "ERROR: missing updater signature: ${UPDATER_ARCHIVE}.sig"
  exit 1
fi
echo "Found updater archive: $UPDATER_ARCHIVE"

echo "Verifying code signature on: $APP_PATH"
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

SIGN_INFO="$(codesign -dv --verbose=4 "$APP_PATH" 2>&1 || true)"
echo "$SIGN_INFO" | awk -F= '/^(Identifier|Signature|TeamIdentifier)=/ { print $1 "=" $2 }'

SIGNATURE_KIND="$(echo "$SIGN_INFO" | awk -F= '/^Signature=/{print $2}')"
TEAM_ID="$(echo "$SIGN_INFO" | awk -F= '/^TeamIdentifier=/{print $2}')"

if [[ "$REQUIRE_DEVELOPER_ID_SIGNATURE" == "true" ]]; then
  if [[ -z "$TEAM_ID" || "$TEAM_ID" == "not set" || "$SIGNATURE_KIND" == "adhoc" ]]; then
    echo "ERROR: app is not signed with Developer ID certificate."
    exit 1
  fi
fi

echo "Verifying Gatekeeper assessment"
spctl --assess --type exec --verbose=4 "$APP_PATH"

if [[ "$REQUIRE_NOTARIZATION" == "true" ]]; then
  echo "Verifying notarization ticket (stapler)"
  # Tauri notarizes/staples the app bundle before DMG creation.
  # Validate the app ticket from the resolved bundle path.
  xcrun stapler validate "$APP_PATH"
fi

echo "macOS release verification passed."
