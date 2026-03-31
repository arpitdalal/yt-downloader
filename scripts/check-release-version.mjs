import { readFileSync } from "node:fs";

function readJson(path) {
	return JSON.parse(readFileSync(path, "utf8"));
}

function readText(path) {
	return readFileSync(path, "utf8");
}

function requireMatch(text, pattern, label) {
	const match = text.match(pattern);
	if (!match?.[1]) {
		throw new Error(`Could not parse ${label}`);
	}
	return match[1];
}

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

const versions = {
	"package.json": packageVersion,
	"src-tauri/tauri.conf.json": tauriVersion,
	"src-tauri/Cargo.toml": cargoVersion,
	"src-tauri/linux/com.ytdownloader.app.metainfo.xml": metainfoVersion,
};

const uniqueVersions = [...new Set(Object.values(versions))];
if (uniqueVersions.length !== 1) {
	console.error("Release version mismatch:");
	for (const [file, version] of Object.entries(versions)) {
		console.error(`- ${file}: ${version}`);
	}
	process.exit(1);
}

const releaseTag = process.env.RELEASE_TAG?.trim();
if (releaseTag) {
	const expectedTag = `v${packageVersion}`;
	if (releaseTag !== expectedTag) {
		console.error(
			`Release tag/version mismatch: RELEASE_TAG=${releaseTag}, expected ${expectedTag}`,
		);
		process.exit(1);
	}
}

console.log(`Release version OK: ${packageVersion}`);
