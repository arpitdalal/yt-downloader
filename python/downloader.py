#!/usr/bin/env python3
"""
YouTube Video Downloader using yt-dlp
Handles live streams, scheduled videos, and regular videos
"""

import json
import sys
import os
import subprocess
import time
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
import yt_dlp
from dataclasses import dataclass, asdict


@dataclass
class VideoInfo:
    """Video information extracted from YouTube"""
    id: str
    title: str
    duration: Optional[int]
    is_live: bool
    is_scheduled: bool
    scheduled_start_time: Optional[str]
    thumbnail: Optional[str]
    uploader: Optional[str]
    view_count: Optional[int]
    upload_date: Optional[str]


@dataclass
class DownloadResult:
    """Result of a download operation"""
    success: bool
    file_path: Optional[str]
    file_size: Optional[int]
    error_message: Optional[str]
    video_info: Optional[VideoInfo]


class YouTubeDownloader:
    """Main downloader class using yt-dlp"""
    
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use OS-aware temp directory
            self.output_dir = Path(tempfile.gettempdir())
            self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_temp_dir(self) -> Path:
        """Get OS-aware temporary directory"""
        return Path(tempfile.gettempdir())
        
    def extract_video_info(self, url: str) -> Optional[VideoInfo]:
        """Extract video information without downloading"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Handle different video types
                is_live = info.get('live_status') == 'is_live'
                is_scheduled = info.get('live_status') == 'is_upcoming'
                
                scheduled_start_time = None
                if is_scheduled and info.get('release_timestamp'):
                    scheduled_start_time = datetime.fromtimestamp(
                        info['release_timestamp']
                    ).isoformat()
                
                return VideoInfo(
                    id=info.get('id', ''),
                    title=info.get('title', ''),
                    duration=info.get('duration'),
                    is_live=is_live,
                    is_scheduled=is_scheduled,
                    scheduled_start_time=scheduled_start_time,
                    thumbnail=info.get('thumbnail'),
                    uploader=info.get('uploader'),
                    view_count=info.get('view_count'),
                    upload_date=info.get('upload_date')
                )
                
        except Exception as e:
            print(f"Error extracting video info: {e}", file=sys.stderr)
            return None
    
    def _get_cached_video_path(self, video_id: str) -> Optional[str]:
        """Check if a cached video exists in temp directory for the given video ID"""
        temp_dir = self._get_temp_dir()
        if not temp_dir.exists():
            return None
        
        # Common video extensions to check
        extensions = ['mp4', 'webm', 'mkv', 'm4a', 'flv', 'avi', 'mov']
        
        for ext in extensions:
            cached_path = temp_dir / f'{video_id}.{ext}'
            if cached_path.exists() and cached_path.is_file():
                # Verify it's not a .part file and has content
                if not cached_path.name.endswith('.part') and cached_path.stat().st_size > 0:
                    # Verify file is complete (size is stable)
                    size1 = cached_path.stat().st_size
                    time.sleep(0.1)
                    size2 = cached_path.stat().st_size
                    if size1 == size2:
                        return str(cached_path)
        
        # Also check for any file with video_id prefix (in case extension is different)
        matching_files = [
            f for f in temp_dir.glob(f'{video_id}.*')
            if f.is_file() and not f.name.endswith('.part') and not f.name.endswith('.ytdl')
            and not '_' in f.name  # Exclude cut files
        ]
        
        if matching_files:
            # Get the most recent file
            candidate = max(matching_files, key=lambda f: f.stat().st_size)  # Prefer larger files (more likely complete)
            if candidate.stat().st_size > 0:
                return str(candidate)
        
        return None
    
    def cut_video(
        self,
        input_path: str,
        output_path: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> bool:
        """Cut video using ffmpeg"""
        # Get ffmpeg path from environment variable (set by Electron) or use 'ffmpeg' as fallback
        ffmpeg_path = os.environ.get('FFMPEG_PATH', 'ffmpeg')
        cmd = None
        try:
            cmd = [ffmpeg_path]
            
            # When using -c copy, -ss must be before -i for accurate seeking
            if start_time is not None:
                cmd.extend(['-ss', str(start_time)])
            
            cmd.extend(['-i', input_path, '-c', 'copy'])
            
            if end_time is not None:
                duration = end_time - (start_time or 0)
                cmd.extend(['-t', str(duration)])
            
            cmd.extend(['-avoid_negative_ts', 'make_zero', output_path, '-y'])
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode() if e.stderr else str(e)
            print(f"FFmpeg error: {error_output}", file=sys.stderr)
            if cmd:
                print(f"FFmpeg command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Input path: {input_path}", file=sys.stderr)
            print(f"Output path: {output_path}", file=sys.stderr)
            return False
        except FileNotFoundError as e:
            print(f"FFmpeg not found at: {ffmpeg_path}", file=sys.stderr)
            print(f"Please ensure FFmpeg is installed or FFMPEG_PATH environment variable is set correctly", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error cutting video: {e}", file=sys.stderr)
            print(f"FFmpeg path used: {ffmpeg_path}", file=sys.stderr)
            if cmd:
                print(f"FFmpeg command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Input path: {input_path}", file=sys.stderr)
            print(f"Output path: {output_path}", file=sys.stderr)
            return False
    
    def download_video(
        self, 
        url: str, 
        output_path: str,
        download_from_start: bool = False,
        quality: str = 'bestvideo+bestaudio/best',
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> DownloadResult:
        """Download a video from YouTube"""
        
        # First extract video info
        video_info = self.extract_video_info(url)
        if not video_info:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message="Failed to extract video information",
                video_info=None
            )
        
        # Check if we need to cut the video
        needs_cut = start_time is not None or end_time is not None
        
        # Track the final downloaded file path (initialize early so it's always available)
        downloaded_file_path = [None]
        
        # Always check for cached video first (regardless of whether cutting is needed)
        cached_video_path = self._get_cached_video_path(video_info.id)
        if cached_video_path:
            # Use cached video, skip download
            original_file_path = cached_video_path
        else:
            # No cache found, will download below
            original_file_path = None
        
        # If we have a cached video, skip the download loop
        if cached_video_path:
            # Skip to file verification and cutting/moving
            pass
        else:
            # Always download full video to temp directory with video ID for caching
            temp_dir = self._get_temp_dir()
            download_output_path = str(temp_dir / f'{video_info.id}.%(ext)s')
            
            # Format selectors to try in order (most preferred first)
            format_selectors = [
                quality,  # Try user-specified format first
                'bestvideo+bestaudio/best',  # Try best video+audio combo
                'best[ext=mp4]/best[ext=webm]/best',  # Try mp4, then webm, then any
                'best',  # Fallback to any best format
            ]
            
            last_error = None
            
            for format_selector in format_selectors:
                # Progress hook to report download progress and capture final file path
                def progress_hook(d):
                    status = d.get('status')
                    
                    # Capture final file path when download finishes
                    if status == 'finished':
                        filename = d.get('filename') or d.get('info_dict', {}).get('_filename')
                        if filename:
                            downloaded_file_path[0] = filename
                    
                    if status == 'downloading':
                        percent_float = None
                        # Try to get percent from _percent_str first
                        percent_str = d.get('_percent_str', '')
                        if percent_str:
                            try:
                                percent_float = float(percent_str.strip('%'))
                            except (ValueError, TypeError):
                                pass
                        
                        # If percent_str not available, calculate from bytes
                        if percent_float is None:
                            downloaded = d.get('downloaded_bytes')
                            total = d.get('total_bytes')
                            if downloaded is not None and total is not None and total > 0:
                                percent_float = (downloaded / total) * 100
                        
                        progress_data = {
                            'type': 'progress',
                            'percent': percent_float,
                            'downloaded_bytes': d.get('downloaded_bytes'),
                            'total_bytes': d.get('total_bytes'),
                            'speed': d.get('_speed_str', 'N/A'),
                            'eta': d.get('_eta_str', 'N/A')
                        }
                        # Output progress as JSON to stderr (so it doesn't interfere with final JSON output)
                        print(json.dumps(progress_data), file=sys.stderr, flush=True)
                
                # Common options to help with 403 errors and ensure complete downloads
                base_opts = {
                    'outtmpl': download_output_path,
                    'format': format_selector,
                    'progress_hooks': [progress_hook],  # Enable progress reporting and capture final file path
                    'quiet': True,  # Suppress output
                    'no_warnings': True,  # Suppress warnings
                    'nocheckcertificate': True,  # Skip certificate checks
                    'retries': 10,  # Retry on failures
                    'fragment_retries': 10,  # Retry fragments
                    'file_access_retries': 3,  # Retry file access
                    'sleep_interval': 1,  # Sleep between requests
                    'max_sleep_interval': 5,  # Max sleep interval
                    'sleep_interval_requests': 1,  # Sleep between requests
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],  # Try different clients
                        }
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                    },
                }
                
                # For live streams, handle download options
                if video_info.is_live and not download_from_start:
                    # Download from current point
                    ydl_opts = {
                        **base_opts,
                        'live_recording_duration': 3600,  # 1 hour max for live
                        'live_from_start': False,
                    }
                else:
                    # Download from start or regular video
                    ydl_opts = {
                        **base_opts,
                        'live_from_start': download_from_start,
                    }
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # Download the video
                        ydl.download([url])
                        # If we get here, download succeeded
                        # Wait a moment for file operations to complete
                        time.sleep(0.5)
                        break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    # If format not available, try next format selector
                    if 'Requested format is not available' in error_msg or 'format is not available' in error_msg.lower():
                        continue
                    # If 403 error, try next format selector (might work with different format)
                    if '403' in error_msg or 'Forbidden' in error_msg:
                        continue
                    # For other errors, re-raise
                    raise
            else:
                # All format selectors failed
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"All format selectors failed. Last error: {last_error}",
                    video_info=video_info
                )
            
            try:
                # Wait for file operations to complete and retry finding the file
                # yt-dlp may still be renaming .part files to final names
                max_retries = 10
                retry_delay = 1.0
                
                if needs_cut:
                    # First, try to use the captured file path from postprocessor hook
                    if downloaded_file_path[0] and Path(downloaded_file_path[0]).exists():
                        original_file_path = downloaded_file_path[0]
                    else:
                        # Fallback: search for file by video ID in temp directory
                        search_dir = self._get_temp_dir()
                        for attempt in range(max_retries):
                            # Find the downloaded file (exclude .part files which are incomplete)
                            downloaded_files = [
                                f for f in search_dir.glob(f'{video_info.id}*')
                                if not f.name.endswith('.part') and not f.name.endswith('.ytdl') and f.is_file()
                                and not '_' in f.name  # Exclude cut files (they have _ in name)
                            ]
                            
                            if downloaded_files:
                                # Get the most recent complete file (in case of multiple files)
                                original_file_path = str(max(downloaded_files, key=lambda f: f.stat().st_mtime))
                                # Verify it's not a .part file by checking the actual filename
                                if not original_file_path.endswith('.part') and not original_file_path.endswith('.ytdl'):
                                    # Verify file is not still being written (check if size is stable)
                                    file_path_obj = Path(original_file_path)
                                    if file_path_obj.exists():
                                        size1 = file_path_obj.stat().st_size
                                        time.sleep(0.2)
                                        size2 = file_path_obj.stat().st_size
                                        if size1 == size2 and size1 > 0:
                                            break  # File size is stable, it's complete
                            
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                retry_delay = min(retry_delay * 1.5, 3.0)  # Exponential backoff, max 3s
                    
                    if not original_file_path or not Path(original_file_path).exists():
                        # Check if there are .part files (incomplete download)
                        search_dir = self._get_temp_dir()
                        part_files = list(search_dir.glob(f'{video_info.id}*.part'))
                        if part_files:
                            return DownloadResult(
                                success=False,
                                file_path=None,
                                file_size=None,
                                error_message="Download incomplete - only .part file found. The download may have been interrupted.",
                                video_info=video_info
                            )
                        return DownloadResult(
                            success=False,
                            file_path=None,
                            file_size=None,
                            error_message="Download completed but file not found after waiting",
                            video_info=video_info
                        )
            except Exception as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=str(e),
                    video_info=video_info
                )
        
        # Verify cached video exists if we're using one
        if cached_video_path:
            if not original_file_path or not Path(original_file_path).exists():
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Cached video file not found",
                    video_info=video_info
                )
        
        # When not cutting, file is in temp directory - find it and move to user's location
        if not needs_cut:
            # First, try to use the captured file path from progress hook
            if downloaded_file_path[0] and Path(downloaded_file_path[0]).exists():
                original_file_path = downloaded_file_path[0]
            else:
                # Search for file by video ID in temp directory
                search_dir = self._get_temp_dir()
                for attempt in range(max_retries):
                    # Find the downloaded file (exclude .part files which are incomplete)
                    downloaded_files = [
                        f for f in search_dir.glob(f'{video_info.id}*')
                        if not f.name.endswith('.part') and not f.name.endswith('.ytdl') and f.is_file()
                        and not '_' in f.name  # Exclude cut files (they have _ in name)
                    ]
                    
                    if downloaded_files:
                        # Get the most recent complete file (in case of multiple files)
                        original_file_path = str(max(downloaded_files, key=lambda f: f.stat().st_mtime))
                        # Verify it's not a .part file by checking the actual filename
                        if not original_file_path.endswith('.part') and not original_file_path.endswith('.ytdl'):
                            # Verify file is not still being written (check if size is stable)
                            file_path_obj = Path(original_file_path)
                            if file_path_obj.exists():
                                size1 = file_path_obj.stat().st_size
                                time.sleep(0.2)
                                size2 = file_path_obj.stat().st_size
                                if size1 == size2 and size1 > 0:
                                    break  # File size is stable, it's complete
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 3.0)  # Exponential backoff, max 3s
            
            if not original_file_path or not Path(original_file_path).exists():
                # Check if there are .part files (incomplete download)
                search_dir = self._get_temp_dir()
                part_files = list(search_dir.glob(f'{video_info.id}*.part'))
                if part_files:
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        file_size=None,
                        error_message="Download incomplete - only .part file found. The download may have been interrupted.",
                        video_info=video_info
                    )
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Download completed but file not found after waiting",
                    video_info=video_info
                )
        
        # Final safety check - ensure the path doesn't end with .part
        if original_file_path and (original_file_path.endswith('.part') or original_file_path.endswith('.ytdl')):
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message="Download incomplete - file is still a .part file",
                video_info=video_info
            )
        
        # If start_time or end_time is provided, cut the video
        if needs_cut:
            # Ensure output directory exists before cutting
            try:
                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"Failed to create output directory: {str(e)}",
                    video_info=video_info
                )
            
            # Cut the video and save to user-specified output path
            if self.cut_video(original_file_path, output_path, start_time, end_time):
                # Verify the cut file was created
                if not Path(output_path).exists():
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        file_size=None,
                        error_message="Video cut completed but output file not found",
                        video_info=video_info
                    )
                final_file_path = output_path
                # Full video in temp directory is kept for future use (caching)
            else:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Failed to cut video",
                    video_info=video_info
                )
        else:
            # No cutting needed, copy file from temp to user's requested location
            # Keep original in temp for caching
            try:
                # Ensure output directory exists
                output_path_obj = Path(output_path)
                output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file to user's location
                shutil.copy2(original_file_path, output_path)
                final_file_path = output_path
                # Original file in temp directory is kept for future use (caching)
            except Exception as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"Failed to copy file to requested location: {str(e)}",
                    video_info=video_info
                )
        
        file_size = os.path.getsize(final_file_path)
        
        # Final verification: ensure the file path doesn't contain .part
        if '.part' in final_file_path or final_file_path.endswith('.ytdl'):
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message=f"Download incomplete - file path contains .part: {final_file_path}",
                video_info=video_info
            )
        
        return DownloadResult(
            success=True,
            file_path=final_file_path,
            file_size=file_size,
            error_message=None,
            video_info=video_info
        )
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is a valid YouTube URL"""
        try:
            # Basic URL validation
            if not url.startswith(('http://', 'https://')):
                return False
            
            # Check if it's a YouTube URL
            if 'youtube.com' not in url and 'youtu.be' not in url:
                return False
            
            # Try to extract info to validate
            info = self.extract_video_info(url)
            return info is not None
            
        except Exception:
            return False


