import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { spawn } from "child_process";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { existsSync } from "fs";
import os from "os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Keep a global reference of the window object
let mainWindow = null;
let currentDownloadProcess = null;

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

async function waitForDevServer(maxAttempts = 30) {
  const http = await import("http");
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const checkServer = () => {
      attempts++;
      const req = http.request("http://localhost:5173", { method: "HEAD" }, (res) => {
        resolve();
      });
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
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    // In development, wait for Vite dev server and load from it
    try {
      await waitForDevServer();
      await mainWindow.loadURL("http://localhost:5173");
      mainWindow.webContents.openDevTools();
    } catch (error) {
      console.error("Failed to connect to dev server:", error);
      mainWindow.loadURL("data:text/html,<h1>Dev server not available</h1><p>Please start the dev server with: pnpm dev:renderer</p>");
    }
  } else {
    // In production, load from built files
    const indexPath = join(__dirname, "../dist/index.html");
    if (existsSync(indexPath)) {
      mainWindow.loadFile(indexPath);
    } else {
      console.error("Production build not found at:", indexPath);
      mainWindow.loadURL("data:text/html,<h1>Build not found</h1><p>Please run: pnpm build</p>");
    }
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(async () => {
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("window-all-closed", () => {
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

// Helper to get Python script path
function getPythonScriptPath() {
  if (isDev) {
    return join(process.cwd(), "python", "downloader.py");
  } else {
    return join(process.resourcesPath, "python", "downloader.py");
  }
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
    const pythonPath = getPythonPath();
    const scriptPath = getPythonScriptPath();

    const pythonProcess = spawn(pythonPath, [scriptPath, "--validate", url]);

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
          reject(new Error(`Failed to parse video info: ${error.message}`));
        }
      } else {
        reject(
          new Error(`Python process failed: ${stderr || "Unknown error"}`)
        );
      }
    });

    pythonProcess.on("error", (error) => {
      reject(new Error(`Failed to start Python process: ${error.message}`));
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
    // Kill any existing download process
    if (currentDownloadProcess) {
      currentDownloadProcess.kill();
      currentDownloadProcess = null;
    }

    const pythonPath = getPythonPath();
    const scriptPath = getPythonScriptPath();

    const args = [scriptPath, url, "false", "bestvideo+bestaudio/best"];

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
    args.push(savePath);

    const pythonProcess = spawn(pythonPath, args);
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
        }
      }
    });

    pythonProcess.on("close", (code) => {
      currentDownloadProcess = null;

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
          reject(
            new Error(`Failed to parse download result: ${error.message}`)
          );
        }
      } else {
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
      reject(new Error(`Failed to start download process: ${error.message}`));
    });
  });
});

// IPC: Cancel download
ipcMain.handle("cancel-download", async () => {
  if (currentDownloadProcess) {
    currentDownloadProcess.kill();
    currentDownloadProcess = null;
    return { success: true };
  }
  return { success: false, message: "No active download" };
});
