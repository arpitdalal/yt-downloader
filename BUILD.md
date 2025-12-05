# Building the Electron App

This document describes how to build the YouTube Downloader Electron app for distribution.

## Prerequisites

- Node.js 20+
- Python 3.11+ (for development)
- ffmpeg installed on your system (for development)
- pnpm package manager

## Development Setup

1. Install dependencies:
   ```bash
   pnpm install
   ```

2. Install Python dependencies:
   ```bash
   pnpm python:install
   ```

3. Run in development mode:
   ```bash
   # Terminal 1: Start Vite dev server
   pnpm dev

   # Terminal 2: Start Electron
   pnpm electron:dev
   ```

## Building for Production

### Step 1: Build the React App

```bash
pnpm build
```

This creates the `dist/` directory with the built React app.

### Step 2: Bundle Python and FFmpeg

**⚠️ IMPORTANT**: The app requires Python runtime and FFmpeg to be bundled for production builds. Without these, the app will not work on end-user machines.

#### Option A: Use System Python/FFmpeg (Development)

In development, the app uses system Python and ffmpeg. Make sure they're in your PATH.

#### Option B: Bundle Python and FFmpeg (Production)

**For Windows builds:**

**Option 1: Manual (Local Build)**
1. Run the bundling script:
   ```powershell
   .\scripts\bundle-dependencies-windows.ps1
   ```
2. Follow the instructions to download and place:
   - Python embeddable package → `resources/python/python.exe`
   - FFmpeg → `resources/ffmpeg/ffmpeg.exe`
   - The script will copy `downloader.py` automatically

**Option 2: Automated (GitHub Actions)**
- The GitHub Actions workflow automatically bundles Python and FFmpeg
- No manual steps needed when using CI/CD

**For macOS builds:**

**Option 1: Manual (Local Build)**
1. Run the bundling script:
   ```bash
   ./scripts/bundle-dependencies-macos.sh
   ```
2. The script will:
   - Create a Python virtual environment with yt-dlp
   - **Fix venv paths** to make it portable (updates `pyvenv.cfg`)
   - Copy system FFmpeg (or install via Homebrew)
   - Copy `downloader.py` automatically
   - Set correct file permissions

**Option 2: Automated (GitHub Actions)**
- The GitHub Actions workflow automatically bundles Python and FFmpeg
- Builds for both x64 and arm64 architectures
- Automatically fixes venv paths for portability

**For Linux builds:**

**Option 1: Manual (Local Build)**
1. Run the bundling script:
   ```bash
   ./scripts/bundle-dependencies-linux.sh
   ```
2. The script will:
   - Create a Python virtual environment with yt-dlp
   - **Fix venv paths** to make it portable (updates `pyvenv.cfg`)
   - Copy system FFmpeg
   - Copy `downloader.py` automatically
   - Set correct file permissions

**Option 2: Automated (GitHub Actions)**
- The GitHub Actions workflow automatically bundles Python and FFmpeg
- Builds for both x64 and arm64 architectures
- Automatically fixes venv paths for portability

**What gets bundled:**
- ✅ Python runtime (Windows: embeddable, macOS/Linux: venv)
- ✅ pip and yt-dlp (installed in Python environment)
- ✅ FFmpeg executable
- ✅ Python script (`downloader.py`)
- ✅ Portable venv configuration (macOS/Linux: `pyvenv.cfg` uses relative paths)

**Important Notes:**
- **macOS/Linux**: The bundling script automatically fixes `pyvenv.cfg` to use relative paths instead of hardcoded build machine paths. This makes the app portable across different machines.
- **Windows**: Uses Python embeddable which is already portable.
- All Python scripts have their shebangs updated to be portable.

### Step 3: Build Electron App

**Build for current platform:**
```bash
pnpm electron:build
```

**Platform-specific builds:**

**Windows:**
```bash
pnpm electron:build:win          # All architectures
pnpm electron:build:win-x64      # x64 only
pnpm electron:build:win-x86      # x86 only
pnpm electron:build:win-arm64    # ARM64 only
```

