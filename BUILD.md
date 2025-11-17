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

#### Option B: Bundle Python and FFmpeg (Production - Windows)

**For Windows builds**, you have two options:

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

**What gets bundled:**
- ✅ Python embeddable runtime (`python.exe`)
- ✅ pip and yt-dlp (installed in Python environment)
- ✅ FFmpeg executable (`ffmpeg.exe`)
- ✅ Python script (`downloader.py`)

### Step 3: Build Electron App

```bash
pnpm electron:build
```

This uses `electron-builder` to create platform-specific installers:
- Mac: `.dmg` file in `dist-electron/`
- Windows: `.exe` installer in `dist-electron/`

## Manual Build Process

Since automated bundling isn't set up yet, here's the manual process:

1. Build the React app: `pnpm build`
2. Ensure Python and ffmpeg are accessible:
   - Development: Use system versions
   - Production: Bundle them in `resources/` directory
3. Run `pnpm electron:build` to create the installer

## Notes

- The app expects Python and ffmpeg to be in specific locations (see `electron/main.js`)
- In development, it uses system Python/ffmpeg
- In production, it looks for bundled versions in `resources/` directory
- The Python script (`downloader.py`) must be accessible to the bundled Python runtime

