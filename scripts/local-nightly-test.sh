#!/usr/bin/env bash
# Local real-world download test (runs via launchd on residential IP).
# On failure, creates a GitHub issue in the repo.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$REPO_DIR/.local-nightly-test.log"

exec > "$LOG_FILE" 2>&1
echo "=== $(date) ==="

cd "$REPO_DIR"

# Ensure bundled python + yt-dlp exist; re-bundle if missing
PYTHON_DIR="$REPO_DIR/src-tauri/resources/python"
if [ ! -f "$PYTHON_DIR/bin/python3" ]; then
  echo "Bundled Python missing, running bundle script..."
  ./scripts/bundle-dependencies-macos.sh
fi

PYTHON="$PYTHON_DIR/bin/python3"
FFMPEG="$REPO_DIR/src-tauri/resources/ffmpeg/ffmpeg"

export RUN_REAL_WORLD_TESTS=1
export YT_DLP_ENABLE_BROWSER_COOKIES=false
[ -f "$FFMPEG" ] && export FFMPEG_PATH="$FFMPEG"

# Add gh to PATH (Homebrew on Apple Silicon)
export PATH="/opt/homebrew/bin:$PATH"

echo "Running real-world download tests..."
if "$PYTHON" -m pytest python/test_downloader_real_world.py -s -v 2>&1; then
  echo "All tests passed."
  exit 0
fi

echo "Tests failed — creating GitHub issue..."

DATE=$(date +%Y-%m-%d)
TITLE="Local nightly download test failed on $DATE"

# Check for duplicate open issue
EXISTING=$(gh issue list \
  --repo arpitdalal/yt-downloader \
  --label nightly-failure \
  --state open \
  --search "$TITLE" \
  --json title -q ".[].title" 2>/dev/null || true)

if echo "$EXISTING" | grep -qF "$TITLE"; then
  echo "Issue already exists, skipping."
  exit 1
fi

gh issue create \
  --repo arpitdalal/yt-downloader \
  --title "$TITLE" \
  --body "Real-world download test failed on local Mac (residential IP).

Check \`$LOG_FILE\` for details.

This likely means YouTube changed something and yt-dlp needs an update." \
  --label nightly-failure

exit 1
