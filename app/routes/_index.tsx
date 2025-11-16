import { spawn } from "child_process";
import { useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "react-router";
import { useFetcher, useLoaderData } from "react-router";
import { DownloadService } from "../lib/download-service.js";
import type { Download, QueueStatus, VideoInfo } from "../lib/types.js";

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = 10;
  const offset = (page - 1) * limit;

  const [downloads, queueStatus] = await Promise.all([
    DownloadService.getAllDownloads(limit, offset),
    DownloadService.getQueueStatus(),
  ]);

  return { downloads, queueStatus, currentPage: page };
}

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  const url = formData.get("url") as string;
  const startTimeStr = formData.get("startTime") as string;
  const endTimeStr = formData.get("endTime") as string;

  console.log(`📥 Received download request for URL: ${url}`);
  console.log(`📥 Start time: ${startTimeStr}, End time: ${endTimeStr}`);

  if (!url) {
    console.log(`❌ No URL provided in request`);
    return { success: false, error: "URL is required" };
  }

  const startTime = startTimeStr ? parseInt(startTimeStr, 10) : null;
  const endTime = endTimeStr ? parseInt(endTimeStr, 10) : null;

  if (startTime !== null && (isNaN(startTime) || startTime < 0)) {
    return {
      success: false,
      error: "Start time must be a valid positive number",
    };
  }

  if (endTime !== null && (isNaN(endTime) || endTime < 0)) {
    return {
      success: false,
      error: "End time must be a valid positive number",
    };
  }

  if (startTime !== null && endTime !== null && startTime >= endTime) {
    return {
      success: false,
      error: "End time must be greater than start time",
    };
  }

  try {
    // Check if video already exists
    console.log(`🔍 Checking for existing download...`);
    const existingDownload = await DownloadService.getDownloadByUrl(url);
    if (existingDownload && existingDownload.status === "COMPLETED") {
      console.log(
        `✅ Found existing completed download: ID ${existingDownload.id}`
      );
      return {
        success: true,
        message: "Video already downloaded",
        existing_download: existingDownload,
      };
    }

    // Extract video info first using Python script directly
    console.log(`🔍 Extracting video information...`);
    const videoInfo = await extractVideoInfo(url);

    if (!videoInfo) {
      console.log(`❌ Failed to extract video information`);
      return { success: false, error: "Failed to extract video information" };
    }

    console.log(`✅ Video info extracted: ${videoInfo.title}`);

    // Check if download with this videoId already exists
    if (videoInfo.id) {
      const existingByVideoId = await DownloadService.getDownloadByVideoId(
        videoInfo.id
      );
      if (existingByVideoId) {
        console.log(
          `✅ Found existing download for video ID ${videoInfo.id}: ID ${existingByVideoId.id}`
        );
        // If it's completed, return it
        if (existingByVideoId.status === "COMPLETED") {
          return {
            success: true,
            message: "Video already downloaded",
            existing_download: existingByVideoId,
          };
        }
        // If it's pending or downloading, return it (don't create duplicate)
        return {
          success: true,
          message: "Download already in queue",
          download_id: existingByVideoId.id,
          existing_download: existingByVideoId,
        };
      }
    }

    // Create new download with video info
    console.log(`📝 Creating new download entry...`);
    const download = await DownloadService.createDownload(
      url,
      videoInfo,
      startTime,
      endTime
    );
    console.log(`📋 Adding download to queue...`);
    await DownloadService.addToQueue(download.id);

    console.log(
      `✅ Download request processed successfully: ID ${download.id}`
    );
    return {
      success: true,
      download_id: download.id,
      message: "Download queued successfully",
    };
  } catch (error) {
    console.error(`💥 Error processing download request:`, error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
    };
  }
}

async function extractVideoInfo(url: string): Promise<VideoInfo | null> {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn("python3", [
      "python/downloader.py",
      "--validate",
      url,
    ]);

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
            const videoInfo: VideoInfo = {
              id: result.video_info.id,
              title: result.video_info.title,
              duration: result.video_info.duration,
              is_live: result.video_info.is_live,
              is_scheduled: result.video_info.is_scheduled,
              scheduled_start_time: result.video_info.scheduled_start_time,
              thumbnail: result.video_info.thumbnail,
              uploader: result.video_info.uploader,
            };

            resolve(videoInfo);
          } else {
            resolve(null);
          }
        } catch (parseError) {
          resolve(null);
        }
      } else {
        resolve(null);
      }
    });

    pythonProcess.on("error", (error) => {
      reject(error);
    });
  });
}

