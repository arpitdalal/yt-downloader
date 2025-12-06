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

type Section = { start: string; end: string };

export default function App() {
  const [url, setUrl] = useState("");
  const [localFile, setLocalFile] = useState<string | null>(null);
  const [sections, setSections] = useState<Section[]>([{ start: "", end: "" }]);
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

  const getErrorMessage = (error: unknown): string => {
    const message = error instanceof Error ? error.message : String(error);

    // Map technical errors to user-friendly messages
    if (message.includes("Invalid input")) {
      if (message.includes("URL")) {
        return "Please enter a valid YouTube URL.";
      }
      if (message.includes("Save path")) {
        return "Please select a valid save location.";
      }
      if (message.includes("time")) {
        return "Please enter valid time values (non-negative integers).";
      }
      return "Please check your input and try again.";
    }
    if (
      message.includes("Failed to start Python process") ||
      message.includes("Configuration error")
    ) {
      return "Unable to start download process. Please ensure the application is properly installed.";
    }
    if (message.includes("403") || message.includes("Forbidden")) {
      return "This video is not available for download. It may be restricted, private, or region-locked.";
    }
    if (
      message.includes("format is not available") ||
      message.includes("Requested format")
    ) {
      return "The requested video quality is not available. Please try again.";
    }
    if (message.includes("disk space") || message.includes("No space")) {
      return "Not enough disk space. Please free up space and try again.";
    }
    if (message.includes("Failed to extract video information")) {
      return "Unable to get video information. Please check the URL and try again.";
    }
    if (message.includes("Download process failed")) {
      return "Download failed. The video may be unavailable or there was a network error. Please try again.";
    }
    if (message.includes("Invalid YouTube URL")) {
      return "Please enter a valid YouTube URL (e.g., https://www.youtube.com/watch?v=...).";
    }

    // Return original message if no mapping found
    return message || "An unexpected error occurred. Please try again.";
  };

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

  const addSection = () => {
    setSections([...sections, { start: "", end: "" }]);
  };

  const removeSection = (index: number) => {
    if (sections.length > 1) {
      setSections(sections.filter((_, i) => i !== index));
    }
  };

  const updateSection = (
    index: number,
    field: "start" | "end",
    value: string
  ) => {
    const newSections = [...sections];
    newSections[index] = { ...newSections[index], [field]: value };
    setSections(newSections);
  };

  const validateSections = (): string | null => {
    // At least one section required
    if (sections.length === 0) {
      return "At least one section is required";
    }

    // Validate each section
    for (let i = 0; i < sections.length; i++) {
      const section = sections[i];
      const start = section.start.trim()
        ? parseInt(section.start.trim(), 10)
        : null;
      const end = section.end.trim() ? parseInt(section.end.trim(), 10) : null;

      // Start time of subsequent sections cannot be empty
      if (i > 0 && start === null) {
        return `Start time of section ${i + 1} cannot be empty`;
      }

      // End time of section with next section cannot be empty
      if (i < sections.length - 1 && end === null) {
        return `End time of section ${
          i + 1
        } cannot be empty (it has a next section)`;
      }

      // Validate start time if provided
      if (start !== null) {
        if (isNaN(start) || start < 0) {
          return `Start time of section ${
            i + 1
          } must be a valid positive number`;
        }
      }

      // Validate end time if provided
      if (end !== null) {
        if (isNaN(end) || end < 0) {
          return `End time of section ${i + 1} must be a valid positive number`;
        }
      }

      // Validate start < end within section
      if (start !== null && end !== null && start >= end) {
        return `End time must be greater than start time in section ${i + 1}`;
      }

      // Validate ordering: next section's start must not be before current section's end
      if (i < sections.length - 1) {
        const nextSection = sections[i + 1];
        const nextStart = nextSection.start.trim()
          ? parseInt(nextSection.start.trim(), 10)
          : null;

        if (end !== null && nextStart !== null && nextStart < end) {
          return `Start time of section ${
            i + 2
          } (${nextStart}s) cannot be before end time of section ${
            i + 1
          } (${end}s)`;
        }
      }
    }

    return null;
  };

  const handleChooseFile = async () => {
    if (!window.electronAPI) return;
    try {
      const result = await window.electronAPI.showOpenDialog({
        filters: [
          {
            name: "Video Files",
            extensions: ["mp4", "webm", "mkv", "mov", "avi"],
          },
        ],
      });
      if (!result.canceled && result.filePaths.length > 0) {
        setLocalFile(result.filePaths[0]);
        setUrl(""); // Clear URL if file selected
        setError(null);
      }
    } catch (err) {
      console.error("Failed to choose file:", err);
      const message = err instanceof Error ? err.message : String(err);
      setError(
        err instanceof Error ? err.message : "Failed to open file picker"
      );
    }
  };

  const handleClearLocalFile = () => {
    setLocalFile(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() && !localFile) return;

    if (!window.electronAPI) {
      setError(
        "Electron API is not available. Please ensure the app is running in Electron."
      );
      setStatus("error");
      return;
    }

    // Validate sections
    const validationError = validateSections();
    if (validationError) {
      setError(validationError);
      setStatus("error");
      return;
    }

    // Reset state
    setError(null);
    setSuccessMessage(null);
    setProgress(0);
    setVideoInfo(null);

    try {
      if (localFile) {
        // Handle local file processing
        setStatus("downloading"); // Use downloading state for processing UI

        // Show save dialog
        const originalFilename = localFile.split(/[/\\]/).pop() || "video.mp4";
        const defaultFilename = `processed_${originalFilename}`;

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

        // Convert sections to format expected by backend
        const sectionsArray = sections.map((s) => ({
          start: s.start.trim() ? parseInt(s.start.trim(), 10) : null,
          end: s.end.trim() ? parseInt(s.end.trim(), 10) : null,
        }));

        const result = await window.electronAPI.processLocalVideo({
          inputPath: localFile,
          savePath: dialogResult.filePath,
          sections: sectionsArray,
        });

        setStatus("completed");
        setSuccessMessage(
          `Processing completed! File saved to: ${result.filePath}`
        );
      } else {
        // Handle YouTube download
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

        // Convert sections to format expected by backend
        const sectionsArray = sections.map((s) => ({
          start: s.start.trim() ? parseInt(s.start.trim(), 10) : null,
          end: s.end.trim() ? parseInt(s.end.trim(), 10) : null,
        }));

        const result = await window.electronAPI.downloadVideo({
          url: url.trim(),
          savePath: dialogResult.filePath,
          sections: sectionsArray,
        });

        setStatus("completed");
        setProgress(100);
        setSuccessMessage(
          `Download completed! File saved to: ${result.filePath}`
        );
      }

      // Reset form (optional, maybe keep it populated? Current behavior resets)
      if (!localFile) setUrl("");
      setLocalFile(null);
      setSections([{ start: "", end: "" }]);
    } catch (err) {
      // Ignore cancellation errors - user already canceled
      const errorMessage = err instanceof Error ? err.message : String(err);
      if (
        errorMessage.includes("Download canceled by user") ||
        errorMessage.includes("canceled by user") ||
        errorMessage.includes("Processing canceled by user")
      ) {
        return;
      }
      setStatus("error");
      setError(getErrorMessage(err));
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
      setLocalFile(null);
      setSections([{ start: "", end: "" }]);
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
            Download or Process Video
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
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
                required={!localFile}
                disabled={
                  status === "extracting" ||
                  status === "downloading" ||
                  !!localFile
                }
              />
            </div>

            <div className="flex items-center gap-4 my-4">
              <div className="flex-1 border-t border-gray-300" />
              <span className="text-gray-500 text-sm">OR</span>
              <div className="flex-1 border-t border-gray-300" />
            </div>

            <div className="mb-6">
              {localFile ? (
                <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <div className="flex items-center overflow-hidden mr-2">
                    <span className="text-sm font-medium text-blue-900 mr-2">
                      File:
                    </span>
                    <span
                      className="text-sm text-blue-800 truncate"
                      title={localFile}
                    >
                      {localFile.split(/[/\\]/).pop()}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={handleClearLocalFile}
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium whitespace-nowrap"
                    disabled={status === "downloading"}
                  >
                    Change
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={handleChooseFile}
                  disabled={status === "extracting" || status === "downloading"}
                  className="w-full py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Choose Video File
                </button>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-gray-700">
                  Video Sections
                </label>
                <button
                  type="button"
                  onClick={addSection}
                  disabled={status === "extracting" || status === "downloading"}
                  className="px-3 py-1 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  + Add Section
                </button>
              </div>

              {sections.map((section, index) => (
                <div
                  key={index}
                  className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-4 items-end"
                >
                  <div>
                    <label
                      htmlFor={`startTime-${index}`}
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Start Time (seconds){" "}
                      {index > 0 && <span className="text-red-500">*</span>}
                    </label>
                    <input
                      type="number"
                      id={`startTime-${index}`}
                      name={`startTime-${index}`}
                      value={section.start}
                      onChange={(e) =>
                        updateSection(index, "start", e.target.value)
                      }
                      placeholder={index === 0 ? "0" : "Required"}
                      min="0"
                      step="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      disabled={
                        status === "extracting" || status === "downloading"
                      }
                      required={index > 0}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor={`endTime-${index}`}
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      End Time (seconds){" "}
                      {index < sections.length - 1 && (
                        <span className="text-red-500">*</span>
                      )}
                    </label>
                    <input
                      type="number"
                      id={`endTime-${index}`}
                      name={`endTime-${index}`}
                      value={section.end}
                      onChange={(e) =>
                        updateSection(index, "end", e.target.value)
                      }
                      placeholder={
                        index < sections.length - 1
                          ? "Required"
                          : "Leave empty for end of video"
                      }
                      min="0"
                      step="1"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      disabled={
                        status === "extracting" || status === "downloading"
                      }
                      required={index < sections.length - 1}
                    />
                  </div>

                  {sections.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeSection(index)}
                      disabled={
                        status === "extracting" || status === "downloading"
                      }
                      className="px-3 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Remove section"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={
                  status === "extracting" ||
                  status === "downloading" ||
                  (!url.trim() && !localFile)
                }
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === "extracting"
                  ? "Extracting video info..."
                  : status === "downloading"
                  ? localFile
                    ? "Processing..."
                    : "Downloading..."
                  : localFile
                  ? "Process Video"
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
                    : localFile
                    ? "Processing Progress"
                    : "Download Progress"}
                </span>
                {status === "downloading" && !localFile && (
                  <span className="text-xs text-gray-600 font-medium">
                    {progress.toFixed(1)}%
                  </span>
                )}
              </div>
              {status === "downloading" && !localFile && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, progress))}%`,
                    }}
                  />
                </div>
              )}
              {status === "downloading" && localFile && (
                <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                  <div className="bg-blue-600 h-2 rounded-full animate-pulse w-full opacity-75" />
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
