import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { spawn } from "child_process";
import { join, dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { existsSync } from "fs";
import os from "os";
import log from "electron-log";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configure logging
log.transports.file.level = "info";
log.transports.console.level = process.env.NODE_ENV === "development" ? "debug" : "info";

// Keep a global reference of the window object
let mainWindow = null;
let currentDownloadProcess = null;
let isDownloadCanceled = false;

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

async function waitForDevServer(maxAttempts = 30) {
  const http = await import("http");
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const checkServer = () => {
      attempts++;
      const req = http.request(
        "http://localhost:5173",
        { method: "HEAD" },
        (res) => {
          resolve();
        }
      );
      req.on("error", () => {
        if (attempts >= maxAttempts) {
          reject(new Error("Dev server did not start in time"));
        } else {
          setTimeout(checkServer, 1000);
        }
      });
      req.end();
    };
    checkServer();
  });
}

async function createWindow() {
  const iconPath = isDev
    ? join(process.cwd(), "build", "icons", "icon.png")
    : join(__dirname, "..", "build", "icons", "icon.png");

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: iconPath,
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true,
    },
  });

  // Set Content Security Policy
  mainWindow.webContents.session.webRequest.onHeadersReceived(
    (details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; connect-src 'self';",
          ],
        },
      });
    }
  );

  if (isDev) {
    // In development, wait for Vite dev server and load from it
    try {
      await waitForDevServer();
      await mainWindow.loadURL("http://localhost:5173");
      mainWindow.webContents.openDevTools();
    } catch (error) {
      log.error("Failed to connect to dev server", { error: error.message });
      mainWindow.loadURL(
        "data:text/html,<h1>Dev server not available</h1><p>Please start the dev server with: pnpm dev:renderer</p>"
      );
    }
  } else {
    // In production, load from built files
    const indexPath = join(__dirname, "../dist/index.html");
    if (existsSync(indexPath)) {
      mainWindow.loadFile(indexPath);
    } else {
      log.error("Production build not found", { path: indexPath });
      mainWindow.loadURL(
        "data:text/html,<h1>Build not found</h1><p>Please run: pnpm build</p>"
      );
    }
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// Cleanup on app exit
app.on("before-quit", () => {
  if (currentDownloadProcess) {
    log.info("Killing active download process on app quit");
    currentDownloadProcess.kill("SIGTERM");
    // Give process 2 seconds to clean up
    setTimeout(() => {
      if (currentDownloadProcess) {
        currentDownloadProcess.kill("SIGKILL");
      }
    }, 2000);
  }
});

app.whenReady().then(async () => {
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  // Cleanup before quit
  if (currentDownloadProcess) {
    currentDownloadProcess.kill("SIGTERM");
  }

  if (process.platform !== "darwin") {
    app.quit();
  }
});

// Helper to get Python executable path
function getPythonPath() {
  if (isDev) {
    // In development, use system Python
    return process.platform === "win32" ? "python" : "python3";
  } else {
    // In production, use bundled Python
    const platform = process.platform;
    const arch = process.arch;
    const pythonPath = join(
      process.resourcesPath,
      "python",
      platform === "win32" ? "python.exe" : "python3"
    );
    return pythonPath;
  }
}

// Validate Python executable exists and is accessible
function validatePythonPath(pythonPath) {
  if (!existsSync(pythonPath)) {
    const error = `Python executable not found at: ${pythonPath}`;
    log.error(error, {
      resourcesPath: process.resourcesPath,
      platform: process.platform,
      arch: process.arch,
    });
    throw new Error(error);
  }
  return pythonPath;
}

// Validate YouTube URL
function validateYouTubeUrl(url) {
  if (typeof url !== "string" || !url.trim()) {
    throw new Error("URL must be a non-empty string");
  }

  let urlObj;
  try {
    urlObj = new URL(url.trim());
  } catch (e) {
    throw new Error("Invalid URL format");
  }

  const allowedHosts = [
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
  ];

  const hostname = urlObj.hostname.replace(/^www\./, "");
  if (!allowedHosts.includes(hostname)) {
    throw new Error("URL must be a valid YouTube URL");
  }

  return url.trim();
}

// Validate save path
function validateSavePath(savePath) {
  if (typeof savePath !== "string" || !savePath.trim()) {
    throw new Error("Save path must be a non-empty string");
  }

  const resolved = resolve(savePath);
  const homeDir = os.homedir();

  // Only allow saving to user's home directory or subdirectories
  if (!resolved.startsWith(resolve(homeDir))) {
    throw new Error("Save path must be within user home directory");
  }

  // Prevent path traversal
  if (resolved.includes("..")) {
    throw new Error("Invalid save path");
  }

  return resolved;
}

// Helper to get Python script path
function getPythonScriptPath() {
  let scriptPath;
  if (isDev) {
    scriptPath = join(process.cwd(), "python", "downloader.py");
  } else {
    scriptPath = join(process.resourcesPath, "python", "downloader.py");
  }

  if (!existsSync(scriptPath)) {
    const error = `Python script not found at: ${scriptPath}`;
    log.error(error);
    throw new Error(error);
  }

  return scriptPath;
}

// Helper to get ffmpeg path
function getFfmpegPath() {
  if (isDev) {
    // In development, use system ffmpeg
    return "ffmpeg";
  } else {
    // In production, use bundled ffmpeg
    const platform = process.platform;
    const ffmpegPath = join(
      process.resourcesPath,
      "ffmpeg",
      platform === "win32" ? "ffmpeg.exe" : "ffmpeg"
    );
    return ffmpegPath;
  }
}

// IPC: Extract video info
ipcMain.handle("extract-video-info", async (event, url) => {
  return new Promise((resolve, reject) => {
    let validatedUrl;
    try {
      validatedUrl = validateYouTubeUrl(url);
    } catch (error) {
      log.error("Invalid URL provided", { url, error: error.message });
      reject(new Error(`Invalid input: ${error.message}`));
      return;
    }

    const pythonPath = getPythonPath();
    let scriptPath;
    try {
      scriptPath = getPythonScriptPath();
      // Validate Python exists before spawning
      if (!isDev) {
        validatePythonPath(pythonPath);
      }
    } catch (error) {
      log.error("Python configuration error", { error: error.message, pythonPath });
      reject(new Error(`Configuration error: ${error.message}`));
      return;
    }

    // On Windows, set working directory to Python directory for DLL loading
    const pythonDir = !isDev && process.platform === "win32" 
      ? dirname(pythonPath) 
      : undefined;
    
    const pythonProcess = spawn(
      pythonPath,
      [scriptPath, "--validate", validatedUrl],
      {
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
        cwd: pythonDir, // Set working directory for Windows Python embeddable
      }
    );

    let stdout = "";
    let stderr = "";

    pythonProcess.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    pythonProcess.on("close", (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          if (result.success && result.video_info) {
            resolve(result.video_info);
          } else {
            reject(new Error(result.error || "Failed to extract video info"));
          }
        } catch (error) {
          log.error("Failed to parse video info", {
            error: error.message,
            stdout,
            url: validatedUrl,
          });
          reject(new Error(`Failed to parse video info: ${error.message}`));
        }
      } else {
        log.error("Python process failed", {
          code,
          stderr,
          url: validatedUrl,
        });
        reject(
          new Error(`Python process failed: ${stderr || "Unknown error"}`)
        );
      }
    });

    pythonProcess.on("error", (error) => {
      log.error("Failed to start Python process", {
        error: error.message,
        errorCode: error.code,
        url: validatedUrl,
        pythonPath,
        scriptPath,
        pythonExists: existsSync(pythonPath),
        resourcesPath: process.resourcesPath,
      });
      // Provide more helpful error message for common Windows issues
      let errorMessage = `Failed to start download process: ${error.message}`;
      if (error.code === "ENOENT") {
        errorMessage = `Python executable not found at: ${pythonPath}. Please ensure the application is properly installed.`;
      } else if (error.code === "EACCES" || error.message.includes("permission")) {
        errorMessage = `Permission denied when trying to run Python at: ${pythonPath}. Please check file permissions.`;
      }
      reject(new Error(errorMessage));
    });
  });
});

