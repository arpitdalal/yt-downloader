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
