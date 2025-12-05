// TypeScript wrapper for Electron IPC API

declare global {
	interface Window {
		electronAPI: {
			extractVideoInfo: (url: string) => Promise<VideoInfo>;
			showSaveDialog: (options: {
				defaultPath?: string;
				defaultFilename?: string;
			}) => Promise<{ canceled: boolean; filePath?: string }>;
			downloadVideo: (options: {
				url: string;
				savePath: string;
				startTime?: number | null;
				endTime?: number | null;
				sections?: Array<{ start: number | null; end: number | null }> | null;
			}) => Promise<{ success: boolean; filePath: string; fileSize: number }>;
			cancelDownload: () => Promise<{ success: boolean; message?: string }>;
			getLogPath: () => Promise<{
				logPath: string;
				resourcesPath: string;
				appPath: string;
				isPackaged: boolean;
			}>;
			onDownloadProgress: (
				callback: (data: DownloadProgressData) => void,
			) => void;
			removeDownloadProgressListener: () => void;
		};
	}
}

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

export interface DownloadProgressData {
	percent: number;
	downloadedBytes?: number;
	totalBytes?: number;
	speed?: string;
	eta?: string;
}

export const electronAPI = window.electronAPI;
