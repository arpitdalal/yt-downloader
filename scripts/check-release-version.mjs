import {
	assertReleaseTagMatchesVersion,
	assertReleaseVersionsAligned,
} from "./release-version-lib.mjs";

const version = assertReleaseVersionsAligned();
assertReleaseTagMatchesVersion(process.env.RELEASE_TAG?.trim(), version);

console.log(`Release version OK: ${version}`);
