# YouTube Video Downloader

A desktop application built with Electron that allows users to download YouTube videos or process local video files with custom start/end times or multiple sections that are automatically concatenated. Built with React, Electron, and Python yt-dlp.

## Features

- 🎥 **YouTube Video Download**: Download videos with custom quality selection
- ✂️ **Video Cutting**: Specify start and end times to download specific segments
- 📂 **Local File Processing**: Load an existing video and cut/concat without downloading
- 🎬 **Multiple Sections**: Cut and combine multiple sections from the same video into one output file
- 📊 **Real-time Progress**: Track download progress with percentage and speed
- 💾 **Save Dialog**: Choose where to save downloaded videos
- 🎯 **Video Info Extraction**: Preview video information before downloading
- 🚫 **Download Cancellation**: Cancel downloads in progress
- 🖥️ **Cross-platform**: Works on Windows, macOS, and Linux

## Tech Stack

- **Frontend**: React 19, TypeScript, Tailwind CSS 4
- **Desktop Framework**: Electron 33
- **Build Tool**: Vite 6
- **Download Engine**: Python 3, yt-dlp
- **Video Processing**: FFmpeg (for video cutting)
- **Package Manager**: pnpm

## Prerequisites

- Node.js 20+
- Python 3.11+
- pnpm
- FFmpeg (for video cutting functionality)

## Local Development Setup

1. **Clone and install dependencies**:
   ```bash
   git clone <repository-url>
   cd yt-downloader
   pnpm install
   ```

2. **Install Python dependencies**:
   ```bash
   pnpm python:install
   ```

3. **Install FFmpeg** (if not already installed):
   - **macOS**: `brew install ffmpeg`
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (RHEL/CentOS)

4. **Start the development server**:
   ```bash
   # Start Vite dev server and Electron app
   pnpm dev:main
   
   # Or run them separately:
   # Terminal 1: Start Vite dev server
   pnpm dev:renderer
   
   # Terminal 2: Start Electron app
   pnpm electron:dev
   ```

5. **The Electron app will open automatically** with the development UI

## Building for Production

### Quick Start

1. **Bundle dependencies** (required for production):
   ```bash
   # macOS
   ./scripts/bundle-dependencies-macos.sh
   
   # Linux
   ./scripts/bundle-dependencies-linux.sh
   
   # Windows
   .\scripts\bundle-dependencies-windows.ps1
   ```

2. **Build the application**:
   ```bash
   # Build for current platform
   pnpm electron:build
   
   # Or build for specific platform
   pnpm electron:build:mac      # macOS
   pnpm electron:build:linux     # Linux
   pnpm electron:build:win       # Windows
   ```

3. **Output**: The built application will be in the `dist-electron` directory

### Platform-Specific Builds

**macOS:**
```bash
./scripts/bundle-dependencies-macos.sh
pnpm electron:build:mac
# Output: .dmg file
```

**Linux:**
```bash
./scripts/bundle-dependencies-linux.sh
pnpm electron:build:linux
# Output: .AppImage, .deb, or .rpm files
```

**Windows:**
```bash
.\scripts\bundle-dependencies-windows.ps1
pnpm electron:build:win
# Output: .exe installer
```

**Note:** For cross-platform builds, see [BUILD.md](./BUILD.md) for detailed instructions. GitHub Actions automatically builds all platforms when you push a tag starting with `v*`.

## Usage

### Download from YouTube

1. Enter YouTube URL.
2. Set sections (optional):
   - Single section: enter start/end seconds. Empty start = beginning. Last section can leave end empty to go to file end.
   - Multiple sections: click "+ Add Section"; sections are cut then concatenated in order.
   - Validation: later sections need a start; all but last need an end; next start cannot precede previous end.
3. Click **Download** → choose save path.
4. Monitor progress; **Cancel** if needed.

### Process a local video file (new)

1. Click **Choose Video File** (disables URL field).
2. Set sections (optional, same rules as above). If left empty, the file is copied as-is.
3. Click **Download/Process** → pick output path.
4. App cuts/concats locally and shows the saved file path on success.

## Project Structure

```
yt-downloader/
├── app/
│   ├── lib/                 # Shared utilities
│   │   ├── electron-api.ts  # Electron IPC API types and wrapper
│   │   └── types.ts         # TypeScript type definitions
│   ├── App.tsx              # Main React component
│   ├── main.tsx             # React entry point
│   └── app.css              # Global styles
├── electron/
│   ├── main.js              # Electron main process
│   └── preload.js           # Electron preload script
├── python/
│   ├── downloader.py        # YouTube downloader (yt-dlp)
│   └── requirements.txt     # Python dependencies
├── public/                  # Static assets
├── dist/                    # Built frontend (generated)
├── dist-electron/           # Built Electron app (generated)
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies and scripts
```

## Architecture

### Electron IPC Communication

The app uses Electron's IPC (Inter-Process Communication) to bridge the React frontend and Node.js main process:

- **Main Process** (`electron/main.js`): Handles file system operations, Python process spawning, and native dialogs
- **Renderer Process** (`app/App.tsx`): React UI that communicates with main process via IPC
- **Preload Script** (`electron/preload.js`): Safely exposes Electron APIs to the renderer

