# YouTube Video Downloader

A desktop application built with Electron that allows users to download YouTube videos with custom start and end times. Built with React, Electron, and Python yt-dlp.

## Features

- 🎥 **YouTube Video Download**: Download videos with custom quality selection
- ✂️ **Video Cutting**: Specify start and end times to download specific segments
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

1. **Build the application**:
   ```bash
   pnpm electron:build
   ```

2. **Output**: The built application will be in the `dist-electron` directory

3. **Platform-specific builds**:
   - The build process automatically detects your platform
   - For cross-platform builds, use CI/CD or build on each target platform

## Usage

1. **Enter YouTube URL**: Paste a valid YouTube URL in the input field
2. **Optional: Set time range**: 
   - Enter start time (in seconds) to begin download from a specific point
   - Enter end time (in seconds) to stop download at a specific point
   - Leave empty to download the full video
3. **Click Download**: The app will extract video information and show a save dialog
4. **Choose save location**: Select where to save the downloaded video
5. **Monitor progress**: Watch real-time download progress with percentage and speed
6. **Cancel if needed**: Use the Cancel button to stop an in-progress download

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

When start/end times are specified:
1. Full video is downloaded to a temporary location
2. FFmpeg is used to cut the video segment
3. Cut video is saved to user-selected location
4. Temporary full video is automatically cleaned up

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
   - Check that start time is less than end time
   - Verify the video format supports cutting

### Production Build Issues

- **Python not bundled**: Ensure Python script is included in `extraResources` in `package.json`
- **FFmpeg not bundled**: FFmpeg needs to be included in the app bundle for production
- **Large app size**: Consider using platform-specific builds to reduce size

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
1. Check the troubleshooting section
2. Review Electron console logs (View → Toggle Developer Tools)
3. Open an issue on GitHub

---

**Note**: This application is designed for personal use. Ensure compliance with YouTube's Terms of Service when downloading content.
