# Manually upgrading bundled FFmpeg

The app bundles a **static** FFmpeg binary for Linux and macOS so it runs without system libraries. This doc describes how to manually upgrade or re-pin that bundle.

- **Linux**: script downloads from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases).
- **macOS**: script downloads from [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) (arm64 static builds).
- **Windows**: script downloads from gyan.dev (see [scripts/bundle-dependencies-windows.ps1](../scripts/bundle-dependencies-windows.ps1)); same idea below.

---

## Linux

**File:** `scripts/bundle-dependencies-linux.sh`

1. Go to [yt-dlp/FFmpeg-Builds releases](https://github.com/yt-dlp/FFmpeg-Builds/releases).
2. Pick an **immutable** release tag (e.g. `autobuild-2026-02-13-14-51`). Do **not** use the `latest` tag for pinning, as it changes and would break the fixed SHA256.
3. In that release, find the Linux x64 GPL tarball, e.g.:
   - `ffmpeg-N-122740-g0a629df0a8-linux64-gpl.tar.xz`
4. Get its SHA256:
   - Either download the release’s `checksums.sha256` and find the line for that file, or
   - Use the GitHub API / UI to read the asset’s checksum.
5. Edit the script and set:
   - `FFMPEG_RELEASE_TAG` = the chosen tag (e.g. `autobuild-2026-02-13-14-51`)
   - `FFMPEG_ARCHIVE_BASE` = the tarball name **without** `.tar.xz` (e.g. `ffmpeg-N-122740-g0a629df0a8-linux64-gpl`)
   - `FFMPEG_SHA256` = the SHA256 from step 4.
6. The `tar` command already uses `"${FFMPEG_ARCHIVE_BASE}/bin/ffmpeg"`; no change needed if the archive layout stays the same.
7. Run on a Linux machine (or CI):
   ```bash
   ./scripts/bundle-dependencies-linux.sh
   ```
   Then run a Linux build to confirm.

---

## macOS

**File:** `scripts/bundle-dependencies-macos.sh`

1. Open [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) and go to the **macOS arm64** section.
2. Find the latest snapshot directory. Format: `{timestamp}_{version}` (e.g. `1770834055_N-122712-g7e3781e3ca`). The base URL is:
   ```text
   https://ffmpeg.martin-riedl.de/download/macos/arm64/{directory}/
   ```
3. Download the checksum file:
   ```text
   https://ffmpeg.martin-riedl.de/download/macos/arm64/{directory}/ffmpeg.zip.sha256
   ```
   It contains one line: `{sha256}  ffmpeg.zip`.
4. Edit the script and set:
   - `FFMPEG_URL` = `https://ffmpeg.martin-riedl.de/download/macos/arm64/{directory}/ffmpeg.zip`
   - `FFMPEG_SHA256` = the 64-character SHA256 from the `.sha256` file.
5. Run on a Mac (arm64 for release):
   ```bash
   ./scripts/bundle-dependencies-macos.sh
   ```
   Then run a macOS build to confirm.

---

## Windows

**File:** `scripts/bundle-dependencies-windows.ps1`

The script uses a fixed URL and `$expectedFfmpegZipHash`. To upgrade:

1. Choose a new [gyan.dev FFmpeg essentials build](https://www.gyan.dev/ffmpeg/builds/) (or the same URL pattern).
2. Download the zip and compute its SHA256 (e.g. `Get-FileHash -Path ffmpeg.zip -Algorithm SHA256` in PowerShell).
3. Update `$ffmpegUrl` and `$expectedFfmpegZipHash` in the script.
4. Run the script and then a Windows build to confirm.

---

## Why pin a specific release?

- **Linux**: The `latest` tag on yt-dlp/FFmpeg-Builds is updated on every new build. The script verifies the download with SHA256; if the file at `latest` changes, the hash no longer matches and the script fails. Pinning to an immutable `autobuild-*` tag keeps the URL and SHA256 in sync until you decide to upgrade.
- **macOS**: Snapshot URLs are already immutable; you only change them when you want a newer FFmpeg.
