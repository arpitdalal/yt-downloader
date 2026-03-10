import type { CookieSelection, CookieSource } from "./tauri-api.js";

export const COOKIE_SELECTION_STORAGE_KEY = "ytd.cookieSelection.v1";
export const COOKIE_OVERRIDE_USE_DEFAULT = "useDefault";

export function normalizeCookieSelection(value: unknown): CookieSelection {
	if (!value || typeof value !== "object") {
		return { mode: "auto" };
	}
	const parsed = value as Record<string, unknown>;
	if (parsed.mode === "manual") {
		const { sourceId } = parsed;
		if (typeof sourceId === "string" && sourceId.trim().length > 0) {
			return { mode: "manual", sourceId };
		}
	}
	return { mode: "auto" };
}

export function cookieSelectionToOptionValue(
	selection: CookieSelection,
): string {
	if (selection.mode === "manual" && selection.sourceId) {
		return `manual:${selection.sourceId}`;
	}
	return "auto";
}

export function resolveOverrideToSelection(
	overrideValue: string,
	globalSelection: CookieSelection,
): CookieSelection {
	if (overrideValue === COOKIE_OVERRIDE_USE_DEFAULT) {
		return globalSelection;
	}
	if (overrideValue === "auto") {
		return { mode: "auto" };
	}
	if (overrideValue.startsWith("manual:")) {
		const sourceId = overrideValue.slice("manual:".length);
		if (sourceId) {
			return { mode: "manual", sourceId };
		}
	}
	return globalSelection;
}

export function reconcileGlobalCookieSelection(
	selection: CookieSelection,
	sources: CookieSource[],
): CookieSelection {
	if (selection.mode !== "manual" || !selection.sourceId) {
		return selection.mode === "manual" ? { mode: "auto" } : selection;
	}
	return sources.some(
		(source) => source.id === selection.sourceId && source.available,
	)
		? selection
		: { mode: "auto" };
}

/**
 * Returns the override value to use after sources change. Resets to default when
 * the current override is a manual source that is no longer in the list.
 */
export function reconcileCookieSelectionOverride(
	overrideValue: string,
	sources: CookieSource[],
): string {
	if (!overrideValue.startsWith("manual:")) {
		return overrideValue;
	}
	const sourceId = overrideValue.slice("manual:".length);
	if (!sourceId) {
		return COOKIE_OVERRIDE_USE_DEFAULT;
	}
	return sources.some((source) => source.id === sourceId && source.available)
		? overrideValue
		: COOKIE_OVERRIDE_USE_DEFAULT;
}
