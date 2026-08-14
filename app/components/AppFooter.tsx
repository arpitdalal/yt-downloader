import { getVersion } from "@tauri-apps/api/app";
import { isTauri } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useEffect, useState } from "react";
import packageJson from "../../package.json";

const WEBSITE_URL = "https://arpit.im?utm_source=yt-downloader&utm_medium=app";

export function AppFooter() {
	const [version, setVersion] = useState(packageJson.version);

	useEffect(() => {
		if (!isTauri()) {
			return;
		}

		void getVersion().then(setVersion).catch(console.warn);
	}, []);

	return (
		<footer className="mt-6 border-t border-gray-200 py-4 text-center text-xs text-gray-500">
			<p className="flex items-center justify-center gap-2">
				<span>
					Made with AI by{" "}
					<a
						href={WEBSITE_URL}
						target="_blank"
						rel="noreferrer"
						onClick={(event) => {
							if (!isTauri()) {
								return;
							}

							event.preventDefault();
							void openUrl(WEBSITE_URL).catch((error: unknown) => {
								console.warn("Failed to open Arpit Dalal's website:", error);
							});
						}}
						className="font-medium text-gray-600 underline decoration-gray-300 underline-offset-4 transition-colors hover:text-blue-700 hover:decoration-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
					>
						Arpit Dalal
					</a>
				</span>
				<span aria-hidden="true" className="text-gray-300">
					|
				</span>
				<span>Version {version}</span>
			</p>
		</footer>
	);
}
