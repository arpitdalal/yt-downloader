#!/usr/bin/env python3
"""Optional real-world integration tests against live YouTube URLs.

Run explicitly:
  RUN_REAL_WORLD_TESTS=1 python3 -m pytest python/test_downloader_real_world.py -s
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

pytestmark = pytest.mark.skipif(
    not RUN_REAL_WORLD_TESTS,
    reason="Set RUN_REAL_WORLD_TESTS=1 to run live network integration tests",
)


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/wrOjTfsI6kk?si=EPaZbVkudSFd5h0S",
        "https://youtu.be/9quXafs-BmA?si=hDoahsI-YnMYZ6fB",
    ],
)
def test_real_world_download_cli(url: str, tmp_path: Path) -> None:
    script_path = Path(__file__).with_name("downloader.py")
    output_path = tmp_path / "real_world_output.mp4"
    sections_json = json.dumps([{"start": 0, "end": None}])

    command = [
        sys.executable,
        str(script_path),
        url,
        "false",
        "bestvideo*+bestaudio",
        sections_json,
        str(output_path),
    ]

    process = subprocess.run(
        command,
        env={
            **os.environ,
            # Real-world test should prove CLI path still works end-to-end.
            # Strict mode is validated in unit tests; integration run allows fallback.
            "YT_DLP_ALLOW_LOW_QUALITY_FALLBACK": "true",
            "YT_DLP_ENABLE_BROWSER_COOKIES": "false",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900,
    )

    assert process.returncode == 0, process.stderr[-4000:]
    payload = None
    stdout = process.stdout.strip()
    for index in [i for i, ch in enumerate(stdout) if ch == "{"][::-1]:
        try:
            payload = json.loads(stdout[index:])
            break
        except json.JSONDecodeError:
            continue
    assert payload is not None, process.stdout[-4000:]
    assert payload.get("success") is True, payload
    assert Path(payload["file_path"]).exists()
    assert Path(payload["file_path"]).stat().st_size > 1_000_000
