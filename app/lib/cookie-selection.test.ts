import { describe, expect, it } from "vitest";
import {
	COOKIE_OVERRIDE_USE_DEFAULT,
	cookieSelectionToOptionValue,
	normalizeCookieSelection,
	reconcileCookieSelectionOverride,
	reconcileGlobalCookieSelection,
	resolveOverrideToSelection,
} from "./cookie-selection.js";
import type { CookieSource } from "./tauri-api.js";

function source(id: string, browser: string): CookieSource {
	return {
		id,
		browser,
		browserLabel: browser,
		profile: null,
		profileLabel: null,
		container: null,
		keyring: null,
		available: true,
		hasYoutubeCookies: true,
		hasYoutubeAuthCookies: true,
		lastError: null,
		priority: 0,
	};
}

describe("cookie selection helpers", () => {
	it("reconciles stale manual global selection to auto", () => {
		const reconciled = reconcileGlobalCookieSelection(
			{ mode: "manual", sourceId: "chrome|Profile 1|" },
			[source("edge|Default|", "edge")],
		);
		expect(reconciled).toEqual({ mode: "auto" });
	});

	it("keeps manual global selection when source still exists", () => {
		const current = { mode: "manual", sourceId: "chrome|Profile 1|" } as const;
		const reconciled = reconcileGlobalCookieSelection(current, [
			source("chrome|Profile 1|", "chrome"),
		]);
		expect(reconciled).toEqual(current);
	});

	it("reconciles manual selection to auto when sources list is empty", () => {
		const reconciled = reconcileGlobalCookieSelection(
			{ mode: "manual", sourceId: "chrome|Profile 1|" },
			[],
		);
		expect(reconciled).toEqual({ mode: "auto" });
	});

	it("leaves auto selection unchanged when reconciling", () => {
		const selection = { mode: "auto" } as const;
		const reconciled = reconcileGlobalCookieSelection(selection, [
			source("chrome|Default|", "chrome"),
		]);
		expect(reconciled).toEqual(selection);
	});

	it("normalizes tampered persisted values to auto", () => {
		expect(normalizeCookieSelection("bad")).toEqual({ mode: "auto" });
		expect(normalizeCookieSelection({ mode: "manual" })).toEqual({
			mode: "auto",
		});
		expect(normalizeCookieSelection({ mode: "manual", sourceId: "" })).toEqual({
			mode: "auto",
		});
		expect(normalizeCookieSelection({ mode: "bad", sourceId: "x" })).toEqual({
			mode: "auto",
		});
	});

	it("reconciles override to default when manual source not in list", () => {
		expect(
			reconcileCookieSelectionOverride("manual:chrome|Profile 1|", [
				source("edge|Default|", "edge"),
			]),
		).toBe(COOKIE_OVERRIDE_USE_DEFAULT);
		expect(
			reconcileCookieSelectionOverride("manual:chrome|Profile 1|", []),
		).toBe(COOKIE_OVERRIDE_USE_DEFAULT);
	});

	it("keeps override when manual source still in list", () => {
		const override = "manual:chrome|Profile 1|";
		expect(
			reconcileCookieSelectionOverride(override, [
				source("chrome|Profile 1|", "chrome"),
			]),
		).toBe(override);
	});

	it("reconciles override to default when manual id is empty", () => {
		expect(
			reconcileCookieSelectionOverride("manual:", [source("chrome", "chrome")]),
		).toBe(COOKIE_OVERRIDE_USE_DEFAULT);
	});

	it("leaves non-manual override unchanged", () => {
		expect(
			reconcileCookieSelectionOverride(COOKIE_OVERRIDE_USE_DEFAULT, []),
		).toBe(COOKIE_OVERRIDE_USE_DEFAULT);
		expect(reconcileCookieSelectionOverride("auto", [])).toBe("auto");
	});

	it("resolves override values correctly", () => {
		const globalSelection = {
			mode: "manual",
			sourceId: "chrome|Default|",
		} as const;
		expect(
			resolveOverrideToSelection(COOKIE_OVERRIDE_USE_DEFAULT, globalSelection),
		).toEqual(globalSelection);
		expect(resolveOverrideToSelection("auto", globalSelection)).toEqual({
			mode: "auto",
		});
		expect(
			resolveOverrideToSelection("manual:edge|Profile 1|", globalSelection),
		).toEqual({
			mode: "manual",
			sourceId: "edge|Profile 1|",
		});
		expect(resolveOverrideToSelection("manual:", globalSelection)).toEqual(
			globalSelection,
		);
		expect(cookieSelectionToOptionValue({ mode: "auto" })).toBe("auto");
		expect(
			cookieSelectionToOptionValue({
				mode: "manual",
				sourceId: "chrome|Default|",
			}),
		).toBe("manual:chrome|Default|");
	});
});
