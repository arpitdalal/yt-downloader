#!/bin/bash
set -euo pipefail

# Verifies macOS release artifacts produced by Tauri.
# Fails if code signature, Gatekeeper policy, or notarization is invalid.

TARGET_ROOT="${1:-src-tauri/target}"
APP_PATH="${APP_PATH:-}"
REQUIRE_DEVELOPER_ID_SIGNATURE="${REQUIRE_DEVELOPER_ID_SIGNATURE:-true}"
REQUIRE_NOTARIZATION="${REQUIRE_NOTARIZATION:-true}"

if [[ -z "$APP_PATH" ]]; then
  APP_PATH="$(find "$TARGET_ROOT" -type d -path "*/bundle/macos/*.app" -print | sort | tail -n 1 || true)"
fi

if [[ -z "$APP_PATH" || ! -d "$APP_PATH" ]]; then
  echo "ERROR: macOS app bundle not found under $TARGET_ROOT"
  exit 1
fi

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
  xcrun stapler validate "$APP_PATH"
fi

echo "macOS release verification passed."
