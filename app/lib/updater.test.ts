import { describe, expect, it } from "vitest";
import { calculateUpdateProgress, formatUpdateError } from "./updater.js";

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
