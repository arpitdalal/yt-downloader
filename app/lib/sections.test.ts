import { describe, expect, it } from "vitest";
import {
	createSection,
	parseTimestamp,
	updateSectionTime,
} from "./sections.js";

describe("section helpers", () => {
	it("keeps section identity stable when editing times", () => {
		const sections = [createSection("section-0")];

		const afterStart = updateSectionTime(sections, 0, "start", "1");
		const afterEnd = updateSectionTime(afterStart, 0, "end", "12");

		expect(afterStart[0]).toMatchObject({
			id: "section-0",
			start: "1",
			end: "",
		});
		expect(afterEnd[0]).toMatchObject({
			id: "section-0",
			start: "1",
			end: "12",
		});
	});

	it("only updates the requested section", () => {
		const sections = [createSection("section-0"), createSection("section-1")];

		const updated = updateSectionTime(sections, 1, "start", "30");

		expect(updated).toEqual([
			{ id: "section-0", start: "", end: "" },
			{ id: "section-1", start: "30", end: "" },
		]);
	});

	it("returns the original sections for an invalid index", () => {
		const sections = [createSection("section-0")];

		expect(updateSectionTime(sections, 2, "start", "1")).toBe(sections);
	});
});

describe("parseTimestamp", () => {
	it("returns null for empty input", () => {
		expect(parseTimestamp("")).toBeNull();
		expect(parseTimestamp("   ")).toBeNull();
	});

	it("parses plain seconds", () => {
		expect(parseTimestamp("0")).toBe(0);
		expect(parseTimestamp("90")).toBe(90);
		expect(parseTimestamp("5080")).toBe(5080);
	});

	it("parses MM:SS", () => {
		expect(parseTimestamp("1:30")).toBe(90);
		expect(parseTimestamp("0:40")).toBe(40);
		expect(parseTimestamp("24:40")).toBe(1480);
	});

	it("parses H:MM:SS", () => {
		expect(parseTimestamp("1:24:40")).toBe(5080);
		expect(parseTimestamp("0:01:30")).toBe(90);
		expect(parseTimestamp("2:00:00")).toBe(7200);
	});

	it("rejects invalid formats", () => {
		expect(() => parseTimestamp("1:60")).toThrow(
			/Seconds must be between 0 and 59/,
		);
		expect(() => parseTimestamp("1:60:00")).toThrow(
			/Minutes and seconds must be between 0 and 59/,
		);
		expect(() => parseTimestamp("1:2:3:4")).toThrow(/Invalid time format/);
		expect(() => parseTimestamp("abc")).toThrow(/Invalid time format/);
		expect(() => parseTimestamp("1:aa")).toThrow(/Invalid time format/);
	});
});