def main():
    """Main function for command line usage"""
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <youtube_url> [download_from_start] [quality] [start_time] [end_time] [output_path] OR python downloader.py --validate <youtube_url>", file=sys.stderr)
        sys.exit(1)
    
    # Check if this is a validation request
    if sys.argv[1] == "--validate":
        if len(sys.argv) < 3:
            print("Usage: python downloader.py --validate <youtube_url>", file=sys.stderr)
            sys.exit(1)
        url = sys.argv[2]
        downloader = YouTubeDownloader()
        
        # Extract video info only (no download)
        video_info = downloader.extract_video_info(url)
        if not video_info:
            sys.stdout.write(json.dumps({
                'success': False,
                'error': 'Failed to extract video information'
            }))
            sys.stdout.flush()
            sys.exit(1)
        
        # Return video info as JSON
        sys.stdout.write(json.dumps({
            'success': True,
            'video_info': asdict(video_info)
        }))
        sys.stdout.flush()
        sys.exit(0)
    
    # Regular download mode
    url = sys.argv[1]
    download_from_start = len(sys.argv) > 2 and sys.argv[2].lower() == 'true'
    quality = sys.argv[3] if len(sys.argv) > 3 else 'bestvideo+bestaudio/best'
    start_time = None
    end_time = None
    output_path = None
    
    # Parse arguments: [url, download_from_start, quality, start_time, end_time, output_path]
    if len(sys.argv) > 4 and sys.argv[4] and sys.argv[4].strip():
      try:
        start_time = int(sys.argv[4])
      except (ValueError, TypeError):
        start_time = None
    if len(sys.argv) > 5 and sys.argv[5] and sys.argv[5].strip():
      try:
        end_time = int(sys.argv[5])
      except (ValueError, TypeError):
        end_time = None
    if len(sys.argv) > 6 and sys.argv[6] and sys.argv[6].strip():
      output_path = sys.argv[6]
    
    if not output_path:
        sys.stdout.write(json.dumps({
            'success': False,
            'error': 'Output path is required'
        }))
        sys.stdout.flush()
        sys.exit(1)
    
    downloader = YouTubeDownloader()
    
    # Validate URL
    if not downloader.validate_url(url):
        sys.stdout.write(json.dumps({
            'success': False,
            'error': 'Invalid YouTube URL'
        }))
        sys.stdout.flush()
        sys.exit(1)
    
    # Extract video info first
    video_info = downloader.extract_video_info(url)
    if not video_info:
        sys.stdout.write(json.dumps({
            'success': False,
            'error': 'Failed to extract video information'
        }))
        sys.stdout.flush()
        sys.exit(1)
    
    # For scheduled videos, don't download yet
    if video_info.is_scheduled:
        sys.stdout.write(json.dumps({
            'success': True,
            'video_info': asdict(video_info),
            'message': 'Video is scheduled. Will download when stream starts.',
            'scheduled': True
        }))
        sys.stdout.flush()
        sys.exit(0)
    
    # Download the video
    result = downloader.download_video(url, output_path, download_from_start, quality, start_time, end_time)
    
    # Output result as JSON
    output = {
        'success': result.success,
        'video_info': asdict(result.video_info) if result.video_info else None,
        'file_path': result.file_path,
        'file_size': result.file_size,
        'error_message': result.error_message
    }
    
    sys.stdout.write(json.dumps(output, indent=2))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
