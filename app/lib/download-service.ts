import { prisma } from "./db.js";
import type { Download, DownloadStatus, VideoInfo } from "./types.js";
import { z } from "zod";
import { existsSync } from "node:fs";

const urlSchema = z
  .string()
  .url()
  .refine((url) => url.includes("youtube.com") || url.includes("youtu.be"), {
    message: "URL must be a valid YouTube URL",
  });

export class DownloadService {
  static async createDownload(
    url: string,
    videoInfo?: VideoInfo,
    startTime?: number | null,
    endTime?: number | null
  ): Promise<Download> {
    try {
      const validatedUrl = urlSchema.parse(url);

      // If videoId exists, check for existing download with matching start/end times
      if (videoInfo?.id) {
        const existing = await this.getDownloadByVideoIdAndTimes(
          videoInfo.id,
          startTime ?? null,
          endTime ?? null
        );
        if (existing) {
          return existing;
        }
      }

      const download = await prisma.download.create({
        data: {
          url: validatedUrl,
          title: videoInfo?.title,
          videoId: videoInfo?.id,
          isLive: videoInfo?.is_live ?? false,
          isScheduled: videoInfo?.is_scheduled ?? false,
          scheduledStartTime: videoInfo?.scheduled_start_time
            ? new Date(videoInfo.scheduled_start_time)
            : null,
          startTime: startTime ?? null,
          endTime: endTime ?? null,
        },
      });

      return download;
    } catch (error: any) {
      console.error(`💥 Error creating download for URL ${url}:`, error);
      throw error;
    }
  }

  static async addToQueue(
    downloadId: number,
    priority: number = 0
  ): Promise<void> {
    try {
      await prisma.queueItem.create({
        data: {
          downloadId,
          priority,
        },
      });
    } catch (error) {
      console.error(
        `💥 Error adding download ID ${downloadId} to queue:`,
        error
      );
      throw error;
    }
  }

  static async getDownloadById(id: number): Promise<Download | null> {
    try {
      const download = await prisma.download.findUnique({
        where: { id },
      });

      return download;
    } catch (error) {
      console.error(`💥 Error looking up download ID ${id}:`, error);
      throw error;
    }
  }

  static async getDownloadByUrl(url: string): Promise<Download | null> {
    try {
      const download = await prisma.download.findFirst({
        where: { url },
        orderBy: { createdAt: "desc" },
      });

      return download;
    } catch (error) {
      console.error(`💥 Error looking up download by URL ${url}:`, error);
      throw error;
    }
  }

  static async getDownloadByVideoId(videoId: string): Promise<Download | null> {
    try {
      const download = await prisma.download.findFirst({
        where: { videoId },
        orderBy: { createdAt: "desc" },
      });

      return download;
    } catch (error) {
      console.error(
        `💥 Error looking up download by video ID ${videoId}:`,
        error
      );
      throw error;
    }
  }

  static async getDownloadByVideoIdAndTimes(
    videoId: string,
    startTime: number | null,
    endTime: number | null
  ): Promise<Download | null> {
    try {
      const download = await prisma.download.findFirst({
        where: {
          videoId,
          startTime: startTime ?? null,
          endTime: endTime ?? null,
        },
        orderBy: { createdAt: "desc" },
      });

      return download;
    } catch (error) {
      console.error(
        `💥 Error looking up download by video ID and times:`,
        error
      );
      throw error;
    }
  }

  static async updateDownloadStatus(
    id: number,
    status: DownloadStatus,
    additionalData?: {
      startedAt?: Date;
      completedAt?: Date;
      filePath?: string;
      fileSize?: number;
      errorMessage?: string;
    }
  ): Promise<Download> {
    try {
      const updateData: any = { status };

      if (additionalData?.startedAt)
        updateData.startedAt = additionalData.startedAt;
      if (additionalData?.completedAt)
        updateData.completedAt = additionalData.completedAt;
      if (additionalData?.filePath !== undefined)
        updateData.filePath = additionalData.filePath;
      if (additionalData?.fileSize !== undefined)
        updateData.fileSize = additionalData.fileSize;
      if (additionalData?.errorMessage !== undefined)
        updateData.errorMessage = additionalData.errorMessage;

      const download = await prisma.download.update({
        where: { id },
        data: updateData,
      });

      return download;
    } catch (error) {
      console.error(`💥 Error updating download ID ${id} status:`, error);
      throw error;
    }
  }

