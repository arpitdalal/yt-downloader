# AGENTS.md

Always use conventional commit messages.

## Cursor Cloud-specific instructions

### Overview

Tauri v2 desktop app (React 19 + Rust + Python yt-dlp). See `README.md` for full stack/scripts reference.

### Non-obvious caveats

- **Rust version**: Dependencies require Rust 1.85+ (edition 2024). Run `rustup update stable` if clippy/build fails with `edition2024` errors.
- **Resource dirs**: `src-tauri/resources/python` and `src-tauri/resources/ffmpeg` must exist for Tauri build/dev. Run `node scripts/prebuild.js` to create them (the `prebuild` npm script runs automatically before `pnpm build`). These dirs are empty in dev — bundled Python/FFmpeg are only needed for production builds.
- **Lefthook + Cursor hooks**: `pnpm install` runs `lefthook install` via the `prepare` script, which conflicts with Cursor's `core.hooksPath`. Use `pnpm install --ignore-scripts` if this blocks, then run other setup steps manually. Deps are already resolved from lockfile so this is safe.
- **Tauri dev requires DISPLAY**: Run `DISPLAY=:1 npx tauri dev` for the desktop app to render. EGL/DRI3 warnings are harmless (software rendering).

### Key commands

| Task | Command |
|---|---|
| Install JS deps | `pnpm install --ignore-scripts` |
| Install Python deps | `pip install -r python/requirements.txt` |
| Lint all | `pnpm lint` (runs biome, ruff, clippy, shellcheck in parallel) |
| Test all | `pnpm test` (rust + python) |
| Typecheck TS | `pnpm typecheck` |
| Typecheck Python | `pnpm python:typecheck` |
| Build frontend | `pnpm build` |
| Tauri release build | `npx tauri build --no-bundle` |
| Run dev | `DISPLAY=:1 npx tauri dev` |