// IPC: Show save dialog
ipcMain.handle("show-save-dialog", async (event, options) => {
  const { defaultPath, defaultFilename } = options;
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath:
      defaultPath ||
      join(os.homedir(), "Downloads", defaultFilename || "video.mp4"),
    filters: [
      { name: "Video Files", extensions: ["mp4", "webm", "mkv", "m4a"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  if (result.canceled) {
    return { canceled: true };
  }

  return { canceled: false, filePath: result.filePath };
});

// IPC: Download video
ipcMain.handle("download-video", async (event, options) => {
  const { url, savePath, startTime, endTime } = options;

  return new Promise((resolve, reject) => {
    // Validate inputs
    let validatedUrl, validatedPath;
    try {
      validatedUrl = validateYouTubeUrl(url);
      validatedPath = validateSavePath(savePath);

      // Validate time parameters
      if (startTime !== null && startTime !== undefined) {
        if (
          typeof startTime !== "number" ||
          startTime < 0 ||
          !Number.isInteger(startTime)
        ) {
          throw new Error("Start time must be a non-negative integer");
        }
      }

      if (endTime !== null && endTime !== undefined) {
        if (
          typeof endTime !== "number" ||
          endTime < 0 ||
          !Number.isInteger(endTime)
        ) {
          throw new Error("End time must be a non-negative integer");
        }
      }

      if (
        startTime !== null &&
        endTime !== null &&
        startTime >= endTime
      ) {
        throw new Error("End time must be greater than start time");
      }
    } catch (error) {
      log.error("Invalid input for download", {
        error: error.message,
        url,
        savePath,
        startTime,
        endTime,
      });
      reject(new Error(`Invalid input: ${error.message}`));
      return;
    }

    // Reset cancellation flag
    isDownloadCanceled = false;

    // Kill any existing download process
    if (currentDownloadProcess) {
      log.info("Killing existing download process");
      currentDownloadProcess.kill();
      currentDownloadProcess = null;
    }

    const pythonPath = getPythonPath();
    let scriptPath;
    try {
      scriptPath = getPythonScriptPath();
      // Validate Python exists before spawning
      if (!isDev) {
        validatePythonPath(pythonPath);
      }
    } catch (error) {
      log.error("Python configuration error", { error: error.message, pythonPath });
      reject(new Error(`Configuration error: ${error.message}`));
      return;
    }

    const args = [
      scriptPath,
      validatedUrl,
      "false",
      "bestvideo+bestaudio/best",
    ];

    // Add start and end times if provided (Python script expects them in order)
    if (startTime !== null && startTime !== undefined) {
      args.push(startTime.toString());
    } else {
      args.push(""); // Empty string if not provided
    }

    if (endTime !== null && endTime !== undefined) {
      args.push(endTime.toString());
    } else {
      args.push(""); // Empty string if not provided
    }

    // Add output path (required)
    args.push(validatedPath);

    log.info("Starting download", {
      url: validatedUrl,
      savePath: validatedPath,
      startTime,
      endTime,
      pythonPath,
    });

    // On Windows, set working directory to Python directory for DLL loading
    const pythonDir = !isDev && process.platform === "win32" 
      ? dirname(pythonPath) 
      : undefined;

    const pythonProcess = spawn(pythonPath, args, {
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
      cwd: pythonDir, // Set working directory for Windows Python embeddable
    });
    currentDownloadProcess = pythonProcess;

    let stdout = "";
    let stderr = "";

    pythonProcess.stdout.on("data", (data) => {
      const output = data.toString();
      stdout += output;
    });

    pythonProcess.stderr.on("data", (data) => {
      const error = data.toString();
      stderr += error;

      // Parse progress updates from stderr (they're JSON lines)
      const lines = error.split("\n").filter((line) => line.trim());
      for (const line of lines) {
        try {
          const parsed = JSON.parse(line.trim());
          if (
            parsed.type === "progress" &&
            parsed.percent !== null &&
            parsed.percent !== undefined
          ) {
            // Send progress update to renderer
            mainWindow?.webContents.send("download-progress", {
              percent: parsed.percent,
              downloadedBytes: parsed.downloaded_bytes,
              totalBytes: parsed.total_bytes,
              speed: parsed.speed,
              eta: parsed.eta,
            });
          }
        } catch (e) {
          // Not JSON, ignore non-progress stderr output
          // Log parsing errors for debugging
          if (isDev) {
            log.debug("Failed to parse progress line", {
              line: line.trim(),
              error: e.message,
            });
          }
        }
      }
    });

    pythonProcess.on("close", (code) => {
      currentDownloadProcess = null;

      // Check if download was canceled by user
      if (isDownloadCanceled) {
        reject(new Error("Download canceled by user"));
        return;
      }

      if (code === 0) {
        try {
          // Extract JSON from stdout
          let jsonStr = stdout.trim();
          if (!jsonStr.startsWith("{")) {
            const jsonMatch = jsonStr.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g);
            if (jsonMatch && jsonMatch.length > 0) {
              jsonStr = jsonMatch[jsonMatch.length - 1];
            }
          }

          const result = JSON.parse(jsonStr);

          if (result.success) {
            resolve({
              success: true,
              filePath: result.file_path,
              fileSize: result.file_size,
            });
          } else {
            reject(new Error(result.error_message || "Download failed"));
          }
        } catch (error) {
          log.error("Failed to parse download result", {
            error: error.message,
            stdout,
            url: validatedUrl,
          });
          reject(
            new Error(`Failed to parse download result: ${error.message}`)
          );
        }
      } else {
        log.error("Download process failed", {
          code,
          stderr,
          url: validatedUrl,
          savePath: validatedPath,
        });
        reject(
          new Error(
            `Download process failed: ${
              stderr || `Process exited with code ${code}`
            }`
          )
        );
      }
    });

    pythonProcess.on("error", (error) => {
      currentDownloadProcess = null;
      log.error("Failed to start download process", {
        error: error.message,
        errorCode: error.code,
        url: validatedUrl,
        savePath: validatedPath,
        pythonPath,
        scriptPath,
        pythonExists: existsSync(pythonPath),
        resourcesPath: process.resourcesPath,
      });
      // Provide more helpful error message for common Windows issues
      let errorMessage = `Failed to start download process: ${error.message}`;
      if (error.code === "ENOENT") {
        errorMessage = `Python executable not found at: ${pythonPath}. Please ensure the application is properly installed.`;
      } else if (error.code === "EACCES" || error.message.includes("permission")) {
        errorMessage = `Permission denied when trying to run Python at: ${pythonPath}. Please check file permissions.`;
      }
      reject(new Error(errorMessage));
    });
  });
});

// IPC: Cancel download
ipcMain.handle("cancel-download", async () => {
  if (currentDownloadProcess) {
    isDownloadCanceled = true;
    currentDownloadProcess.kill();
    currentDownloadProcess = null;
    return { success: true };
  }
  return { success: false, message: "No active download" };
});