export default function HomePage() {
  const { downloads, queueStatus } = useLoaderData<typeof loader>();
  const fetcher = useFetcher();
  const [url, setUrl] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");

  const isSubmitting = fetcher.state === "submitting";
  const actionData = fetcher.data;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    const formData = new FormData();
    formData.append("url", url.trim());
    if (startTime.trim()) formData.append("startTime", startTime.trim());
    if (endTime.trim()) formData.append("endTime", endTime.trim());

    fetcher.submit(formData, { method: "post" });
    setUrl("");
    setStartTime("");
    setEndTime("");
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            YouTube Video Downloader
          </h1>
          <p className="text-gray-600">
            Download and cut YouTube videos with custom start and end times
          </p>
        </div>

        {/* Queue Status */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Queue Status
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {queueStatus.total}
              </div>
              <div className="text-sm text-gray-600">Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">
                {queueStatus.pending}
              </div>
              <div className="text-sm text-gray-600">Pending</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {queueStatus.downloading}
              </div>
              <div className="text-sm text-gray-600">Downloading</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {queueStatus.completed}
              </div>
              <div className="text-sm text-gray-600">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {queueStatus.failed}
              </div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
          </div>
        </div>

        {/* Download Form */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Add New Download
          </h2>

          <fetcher.Form onSubmit={handleSubmit} className="space-y-4">
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
                disabled={isSubmitting}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
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
                  disabled={isSubmitting}
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
                  disabled={isSubmitting}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !url.trim()}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Processing..." : "Download Video"}
            </button>
          </fetcher.Form>

          {/* Action Feedback */}
          {actionData && (
            <div
              className={`mt-4 p-4 rounded-md ${
                actionData.success
                  ? "bg-green-50 border border-green-200 text-green-800"
                  : "bg-red-50 border border-red-200 text-red-800"
              }`}
            >
              {actionData.success ? (
                <div>
                  <p className="font-medium">{actionData.message}</p>
                  {actionData.existing_download &&
                    actionData.existing_download.status === "COMPLETED" && (
                      <p className="text-sm mt-1">
                        <a
                          href={`/api/download/${actionData.existing_download.id}`}
                          className="text-blue-600 hover:underline"
                        >
                          Download Video
                        </a>
                      </p>
                    )}
                </div>
              ) : (
                <p className="font-medium">{actionData.error}</p>
              )}
            </div>
          )}
        </div>

        {/* Recent Downloads */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Downloads
          </h2>

          {downloads.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No downloads yet</p>
          ) : (
            <div className="space-y-4">
              {downloads.map((download) => (
                <DownloadItem key={download.id} download={download} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DownloadItem({ download }: { download: Download }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return "text-green-600 bg-green-100";
      case "DOWNLOADING":
        return "text-blue-600 bg-blue-100";
      case "PENDING":
        return "text-yellow-600 bg-yellow-100";
      case "FAILED":
        return "text-red-600 bg-red-100";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return "Unknown";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-medium text-gray-900 mb-1">
            {download.title || "Untitled Video"}
          </h3>
          <p className="text-sm text-gray-600 mb-2">{download.url}</p>

          <div className="flex items-center space-x-4 text-sm text-gray-500">
            <span>ID: {download.videoId || "Unknown"}</span>
            {download.fileSize && (
              <span>Size: {formatFileSize(download.fileSize)}</span>
            )}
            <span>
              Created: {new Date(download.createdAt).toLocaleDateString()}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end space-y-2">
          <span
            className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(
              download.status
            )}`}
          >
            {download.status}
          </span>

          {download.status === "COMPLETED" && (
            <a
              href={`/api/download/${download.id}`}
              className="text-blue-600 hover:text-blue-800 text-sm"
            >
              Download Video
            </a>
          )}

          {download.errorMessage && (
            <p className="text-red-600 text-xs max-w-xs text-right">
              {download.errorMessage}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
