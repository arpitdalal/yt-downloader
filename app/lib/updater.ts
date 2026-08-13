import { BundleType, getBundleType } from "@tauri-apps/api/app";
import { isTauri } from "@tauri-apps/api/core";
import { relaunch } from "@tauri-apps/plugin-process";
import {
	check,
	type DownloadEvent,
	type Update,
} from "@tauri-apps/plugin-updater";

export interface UpdateDownloadProgress {
	downloadedBytes: number;
	totalBytes: number | null;
	percent: number | null;
}

let updateCheck: Promise<Update | null> | null = null;
const UPDATE_DOWNLOAD_TIMEOUT_MS = 60 * 60 * 1000;
const UPDATABLE_BUNDLE_TYPES = new Set<BundleType>([
	BundleType.App,
	BundleType.Nsis,
	BundleType.AppImage,
]);

export function supportsInAppUpdates(
	bundleType: BundleType | null | undefined,
): boolean {
	return bundleType !== null && bundleType !== undefined
		? UPDATABLE_BUNDLE_TYPES.has(bundleType)
		: false;
}

export function calculateUpdateProgress(
	downloadedBytes: number,
	totalBytes: number | null,
): UpdateDownloadProgress {
	const safeDownloadedBytes = Math.max(0, downloadedBytes);
	const safeTotalBytes =
		totalBytes !== null && totalBytes > 0 ? totalBytes : null;
	const percent =
		safeTotalBytes === null
			? null
			: Math.min(100, (safeDownloadedBytes / safeTotalBytes) * 100);

	return {
		downloadedBytes: safeDownloadedBytes,
		totalBytes: safeTotalBytes,
		percent,
	};
}

export function checkForAppUpdate(): Promise<Update | null> {
	if (!isTauri()) {
		return Promise.resolve(null);
	}

	updateCheck ??= getBundleType().then((bundleType) =>
		supportsInAppUpdates(bundleType) ? check({ timeout: 10_000 }) : null,
	);
	return updateCheck;
}

export async function downloadAndInstallAppUpdate(
	update: Update,
	onProgress: (progress: UpdateDownloadProgress) => void,
): Promise<void> {
	let downloadedBytes = 0;
	let totalBytes: number | null = null;

	await update.downloadAndInstall(
		(event: DownloadEvent) => {
			switch (event.event) {
				case "Started":
					totalBytes = event.data.contentLength ?? null;
					downloadedBytes = 0;
					onProgress(calculateUpdateProgress(downloadedBytes, totalBytes));
					break;
				case "Progress":
					downloadedBytes += event.data.chunkLength;
					onProgress(calculateUpdateProgress(downloadedBytes, totalBytes));
					break;
				case "Finished":
					onProgress({
						downloadedBytes: totalBytes ?? downloadedBytes,
						totalBytes,
						percent: 100,
					});
					break;
			}
		},
		{ timeout: UPDATE_DOWNLOAD_TIMEOUT_MS },
	);
}

export async function relaunchAfterUpdate(): Promise<void> {
	await relaunch();
}

export function formatUpdateError(error: unknown): string {
	if (error instanceof Error && error.message.trim()) {
		return error.message;
	}
	if (typeof error === "string" && error.trim()) {
		return error;
	}
	return "The update could not be installed. Please try again.";
}
