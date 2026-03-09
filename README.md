# YouTube Video Downloader

Desktop app (Tauri v2 + React + Python yt-dlp) for downloading YouTube videos or processing local videos with section cutting/concat.

## Features

- YouTube download
- Local file processing
- Multiple sections with ordering validation
- Real-time progress updates
- Save/open native dialogs
- Cancel active work
- macOS, Windows, Linux support

## Stack

- Frontend: React 19, TypeScript, Tailwind CSS 4, Vite 6
- Desktop runtime: Tauri v2 (Rust)
- Download/processing engine: Python 3 + yt-dlp + FFmpeg

## Prerequisites

- Node.js 20+
- pnpm
- Rust toolchain (cargo/rustc)
- Python 3.11+
- FFmpeg (for development)

## Local Setup

```bash
pnpm install
pnpm python:install
```

## Development

```bash
pnpm tauri:dev
```

## Build

Bundle runtime dependencies first:

```bash
# macOS
./scripts/bundle-dependencies-macos.sh

# Linux
./scripts/bundle-dependencies-linux.sh

# Windows (PowerShell)
./scripts/bundle-dependencies-windows.ps1
```

Then build:

```bash
# current platform
pnpm tauri:build

# platform-specific targets
pnpm tauri:build:mac
pnpm tauri:build:win
pnpm tauri:build:linux
```

For downloadable macOS releases, use Developer ID signing + notarization. Unsigned/unnotarized DMGs are blocked by Gatekeeper.

## YouTube Auth / Quality

- App uses yt-dlp’s `--cookies-from-browser` at extract/download time (no cookie file sync).
- App applies yt-dlp `-t mp4` preset behavior for compatibility-first best quality:
  - base selector remains adaptive best-first (`bestvideo*+bestaudio/best`)
  - downloads are merged/remuxed to `.mp4` when possible
  - stream sorting prefers H.264 video + AAC audio for broad playback support
- MP4-compatible fallback selectors are tried before any low-quality fallback.
- App can enable yt-dlp `fetch_pot` when a JS runtime is available (macOS bundles Deno; Linux/Windows bundle Node.js).
- UI provides cookie-source controls:
  - Global default (`Auto` or specific browser profile), persisted in localStorage
  - Per-download one-off override (`Use app default`, `Auto`, or specific source); resets after submit or cancel
  - Refresh source discovery
  - Stale selection handling: if the chosen source is no longer in the list (e.g. after refresh), global default and per-download override are reset to Auto / Use app default
- Cookie source discovery/probing is cross-platform and profile-aware (macOS/Windows/Linux).
- App sends explicit source selection to Python via `YT_DLP_COOKIE_SOURCES_JSON` + `YT_DLP_COOKIE_SELECTION_MODE`, and Python delegates cookie loading/decryption to yt-dlp.
- See [docs/yt-dlp-presets.md](docs/yt-dlp-presets.md) for preset-alias details.
- Optional env overrides:
  - `YT_DLP_ENABLE_BROWSER_COOKIES=false` — disable browser cookie attempts
  - `YT_DLP_COOKIES_BROWSER=arc,chrome,edge,firefox,safari` — control browser order
  - `YT_DLP_COOKIE_SOURCES_JSON='[...]'` — explicit ordered cookie sources (takes precedence when app selection is provided)
  - `YT_DLP_COOKIE_SELECTION_MODE=auto|manual` — explicit cookie selection mode (used with `YT_DLP_COOKIE_SOURCES_JSON`)
  - `YT_DLP_ENABLE_FETCH_POT=false` — disable fetch_pot attempts
  - `YT_DLP_JS_RUNTIME_PATH=/absolute/path/to/runtime` (or `node`/`deno` on PATH) — override JS runtime binary
  - `YT_DLP_JS_RUNTIME_NAME=deno|node` — override runtime name used for fetch_pot
  - `YT_DLP_ALLOW_LOW_QUALITY_FALLBACK=true` — allow low progressive fallback when adaptive streams are blocked

## Scripts

- `pnpm dev` / `pnpm dev:renderer`: run Vite only
- `pnpm tauri:dev`: run app in Tauri dev mode
- `pnpm build`: build frontend
- `pnpm tauri:build`: bundle app with Tauri
- `pnpm typecheck`: TypeScript typecheck
- `pnpm python:install`: install Python deps
- `pnpm python:typecheck`: run mypy

## Layout

```text
yt-downloader/
├── app/                    # React UI
├── python/                 # downloader.py and requirements
├── scripts/                # dependency bundling scripts
├── src-tauri/              # Rust backend + Tauri config
├── build/icons/            # app icons
├── plans/                  # migration docs/checklist
└── .github/workflows/      # Tauri CI
```

## Logging / Debugging

See `DEBUGGING.md`.

## License

MIT
