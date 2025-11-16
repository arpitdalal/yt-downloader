import { spawn, type ChildProcess } from "child_process";
import { DownloadService } from "./download-service.js";

const MAX_CONCURRENT_DOWNLOADS = parseInt(process.env.MAX_CONCURRENT_DOWNLOADS || "1", 10);
const activeDownloads = new Map<number, ChildProcess>();

export class DownloadWorker {
	static async processQueue(): Promise<void> {
		if (activeDownloads.size >= MAX_CONCURRENT_DOWNLOADS) {
			return; // Already at max capacity
		}

		const nextDownload = await DownloadService.getNextPendingDownload();
		if (!nextDownload) {
			return; // No pending downloads
		}

		const { download, queueItem } = nextDownload;

		// Mark as downloading and reset progress
		await DownloadService.updateDownloadStatus(download.id, "DOWNLOADING", {
			startedAt: new Date(),
		});
		await DownloadService.updateDownloadProgress(download.id, 0);

		// Remove from queue
		await DownloadService.removeFromQueue(download.id);

		// Start download process
		DownloadWorker.startDownload(download.id, download.url).catch((error) => {
			console.error(`💥 Error starting download for ID ${download.id}:`, error);
		});
	}

	private static async startDownload(
		downloadId: number,
		url: string,
	): Promise<void> {

		// Get download info to retrieve start/end times
		const download = await DownloadService.getDownloadById(downloadId);
		if (!download) {
			console.error(`❌ Download ID ${downloadId} not found`);
			await DownloadService.updateDownloadStatus(downloadId, "FAILED", {
				errorMessage: "Download record not found",
			});
			return;
		}

		const args = [
			"python/downloader.py",
			url,
			"false", // downloadFromStart
			"bestvideo+bestaudio/best", // quality
		];

		// Add start and end times if provided
		// If either is provided, we need to pass both (use empty string for missing one)
		if (download.startTime !== null || download.endTime !== null) {
			args.push(
				download.startTime !== null ? download.startTime.toString() : "",
			);
			args.push(download.endTime !== null ? download.endTime.toString() : "");
		}

		const pythonProcess = spawn("python3", args);

		activeDownloads.set(downloadId, pythonProcess);

		let stdout = "";
		let stderr = "";

		pythonProcess.stdout.on("data", (data) => {
			const output = data.toString();
			stdout += output;
		});

		pythonProcess.stderr.on("data", async (data) => {
			const error = data.toString();
			stderr += error;
			
			// Parse progress updates from stderr (they're JSON lines)
			const lines = error.split('\n').filter(line => line.trim());
			for (const line of lines) {
				try {
					const parsed = JSON.parse(line.trim());
					if (parsed.type === 'progress' && parsed.percent !== null && parsed.percent !== undefined) {
						// Update progress in database
						await DownloadService.updateDownloadProgress(downloadId, parsed.percent);
					}
				} catch (e) {
					// Not JSON, ignore non-progress stderr output
				}
			}
		});

		pythonProcess.on("close", async (code) => {
			activeDownloads.delete(downloadId);

			try {
				if (code === 0) {

					// Extract JSON from stdout (handle any mixed output)
					let jsonStr = stdout.trim();

					// If there's mixed output, try to find the JSON object
					if (!jsonStr.startsWith("{")) {
						// Find the last occurrence of a JSON object
						const jsonMatch = jsonStr.match(/\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g);
						if (jsonMatch && jsonMatch.length > 0) {
							jsonStr = jsonMatch[jsonMatch.length - 1];
						}
					}

					const result = JSON.parse(jsonStr);

					if (result.success) {
						// Download successful, save file path and set progress to 100%
						await DownloadService.updateDownloadProgress(downloadId, 100);
						await DownloadService.updateDownloadStatus(
							downloadId,
							"COMPLETED",
							{
								completedAt: new Date(),
								filePath: result.file_path,
								fileSize: result.file_size,
							},
						);
					} else {
						console.error(
							`💥 Download failed for ID ${downloadId}:`,
							result.error_message,
						);
						// Download failed
						await DownloadService.updateDownloadStatus(downloadId, "FAILED", {
							errorMessage: result.error_message || "Download failed",
						});
					}
				} else {
					console.error(
						`💥 Python process failed for ID ${downloadId} with code ${code}`,
					);
					console.error(`📄 Full stderr for ID ${downloadId}:`, stderr);
					// Process failed
					await DownloadService.updateDownloadStatus(downloadId, "FAILED", {
						errorMessage: stderr || `Process exited with code ${code}`,
					});
				}
			} catch (error) {
				console.error(
					`💥 Error processing download result for ID ${downloadId}:`,
					error,
				);
				await DownloadService.updateDownloadStatus(downloadId, "FAILED", {
					errorMessage:
						error instanceof Error ? error.message : "Unknown error",
				});
			}

			// Process next item in queue
			DownloadWorker.processQueue();
		});

		pythonProcess.on("error", async (error) => {
			console.error(
				`💥 Failed to start Python process for ID ${downloadId}:`,
				error,
			);
			activeDownloads.delete(downloadId);

			await DownloadService.updateDownloadStatus(downloadId, "FAILED", {
				errorMessage: `Failed to start download process: ${error.message}`,
			});

			// Process next item in queue
			DownloadWorker.processQueue();
		});
	}

	static getActiveDownloadsCount(): number {
		return activeDownloads.size;
	}

	static stopDownload(downloadId: number): boolean {
		const process = activeDownloads.get(downloadId);
		if (process) {
			process.kill();
			activeDownloads.delete(downloadId);
			return true;
		}
		return false;
	}

	static stopAllDownloads(): void {
		for (const [downloadId, process] of activeDownloads) {
			process.kill();
		}
		activeDownloads.clear();
	}
}

// Start processing queue every 5 seconds
let queueInterval: NodeJS.Timeout | null = null;

export function startQueueProcessor(): void {
	if (queueInterval) {
		clearInterval(queueInterval);
	}

	queueInterval = setInterval(async () => {
		try {
			await DownloadWorker.processQueue();
		} catch (error) {
			console.error("Error processing queue:", error);
		}
	}, 5000);
}

export function stopQueueProcessor(): void {
	if (queueInterval) {
		clearInterval(queueInterval);
		queueInterval = null;
	}
	DownloadWorker.stopAllDownloads();
}
