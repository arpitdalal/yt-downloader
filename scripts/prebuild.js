import { existsSync } from "node:fs";
import { mkdir, readdir } from "node:fs/promises";
import { platform } from "node:os";
import { join } from "node:path";

const isWindows = platform() === "win32";
const isMac = platform() === "darwin";
const resourcesRoot = "src-tauri/resources";

const resourcesDirs = [
	{
		path: join(resourcesRoot, "python"),
		name: "Python",
		required: isWindows
			? ["python.exe", "downloader.py"]
			: ["bin/python3", "downloader.py"], // macOS/Linux: python3 is in bin/
	},
	{
		path: join(resourcesRoot, "ffmpeg"),
		name: "FFmpeg",
		required: isWindows ? ["ffmpeg.exe", "ffprobe.exe"] : ["ffmpeg", "ffprobe"],
	},
	{
		path: join(resourcesRoot, "jsruntime"),
		name: "JS runtime",
		required: isWindows ? ["node.exe"] : isMac ? ["deno"] : ["node"],
	},
];

async function ensureResourcesDirs() {
	for (const dir of resourcesDirs) {
		if (!existsSync(dir.path)) {
			console.log(`Creating directory: ${dir.path}`);
			await mkdir(dir.path, { recursive: true });
		}

		// Check if directory is empty or missing required files
		// Only warn if directory exists and has some files but is missing required ones
		if (existsSync(dir.path)) {
			try {
				const files = await readdir(dir.path);
				// Only warn if directory has files but is missing required ones
				// Empty directory is expected before bundling
				if (files.length > 0) {
					// readdir() returns names, not nested paths; verify via existsSync
					const missing = dir.required.filter(
						(file) => !existsSync(join(dir.path, file)),
					);
					if (missing.length > 0) {
						console.warn(
							`⚠️  Warning: ${
								dir.name
							} directory exists but is missing required files: ${missing.join(
								", ",
							)}`,
						);
						console.warn(
							`   The build will succeed, but the app may not work without ${dir.name}.`,
						);
						console.warn(
							`   Run the bundling script or ensure ${dir.name} is properly installed.`,
						);
					}
				}
				// If directory is empty, that's expected before bundling - no warning needed
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				console.warn(
					`Warning: Could not read ${dir.name} directory (${dir.path}): ${message}`,
				);
			}
		}
	}
	console.log("Resources directories ready");
}

ensureResourcesDirs().catch((error) => {
	console.error("Failed to create resources directories:", error);
	process.exit(1);
});
