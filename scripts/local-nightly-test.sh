#!/usr/bin/env bash
# Local real-world download test (runs via launchd on residential IP).
# On failure, creates a GitHub issue in the repo.
# On success, closes any open nightly-failure issues.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$REPO_DIR/.local-nightly-test.log"
GH_REPO="arpitdalal/yt-downloader"

exec > "$LOG_FILE" 2>&1
echo "=== $(date) ==="

cd "$REPO_DIR"

# Ensure bundled python exists; full re-bundle only when missing
PYTHON_DIR="$REPO_DIR/src-tauri/resources/python"
if [ ! -f "$PYTHON_DIR/bin/python3" ]; then
  echo "Bundled Python missing, running bundle script..."
  ./scripts/bundle-dependencies-macos.sh
fi

PYTHON="$PYTHON_DIR/bin/python3"
FFMPEG="$REPO_DIR/src-tauri/resources/ffmpeg/ffmpeg"

# Keep bundled yt-dlp/pytest aligned with requirements.txt (avoids stale runtime)
echo "Syncing bundled Python dependencies from requirements.txt..."
"$PYTHON" -m pip install -q -r "$REPO_DIR/python/requirements.txt"
cp "$REPO_DIR/python/downloader.py" "$PYTHON_DIR/downloader.py"
echo "Bundled yt-dlp: $("$PYTHON" -m pip show yt-dlp | awk '/^Version:/{print $2}')"

export RUN_REAL_WORLD_TESTS=1
export YT_DLP_ENABLE_BROWSER_COOKIES=false
[ -f "$FFMPEG" ] && export FFMPEG_PATH="$FFMPEG"

# Add gh to PATH (Homebrew on Apple Silicon)
export PATH="/opt/homebrew/bin:$PATH"

close_nightly_failure_issues() {
  local issue_numbers
  issue_numbers=$(gh issue list \
    --repo "$GH_REPO" \
    --label nightly-failure \
    --state open \
    --json number -q '.[].number' 2>/dev/null || true)

  if [ -z "$issue_numbers" ]; then
    echo "No open nightly-failure issues to close."
    return 0
  fi

  local closed=0
  for issue_number in $issue_numbers; do
    gh issue close "$issue_number" \
      --repo "$GH_REPO" \
      --comment "Auto-closed: real-world download tests passed on $(date +%Y-%m-%d)." \
      >/dev/null
    echo "Closed issue #$issue_number"
    closed=$((closed + 1))
  done
  echo "Closed $closed nightly-failure issue(s)."
}

echo "Running real-world download tests..."
if "$PYTHON" -m pytest python/test_downloader_real_world.py -s -v 2>&1; then
  echo "All tests passed."
  close_nightly_failure_issues
  exit 0
fi

echo "Tests failed — creating GitHub issue..."

DATE=$(date +%Y-%m-%d)
TITLE="Local nightly download test failed on $DATE"

# Check for duplicate open issue
EXISTING=$(gh issue list \
  --repo "$GH_REPO" \
  --label nightly-failure \
  --state open \
  --search "$TITLE" \
  --json title -q ".[].title" 2>/dev/null || true)

if echo "$EXISTING" | grep -qF "$TITLE"; then
  echo "Issue already exists, skipping."
  exit 1
fi

gh issue create \
  --repo "$GH_REPO" \
  --title "$TITLE" \
  --body "Real-world download test failed on local Mac (residential IP).

Check \`$LOG_FILE\` for details.

This likely means YouTube changed something and yt-dlp needs an update." \
  --label nightly-failure

exit 1
