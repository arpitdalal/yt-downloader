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

## 4. Dev tools (lint, format)

Lint and format are wired to **Biome** (TS/JS), **Ruff** (Python), **cargo fmt/clippy** (Rust), and **shellcheck** (shell). Git hooks use **lefthook** (pre-commit: format; pre-push: lint + typecheck).

Install system tools for full `pnpm lint` / `pnpm format`:

- **Ruff**: `pip install ruff` or `brew install ruff`
- **shellcheck**: `brew install shellcheck` (macOS) or `apt-get install shellcheck` (Linux)

Then:

```bash
pnpm format   # format all
pnpm lint    # lint all (fails if any check fails)
```

After `pnpm install`, lefthook installs git hooks; pre-commit formats staged files and pre-push runs the full lint suite.

## 5. CI workflows

- `tauri-gate.yml`: all-OS gate (macOS, Windows, Linux) with `tauri build --debug --no-bundle`
- `tauri-release.yml`: release bundles on `v*` tags with artifact verification on each OS
- macOS release is enforced as signed + notarized. Required GitHub secrets:
  - `APPLE_CERTIFICATE` (base64 `.p12`)
  - `APPLE_CERTIFICATE_PASSWORD`
  - `APPLE_API_KEY` (key id)
  - `APPLE_API_ISSUER` (issuer id)
  - `APPLE_API_KEY_CONTENT` (raw `.p8` contents)
- Automatic updates require encrypted GitHub secrets:
  - `TAURI_SIGNING_PRIVATE_KEY`
  - `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
  - The matching public key is intentionally committed in `src-tauri/tauri.conf.json`; never commit either private value.
- Verification scripts used by release workflow:
  - `scripts/verify-release-macos.sh`
  - `scripts/verify-release-windows.ps1`
  - `scripts/verify-release-linux.sh`

## 6. Notes

- App identifier is `com.ytdownloader.app`.
- Tauri warns on macOS because identifier ends with `.app`; kept intentionally for identity parity.
- If runtime resources are missing, the backend returns configuration errors for Python/FFmpeg/script paths.

## 7. Troubleshooting

- Run `node scripts/prebuild.js` to ensure resource folders exist.
- Run `pnpm typecheck` and `source $HOME/.cargo/env && cargo test` in `src-tauri`.
- See `DEBUGGING.md` for log retrieval and common failures.
- macOS release notarization `HTTP 403` / "required agreement is missing or has expired":
  - Signing secrets are fine; Apple is rejecting notarization until legal agreements are accepted.
  - Account holder/Admin: accept pending agreements at [developer.apple.com/account](https://developer.apple.com/account) and [appstoreconnect.apple.com/agreements](https://appstoreconnect.apple.com/agreements), wait a few minutes, re-run `tauri-release.yml`.
