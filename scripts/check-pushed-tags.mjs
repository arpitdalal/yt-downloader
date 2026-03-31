import readline from "node:readline";
import {
	assertReleaseTagMatchesVersion,
	assertReleaseVersionsAligned,
} from "./release-version-lib.mjs";

const version = assertReleaseVersionsAligned();
const rl = readline.createInterface({
	input: process.stdin,
	crlfDelay: Infinity,
});

let checkedAnyReleaseTag = false;

for await (const line of rl) {
	if (!line.trim()) continue;

	const [localRef] = line.split(/\s+/, 4);
	if (!localRef?.startsWith("refs/tags/v")) continue;

	const releaseTag = localRef.slice("refs/tags/".length);
	assertReleaseTagMatchesVersion(releaseTag, version);
	checkedAnyReleaseTag = true;
}

if (checkedAnyReleaseTag) {
	console.log(`Tag push version OK: v${version}`);
}