  static async updateDownloadProgress(
    id: number,
    progressPercent: number
  ): Promise<Download> {
    try {
      const download = await prisma.download.update({
        where: { id },
        data: { progressPercent },
      });

      return download;
    } catch (error) {
      console.error(`💥 Error updating download ID ${id} progress:`, error);
      throw error;
    }
  }

  static async getNextPendingDownload(): Promise<{
      download: Download;
      queueItem: {
        id: number;
        downloadId: number;
        priority: number;
        createdAt: Date;
      };
    } | null> {
    try {
      const result = await prisma.download.findFirst({
        where: {
          status: "PENDING",
          queueItem: { isNot: null },
        },
        include: {
          queueItem: true,
        },
        orderBy: {
          queueItem: {
            createdAt: "asc",
          },
        },
      });

      if (!result || !result.queueItem) {
        return null;
      }

      return {
        download: result,
        queueItem: result.queueItem,
      };
    } catch (error) {
      console.error(`💥 Error getting next pending download:`, error);
      throw error;
    }
  }

  static async removeFromQueue(downloadId: number): Promise<void> {
    try {
      await prisma.queueItem.delete({
        where: { downloadId },
      });
    } catch (error) {
      console.error(
        `💥 Error removing download ID ${downloadId} from queue:`,
        error
      );
      throw error;
    }
  }

  static async getQueueStatus(): Promise<{
    total: number;
    pending: number;
    downloading: number;
    completed: number;
    failed: number;
  }> {
    try {
      const [total, pending, downloading, completed, failed] =
        await Promise.all([
          prisma.download.count(),
          prisma.download.count({ where: { status: "PENDING" } }),
          prisma.download.count({ where: { status: "DOWNLOADING" } }),
          prisma.download.count({ where: { status: "COMPLETED" } }),
          prisma.download.count({ where: { status: "FAILED" } }),
        ]);

      return { total, pending, downloading, completed, failed };
    } catch (error) {
      console.error(`💥 Error getting queue status:`, error);
      throw error;
    }
  }

  static async getQueuePosition(downloadId: number): Promise<number> {
    try {
      const download = await prisma.download.findUnique({
        where: { id: downloadId },
        include: { queueItem: true },
      });

      if (!download || !download.queueItem) {
        return 0;
      }

      const position = await prisma.queueItem.count({
        where: {
          createdAt: { lt: download.queueItem.createdAt },
          download: { status: "PENDING" },
        },
      });

      return position + 1;
    } catch (error) {
      console.error(
        `💥 Error getting queue position for download ID ${downloadId}:`,
        error
      );
      throw error;
    }
  }

  static async getAllDownloads(
    limit: number = 50,
    offset: number = 0
  ): Promise<Download[]> {
    try {
      const downloads = await prisma.download.findMany({
        orderBy: { createdAt: "desc" },
        take: limit,
        skip: offset,
      });

      // Check if files exist for completed downloads
      const downloadsWithFileCheck = downloads.map((download) => {
        let fileExists = false;
        if (download.status === "COMPLETED" && download.filePath) {
          fileExists = existsSync(download.filePath);
        }
        return {
          ...download,
          fileExists,
        };
      });

      return downloadsWithFileCheck as Download[];
    } catch (error) {
      console.error(`💥 Error getting all downloads:`, error);
      throw error;
    }
  }

  static async getActiveDownloads(): Promise<Download[]> {
    try {
      const downloads = await prisma.download.findMany({
        where: {
          status: { in: ["PENDING", "DOWNLOADING"] },
        },
        orderBy: { createdAt: "asc" },
      });

      return downloads;
    } catch (error) {
      console.error(`💥 Error getting active downloads:`, error);
      throw error;
    }
  }

  static async getCompletedDownloads(): Promise<Download[]> {
    try {
      const downloads = await prisma.download.findMany({
        where: { status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
      });

      return downloads;
    } catch (error) {
      console.error(`💥 Error getting completed downloads:`, error);
      throw error;
    }
  }

  static async retryDownload(downloadId: number): Promise<Download> {
    try {
      const download = await prisma.download.findUnique({
        where: { id: downloadId },
      });

      if (!download) {
        throw new Error(`Download ID ${downloadId} not found`);
      }

      // Reset download status and clear file info
      const updatedDownload = await prisma.download.update({
        where: { id: downloadId },
        data: {
          status: "PENDING",
          filePath: null,
          fileSize: null,
          errorMessage: null,
          startedAt: null,
          completedAt: null,
        },
      });

      // Add back to queue
      await this.addToQueue(downloadId);

      return updatedDownload;
    } catch (error) {
      console.error(`💥 Error retrying download ID ${downloadId}:`, error);
      throw error;
    }
  }
}
