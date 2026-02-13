# Electron -> Tauri v2 Migration

## Summary
- Goal: replace Electron runtime with Tauri v2, keep React UI + Python downloader architecture.
- Chosen: Tauri v2, keep Python+FFmpeg side resources, keep app identity, migrate logging with `tauri-plugin-log`.
- Build policy: after each milestone task, run all OS envs (macOS arm64, Windows x64, Linux x64). Full arch matrix only near release.
- Out of scope: code signing/notarization, updater, mobile targets.

## Public API / Interface Changes
- Remove renderer bridge `window.electronAPI` from `app/lib/electron-api.ts`.
- Add typed Tauri API wrapper `app/lib/tauri-api.ts` using:
  1. `invoke` from `@tauri-apps/api/core`
  2. `listen` from `@tauri-apps/api/event`
  3. `open/save` from `@tauri-apps/plugin-dialog`
- Backend IPC contract moves to Rust commands in `src-tauri/src/lib.rs`:
  1. `extract_video_info(url: String) -> VideoInfo`
  2. `download_video(payload: DownloadOptions) -> DownloadResult`
  3. `process_local_video(payload: ProcessLocalOptions) -> DownloadResult`
  4. `cancel_download() -> CancelResult`
  5. `get_log_info() -> LogInfo`
- Progress stream stays event-based with name `download-progress` and same payload shape.

## Milestone Build Gate (run after every task below)
- CI workflow name: `tauri-gate`.
- Matrix: `macos-14` + `windows-2022` + `ubuntu-22.04`.
- Each job runs:
  1. `pnpm install`
  2. OS bundling script for Python/FFmpeg
  3. `pnpm typecheck`
  4. `pnpm build`
  5. `pnpm tauri build` with platform target set
- Gate rule: task not marked done until all 3 OS jobs pass.

## Tasks

## [x] T0. Create migration tracking artifacts
Dependencies: none.
Steps:
1. Create `plans/migrate-to-tauri.md` with this plan.
2. Create `plans/migrate-to-tauri-checklist.md` with one checkbox per task + gate status table.
3. Create branch `codex/tauri-migration`.
Done when: both docs committed; branch created.
Build gate: run `tauri-gate`.

