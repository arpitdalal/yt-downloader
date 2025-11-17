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

The app requires Python and ffmpeg to be bundled. For now, this is done manually:

#### Option A: Use System Python/FFmpeg (Development)

In development, the app uses system Python and ffmpeg. Make sure they're in your PATH.

#### Option B: Bundle Python and FFmpeg (Production)

1. **Python**: 
   - Option 1: Use PyInstaller to create a standalone Python executable
   - Option 2: Bundle a portable Python runtime
   - Place Python executable in `resources/python/` directory

2. **FFmpeg**:
   - Download platform-specific ffmpeg binaries
   - Place ffmpeg executable in `resources/ffmpeg/` directory
   - For Mac: `resources/ffmpeg/ffmpeg`
   - For Windows: `resources/ffmpeg/ffmpeg.exe`

3. **Python Script**:
   - Copy `python/downloader.py` to `resources/python/downloader.py`
   - Ensure all Python dependencies are installed in the bundled Python environment

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

