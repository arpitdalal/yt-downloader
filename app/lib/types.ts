import type { Download as PrismaDownload } from "@prisma/client";

export type Download = PrismaDownload & {
  fileExists?: boolean;
};

export type DownloadStatus = "PENDING" | "DOWNLOADING" | "COMPLETED" | "FAILED";

export interface VideoInfo {
  id: string;
  title: string;
  duration: number | null;
  is_live: boolean;
  is_scheduled: boolean;
  scheduled_start_time: string | null;
  thumbnail: string | null;
  uploader: string | null;
}

export interface DownloadRequest {
  url: string;
  downloadFromStart?: boolean;
}

export interface DownloadResponse {
  success: boolean;
  download_id: number;
  message: string;
  video_info?: VideoInfo;
  existing_download?: Download;
}

export interface QueueStatus {
  total: number;
  pending: number;
  downloading: number;
  completed: number;
  failed: number;
  queue_position?: number;
  estimated_wait_minutes?: number;
}

export interface OneDriveUploadResponse {
  success: boolean;
  file_id: string;
  web_url: string;
  download_url: string;
  error?: string;
}

export interface ValidationResult {
  isValid: boolean;
  error?: string;
  videoInfo?: VideoInfo;
}

export interface DownloadProgress {
  download_id: number;
  status: DownloadStatus;
  progress_percent?: number;
  downloaded_bytes?: number;
  total_bytes?: number;
  speed?: string;
  eta?: string;
}
