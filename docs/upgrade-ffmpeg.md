# Manually upgrading bundled FFmpeg

The app bundles a **static** FFmpeg binary for Linux and macOS so it runs without system libraries. This doc describes how to manually upgrade or re-pin that bundle.

- **Linux**: script downloads from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases).
- **macOS**: script downloads from [ffmpeg.martin-riedl.de](https://ffmpeg.martin-riedl.de/) (arm64 static builds).
- **Windows**: script downloads from [yt-dlp/FFmpeg-Builds](https://github.com/yt-dlp/FFmpeg-Builds/releases) using a pinned release asset.

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

1. Go to [yt-dlp/FFmpeg-Builds releases](https://github.com/yt-dlp/FFmpeg-Builds/releases).
2. Pick an **immutable** release tag (e.g. `autobuild-2026-03-31-15-13`). Do **not** use the mutable `latest` tag for pinning.
3. In that release, find the Windows x64 GPL zip, e.g.:
   - `ffmpeg-N-123778-g3b55818764-win64-gpl.zip`
4. Get its SHA256 from the asset digest or by downloading it and running:
   ```powershell
   Get-FileHash -Path ffmpeg.zip -Algorithm SHA256
   ```
5. Edit the script and set:
   - `$ffmpegReleaseTag` = chosen immutable tag
   - `$ffmpegArchiveName` = chosen zip filename
   - `$expectedFfmpegZipHash` = SHA256 from step 4
6. Run the script and then a Windows build to confirm.

---

## Why pin a specific release?

- **Linux**: The `latest` tag on yt-dlp/FFmpeg-Builds is updated on every new build. The script verifies the download with SHA256; if the file at `latest` changes, the hash no longer matches and the script fails. Pinning to an immutable `autobuild-*` tag keeps the URL and SHA256 in sync until you decide to upgrade.
- **macOS**: Snapshot URLs are already immutable; you only change them when you want a newer FFmpeg.
