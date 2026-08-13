---
name: upgrade-ffmpeg-bundle
description: Pin or upgrade the bundled FFmpeg used by Linux and macOS bundling scripts. Use when the user asks to upgrade FFmpeg, pin to a specific release, or update the static FFmpeg download URLs/SHA256 in scripts/bundle-dependencies-linux.sh or scripts/bundle-dependencies-macos.sh.
---

# Upgrade FFmpeg bundle

## Scope

- **Linux**: [scripts/bundle-dependencies-linux.sh](scripts/bundle-dependencies-linux.sh) — downloads static build from yt-dlp/FFmpeg-Builds. Uses pinned release tag, archive base name, and SHA256.
- **macOS**: [scripts/bundle-dependencies-macos.sh](scripts/bundle-dependencies-macos.sh) — downloads static arm64 build from ffmpeg.martin-riedl.de. Uses pinned snapshot URL and SHA256.
- **Windows**: [scripts/bundle-dependencies-windows.ps1](scripts/bundle-dependencies-windows.ps1) — already pins gyan.dev URL + SHA256; same idea if upgrading.

## Linux (yt-dlp/FFmpeg-Builds)

1. Open [yt-dlp/FFmpeg-Builds releases](https://github.com/yt-dlp/FFmpeg-Builds/releases). Use an **immutable** tag (e.g. `autobuild-YYYY-MM-DD-HH-MM`), not `latest`.
2. From that release, get:
   - **Tag**: e.g. `autobuild-2026-02-13-14-51`
   - **Asset name**: the linux64 GPL tarball, e.g. `ffmpeg-N-122740-g0a629df0a8-linux64-gpl.tar.xz`. The **archive base** is the filename without `.tar.xz`.
   - **SHA256**: from the release’s `checksums.sha256` asset or the API `digest` for that asset.
3. In `scripts/bundle-dependencies-linux.sh`, update:
   - `FFMPEG_RELEASE_TAG` = chosen tag
   - `FFMPEG_ARCHIVE_BASE` = archive base (no extension)
   - `FFMPEG_SHA256` = SHA256 of the tarball
4. Update the `tar` line so the member path matches: `"${FFMPEG_ARCHIVE_BASE}/bin/ffmpeg"` (already correct if you only change the three variables above).

## macOS (martin-riedl.de)

1. Open [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) and find the latest **macOS arm64** snapshot (directory listing under `download/macos/arm64/`). Directory name format: `{timestamp}_{version}` e.g. `1770834055_N-122712-g7e3781e3ca`.
2. Download URL: `https://ffmpeg.martin-riedl.de/download/macos/arm64/{dir}/ffmpeg.zip`
3. Get SHA256 from `https://ffmpeg.martin-riedl.de/download/macos/arm64/{dir}/ffmpeg.zip.sha256` (format: `{hash}  ffmpeg.zip`).
4. In `scripts/bundle-dependencies-macos.sh`, set `FFMPEG_URL` and `FFMPEG_SHA256` to those values. No change to `unzip`/path if the zip still contains a single `ffmpeg` binary at root.

## After editing

- Run the bundling script for the platform you changed (e.g. `./scripts/bundle-dependencies-linux.sh` on Linux) and confirm it completes and `ffmpeg -version` passes.
- Optionally run the full build (e.g. `pnpm tauri build`) for that platform.

## Reference

Manual steps are also documented in [docs/upgrade-ffmpeg.md](docs/upgrade-ffmpeg.md).
