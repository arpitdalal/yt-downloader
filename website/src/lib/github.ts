const REPO = "arpitdalal/yt-downloader";
const API_URL = `https://api.github.com/repos/${REPO}/releases/latest`;

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

function mapAssets(assets: GhAsset[]): ReleaseData["assets"] {
  const result: ReleaseData["assets"] = {};
  for (const a of assets) {
    const url = a.browser_download_url;
    const size = a.size;
    const name = a.name;
    if (a.name.endsWith(".dmg")) result.macos = { name, url, size };
    else if (a.name.endsWith(".exe")) result.windows = { name, url, size };
    else if (a.name.endsWith(".AppImage")) result.linuxAppImage = { name, url, size };
    else if (a.name.endsWith(".deb")) result.linuxDeb = { name, url, size };
    else if (a.name.endsWith(".rpm")) result.linuxRpm = { name, url, size };
  }
  return result;
}

function emptyRelease(): ReleaseData {
  return {
    tag: "v0.0.0",
    version: "0.0.0",
    assets: {},
  };
}

export async function getReleaseData(): Promise<ReleaseData> {
  try {
    const signal = AbortSignal.timeout(5000);
    const res = await fetch(API_URL, {
      signal,
      headers: { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
    });
    if (!res.ok) {
      return emptyRelease();
    }
    const data = (await res.json()) as GhRelease;
    const version = data.tag_name.replace(/^v/, "");
    return {
      tag: data.tag_name,
      version,
      assets: mapAssets(data.assets ?? []),
    };
  } catch {
    return emptyRelease();
  }
}
