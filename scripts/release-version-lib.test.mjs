import assert from "node:assert/strict";
import test from "node:test";
import {
	assertReleaseTagMatchesVersion,
	assertStableReleaseVersion,
} from "./release-version-lib.mjs";

test("accepts stable release versions", () => {
	assert.doesNotThrow(() => assertStableReleaseVersion("2.4.0"));
});

test("rejects prerelease versions from the stable release pipeline", () => {
	assert.throws(
		() =>
			assertReleaseTagMatchesVersion("v2.4.0-beta.1", "2.4.0-beta.1"),
		/Stable releases require a major\.minor\.patch version/,
	);
});
