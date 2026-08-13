import { readFileSync } from "node:fs";

function readJson(path) {
	try {
		return JSON.parse(readFileSync(path, "utf8"));
	} catch (error) {
		throw new Error(`failed to read ${path}: ${error.message}`, {
			cause: error,
		});
	}
}

function readText(path) {
	try {
		return readFileSync(path, "utf8");
	} catch (error) {
		throw new Error(`failed to read ${path}: ${error.message}`, {
			cause: error,
		});
	}
}

function requireMatch(text, pattern, label) {
	const match = text.match(pattern);
	if (!match?.[1]) {
		throw new Error(`Could not parse ${label}`);
	}
	return match[1];
}

export function getReleaseVersions() {
	const packageVersion = readJson("package.json").version;
	const tauriVersion = readJson("src-tauri/tauri.conf.json").version;
	const cargoVersion = requireMatch(
		readText("src-tauri/Cargo.toml"),
		/^version = "([^"]+)"$/m,
		"Cargo.toml version",
	);
	const metainfoVersion = requireMatch(
		readText("src-tauri/linux/com.ytdownloader.app.metainfo.xml"),
		/<release version="([^"]+)"/,
		"metainfo release version",
	);

	return {
		"package.json": packageVersion,
		"src-tauri/tauri.conf.json": tauriVersion,
		"src-tauri/Cargo.toml": cargoVersion,
		"src-tauri/linux/com.ytdownloader.app.metainfo.xml": metainfoVersion,
	};
}

export function assertReleaseVersionsAligned() {
	const versions = getReleaseVersions();
	const uniqueVersions = [...new Set(Object.values(versions))];

	if (uniqueVersions.length !== 1) {
		console.error("Release version mismatch:");
		for (const [file, version] of Object.entries(versions)) {
			console.error(`- ${file}: ${version}`);
		}
		process.exit(1);
	}

	return uniqueVersions[0];
}

export function assertStableReleaseVersion(version) {
	if (!/^\d+\.\d+\.\d+$/.test(version)) {
		throw new Error(
			`Stable releases require a major.minor.patch version; received ${version}`,
		);
	}
}

export function assertReleaseTagMatchesVersion(releaseTag, version) {
	if (!releaseTag) return;
	assertStableReleaseVersion(version);
	const expectedTag = `v${version}`;
	if (releaseTag !== expectedTag) {
		console.error(
			`Release tag/version mismatch: RELEASE_TAG=${releaseTag}, expected ${expectedTag}`,
		);
		process.exit(1);
	}
}
