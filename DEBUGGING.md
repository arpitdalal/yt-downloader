# Debugging Guide

## Finding Logs

### macOS

The app logs are stored in:

```
~/Library/Logs/yt-downloader/main.log
```

**To view logs:**

1. **Via Terminal:**
   ```bash
   # View the log file
   cat ~/Library/Logs/yt-downloader/main.log
   
   # Follow the log in real-time
   tail -f ~/Library/Logs/yt-downloader/main.log
   
   # View last 100 lines
   tail -n 100 ~/Library/Logs/yt-downloader/main.log
   ```

2. **Via Console.app:**
   - Open Console.app (Applications > Utilities > Console)
   - Search for "yt-downloader" or "main.log"
   - Filter by your app name

3. **Via Finder:**
   - Press `Cmd+Shift+G` in Finder
   - Enter: `~/Library/Logs/yt-downloader/`
   - Open `main.log` with any text editor

4. **View Console Output (Real-time):**
   ```bash
   # Run the app from terminal to see console.log output
   /Applications/YouTube\ Downloader.app/Contents/MacOS/YouTube\ Downloader
   ```

### Windows

Logs are stored in:
```
%USERPROFILE%\AppData\Roaming\yt-downloader\logs\main.log
```

**To view logs:**
```powershell
# View the log file
Get-Content "$env:USERPROFILE\AppData\Roaming\yt-downloader\logs\main.log"

# View last 100 lines
Get-Content "$env:USERPROFILE\AppData\Roaming\yt-downloader\logs\main.log" -Tail 100
```

### Linux

Logs are stored in:
```
~/.config/yt-downloader/logs/main.log
```

**To view logs:**
```bash
# View the log file
cat ~/.config/yt-downloader/logs/main.log

# Follow the log in real-time
tail -f ~/.config/yt-downloader/logs/main.log

# View last 100 lines
tail -n 100 ~/.config/yt-downloader/logs/main.log
```

## Common Issues

### Python Not Found

If you see errors like "Python executable not found", check the log for:
- `pythonPath` - The path being checked
- `pythonExists` - Whether the file exists
- `resourcesPath` - Where resources are located
- `pythonDir` - Directory listing of Python directory

**Example log entry:**
```json
{
  "pythonPath": "/path/to/app/Resources/python/bin/python3",
  "pythonExists": false,
  "resourcesPath": "/path/to/app/Resources"
}
```

**Common causes:**
1. **Hardcoded venv paths**: The Python venv was created with absolute paths from the build machine. The bundling script now automatically fixes this by updating `pyvenv.cfg` to use relative paths.
2. **Missing resources**: Resources weren't bundled correctly during build - ensure you ran the bundling script before building
3. **Wrong resourcesPath**: The app is looking in the wrong location - check the log for the actual `resourcesPath` value
4. **File permissions**: Python executable might not have execute permissions (should be set automatically by bundling script)

### Permission Errors

If you see permission errors:
- Check if Python executable has execute permissions
- On macOS, check if Gatekeeper is blocking the app
- Try: `chmod +x /path/to/python3`

## Debugging Steps

1. **Check startup logs:**
   - Look for "App starting" entry
   - Check "Resource paths" section
   - Verify Python and FFmpeg paths exist

2. **Check error logs:**
   - Look for "Python configuration error"
   - Check "Failed to start Python process"
   - Note the exact error code and message

3. **Verify bundled resources:**
   - **macOS/Linux**: Check if `resources/python/bin/python3` exists
   - **Windows**: Check if `resources/python/python.exe` exists
   - Check if `resources/ffmpeg/ffmpeg` (or `ffmpeg.exe` on Windows) exists
   - Verify file permissions (should be executable)
   - **macOS/Linux**: Check `resources/python/pyvenv.cfg` - should have `home = bin` (not absolute path)

4. **Test Python manually:**
   ```bash
   # macOS/Linux: From the app's Resources directory
   ./python/bin/python3 --version
   ./python/bin/python3 -c "import yt_dlp; print('OK')"
   
   # Windows: From the app's Resources directory
   python\python.exe --version
   python\python.exe -c "import yt_dlp; print('OK')"
   ```

5. **View console output in real-time:**
   ```bash
   # Run the installed app from terminal
   /Applications/YouTube\ Downloader.app/Contents/MacOS/YouTube\ Downloader
   ```
   This will show all `console.log()` output directly in the terminal.

## Getting Log Path Programmatically

The app exposes a log path API. In the renderer process:

```javascript
const logInfo = await window.electronAPI.getLogPath();
console.log('Log file:', logInfo.logPath);
```

## Enabling More Verbose Logging

To enable debug-level logging, modify `electron/main.js`:

```javascript
log.transports.file.level = "debug";
log.transports.console.level = "debug";
```

Then rebuild the app.

## Fixing Python Venv Path Issues

If you see errors about Python paths, the venv might have hardcoded paths. **The bundling script now fixes this automatically**, but if you need to fix it manually:

**macOS/Linux:**
```bash
# After creating venv, update pyvenv.cfg
PYTHON_VERSION=$(resources/python/bin/python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
cat > resources/python/pyvenv.cfg <<EOF
home = bin
include-system-site-packages = false
version = $PYTHON_VERSION
executable = bin/python3
EOF

# Fix shebangs in Python scripts
find resources/python/bin -type f -name "*.py" -exec sed -i '' "1s|^#!.*python.*|#!/usr/bin/env python3|" {} \;
```

**Note:** This should not be necessary as the bundling scripts (`bundle-dependencies-macos.sh` and `bundle-dependencies-linux.sh`) handle this automatically.
