const REPO = "arpitdalal/yt-downloader";

function getApiUrl(): string {
	const tag =
		typeof process !== "undefined" ? process.env?.RELEASE_TAG?.trim() : "";
	if (tag) {
		return `https://api.github.com/repos/${REPO}/releases/tags/${encodeURIComponent(tag)}`;
	}
	return `https://api.github.com/repos/${REPO}/releases/latest`;
}

export interface Asset {
	name: string;
	url: string;
	size: number;
}

export interface ReleaseData {
	tag: string;
	version: string;
	assets: {
		macos?: Asset;
		macosAppleSilicon?: Asset;
		macosIntel?: Asset;
		windows?: Asset;
		linuxAppImage?: Asset;
		linuxDeb?: Asset;
		linuxRpm?: Asset;
	};
}

interface GhAsset {
	name: string;
	browser_download_url: string;
	size: number;
}

interface GhRelease {
	tag_name: string;
	assets: GhAsset[];
}

function setAsset(
	result: ReleaseData["assets"],
	key: keyof ReleaseData["assets"],
	value: Asset,
): void {
	if (result[key]) {
		console.warn(
			`[github] Duplicate asset for ${key}, keeping first. Second: ${value.name}`,
		);
		return;
	}
	(result as Record<string, Asset>)[key] = value;
}

function mapAssets(assets: GhAsset[]): ReleaseData["assets"] {
	const result: ReleaseData["assets"] = {};
	for (const a of assets) {
		const url = a.browser_download_url;
		const size = a.size;
		const name = a.name;
		const asset: Asset = { name, url, size };
		if (a.name.endsWith(".dmg")) {
			const lower = a.name.toLowerCase();
			if (/aarch64|arm64/.test(lower))
				setAsset(result, "macosAppleSilicon", asset);
			else if (/x64|x86_64/.test(lower)) setAsset(result, "macosIntel", asset);
			else setAsset(result, "macos", asset);
		} else if (a.name.endsWith(".exe")) setAsset(result, "windows", asset);
		else if (a.name.endsWith(".AppImage"))
			setAsset(result, "linuxAppImage", asset);
		else if (a.name.endsWith(".deb")) setAsset(result, "linuxDeb", asset);
		else if (a.name.endsWith(".rpm")) setAsset(result, "linuxRpm", asset);
	}
	result.macos = result.macos ?? result.macosAppleSilicon ?? result.macosIntel;
	return result;
}

function emptyRelease(): ReleaseData {
	return {
		tag: "v0.0.0",
		version: "0.0.0",
		assets: {},
	};
}

function getAuthHeaders(): Record<string, string> {
	const token =
		typeof process !== "undefined" ? process.env?.GITHUB_TOKEN : undefined;
	const headers: Record<string, string> = {
		Accept: "application/vnd.github+json",
		"X-GitHub-Api-Version": "2022-11-28",
	};
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function getReleaseData(): Promise<ReleaseData> {
	try {
		const signal = AbortSignal.timeout(5000);
		const res = await fetch(getApiUrl(), {
			signal,
			headers: getAuthHeaders(),
		});
		if (!res.ok) {
			console.error(
				"[github] getReleaseData non-OK:",
				res.status,
				res.statusText,
			);
			return emptyRelease();
		}
		const data = (await res.json()) as GhRelease;
		const version = data.tag_name.replace(/^v/, "");
		return {
			tag: data.tag_name,
			version,
			assets: mapAssets(data.assets ?? []),
		};
	} catch (err) {
		console.error("[github] getReleaseData failed:", err);
		return emptyRelease();
	}
}
