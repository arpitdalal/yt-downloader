# Debugging Guide (Tauri)

## Find log file quickly

Preferred: ask app for exact path.

```ts
import { tauriAPI } from "./app/lib/tauri-api";

const info = await tauriAPI.getLogPath();
console.log(info.logPath);
```

`getLogPath()` returns:
- `logPath`
- `resourcesPath`
- `appPath`
- `isPackaged`

## Typical log locations

- macOS: `~/Library/Logs/com.ytdownloader.app/main.log`
- Windows: `%APPDATA%\\com.ytdownloader.app\\logs\\main.log`
- Linux: `$XDG_STATE_HOME/com.ytdownloader.app/logs/main.log` or `~/.local/state/com.ytdownloader.app/logs/main.log`

## View logs

### macOS / Linux

```bash
cat "<logPath>"
tail -n 200 "<logPath>"
tail -f "<logPath>"
```

### Windows (PowerShell)

```powershell
Get-Content "<logPath>"
Get-Content "<logPath>" -Tail 200
Get-Content "<logPath>" -Wait
```

## What to check first

1. `Configuration error: Python executable not found...`
2. `Configuration error: Python script not found...`
3. `Configuration error: FFmpeg not found...`
4. `Failed to start download process...` / `Failed to start processing...`
5. `Download process failed...` / `Processing failed...`

## Validation errors surfaced to UI

- Invalid YouTube URL
- Save path outside home directory
- Invalid section ordering or negative timestamps

## `Sign in to confirm you're not a bot`

This is what YouTube returns when yt-dlp cannot solve its verification challenge.
Before blaming cookies or IP reputation, check the JS runtime — yt-dlp needs one to
run the challenge, and a runtime that only *starts* is indistinguishable from a
working one unless you execute code with it:

```bash
./scripts/jsruntime-smoke-test.sh src-tauri/resources/jsruntime/deno deno
```

`Failed to reserve virtual memory for CodeRange` means the macOS signature is wrong:
the runtime is signed with the Hardened Runtime but is missing its JIT entitlements,
so V8 cannot map its code range. Rebuild it with
`./scripts/bundle-dependencies-macos.sh`, or re-sign it manually with
`--options runtime --entitlements src-tauri/entitlements.macos.plist`.

The same state is reported in the downloader's debug stream on stderr:

```json
{"type": "auth_debug", "event": "extract_attempt_plan", "js_runtime_configured": true, "js_runtime_usable": false, "js_runtime_error": "..."}
```

and by `python downloader.py --auth-capabilities`. The app surfaces it in Settings as
"<runtime> cannot execute JavaScript" and on the download-failure screen.

An unusable runtime is also *withheld* from yt-dlp rather than handed over, and
`fetch_pot_runtime_usable` in the debug stream records the difference:

```json
{"fetch_pot_runtime_available": true, "fetch_pot_runtime_usable": false}
```

That gap is not cosmetic. yt-dlp discovers a runtime with `--version`, so a runtime
that only starts looks healthy to it; it then picks that runtime for every challenge
and every PO token and fails each one. Withholding it makes yt-dlp report the runtime
as missing, which fails loudly instead of repeatedly.

## fetch_pot never runs

`fetch_pot` is deliberately opt-in. It needs two separate things, and the debug
stream reports them separately because they fail for different reasons:

```json
{"po_token_providers_registered": true, "po_token_providers_configured": false, "po_token_providers_available": false}
```

- `registered: false` — `bgutil-ytdlp-pot-provider` is missing from the bundled
  Python. Re-run the bundle script; it is in `python/requirements.txt`.
- `registered: true, configured: false` — the plugin is there but no generator is.
  The generator is ~700MB of Node modules, so it is not bundled. Run a bgutil HTTP
  server (default `http://127.0.0.1:4416`) or clone its repo for script mode, then
  set `YT_DLP_POT_PROVIDER_BASE_URL` or `YT_DLP_POT_PROVIDER_SERVER_HOME`.
- `configured: true, available: true` — fetch_pot attempts will run. If YouTube
  still rejects them, the failure is coming from the provider, not the app; the
  `bgutil` warnings on stderr name it.

`registered` alone is not enough to gate the ladder: bgutil's HTTP provider
reports itself available without probing, so gating on registration would add a
doomed attempt and a misleading warning to every run.

## Manual binary run (packaged app)

### macOS

```bash
/Applications/YouTube\ Downloader.app/Contents/MacOS/YouTube\ Downloader
```

### Linux / Windows

Run the installed executable directly from terminal/PowerShell to see stdout/stderr in real-time.
