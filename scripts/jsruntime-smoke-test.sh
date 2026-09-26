#!/bin/bash
set -euo pipefail

# Executes real JavaScript through a bundled JS runtime.
#
# `--version` only proves the binary can start. It does not prove the runtime
# can execute JS, which is what yt-dlp needs for YouTube's EJS challenges. On
# macOS a runtime signed with the Hardened Runtime but without
# com.apple.security.cs.allow-jit passes `--version` and then dies with
# "Failed to reserve virtual memory for CodeRange" on the first script.
#
# Usage: jsruntime-smoke-test.sh <runtime-path> [runtime-name]

RUNTIME_PATH="${1:-}"
RUNTIME_NAME="${2:-}"

if [ -z "$RUNTIME_PATH" ]; then
  echo "ERROR: JS runtime path is required" >&2
  exit 2
fi

if [ ! -x "$RUNTIME_PATH" ]; then
  echo "ERROR: JS runtime is not executable: $RUNTIME_PATH" >&2
  exit 1
fi

if [ -z "$RUNTIME_NAME" ]; then
  case "$(basename "$RUNTIME_PATH")" in
    deno*) RUNTIME_NAME="deno" ;;
    node*) RUNTIME_NAME="node" ;;
    *) RUNTIME_NAME="deno" ;;
  esac
fi

# Matches the argv shape yt-dlp's builtin EJS provider uses, so the probe fails
# for the same reasons real extraction would.
case "$RUNTIME_NAME" in
  deno)
    COMMAND=("$RUNTIME_PATH" run --ext=js --no-code-cache --no-prompt --no-remote
      --no-lock --node-modules-dir=none --no-config -)
    ;;
  node)
    COMMAND=("$RUNTIME_PATH" -)
    ;;
  *)
    echo "ERROR: unsupported JS runtime name: $RUNTIME_NAME" >&2
    exit 2
    ;;
esac

# Exercises the JIT path (a computed function call, not a constant fold) and
# asserts on the result, so a runtime that cannot execute JS fails the build.
PROBE='const add = (a, b) => a + b;
if (add(20, 22) !== 42) {
  throw new Error("unexpected result");
}
console.log("ytdl-jsruntime-ok");'

if OUTPUT="$("${COMMAND[@]}" <<<"$PROBE" 2>&1)"; then
  if printf '%s' "$OUTPUT" | grep -q "ytdl-jsruntime-ok"; then
    echo "OK: $RUNTIME_NAME executed JavaScript ($RUNTIME_PATH)"
    exit 0
  fi
  echo "ERROR: $RUNTIME_NAME ran without reporting the expected probe output" >&2
  echo "$OUTPUT" >&2
  exit 1
fi

echo "ERROR: $RUNTIME_NAME could not execute JavaScript ($RUNTIME_PATH)" >&2
echo "$OUTPUT" >&2
case "$RUNTIME_NAME" in
  deno)
    if printf '%s' "$OUTPUT" | grep -qi "reserve virtual memory"; then
      cat >&2 <<'EOF'
Hint: this is the macOS Hardened Runtime signature. The JS runtime is signed
with --options runtime but is missing com.apple.security.cs.allow-jit, so V8
cannot map its JIT code range and every script dies. Sign the bundled runtime
with the JIT entitlements (see scripts/bundle-dependencies-macos.sh).
EOF
    fi
    ;;
esac
exit 1
