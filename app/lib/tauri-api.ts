import { invoke, isTauri } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open, save } from "@tauri-apps/plugin-dialog";

export interface VideoInfo {
  id: string;
  title: string;
  duration: number | null;
  is_live: boolean;
  is_scheduled: boolean;
  scheduled_start_time: string | null;
  thumbnail: string | null;
  uploader: string | null;
  view_count: number | null;
  upload_date: string | null;
}

export interface DownloadProgressData {
  percent?: number;
  downloadedBytes?: number;
  totalBytes?: number;
  speed?: string;
  eta?: string;
}

export interface LogInfo {
  logPath: string;
  resourcesPath: string;
  appPath: string;
  isPackaged: boolean;
}

export interface YouTubeAuthStatus {
  connected: boolean;
  detectedBrowser: string | null;
}

let unlistenDownloadProgress: UnlistenFn | null = null;
let downloadProgressListenerSeq = 0;

function ensureTauriRuntime() {
  if (!isTauri()) {
    throw new Error(
      "Tauri API is not available. Please run this app inside a Tauri window."
    );
  }
}

export const tauriAPI = {
  async extractVideoInfo(url: string): Promise<VideoInfo> {
    ensureTauriRuntime();
    return invoke<VideoInfo>("extract_video_info", { url });
  },

  async showSaveDialog(options: {
    defaultPath?: string;
    defaultFilename?: string;
  }): Promise<{ canceled: boolean; filePath?: string }> {
    ensureTauriRuntime();
    const defaultPath = options.defaultPath ?? options.defaultFilename;
    const filePath = await save({
      defaultPath,
      filters: [
        { name: "Video Files", extensions: ["mp4", "webm", "mkv", "m4a"] },
        { name: "All Files", extensions: ["*"] },
      ],
    });

    if (!filePath) {
      return { canceled: true };
    }
    return { canceled: false, filePath };
  },

  async showOpenDialog(options: {
    filters?: Array<{ name: string; extensions: string[] }>;
  }): Promise<{ canceled: boolean; filePaths: string[] }> {
    ensureTauriRuntime();
    const result = await open({
      multiple: false,
      directory: false,
      filters: options.filters,
    });

    if (!result) {
      return { canceled: true, filePaths: [] };
    }

    if (Array.isArray(result)) {
      return {
        canceled: false,
        filePaths: result.map((entry) => String(entry)),
      };
    }

    return { canceled: false, filePaths: [String(result)] };
  },

  async downloadVideo(options: {
    url: string;
    savePath: string;
    startTime?: number | null;
    endTime?: number | null;
    sections?: Array<{ start: number | null; end: number | null }> | null;
  }): Promise<{ success: boolean; filePath: string; fileSize: number }> {
    ensureTauriRuntime();
    return invoke("download_video", { options });
  },

  async processLocalVideo(options: {
    inputPath: string;
    savePath: string;
    sections?: Array<{ start: number | null; end: number | null }> | null;
  }): Promise<{ success: boolean; filePath: string; fileSize: number }> {
    ensureTauriRuntime();
    return invoke("process_local_video", { options });
  },

  async cancelDownload(): Promise<{ success: boolean; message?: string }> {
    ensureTauriRuntime();
    return invoke("cancel_download");
  },

  async getLogPath(): Promise<LogInfo> {
    ensureTauriRuntime();
    return invoke("get_log_info");
  },

  async getYouTubeAuthStatus(): Promise<YouTubeAuthStatus> {
    ensureTauriRuntime();
    return invoke("get_youtube_auth_status");
  },

  onDownloadProgress(callback: (data: DownloadProgressData) => void): void {
    ensureTauriRuntime();
    const listenerSeq = ++downloadProgressListenerSeq;
    if (unlistenDownloadProgress) {
      void unlistenDownloadProgress();
      unlistenDownloadProgress = null;
    }
    void listen<DownloadProgressData>("download-progress", (event) => {
      callback(event.payload);
    }).then((unlisten) => {
      if (listenerSeq !== downloadProgressListenerSeq) {
        void unlisten();
        return;
      }
      unlistenDownloadProgress = unlisten;
    });
  },

  removeDownloadProgressListener(): void {
    downloadProgressListenerSeq += 1;
    if (unlistenDownloadProgress) {
      void unlistenDownloadProgress();
      unlistenDownloadProgress = null;
    }
  },
};
