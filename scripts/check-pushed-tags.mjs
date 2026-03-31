import readline from "node:readline";
import {
	assertReleaseTagMatchesVersion,
	assertReleaseVersionsAligned,
} from "./release-version-lib.mjs";

const rl = readline.createInterface({
	input: process.stdin,
	crlfDelay: Infinity,
});

const releaseTags = [];

for await (const line of rl) {
	if (!line.trim()) continue;

	const [localRef] = line.split(/\s+/, 4);
	if (!localRef?.startsWith("refs/tags/v")) continue;

	releaseTags.push(localRef.slice("refs/tags/".length));
}

if (releaseTags.length > 0) {
	const version = assertReleaseVersionsAligned();
	for (const releaseTag of releaseTags) {
		assertReleaseTagMatchesVersion(releaseTag, version);
	}
	console.log(`Tag push version OK: v${version}`);
}