**macOS:**
```bash
pnpm electron:build:mac          # Current architecture
pnpm electron:build:mac-x64      # x64 only
pnpm electron:build:mac-arm64    # ARM64 only
```

**Linux:**
```bash
pnpm electron:build:linux        # Current architecture
pnpm electron:build:linux-x64    # x64 only
pnpm electron:build:linux-arm64  # ARM64 only
```

**Note:** You can build Linux on macOS! Electron Builder supports cross-platform builds.

This uses `electron-builder` to create platform-specific installers:
- macOS: `.dmg` file in `dist-electron/`
- Windows: `.exe` installer in `dist-electron/`
- Linux: `.AppImage`, `.deb`, or `.rpm` in `dist-electron/`

## Building on macOS for Multiple Platforms

Yes, you can build for macOS, Linux, and Windows all from your macOS machine!

1. **Build for macOS:**
   ```bash
   ./scripts/bundle-dependencies-macos.sh
   pnpm electron:build:mac
   ```

2. **Build for Linux (from macOS):**
   
   **⚠️ Important:** Building Linux on macOS has limitations:
   - Electron Builder CAN create Linux packages (.AppImage, .deb, .rpm) from macOS
   - BUT the bundled Python/FFmpeg will be macOS binaries that won't run on Linux
   - **Recommended:** Use GitHub Actions for proper Linux builds
   
   **If you still want to try:**
   ```bash
   ./scripts/bundle-dependencies-linux.sh  # Will warn about macOS binaries
   pnpm electron:build:linux
   ```
   
   **Better approach for Linux from macOS:**
   - Use Docker to bundle Linux-compatible binaries
   - Or just use GitHub Actions (easiest)

3. **Build for Windows (from macOS):**
   - Use GitHub Actions (recommended)
   - Or use Wine/Cross-compilation tools (complex)

## GitHub Actions Builds

All platforms are automatically built on GitHub Actions when you:
- Push a tag starting with `v*` (e.g., `v1.0.0`)
- Manually trigger the workflow from GitHub Actions UI

Workflows:
- `.github/workflows/build-windows.yml` - Windows (x64, x86, arm64)
- `.github/workflows/build-macos.yml` - macOS (x64, arm64)
- `.github/workflows/build-linux.yml` - Linux (x64, arm64)

## Notes

- The app expects Python and ffmpeg to be in specific locations (see `electron/main.js`):
  - **Windows**: `resources/python/python.exe` and `resources/ffmpeg/ffmpeg.exe`
  - **macOS/Linux**: `resources/python/bin/python3` and `resources/ffmpeg/ffmpeg`
- In development, it uses system Python/ffmpeg
- In production, it looks for bundled versions in `resources/` directory (packaged as `extraResources`)
- The Python script (`downloader.py`) must be accessible to the bundled Python runtime
- The bundling scripts automatically make Python venvs portable by fixing `pyvenv.cfg` paths

## Troubleshooting Builds

### Python Not Found After Installation

If users report "Python executable not found" errors:

1. **Check if resources were bundled correctly:**
   - Verify `resources/python/` exists before building
   - On macOS/Linux, check for `resources/python/bin/python3`
   - On Windows, check for `resources/python/python.exe`

2. **Verify venv portability (macOS/Linux):**
   - Check `resources/python/pyvenv.cfg` - should have `home = bin` (not absolute path)
   - The bundling script should fix this automatically

3. **Check file permissions:**
   - Python executable should be executable: `chmod +x resources/python/bin/python3`
   - The bundling script sets this automatically

4. **View logs:**
   - See [DEBUGGING.md](./DEBUGGING.md) for log file locations
   - Logs will show the exact paths being checked

### Build Verification

After building, verify the bundle contains resources:

**macOS:**
```bash
ls -la "dist-electron/mac-*/YouTube Downloader.app/Contents/Resources/python/bin/python3"
ls -la "dist-electron/mac-*/YouTube Downloader.app/Contents/Resources/ffmpeg/ffmpeg"
```

**Linux:**
```bash
# Extract AppImage or check .deb contents
```

**Windows:**
```bash
# Check installer contents or extracted app directory
```

