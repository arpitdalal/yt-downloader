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

## Manual binary run (packaged app)

### macOS

```bash
/Applications/YouTube\ Downloader.app/Contents/MacOS/YouTube\ Downloader
```

### Linux / Windows

Run the installed executable directly from terminal/PowerShell to see stdout/stderr in real-time.
