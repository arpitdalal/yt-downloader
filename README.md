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
