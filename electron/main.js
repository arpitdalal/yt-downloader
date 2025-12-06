import { spawn } from "child_process";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import log from "electron-log";
import { existsSync, readdirSync, statSync } from "fs";
import os from "os";
import { dirname, join, resolve } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configure logging
log.transports.file.level = "info";
log.transports.console.level =
  process.env.NODE_ENV === "development" ? "debug" : "info";

// Keep a global reference of the window object
let mainWindow = null;
let currentDownloadProcess = null;
let isDownloadCanceled = false;

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

// Log file location for debugging (only in production)
if (!isDev) {
  console.log("Log file:", log.transports.file.getFile().path);
}

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
  // Log startup diagnostics
  log.info("App starting", {
    isDev,
    isPackaged: app.isPackaged,
    platform: process.platform,
    arch: process.arch,
    resourcesPath: process.resourcesPath,
    appPath: app.getAppPath(),
  });

  // Log Python and FFmpeg paths at startup
  try {
    const pythonPath = getPythonPath();
    const ffmpegPath = getFfmpegPath();
    const scriptPath = getPythonScriptPath();

    log.info("Resource paths", {
      pythonPath,
      pythonExists: existsSync(pythonPath),
      ffmpegPath,
      ffmpegExists: existsSync(ffmpegPath),
      scriptPath,
      scriptExists: existsSync(scriptPath),
    });

    // List Python directory contents for debugging
    if (!isDev && process.platform !== "win32") {
      const pythonDir = join(process.resourcesPath, "python");
      const pythonBinDir = join(pythonDir, "bin");
      try {
        if (existsSync(pythonBinDir)) {
          const binFiles = readdirSync(pythonBinDir);
          log.info("Python bin directory contents", {
            path: pythonBinDir,
            files: binFiles,
          });
        }
        if (existsSync(pythonDir)) {
          const pythonFiles = readdirSync(pythonDir);
          log.info("Python directory contents", {
            path: pythonDir,
            files: pythonFiles,
          });
        }
      } catch (error) {
        log.warn("Could not list Python directory", { error: error.message });
      }
    }
  } catch (error) {
    log.error("Error checking resource paths at startup", {
      error: error.message,
      stack: error.stack,
    });
  }

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
    if (platform === "win32") {
      // Windows: Python embeddable has python.exe in root
      return join(process.resourcesPath, "python", "python.exe");
    } else {
      // macOS/Linux: Python venv has python3 in bin/ directory
      return join(process.resourcesPath, "python", "bin", "python3");
    }
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
      pythonPath,
      // List directory contents for debugging
      pythonDir:
        process.platform === "win32"
          ? dirname(pythonPath)
          : join(process.resourcesPath, "python", "bin"),
    });
    throw new Error(error);
  }

  // On macOS/Linux, check if executable has execute permissions
  if (process.platform !== "win32") {
    try {
      const stats = statSync(pythonPath);
      if (!(stats.mode & 0o111)) {
        log.warn("Python executable may not have execute permissions", {
          pythonPath,
          mode: stats.mode.toString(8),
        });
      }
    } catch (error) {
      log.warn("Could not check Python executable permissions", {
        pythonPath,
        error: error.message,
      });
    }
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

      log.info("Validating Python setup for extract-video-info", {
        pythonPath,
        scriptPath,
        pythonExists: existsSync(pythonPath),
        scriptExists: existsSync(scriptPath),
        resourcesPath: process.resourcesPath,
      });

      // Validate Python exists before spawning
      if (!isDev) {
        validatePythonPath(pythonPath);
      }
    } catch (error) {
      log.error("Python configuration error for extract-video-info", {
        error: error.message,
        pythonPath,
        scriptPath,
        resourcesPath: process.resourcesPath,
        stack: error.stack,
      });
      reject(new Error(`Configuration error: ${error.message}`));
      return;
    }

    // On Windows, set working directory to Python directory for DLL loading
    const pythonDir =
      !isDev && process.platform === "win32" ? dirname(pythonPath) : undefined;

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
      } else if (
        error.code === "EACCES" ||
        error.message.includes("permission")
      ) {
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

// IPC: Show open dialog
ipcMain.handle("show-open-dialog", async (event, options) => {
  const { filters } = options;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openFile"],
    filters: filters || [
      { name: "Video Files", extensions: ["mp4", "webm", "mkv", "mov", "avi"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  return { canceled: result.canceled, filePaths: result.filePaths };
});

// IPC: Process local video
ipcMain.handle("process-local-video", async (event, options) => {
  const { inputPath, savePath, sections } = options;

  return new Promise((resolve, reject) => {
    // Validate inputs
    if (!inputPath || !savePath) {
      reject(new Error("Input path and save path are required"));
      return;
    }

    // Reset cancellation flag
    isDownloadCanceled = false;

    // Kill any existing download process
    if (currentDownloadProcess) {
      log.info("Killing existing process");
      currentDownloadProcess.kill();
      currentDownloadProcess = null;
    }

    const pythonPath = getPythonPath();
    let scriptPath;
    try {
      scriptPath = getPythonScriptPath();
      if (!isDev) {
        validatePythonPath(pythonPath);
      }
    } catch (error) {
      reject(new Error(`Configuration error: ${error.message}`));
      return;
    }

    // Prepare arguments for local processing
    // Format: script.py --local <input_path> <sections_json> <output_path>
    const args = [scriptPath, "--local", inputPath];

    if (sections && Array.isArray(sections) && sections.length > 0) {
      args.push(JSON.stringify(sections));
    } else {
      args.push("[]"); // Empty sections list
    }

    args.push(savePath);

    log.info("Starting local video processing", {
      inputPath,
      savePath,
      sections,
      pythonPath,
    });

    const pythonDir =
      !isDev && process.platform === "win32" ? dirname(pythonPath) : undefined;

    const ffmpegPath = getFfmpegPath();
    const env = { ...process.env, FFMPEG_PATH: ffmpegPath };

    const pythonProcess = spawn(pythonPath, args, {
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
      cwd: pythonDir,
      env: env,
    });
    currentDownloadProcess = pythonProcess;

    let stdout = "";
    let stderr = "";

    pythonProcess.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on("data", (data) => {
      const error = data.toString();
      stderr += error;
    });

    pythonProcess.on("close", (code) => {
      currentDownloadProcess = null;

      if (isDownloadCanceled) {
        reject(new Error("Processing canceled by user"));
        return;
      }

      if (code === 0) {
        try {
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
            reject(new Error(result.error_message || "Processing failed"));
          }
        } catch (error) {
          log.error("Failed to parse processing result", {
            error: error.message,
            stdout,
          });
          reject(
            new Error(`Failed to parse processing result: ${error.message}`)
          );
        }
      } else {
        log.error("Processing failed", {
          code,
          stderr,
        });
        reject(
          new Error(
            `Processing failed: ${stderr || `Process exited with code ${code}`}`
          )
        );
      }
    });

    pythonProcess.on("error", (error) => {
      currentDownloadProcess = null;
      log.error("Failed to start processing", { error: error.message });
      reject(new Error(`Failed to start processing: ${error.message}`));
    });
  });
});

// IPC: Download video
ipcMain.handle("download-video", async (event, options) => {
  const { url, savePath, startTime, endTime, sections } = options;

  return new Promise((resolve, reject) => {
    // Validate inputs
    let validatedUrl, validatedPath;
    let sectionsArray = null; // Declare outside try block for proper scope

    try {
      validatedUrl = validateYouTubeUrl(url);
      validatedPath = validateSavePath(savePath);

      // Handle sections array (new format) or legacy startTime/endTime

      if (sections && Array.isArray(sections) && sections.length > 0) {
        sectionsArray = sections.map((section, index) => {
          const { start, end } = section;

          // Start time of subsequent sections cannot be empty
          if (index > 0 && (start === null || start === undefined)) {
            throw new Error(
              `Start time of section ${index + 1} cannot be empty`
            );
          }

          // End time of section with next section cannot be empty
          if (
            index < sections.length - 1 &&
            (end === null || end === undefined)
          ) {
            throw new Error(
              `End time of section ${
                index + 1
              } cannot be empty (it has a next section)`
            );
          }

          // Validate start time if provided
          if (start !== null && start !== undefined) {
            if (
              typeof start !== "number" ||
              start < 0 ||
              !Number.isInteger(start)
            ) {
              throw new Error(
                `Start time of section ${
                  index + 1
                } must be a non-negative integer`
              );
            }
          }

          // Validate end time if provided
          if (end !== null && end !== undefined) {
            if (typeof end !== "number" || end < 0 || !Number.isInteger(end)) {
              throw new Error(
                `End time of section ${
                  index + 1
                } must be a non-negative integer`
              );
            }
          }

          // Validate start < end within section
          if (
            start !== null &&
            start !== undefined &&
            end !== null &&
            end !== undefined &&
            start >= end
          ) {
            throw new Error(
              `End time must be greater than start time in section ${index + 1}`
            );
          }

          // Validate ordering: next section's start must not be before current section's end
          if (index < sections.length - 1) {
            const nextSection = sections[index + 1];
            const nextStart = nextSection.start;
            if (
              end !== null &&
              end !== undefined &&
              nextStart !== null &&
              nextStart !== undefined &&
              nextStart < end
            ) {
              throw new Error(
                `Start time of section ${
                  index + 2
                } (${nextStart}s) cannot be before end time of section ${
                  index + 1
                } (${end}s)`
              );
            }
          }

          return { start, end };
        });
      } else {
        // Legacy format: convert startTime/endTime to single section
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

        if (startTime !== null && endTime !== null && startTime >= endTime) {
          throw new Error("End time must be greater than start time");
        }

        // Convert to sections array for backward compatibility
        sectionsArray = [{ start: startTime ?? null, end: endTime ?? null }];
      }
    } catch (error) {
      log.error("Invalid input for download", {
        error: error.message,
        url,
        savePath,
        startTime,
        endTime,
        sections,
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

      log.info("Validating Python setup for download-video", {
        pythonPath,
        scriptPath,
        pythonExists: existsSync(pythonPath),
        scriptExists: existsSync(scriptPath),
        resourcesPath: process.resourcesPath,
      });

      // Validate Python exists before spawning
      if (!isDev) {
        validatePythonPath(pythonPath);
      }
    } catch (error) {
      log.error("Python configuration error for download-video", {
        error: error.message,
        pythonPath,
        scriptPath,
        resourcesPath: process.resourcesPath,
        stack: error.stack,
      });
      reject(new Error(`Configuration error: ${error.message}`));
      return;
    }

    const args = [
      scriptPath,
      validatedUrl,
      "false",
      "bestvideo+bestaudio/best",
    ];

    // Add sections as JSON string if provided, otherwise use legacy format
    if (sectionsArray && sectionsArray.length > 0) {
      args.push(JSON.stringify(sectionsArray));
    } else {
      // Legacy format: add start and end times if provided
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
    }

    // Add output path (required)
    args.push(validatedPath);

    log.info("Starting download", {
      url: validatedUrl,
      savePath: validatedPath,
      sections: sectionsArray,
      pythonPath,
    });

    // On Windows, set working directory to Python directory for DLL loading
    const pythonDir =
      !isDev && process.platform === "win32" ? dirname(pythonPath) : undefined;

    // Get ffmpeg path and pass it to Python script via environment variable
    const ffmpegPath = getFfmpegPath();
    const env = { ...process.env, FFMPEG_PATH: ffmpegPath };

    const pythonProcess = spawn(pythonPath, args, {
      shell: false,
      stdio: ["pipe", "pipe", "pipe"],
      cwd: pythonDir, // Set working directory for Windows Python embeddable
      env: env, // Pass ffmpeg path via environment variable
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
      } else if (
        error.code === "EACCES" ||
        error.message.includes("permission")
      ) {
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

// IPC: Get log file path (for debugging)
ipcMain.handle("get-log-path", async () => {
  return {
    logPath: log.transports.file.getFile().path,
    resourcesPath: process.resourcesPath,
    appPath: app.getAppPath(),
    isPackaged: app.isPackaged,
  };
});
