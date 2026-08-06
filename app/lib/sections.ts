export type Section = {
	id: string;
	start: string;
	end: string;
};

export type SectionTimeField = "start" | "end";

export function createSection(id: string): Section {
	return { id, start: "", end: "" };
}

export function updateSectionTime(
	sections: Section[],
	index: number,
	field: SectionTimeField,
	value: string,
): Section[] {
	if (index < 0 || index >= sections.length) {
		return sections;
	}

	return sections.map((section, sectionIndex) =>
		sectionIndex === index ? { ...section, [field]: value } : section,
	);
}

/**
 * Parse a timestamp to whole seconds.
 * Accepts plain seconds (`90`), `MM:SS` (`1:30`), or `H:MM:SS` (`1:24:40`).
 * Returns null for empty input; throws for invalid format.
 */
export function parseTimestamp(value: string): number | null {
	const trimmed = value.trim();
	if (!trimmed) {
		return null;
	}

	if (/^\d+$/.test(trimmed)) {
		return Number.parseInt(trimmed, 10);
	}

	const parts = trimmed.split(":");
	if (parts.length !== 2 && parts.length !== 3) {
		throw new Error(
			"Invalid time format. Use seconds, MM:SS, or H:MM:SS (e.g. 90, 1:30, 1:24:40)",
		);
	}

	if (parts.some((part) => !/^\d+$/.test(part))) {
		throw new Error(
			"Invalid time format. Use seconds, MM:SS, or H:MM:SS (e.g. 90, 1:30, 1:24:40)",
		);
	}

	const nums = parts.map((part) => Number.parseInt(part, 10));

	if (nums.length === 2) {
		const [minutes, seconds] = nums;
		if (seconds >= 60) {
			throw new Error("Seconds must be between 0 and 59");
		}
		return minutes * 60 + seconds;
	}

	const [hours, minutes, seconds] = nums;
	if (minutes >= 60 || seconds >= 60) {
		throw new Error("Minutes and seconds must be between 0 and 59");
	}
	return hours * 3600 + minutes * 60 + seconds;
}
