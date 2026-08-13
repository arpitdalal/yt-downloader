import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { assertStableReleaseVersion } from "./release-version-lib.mjs";

const PLATFORM_ARTIFACTS = [
	{
		key: "darwin-aarch64",
		label: "macOS updater archive",
		matches: (file) => file.endsWith(".app.tar.gz"),
	},
	{
		key: "windows-x86_64",
		label: "Windows NSIS installer",
		matches: (file) => file.endsWith(".exe"),
	},
	{
		key: "linux-x86_64",
		label: "Linux AppImage",
		matches: (file) => file.endsWith(".AppImage"),
	},
];

async function walk(directory) {
	const entries = await readdir(directory, { withFileTypes: true });
	const files = await Promise.all(
		entries.map((entry) => {
			const path = join(directory, entry.name);
			return entry.isDirectory() ? walk(path) : [path];
		}),
	);
	return files.flat();
}

function requireOne(files, matches, label) {
	const found = files.filter(matches);
	if (found.length !== 1) {
		throw new Error(`Expected exactly one ${label}; found ${found.length}`);
	}
	return found[0];
}

function validateReleaseInput({ repo, tag, version }) {
	if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)) {
		throw new Error(`Invalid GitHub repository: ${repo}`);
	}
	assertStableReleaseVersion(version);
	if (tag !== `v${version}`) {
		throw new Error(`Invalid release tag: ${tag}`);
	}
}

export async function generateUpdaterManifest({
	artifactsDirectory,
	repo,
	tag,
	version,
}) {
	validateReleaseInput({ repo, tag, version });
	const files = await walk(artifactsDirectory);
	const fileSet = new Set(files);
	const platforms = {};

	for (const platform of PLATFORM_ARTIFACTS) {
		const artifact = requireOne(files, platform.matches, platform.label);
		const artifactStats = await stat(artifact);
		if (!artifactStats.isFile() || artifactStats.size === 0) {
			throw new Error(`Updater artifact is empty: ${basename(artifact)}`);
		}
		const signatureFile = `${artifact}.sig`;
		if (!fileSet.has(signatureFile)) {
			throw new Error(`Missing updater signature: ${basename(signatureFile)}`);
		}

		const signature = (await readFile(signatureFile, "utf8")).trim();
		if (!signature) {
			throw new Error(`Updater signature is empty: ${basename(signatureFile)}`);
		}

		const assetName = basename(artifact);
		platforms[platform.key] = {
			signature,
			url: `https://github.com/${repo}/releases/download/${encodeURIComponent(tag)}/${encodeURIComponent(assetName)}`,
		};
	}

	return {
		version,
		notes: `Release notes: https://github.com/${repo}/releases/tag/${encodeURIComponent(tag)}`,
		platforms,
	};
}

function parseArguments(args) {
	const parsed = {};
	for (let index = 0; index < args.length; index += 2) {
		const name = args[index];
		const value = args[index + 1];
		if (!name?.startsWith("--") || !value) {
			throw new Error(`Invalid argument near: ${name ?? "<end>"}`);
		}
		parsed[name.slice(2)] = value;
	}
	return parsed;
}

async function main() {
	const args = parseArguments(process.argv.slice(2));
	for (const required of ["artifacts", "repo", "tag", "version", "output"]) {
		if (!args[required]) {
			throw new Error(`Missing required argument: --${required}`);
		}
	}

	const manifest = await generateUpdaterManifest({
		artifactsDirectory: resolve(args.artifacts),
		repo: args.repo,
		tag: args.tag,
		version: args.version,
	});
	await writeFile(resolve(args.output), `${JSON.stringify(manifest, null, 2)}\n`);
	console.log(`Updater manifest written to ${args.output}`);
}

if (fileURLToPath(import.meta.url) === resolve(process.argv[1] ?? "")) {
	await main();
}
