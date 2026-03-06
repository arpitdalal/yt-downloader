# yt-dlp Preset Aliases

The downloader mirrors a subset of yt-dlp preset aliases in `python/downloader.py` (`YT_DLP_PRESET_ALIASES`).

## Supported Aliases

- `mp4`
  - `--merge-output-format mp4`
  - `--remux-video mp4`
  - `-S vcodec:h264,lang,quality,res,fps,hdr:12,acodec:aac`
- `mkv`
  - `--merge-output-format mkv`
  - `--remux-video mkv`
- `mp3`
  - `-f ba[acodec^=mp3]/ba/b`
  - `-x --audio-format mp3`
- `aac`
  - `-f ba[acodec^=aac]/ba[acodec^=mp4a.40.]/ba/b`
  - `-x --audio-format aac`
- `sleep`
  - request/subtitle sleep tuning flags for throttled endpoints

## Current App Behavior

- Download attempts always apply the `mp4` preset-equivalent options.
- Format selection is still best-first (`bestvideo*+bestaudio/best`), then MP4/H.264/AAC-compatible fallback selectors.
- Low-quality progressive fallback stays opt-in via `YT_DLP_ALLOW_LOW_QUALITY_FALLBACK=true`.

Result: highest available quality is still targeted, but output is biased toward broadly compatible MP4 playback.
