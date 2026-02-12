# Build Guide (Tauri)

## 1. Install dependencies

```bash
pnpm install
pnpm python:install
```

## 2. Bundle Python + FFmpeg into `src-tauri/resources`

```bash
# macOS
./scripts/bundle-dependencies-macos.sh

# Linux
./scripts/bundle-dependencies-linux.sh

# Windows (PowerShell)
./scripts/bundle-dependencies-windows.ps1
```

Expected outputs:

- `src-tauri/resources/python/...`
- `src-tauri/resources/ffmpeg/...`

## 3. Build app

```bash
# current platform
pnpm tauri:build

# explicit targets
pnpm tauri:build:mac
pnpm tauri:build:win
pnpm tauri:build:linux
```

## 4. CI workflows

- `tauri-gate.yml`: all-OS gate (macOS, Windows, Linux) with `tauri build --debug --no-bundle`
- `tauri-release.yml`: release bundles on `v*` tags

## Notes

- App identifier is `com.ytdownloader.app`.
- Tauri warns on macOS because identifier ends with `.app`; kept intentionally for identity parity.
- If runtime resources are missing, the backend returns configuration errors for Python/FFmpeg/script paths.

## Troubleshooting

- Run `node scripts/prebuild.js` to ensure resource folders exist.
- Run `pnpm typecheck` and `source $HOME/.cargo/env && cargo test` in `src-tauri`.
- See `DEBUGGING.md` for log retrieval and common failures.
