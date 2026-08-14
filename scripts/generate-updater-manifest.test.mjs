import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { generateUpdaterManifest } from "./generate-updater-manifest.mjs";

async function createArtifacts({
	emptyArtifact = false,
	missingSignature = false,
} = {}) {
	const directory = await mkdtemp(join(tmpdir(), "yt-downloader-updater-"));
	const artifacts = [
		["mac", "YouTube Downloader.app.tar.gz", "mac-signature"],
		[
			"windows",
			"YouTube Downloader_2.4.0_x64-setup.exe",
			"win-signature",
		],
		[
			"linux",
			"YouTube Downloader_2.4.0_amd64.AppImage",
			"linux-signature",
		],
	];

	for (const [folder, name, signature] of artifacts) {
		const target = join(directory, folder);
		await mkdir(target);
		await writeFile(
			join(target, name),
			emptyArtifact && folder === "linux" ? "" : "artifact",
		);
		if (!(missingSignature && folder === "linux")) {
			await writeFile(join(target, `${name}.sig`), signature);
		}
	}

	return directory;
}

test("generates a signed entry for every supported desktop target", async () => {
	const directory = await createArtifacts();
	try {
		const manifest = await generateUpdaterManifest({
			artifactsDirectory: directory,
			repo: "arpitdalal/yt-downloader",
			tag: "v2.4.0",
			version: "2.4.0",
		});

		assert.equal(manifest.version, "2.4.0");
		assert.deepEqual(Object.keys(manifest.platforms), [
			"darwin-aarch64",
			"windows-x86_64",
			"linux-x86_64",
		]);
		assert.equal(
			manifest.platforms["darwin-aarch64"].signature,
			"mac-signature",
		);
		assert.match(
			manifest.platforms["windows-x86_64"].url,
			/^https:\/\/github\.com\/arpitdalal\/yt-downloader\/releases\/download\/v2\.4\.0\/YouTube\.Downloader_2\.4\.0_x64-setup\.exe$/,
		);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

test("refuses to publish a manifest with a missing signature", async () => {
	const directory = await createArtifacts({ missingSignature: true });
	try {
		await assert.rejects(
			generateUpdaterManifest({
				artifactsDirectory: directory,
				repo: "arpitdalal/yt-downloader",
				tag: "v2.4.0",
				version: "2.4.0",
			}),
			/Missing updater signature/,
		);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

test("refuses to publish a manifest with an empty artifact", async () => {
	const directory = await createArtifacts({ emptyArtifact: true });
	try {
		await assert.rejects(
			generateUpdaterManifest({
				artifactsDirectory: directory,
				repo: "arpitdalal/yt-downloader",
				tag: "v2.4.0",
				version: "2.4.0",
			}),
			/Updater artifact is empty/,
		);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});

test("refuses to publish a prerelease through the stable feed", async () => {
	const directory = await createArtifacts();
	try {
		await assert.rejects(
			generateUpdaterManifest({
				artifactsDirectory: directory,
				repo: "arpitdalal/yt-downloader",
				tag: "v2.4.0-beta.1",
				version: "2.4.0-beta.1",
			}),
			/Stable releases require a major\.minor\.patch version/,
		);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});
