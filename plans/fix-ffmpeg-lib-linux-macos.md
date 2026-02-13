---
name: Fix ffmpeg bundling portability
overview: Replace `cp $(which ffmpeg)` in Linux/macOS bundling scripts with downloading pre-built static ffmpeg binaries (mirroring the Windows pattern), so the app ships a self-contained ffmpeg that works on any target machine.
todos:
  - id: linux-script
    content: Rewrite ffmpeg section of bundle-dependencies-linux.sh to download static build from yt-dlp/FFmpeg-Builds with SHA-256 verification
    status: completed
  - id: macos-script
    content: Rewrite ffmpeg section of bundle-dependencies-macos.sh to download static arm64 build from martin-riedl.de with SHA-256 verification
    status: completed
  - id: ci-gate
    content: Remove ffmpeg from apt-get install in tauri-gate.yml Linux job
    status: completed
  - id: ci-release
    content: Remove ffmpeg from apt-get install in tauri-release.yml Linux job
    status: completed
  - id: validation
    content: Add post-download ffmpeg -version sanity check in both scripts
    status: completed
isProject: false
---

# Fix ffmpeg shared-library bundling for Linux and macOS

## Root cause

`[bundle-dependencies-linux.sh](scripts/bundle-dependencies-linux.sh)` and `[bundle-dependencies-macos.sh](scripts/bundle-dependencies-macos.sh)` both do `cp "$(which ffmpeg)"` which copies only the executable. If dynamically linked, the required `.so`/`.dylib` files are missing on the target machine and ffmpeg fails at runtime.

## Approach

Mirror the Windows script pattern: **download a pre-built, statically linked ffmpeg binary** from a trusted source, verify SHA-256, extract, and bundle. No runtime Rust code or Tauri config changes needed.

### Sources per platform

| Platform         | Source                                                                            | Notes                                                                                       |
| ---------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Linux x86_64** | [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases) (GitHub) | Fork of BtbN; provides static GPL builds with yt-dlp patches. Pin a specific autobuild tag. |
| **macOS arm64**  | [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/)                         | Provides static arm64 macOS builds with SHA-256 checksums. Pin a specific snapshot URL.     |
| **Windows**      | **No change** (already downloads from gyan.dev)                                   | Already self-contained.                                                                     |

**Why these sources:**

- Linux: yt-dlp/FFmpeg-Builds is ideal -- maintained by the yt-dlp project (which this app uses), GitHub-hosted, static, and includes yt-dlp-specific patches.
- macOS: evermeet.cx does NOT offer native ARM64 builds (Intel only). martin-riedl.de is the only source providing static ARM64 macOS builds with SHA-256 verification. Builds run daily since 2021.
- If martin-riedl.de ever becomes unavailable, fallback is to use `dylibbundler` (via Homebrew) to copy Homebrew ffmpeg's dylibs and rewrite load paths with `@loader_path`. This keeps native ARM64 and avoids depending on an external build service.

### Size impact

- **Windows**: unchanged.
- **Linux**: binary grows from ~5 MB (broken dynamic) to ~70 MB (working static). The dynamic binary was never functional standalone, so there is no real regression -- just the cost of correctness.
- **macOS**: similar to Linux.
- The compressed app archive increase is smaller due to xz/gz compression on the static binary.

## Changes

### 1. `[scripts/bundle-dependencies-linux.sh](scripts/bundle-dependencies-linux.sh)` -- Step 2 rewrite

Replace the current ffmpeg section (lines 56-63) with:

```bash
FFMPEG_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/<pinned-tag>/ffmpeg-master-latest-linux64-gpl.tar.xz"
FFMPEG_SHA256="<sha256-of-archive>"

curl -fSL -o ffmpeg.tar.xz "$FFMPEG_URL"
echo "$FFMPEG_SHA256  ffmpeg.tar.xz" | sha256sum -c -
tar -xf ffmpeg.tar.xz --strip-components=2 -C "$FFMPEG_DIR" --wildcards '*/bin/ffmpeg'
chmod +x "$FFMPEG_DIR/ffmpeg"
rm -f ffmpeg.tar.xz
```

- Remove the `command -v ffmpeg` check and system-install fallback.
- Add `curl` to any CI prerequisite install if not present (it is on Ubuntu runners by default).

### 2. `[scripts/bundle-dependencies-macos.sh](scripts/bundle-dependencies-macos.sh)` -- Step 2 rewrite

Replace lines 49-61 with:

```bash
FFMPEG_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/<pinned-snapshot>/ffmpeg.zip"
FFMPEG_SHA256="<sha256-of-zip>"

curl -fSL -o ffmpeg.zip "$FFMPEG_URL"
echo "$FFMPEG_SHA256  ffmpeg.zip" | shasum -a 256 -c -
unzip -o ffmpeg.zip -d "$FFMPEG_DIR"
chmod +x "$FFMPEG_DIR/ffmpeg"
rm -f ffmpeg.zip
```

- Remove `brew install ffmpeg` fallback.
- No `dylibbundler` needed since the downloaded binary is statically linked.

### 3. CI workflows -- remove system ffmpeg install

`**[.github/workflows/tauri-gate.yml](/.github/workflows/tauri-gate.yml)**` (line 44): Remove `ffmpeg` from the `apt-get install` list for Linux. macOS doesn't install it via apt, so no change there.

`**[.github/workflows/tauri-release.yml](/.github/workflows/tauri-release.yml)**` (line 112): Same -- remove `ffmpeg` from `apt-get install` for the Linux release job.

### 4. `[scripts/prebuild.js](scripts/prebuild.js)` -- no change needed

Already checks for the presence of `ffmpeg` in the resources dir. No structural changes.

### 5. Rust runtime code -- no change needed

`get_ffmpeg_path()` in `[src-tauri/src/lib.rs](src-tauri/src/lib.rs)` resolves to `resource_dir/ffmpeg/ffmpeg` and passes it to Python. Static binary works identically. Tauri's resource bundling config (`"resources/ffmpeg": "ffmpeg"`) copies the entire directory, so the structure is preserved.

### 6. Post-download validation (both scripts)

Add a quick sanity check after extraction:

```bash
"$FFMPEG_DIR/ffmpeg" -version >/dev/null 2>&1 || { echo "ERROR: bundled ffmpeg binary does not execute"; exit 1; }
```

This catches corrupt downloads, wrong-arch binaries, or missing dynamic deps (should never happen with static builds, but defense in depth).

## What is NOT changing

- Windows bundling script (already correct)
- Tauri config (`tauri.conf.json`)
- Rust runtime code (`lib.rs`)
- Python downloader script
- `prebuild.js` validation
