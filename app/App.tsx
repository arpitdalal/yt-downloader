import { useEffect, useState } from "react";
import {
  electronAPI,
  type VideoInfo,
  type DownloadProgressData,
} from "./lib/electron-api.js";

type DownloadStatus =
  | "idle"
  | "extracting"
  | "downloading"
  | "completed"
  | "error";

export default function App() {
  const [url, setUrl] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [status, setStatus] = useState<DownloadStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Set up progress listener
  useEffect(() => {
    if (!window.electronAPI) {
      return;
    }

    window.electronAPI.onDownloadProgress((data: DownloadProgressData) => {
      if (status === "downloading") {
        setProgress(data.percent || 0);
      }
    });

    return () => {
      window.electronAPI.removeDownloadProgressListener();
    };
  }, [status]);

  const sanitizeFilename = (filename: string): string => {
    // Remove emojis and other special Unicode characters
    // Emoji ranges: U+1F300-U+1F9FF, U+2600-U+26FF, U+2700-U+27BF, U+FE00-U+FE0F, U+1F900-U+1F9FF, U+1F1E0-U+1F1FF
    // Also remove other problematic Unicode characters
    let sanitized = filename
      // Remove emojis and emoji-related characters
      .replace(/[\u{1F300}-\u{1F9FF}]/gu, "") // Miscellaneous Symbols and Pictographs
      .replace(/[\u{2600}-\u{26FF}]/gu, "") // Miscellaneous Symbols
      .replace(/[\u{2700}-\u{27BF}]/gu, "") // Dingbats
      .replace(/[\u{FE00}-\u{FE0F}]/gu, "") // Variation Selectors
      .replace(/[\u{1F900}-\u{1F9FF}]/gu, "") // Supplemental Symbols and Pictographs
      .replace(/[\u{1F1E0}-\u{1F1FF}]/gu, "") // Regional Indicator Symbols
      .replace(/[\u{200D}]/gu, "") // Zero Width Joiner
      .replace(/[\u{FE0F}]/gu, "") // Variation Selector-16
      // Remove other special Unicode characters (keep ASCII alphanumeric, spaces, hyphens, underscores, periods)
      .replace(/[^\x20-\x7E\u00A0-\u00FF]/g, "") // Keep ASCII and Latin-1 Supplement, remove rest
      // Remove invalid filename characters
      .replace(/[<>:"/\\|?*]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .substring(0, 200); // Limit length

    return sanitized;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    if (!window.electronAPI) {
      setError(
        "Electron API is not available. Please ensure the app is running in Electron."
      );
      setStatus("error");
      return;
    }

    // Validate inputs
    const start = startTime.trim() ? parseInt(startTime.trim(), 10) : null;
    const end = endTime.trim() ? parseInt(endTime.trim(), 10) : null;

    if (start !== null && (isNaN(start) || start < 0)) {
      setError("Start time must be a valid positive number");
      setStatus("error");
      return;
    }

    if (end !== null && (isNaN(end) || end < 0)) {
      setError("End time must be a valid positive number");
      setStatus("error");
      return;
    }

    if (start !== null && end !== null && start >= end) {
      setError("End time must be greater than start time");
      setStatus("error");
      return;
    }

    // Reset state
    setError(null);
    setSuccessMessage(null);
    setProgress(0);
    setVideoInfo(null);

    try {
      // Step 1: Extract video info
      setStatus("extracting");
      const info = await window.electronAPI.extractVideoInfo(url.trim());

      if (!info) {
        throw new Error("Failed to extract video information");
      }

      setVideoInfo(info);

      // Step 2: Show save dialog
      const sanitizedTitle = sanitizeFilename(info.title || "video");
      const defaultFilename = `${sanitizedTitle}.mp4`;

      const dialogResult = await window.electronAPI.showSaveDialog({
        defaultFilename,
      });

      if (dialogResult.canceled) {
        setStatus("idle");
        return;
      }

      if (!dialogResult.filePath) {
        setError("No file path selected");
        setStatus("error");
        return;
      }

      // Step 3: Start download
      setStatus("downloading");
      setProgress(0);

      const result = await window.electronAPI.downloadVideo({
        url: url.trim(),
        savePath: dialogResult.filePath,
        startTime: start,
        endTime: end,
      });

      setStatus("completed");
      setProgress(100);
      setSuccessMessage(
        `Download completed! File saved to: ${result.filePath}`
      );

      // Reset form
      setUrl("");
      setStartTime("");
      setEndTime("");
    } catch (err) {
      // Ignore cancellation errors - user already canceled
      const errorMessage = err instanceof Error ? err.message : String(err);
      if (errorMessage.includes("Download canceled by user") || errorMessage.includes("canceled by user")) {
        return;
      }
      setStatus("error");
      setError(errorMessage);
    }
  };

  const handleCancel = async () => {
    if (!window.electronAPI) {
      return;
    }
    try {
      await window.electronAPI.cancelDownload();
      setStatus("idle");
      setProgress(0);
      setError(null);
      setUrl("");
      setStartTime("");
      setEndTime("");
      setVideoInfo(null);
      setSuccessMessage(null);
    } catch (err) {
      console.error("Failed to cancel download:", err);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-4 sm:py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <div className="mb-6 sm:mb-8">
          <div className="text-center sm:text-left">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 mb-2">
              YouTube Video Downloader
            </h1>
            <p className="text-sm sm:text-base text-gray-600">
              Download and cut YouTube videos with custom start and end times
            </p>
          </div>
        </div>

        {/* Download Form */}
        <div className="bg-white rounded-lg shadow-sm p-4 sm:p-6 mb-6 sm:mb-8">
          <h2 className="text-base sm:text-lg font-semibold text-gray-900 mb-4">
            Download Video
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="url"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                YouTube URL
              </label>
              <input
                type="url"
                id="url"
                name="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={status === "extracting" || status === "downloading"}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="startTime"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Start Time (seconds)
                </label>
                <input
                  type="number"
                  id="startTime"
                  name="startTime"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  placeholder="0"
                  min="0"
                  step="1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  disabled={status === "extracting" || status === "downloading"}
                />
              </div>

              <div>
                <label
                  htmlFor="endTime"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  End Time (seconds)
                </label>
                <input
                  type="number"
                  id="endTime"
                  name="endTime"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  placeholder="Leave empty for full video"
                  min="0"
                  step="1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  disabled={status === "extracting" || status === "downloading"}
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={
                  status === "extracting" ||
                  status === "downloading" ||
                  !url.trim()
                }
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === "extracting"
                  ? "Extracting video info..."
                  : status === "downloading"
                  ? "Downloading..."
                  : "Download Video"}
              </button>

              {status === "downloading" && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>

          {/* Progress Bar */}
          {(status === "downloading" || status === "extracting") && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-600 font-medium">
                  {status === "extracting"
                    ? "Extracting video information..."
                    : "Download Progress"}
                </span>
                {status === "downloading" && (
                  <span className="text-xs text-gray-600 font-medium">
                    {progress.toFixed(1)}%
                  </span>
                )}
              </div>
              {status === "downloading" && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, progress))}%`,
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {/* Success Message */}
          {successMessage && (
            <div className="mt-4 p-4 rounded-md bg-green-50 border border-green-200 text-green-800">
              <p className="font-medium">{successMessage}</p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-4 rounded-md bg-red-50 border border-red-200 text-red-800">
              <p className="font-medium">{error}</p>
            </div>
          )}

          {/* Video Info Display */}
          {videoInfo && status !== "idle" && (
            <div className="mt-4 p-4 rounded-md bg-gray-50 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">
                Video Information
              </h3>
              <p className="text-sm text-gray-700">{videoInfo.title}</p>
              {videoInfo.uploader && (
                <p className="text-xs text-gray-500 mt-1">
                  by {videoInfo.uploader}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