## [x] T1. Scaffold Tauri v2 without removing Electron
Dependencies: T0.
Steps:
1. Add Tauri packages to `package.json` (`@tauri-apps/cli`, `@tauri-apps/api`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-log`).
2. Initialize `src-tauri/` with Rust crate.
3. Set `src-tauri/tauri.conf.json`:
- `identifier: "com.ytdownloader.app"`
- `productName: "YouTube Downloader"`
- `build.devUrl: "http://localhost:5173"`
- `build.beforeDevCommand: "pnpm dev:renderer"`
- `build.beforeBuildCommand: "pnpm build"`
- `build.frontendDist: "../dist"`
4. Add scripts in `package.json`:
- `tauri:dev`
- `tauri:build`
- `tauri:build:mac`
- `tauri:build:win`
- `tauri:build:linux`
5. Add `src-tauri/capabilities/default.json` with permissions: `core:default`, `dialog:default`, `log:default`.
Done when: `pnpm tauri:dev` opens app shell with current frontend.
Build gate: run `tauri-gate`.

## [x] T2. Implement Rust domain models + validation parity
Dependencies: T1.
Steps:
1. In `src-tauri/src/lib.rs`, add serde structs mirroring TS types in `app/lib/electron-api.ts`.
2. Port validation logic from `electron/main.js`:
- YouTube host allowlist.
- save path restricted to user home.
- section ordering/integer checks.
3. Add uniform error mapping with stable user-safe messages.
4. Add unit tests in `src-tauri/src/lib.rs` (or `src-tauri/src/tests.rs`) for validators.
Done when: Rust tests pass and behavior equals Electron validation contract.
Build gate: run `tauri-gate`.

## [x] T3. Implement Python process orchestration in Rust
Dependencies: T2.
Steps:
1. Add shared app state for active child process + cancel flag (`Arc<Mutex<Option<Child>>>`, `AtomicBool`).
2. Implement path resolvers:
- Dev: `python`/`python3`, `ffmpeg` from PATH.
- Prod: `app.path().resource_dir()?.join("python/...")` and `.../ffmpeg/...`.
3. Windows-specific: set `cwd` to Python dir for DLL load parity.
4. Implement commands:
- `extract_video_info`: spawn python `--validate`.
- `download_video`: spawn python download flow, parse `stderr` JSON progress lines, emit `download-progress`.
- `process_local_video`: spawn python `--local`.
- `cancel_download`: kill child safely, return deterministic state.
5. Ensure cleanup on app exit.
Done when: all command flows execute from Rust with same JSON IO contract as current Electron main process.
Build gate: run `tauri-gate`.

## [x] T4. Migrate frontend integration to Tauri APIs
Dependencies: T3.
Steps:
1. Replace `app/lib/electron-api.ts` with `app/lib/tauri-api.ts`.
2. Update `app/App.tsx` imports and calls:
- `invoke` for commands
- `listen`/`unlisten` for progress events
- `open`/`save` plugin dialog APIs
3. Keep UI copy, error behavior, section validation UX unchanged.
4. Remove Electron runtime checks (`window.electronAPI`).
Done when: full user flow works in `pnpm tauri:dev` with no Electron codepath usage.
Build gate: run `tauri-gate`.

## [x] T5. Logging migration and debug parity
Dependencies: T4.
Steps:
1. Register `tauri-plugin-log` in Rust builder.
2. Configure log targets to file + stdout; set app log directory via plugin configuration.
3. Add command `get_log_info` returning resolved log path and app/resource paths.
4. Update frontend wrapper type for `get_log_info`.
5. Update `DEBUGGING.md` log locations and commands for Tauri.
Done when: packaged app writes logs; debug doc paths verified on all OS gate runners.
Build gate: run `tauri-gate`.

## [x] T6. Resource bundling migration (Python + FFmpeg)
Dependencies: T3, T5.
Steps:
1. Move bundling outputs to `src-tauri/resources/python` and `src-tauri/resources/ffmpeg`.
2. Update scripts:
- `scripts/bundle-dependencies-macos.sh`
- `scripts/bundle-dependencies-linux.sh`
- `scripts/bundle-dependencies-windows.ps1`
3. Update `src-tauri/tauri.conf.json` `bundle.resources` mapping for those directories.
4. Verify runtime lookup in Rust matches packaged structure.
Done when: packaged app finds Python/FFmpeg on all 3 OS gates and can execute one smoke command.
Build gate: run `tauri-gate`.

## [x] T7. Packaging parity configuration
Dependencies: T6.
Steps:
1. Configure bundle targets to match Electron outputs:
- macOS: `dmg`
- Windows: `nsis`
- Linux: `appimage`, `deb`, `rpm`
2. Keep icon set from `build/icons`.
3. Keep app identity (`com.ytdownloader.app`, `YouTube Downloader`).
4. Add platform-specific config files if needed:
- `src-tauri/tauri.macos.conf.json`
- `src-tauri/tauri.windows.conf.json`
- `src-tauri/tauri.linux.conf.json`
Done when: installers produced in same family as current Electron outputs.
Build gate: run `tauri-gate`.

## [x] T8. CI migration for milestone gates + release matrix
Dependencies: T7.
Steps:
1. Replace Electron workflows in `.github/workflows/` with:
- `tauri-gate.yml` (primary arch per OS, every PR/push).
- `tauri-release.yml` (full arch matrix on tags).
2. Each workflow runs resource bundling before `tauri build`.
3. Upload artifacts per OS and target type.
4. Keep release retention + naming parity.
Done when: `tauri-gate` required check enforced; `tauri-release` produces full artifact matrix.
Build gate: run `tauri-gate`.

## [x] T9. Remove Electron code and configs
Dependencies: T8.
Steps:
1. Delete `electron/`.
2. Remove Electron deps/scripts/build config from `package.json`.
3. Remove Electron-only scripts no longer used.
4. Update docs:
- `README.md`
- `BUILD.md`
- `DEBUGGING.md`
Done when: repo has no runtime Electron dependency and docs fully Tauri-aligned.
Build gate: run `tauri-gate`.

## [x] T10. Final verification and cutover
Dependencies: T9.
Steps:
1. Run manual smoke matrix:
- YouTube download
- local file processing
- multi-section concat
- cancel in-progress
- invalid input handling
2. Run packaged binary smoke on each OS artifact.
3. Validate logs and error messages.
4. Tag release candidate and run `tauri-release`.
Done when: all acceptance scenarios pass and full release matrix artifacts produced.

## Test Cases / Scenarios (must pass before marking T10 done)
1. Extract video info returns title/uploader/duration for valid YouTube URL.
2. Non-YouTube URL rejected with user-safe error.
3. Save path outside home rejected.
4. Section validation catches invalid ordering, missing required boundaries, negative/non-int values.
5. Download flow emits `download-progress` continuously, reaches completion, output file exists.
6. Local processing with empty sections copies full file.
7. Local processing with multiple sections produces concatenated output.
8. Cancel during download kills process and returns canceled state.
9. Packaged app resolves bundled Python/FFmpeg paths correctly on macOS/Windows/Linux.
10. Debug log file path returned by `get_log_info` and file contains startup + process logs.

## Assumptions / Defaults
- Tauri v2 only.
- Python runtime kept (no Rust downloader rewrite).
- No shell plugin sidecar execution from JS; process spawning handled in Rust commands.
- Build-all-env policy interpreted as all OS each milestone (primary arch), full arch matrix near release.
- Signing/notarization excluded from this migration scope.
- Existing UI/UX preserved; migration is runtime/backend/platform change, not product redesign.

## Research References
- [Tauri v2: Embedding Additional Files (`bundle.resources`)](https://v2.tauri.app/develop/resources/)
- [Tauri v2: Embedding External Binaries (`externalBin`, target triple rules)](https://v2.tauri.app/develop/sidecar/)
- [Tauri v2: Capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri v2: Core Permissions](https://v2.tauri.app/reference/acl/core-permissions/)
- [Tauri v2 Plugin: Dialog](https://v2.tauri.app/plugin/dialog/)
- [Tauri v2 Plugin: Logging](https://v2.tauri.app/plugin/logging/)
- [Tauri v2 IPC Concepts (Commands vs Events)](https://v2.tauri.app/concept/inter-process-communication/)
- [Tauri v2 JS `invoke` API](https://v2.tauri.app/reference/javascript/api/namespacecore/)
- [Tauri PathResolver `resource_dir` behavior (docs.rs)](https://docs.rs/tauri/latest/tauri/path/struct.PathResolver.html)
- [Tauri v2 Config Reference (bundle targets)](https://v2.tauri.app/reference/config/)
