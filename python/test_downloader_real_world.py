#!/usr/bin/env python3
"""Optional real-world integration tests against live YouTube URLs.

Run explicitly:
  RUN_REAL_WORLD_TESTS=1 python3 -m pytest python/test_downloader_real_world.py -s

Uses same quality string and sections format as the Tauri app (lib.rs).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


RUN_REAL_WORLD_TESTS = os.environ.get("RUN_REAL_WORLD_TESTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

# Quality string must match app: src-tauri/src/lib.rs run_download_video
APP_QUALITY_STRING = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

# Sections for full-download (no cut): matches app default when user doesn't set sections
FULL_DOWNLOAD_SECTIONS_JSON = json.dumps([{"start": None, "end": None}])

# Mix of existing + ultra-stable URLs (Rick Astley, YouTube Rewind 2018)
REAL_WORLD_URLS = [
    "https://youtu.be/wrOjTfsI6kk?si=EPaZbVkudSFd5h0S",
    "https://youtu.be/9quXafs-BmA?si=hDoahsI-YnMYZ6fB",
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=YbJOTdZBX1g",
]

pytestmark = pytest.mark.skipif(
    not RUN_REAL_WORLD_TESTS,
    reason="Set RUN_REAL_WORLD_TESTS=1 to run live network integration tests",
)


def _parse_last_json_object(text: str) -> dict | None:
    """Return the last valid JSON object found in *text*, or None."""
    for index in [i for i, ch in enumerate(text) if ch == "{"][::-1]:
        try:
            return json.loads(text[index:])
        except json.JSONDecodeError:
            continue
    return None


def _run_ffmpeg_integrity_check(file_path: Path, ffmpeg_path: str) -> None:
    """Decode first 5s of file; proves playable and FFmpeg works. Raises on failure."""
    result = subprocess.run(
        [ffmpeg_path, "-v", "error", "-i", str(file_path), "-t", "5", "-f", "null", "-"],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"FFmpeg integrity check failed: {result.stderr.decode('utf-8', errors='replace')}"
    )


@pytest.mark.parametrize("url", REAL_WORLD_URLS)
def test_extract_video_info_cli(url: str) -> None:
    """App always calls --validate before download; catch info-extraction breakage."""
    script_path = Path(__file__).with_name("downloader.py")
    command = [sys.executable, str(script_path), "--validate", url]

    process = subprocess.run(
        command,
        env={**os.environ, "YT_DLP_ENABLE_BROWSER_COOKIES": "false"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )

    assert process.returncode == 0, process.stderr[-4000:]
    payload = _parse_last_json_object(process.stdout)
    assert payload is not None, process.stdout[-4000:]
    assert payload.get("success") is True, payload
    info = payload.get("video_info")
    assert info, payload
    assert info.get("title"), "video_info.title must be non-empty"
    duration = info.get("duration")
    assert duration is None or (isinstance(duration, (int, float)) and duration > 0), (
        "duration should be missing or positive"
    )


@pytest.mark.parametrize("url", REAL_WORLD_URLS)
def test_real_world_download_cli(url: str, tmp_path: Path) -> None:
    """Full download with app-matching quality and sections; no low-quality fallback."""
    script_path = Path(__file__).with_name("downloader.py")
    output_path = tmp_path / "real_world_output.mp4"

    command = [
        sys.executable,
        str(script_path),
        url,
        "false",
        APP_QUALITY_STRING,
        FULL_DOWNLOAD_SECTIONS_JSON,
        str(output_path),
    ]

    env = {**os.environ, "YT_DLP_ENABLE_BROWSER_COOKIES": "false"}
    process = subprocess.run(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
    )

    assert process.returncode == 0, process.stderr[-4000:]
    payload = _parse_last_json_object(process.stdout.strip())
    assert payload is not None, process.stdout[-4000:]
    assert payload.get("success") is True, payload
    file_path = payload.get("file_path")
    assert file_path, f"payload missing 'file_path': {payload}"
    out_file = Path(file_path)
    assert out_file.exists(), f"output file not found: {out_file}"
    assert out_file.stat().st_size > 5_000_000, "expected >5MB for a real download"

    ffmpeg_path = os.environ.get("FFMPEG_PATH")
    if ffmpeg_path and Path(ffmpeg_path).exists():
        _run_ffmpeg_integrity_check(out_file, ffmpeg_path)
