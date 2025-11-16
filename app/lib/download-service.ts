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
    console.log(`📝 Creating download for URL: ${url}`);

    try {
      const validatedUrl = urlSchema.parse(url);
      console.log(`✅ URL validation passed: ${validatedUrl}`);

      // If videoId exists, check for existing download with matching start/end times
      if (videoInfo?.id) {
        const existing = await this.getDownloadByVideoIdAndTimes(
          videoInfo.id,
          startTime ?? null,
          endTime ?? null
        );
        if (existing) {
          console.log(
            `✅ Found existing download for video ID ${videoInfo.id} with matching times, returning existing download`
          );
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

      console.log(`✅ Download created with ID: ${download.id}`);
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
    console.log(
      `📋 Adding download ID ${downloadId} to queue with priority ${priority}`
    );

    try {
      await prisma.queueItem.create({
        data: {
          downloadId,
          priority,
        },
      });
      console.log(`✅ Download ID ${downloadId} added to queue successfully`);
    } catch (error) {
      console.error(
        `💥 Error adding download ID ${downloadId} to queue:`,
        error
      );
      throw error;
    }
  }

  static async getDownloadById(id: number): Promise<Download | null> {
    console.log(`🔍 Looking up download by ID: ${id}`);

    try {
      const download = await prisma.download.findUnique({
        where: { id },
      });

      if (download) {
        console.log(
          `✅ Found download ID ${id}: ${download.title || "Untitled"}`
        );
      } else {
        console.log(`❌ Download ID ${id} not found`);
      }

      return download;
    } catch (error) {
      console.error(`💥 Error looking up download ID ${id}:`, error);
      throw error;
    }
  }

  static async getDownloadByUrl(url: string): Promise<Download | null> {
    console.log(`🔍 Looking up download by URL: ${url}`);

    try {
      const download = await prisma.download.findFirst({
        where: { url },
        orderBy: { createdAt: "desc" },
      });

      if (download) {
        console.log(
          `✅ Found existing download for URL: ${
            download.title || "Untitled"
          } (ID: ${download.id})`
        );
      } else {
        console.log(`❌ No existing download found for URL`);
      }

      return download;
    } catch (error) {
      console.error(`💥 Error looking up download by URL ${url}:`, error);
      throw error;
    }
  }

  static async getDownloadByVideoId(videoId: string): Promise<Download | null> {
    console.log(`🔍 Looking up download by video ID: ${videoId}`);

    try {
      const download = await prisma.download.findFirst({
        where: { videoId },
        orderBy: { createdAt: "desc" },
      });

      if (download) {
        console.log(
          `✅ Found download for video ID ${videoId}: ${
            download.title || "Untitled"
          }`
        );
      } else {
        console.log(`❌ No download found for video ID ${videoId}`);
      }

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
    console.log(
      `🔍 Looking up download by video ID ${videoId} with startTime=${startTime}, endTime=${endTime}`
    );

    try {
      const download = await prisma.download.findFirst({
        where: {
          videoId,
          startTime: startTime ?? null,
          endTime: endTime ?? null,
        },
        orderBy: { createdAt: "desc" },
      });

      if (download) {
        console.log(
          `✅ Found download for video ID ${videoId} with matching times: ${
            download.title || "Untitled"
          }`
        );
      } else {
        console.log(
          `❌ No download found for video ID ${videoId} with matching times`
        );
      }

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
    console.log(`🔄 Updating download ID ${id} status to: ${status}`);

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

      console.log(`✅ Download ID ${id} status updated to: ${status}`);
      if (additionalData?.errorMessage) {
        console.log(`⚠️ Error message: ${additionalData.errorMessage}`);
      }

      return download;
    } catch (error) {
      console.error(`💥 Error updating download ID ${id} status:`, error);
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
    console.log(`🔍 Looking for next pending download...`);

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
        console.log(`❌ No pending downloads found in queue`);
        return null;
      }

      console.log(
        `✅ Found next pending download: ID ${result.id}, URL: ${result.url}`
      );
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
    console.log(`🗑️ Removing download ID ${downloadId} from queue`);

    try {
      await prisma.queueItem.delete({
        where: { downloadId },
      });
      console.log(`✅ Download ID ${downloadId} removed from queue`);
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
    console.log(`📊 Getting queue status...`);

    try {
      const [total, pending, downloading, completed, failed] =
        await Promise.all([
          prisma.download.count(),
          prisma.download.count({ where: { status: "PENDING" } }),
          prisma.download.count({ where: { status: "DOWNLOADING" } }),
          prisma.download.count({ where: { status: "COMPLETED" } }),
          prisma.download.count({ where: { status: "FAILED" } }),
        ]);

      const status = { total, pending, downloading, completed, failed };
      console.log(`📊 Queue status:`, status);
      return status;
    } catch (error) {
      console.error(`💥 Error getting queue status:`, error);
      throw error;
    }
  }

  static async getQueuePosition(downloadId: number): Promise<number> {
    console.log(`🔍 Getting queue position for download ID ${downloadId}`);

    try {
      const download = await prisma.download.findUnique({
        where: { id: downloadId },
        include: { queueItem: true },
      });

      if (!download || !download.queueItem) {
        console.log(`❌ Download ID ${downloadId} not found in queue`);
        return 0;
      }

      const position = await prisma.queueItem.count({
        where: {
          createdAt: { lt: download.queueItem.createdAt },
          download: { status: "PENDING" },
        },
      });

      const queuePosition = position + 1;
      console.log(
        `✅ Download ID ${downloadId} queue position: ${queuePosition}`
      );
      return queuePosition;
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
    console.log(
      `📋 Getting all downloads (limit: ${limit}, offset: ${offset})`
    );

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
          if (!fileExists) {
            console.log(
              `⚠️ File not found for completed download ID ${download.id}: ${download.filePath}`
            );
          }
        }
        return {
          ...download,
          fileExists,
        };
      });

      console.log(`✅ Retrieved ${downloads.length} downloads`);
      return downloadsWithFileCheck as Download[];
    } catch (error) {
      console.error(`💥 Error getting all downloads:`, error);
      throw error;
    }
  }

  static async getActiveDownloads(): Promise<Download[]> {
    console.log(`📋 Getting active downloads...`);

    try {
      const downloads = await prisma.download.findMany({
        where: {
          status: { in: ["PENDING", "DOWNLOADING"] },
        },
        orderBy: { createdAt: "asc" },
      });

      console.log(`✅ Retrieved ${downloads.length} active downloads`);
      return downloads;
    } catch (error) {
      console.error(`💥 Error getting active downloads:`, error);
      throw error;
    }
  }

  static async getCompletedDownloads(): Promise<Download[]> {
    console.log(`📋 Getting completed downloads...`);

    try {
      const downloads = await prisma.download.findMany({
        where: { status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
      });

      console.log(`✅ Retrieved ${downloads.length} completed downloads`);
      return downloads;
    } catch (error) {
      console.error(`💥 Error getting completed downloads:`, error);
      throw error;
    }
  }

  static async retryDownload(downloadId: number): Promise<Download> {
    console.log(`🔄 Retrying download ID ${downloadId}`);

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

      console.log(`✅ Download ID ${downloadId} queued for retry`);
      return updatedDownload;
    } catch (error) {
      console.error(`💥 Error retrying download ID ${downloadId}:`, error);
      throw error;
    }
  }
}
