import type {
	DownloadEvent,
	DownloadOptions,
	Update,
} from "@tauri-apps/plugin-updater";
import { describe, expect, it } from "vitest";
import {
	calculateUpdateProgress,
	downloadAndInstallAppUpdate,
	formatUpdateError,
	type UpdateDownloadProgress,
} from "./updater.js";

describe("calculateUpdateProgress", () => {
	it("calculates a bounded percentage", () => {
		expect(calculateUpdateProgress(25, 100)).toEqual({
			downloadedBytes: 25,
			totalBytes: 100,
			percent: 25,
		});
		expect(calculateUpdateProgress(150, 100).percent).toBe(100);
	});

	it("supports downloads without a known content length", () => {
		expect(calculateUpdateProgress(512, null)).toEqual({
			downloadedBytes: 512,
			totalBytes: null,
			percent: null,
		});
		expect(calculateUpdateProgress(-1, 0)).toEqual({
			downloadedBytes: 0,
			totalBytes: null,
			percent: null,
		});
	});
});

describe("downloadAndInstallAppUpdate", () => {
	it("bounds the download duration and reports progress", async () => {
		let receivedOptions: DownloadOptions | undefined;
		const progress: UpdateDownloadProgress[] = [];
		const update = {
			async downloadAndInstall(
				onEvent?: (event: DownloadEvent) => void,
				options?: DownloadOptions,
			): Promise<void> {
				receivedOptions = options;
				onEvent?.({ event: "Started", data: { contentLength: 100 } });
				onEvent?.({ event: "Progress", data: { chunkLength: 25 } });
				onEvent?.({ event: "Finished" });
			},
		} as unknown as Update;

		await downloadAndInstallAppUpdate(update, (nextProgress) => {
			progress.push(nextProgress);
		});

		expect(receivedOptions).toEqual({ timeout: 3_600_000 });
		expect(progress.at(-1)).toEqual({
			downloadedBytes: 100,
			totalBytes: 100,
			percent: 100,
		});
	});
});

describe("formatUpdateError", () => {
	it("keeps actionable updater errors", () => {
		expect(formatUpdateError(new Error("Signature verification failed"))).toBe(
			"Signature verification failed",
		);
		expect(formatUpdateError("Network unavailable")).toBe(
			"Network unavailable",
		);
	});

	it("uses a safe fallback for unknown errors", () => {
		expect(formatUpdateError({ code: 500 })).toBe(
			"The update could not be installed. Please try again.",
		);
	});
});