### Download Flow

1. User enters YouTube URL and optional time range
2. Frontend calls `extractVideoInfo` IPC handler
3. Main process spawns Python script to extract video metadata
4. User selects save location via native save dialog
5. Frontend calls `downloadVideo` IPC handler
6. Main process spawns Python script with yt-dlp
7. Progress updates are streamed back via IPC events
8. Completed file is saved to user-selected location

### Local File Flow

1. User picks a local video (URL input disables)
2. Frontend calls `processLocalVideo` IPC handler with sections and save path
3. Main process runs `python/downloader.py --local <input> <sections_json> <output>`
4. Python uses FFmpeg to cut/concat (or copy if sections are empty) and returns file info

## Available Scripts

- `pnpm dev` - Start Vite dev server only
- `pnpm dev:renderer` - Start Vite dev server only
- `pnpm dev:main` - Start Vite dev server and Electron app together
- `pnpm electron:dev` - Start Electron app (assumes dev server is running)
- `pnpm build` - Build frontend for production
- `pnpm electron:build` - Build complete Electron app for distribution
- `pnpm python:install` - Install Python dependencies
- `pnpm python:typecheck` - Type check Python code with mypy
- `pnpm typecheck` - Type check TypeScript code

## Development Notes

### Python Script Integration

The Python downloader script (`python/downloader.py`) is called via child process from the Electron main process. It communicates via:
- **stdout**: JSON results (video info, download results)
- **stderr**: JSON progress updates (percentage, speed, ETA)

### Video Cutting

**Single Section:**
When start/end times are specified:
1. Full video is downloaded to a temporary location
2. FFmpeg is used to cut the video segment
3. Cut video is saved to user-selected location
4. Temporary full video is automatically cleaned up

**Multiple Sections:**
When multiple sections are specified:
1. Full video is downloaded to a temporary location (cached for reuse)
2. Each section is cut individually to a temporary file using FFmpeg
3. All sections are concatenated in order using FFmpeg's concat demuxer
4. Final concatenated video is saved to user-selected location
5. All temporary files (individual sections and concat file) are automatically cleaned up
6. Original full video remains cached for future cuts from the same video

## Troubleshooting

### Common Issues

1. **Python dependencies not found**:
   ```bash
   pnpm python:install
   ```

2. **FFmpeg not found**:
   - Ensure FFmpeg is installed and available in PATH
   - For production builds, FFmpeg needs to be bundled with the app

3. **Download failures**:
   - Check if yt-dlp is up to date: `pip install --upgrade yt-dlp`
   - Verify YouTube URL is accessible
   - Check available disk space
   - Some videos may have format restrictions

4. **Electron app won't start**:
   - Ensure Vite dev server is running on port 5173 (for development)
   - Check that all dependencies are installed: `pnpm install`
   - Verify Python is accessible: `python3 --version`

5. **Video cutting fails**:
   - Ensure FFmpeg is installed and working: `ffmpeg -version`
   - Check that start time is less than end time within each section
   - For multiple sections, verify sections don't overlap and are in order
   - Verify the video format supports cutting and concatenation

6. **Local file processing fails**:
   - Ensure the source file is readable (avoid locked/network locations)
   - Confirm FFmpeg is installed or bundled
   - Validate sections are integers and ordered; empty list copies the whole file

7. **"Unable to start download process" error in production**:
   - Check the log file (see [DEBUGGING.md](./DEBUGGING.md) for locations)
   - Verify Python and FFmpeg are properly bundled
   - Ensure you ran the bundling script before building
   - On macOS, check Console.app for detailed error messages

### Production Build Issues

- **Python not bundled**: Run the platform-specific bundling script before building
- **FFmpeg not bundled**: The bundling script should include FFmpeg automatically
- **Large app size**: Consider using platform-specific builds to reduce size
- **Python venv path errors**: The bundling scripts now automatically fix venv paths for portability

### Getting Help

If you encounter issues:

1. **Check the log file** - see [DEBUGGING.md](./DEBUGGING.md) for log locations:
   - macOS: `~/Library/Logs/yt-downloader/main.log`
   - Windows: `%USERPROFILE%\AppData\Roaming\yt-downloader\logs\main.log`
   - Linux: `~/.config/yt-downloader/logs/main.log`

2. **View console output** (macOS/Linux):
   ```bash
   # Run app from terminal to see real-time logs
   /Applications/YouTube\ Downloader.app/Contents/MacOS/YouTube\ Downloader
   ```

3. **Check the troubleshooting section** in [BUILD.md](./BUILD.md)

4. **Open an issue on GitHub** with:
   - Your platform and architecture
   - Relevant log file entries
   - Steps to reproduce

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on your target platform(s)
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review log files (see [DEBUGGING.md](./DEBUGGING.md))
3. Check [BUILD.md](./BUILD.md) for build-related issues
4. Open an issue on GitHub with log file entries

---

**Note**: This application is designed for personal use. Ensure compliance with YouTube's Terms of Service when downloading content.
