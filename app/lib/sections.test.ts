import { describe, expect, it } from "vitest";
import { createSection, updateSectionTime } from "./sections.js";

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
