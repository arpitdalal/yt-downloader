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
import re
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
import yt_dlp
from dataclasses import dataclass, asdict


# Constants
CUT_FILE_MARKER = '_cut_'  # Marker for cut files to distinguish from originals
FILE_STABILITY_CHECK_DELAY = 0.2  # Seconds to wait between file size checks
FILE_STABILITY_CHECK_RETRIES = 3  # Number of times to check file stability
DOWNLOAD_COMPLETION_WAIT = 0.5  # Seconds to wait after download completes
MAX_FILE_FIND_RETRIES = 10
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 3.0
RETRY_BACKOFF_MULTIPLIER = 1.5
INCOMPLETE_FILE_EXTENSIONS = ('.part', '.ytdl')
VIDEO_EXTENSIONS = ['mp4', 'webm', 'mkv', 'm4a', 'flv', 'avi', 'mov']


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
    cached_file_path: Optional[str] = None  # Path to cached full video in temp directory


class DownloadProgressTracker:
    """Tracks download progress and final file path"""
    def __init__(self):
        self.final_file_path: Optional[str] = None
    
    def create_hook(self):
        """Create a progress hook function"""
        def progress_hook(d):
            status = d.get('status')
            
            # Capture final file path when download finishes
            if status == 'finished':
                filename = d.get('filename') or d.get('info_dict', {}).get('_filename')
                if filename:
                    self.final_file_path = filename
            
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
        
        return progress_hook


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
    
    @staticmethod
    def _sanitize_video_id(video_id: str) -> str:
        """Sanitize video ID to prevent path traversal attacks"""
        # Remove any path separators and dangerous characters
        sanitized = re.sub(r'[<>:"|?*\x00-\x1f]', '', video_id)
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        # Ensure it's not empty
        if not sanitized:
            raise ValueError("Invalid video ID: empty after sanitization")
        return sanitized
    
    @staticmethod
    def _validate_ffmpeg_path(ffmpeg_path: str) -> str:
        """Validate and sanitize ffmpeg path to prevent command injection"""
        if not ffmpeg_path:
            raise ValueError("FFmpeg path cannot be empty")
        
        # Remove any command injection attempts
        if any(char in ffmpeg_path for char in [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']):
            raise ValueError(f"Invalid characters in FFmpeg path: {ffmpeg_path}")
        
        # If it's a relative path, resolve it
        path = Path(ffmpeg_path)
        if path.is_absolute():
            if not path.exists():
                raise FileNotFoundError(f"FFmpeg not found at: {ffmpeg_path}")
        else:
            # Check if it's in PATH
            which_result = shutil.which(ffmpeg_path)
            if not which_result:
                raise FileNotFoundError(f"FFmpeg not found in PATH: {ffmpeg_path}")
            ffmpeg_path = which_result
        
        return ffmpeg_path
    
    @staticmethod
    def _validate_output_path(output_path: str) -> None:
        """Validate output path for security and correctness"""
        if not output_path or not output_path.strip():
            raise ValueError("Output path cannot be empty")
        
        path = Path(output_path)
        
        # Check for path traversal attempts
        try:
            path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            # Path is outside current directory - this might be intentional, but log it
            pass
        
        # Ensure parent directory can be created
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise ValueError(f"Cannot create output directory: {e}")
    
    @staticmethod
    def _is_cut_file(filename: str) -> bool:
        """Check if a filename indicates it's a cut file"""
        return CUT_FILE_MARKER in filename
    
    @staticmethod
    def _is_incomplete_file(filename: str) -> bool:
        """Check if a file is incomplete (e.g., .part, .ytdl)"""
        return filename.endswith(INCOMPLETE_FILE_EXTENSIONS)
    
    @staticmethod
    def _is_valid_video_file(file_path: Path) -> bool:
        """Check if a file is a valid complete video file"""
        if not file_path.exists() or not file_path.is_file():
            return False
        
        if file_path.stat().st_size == 0:
            return False
        
        if YouTubeDownloader._is_incomplete_file(file_path.name):
            return False
        
        if YouTubeDownloader._is_cut_file(file_path.name):
            return False
        
        return True
    
    @staticmethod
    def _check_file_stability(file_path: Path, max_checks: int = FILE_STABILITY_CHECK_RETRIES) -> bool:
        """Check if file size is stable (not being written to)"""
        if not file_path.exists():
            return False
        
        sizes = []
        for _ in range(max_checks):
            try:
                size = file_path.stat().st_size
                sizes.append(size)
                if len(sizes) > 1 and sizes[-1] != sizes[-2]:
                    return False
                time.sleep(FILE_STABILITY_CHECK_DELAY)
            except (OSError, FileNotFoundError):
                return False
        
        # All sizes are the same and file exists
        return len(sizes) == max_checks and sizes[0] > 0
    
    def _find_downloaded_file(
        self,
        video_id: str,
        search_dir: Path,
        progress_tracker: Optional[DownloadProgressTracker] = None,
        max_retries: int = MAX_FILE_FIND_RETRIES
    ) -> Optional[Path]:
        """Find the downloaded video file in the search directory"""
        # Try both original and sanitized video_id for backward compatibility
        search_ids = [video_id]  # Try original first (matches download path)
        
        try:
            sanitized_id = self._sanitize_video_id(video_id)
            if sanitized_id != video_id:
                search_ids.append(sanitized_id)  # Also try sanitized if different
        except ValueError:
            pass  # If sanitization fails, just use original
        
        # First, try to use the captured file path from progress hook
        if progress_tracker and progress_tracker.final_file_path:
            candidate = Path(progress_tracker.final_file_path)
            if candidate.exists() and self._is_valid_video_file(candidate):
                if self._check_file_stability(candidate):
                    return candidate
        
        # Fallback: search for file by video ID in temp directory
        retry_delay = INITIAL_RETRY_DELAY
        
        for attempt in range(max_retries):
            # Try each possible video ID
            for search_id in search_ids:
                # Find the downloaded file (exclude incomplete and cut files)
                downloaded_files = [
                    f for f in search_dir.glob(f'{search_id}*')
                    if self._is_valid_video_file(f)
                ]
                
                if downloaded_files:
                    # Get the most recent complete file (in case of multiple files)
                    candidate = max(downloaded_files, key=lambda f: f.stat().st_mtime)
                    
                    # Verify file is not still being written (check if size is stable)
                    if self._check_file_stability(candidate):
                        return candidate
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
        
        return None
    
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
                
        except yt_dlp.utils.DownloadError as e:
            print(f"Error extracting video info (DownloadError): {e}", file=sys.stderr)
            return None
        except yt_dlp.utils.ExtractorError as e:
            print(f"Error extracting video info (ExtractorError): {e}", file=sys.stderr)
            return None
        except (ValueError, KeyError, TypeError) as e:
            print(f"Error extracting video info (DataError): {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Error extracting video info (Unexpected): {e}", file=sys.stderr)
            return None
    
    def _get_cached_video_path(self, video_id: str) -> Optional[str]:
        """Check if a cached video exists in temp directory for the given video ID"""
        temp_dir = self._get_temp_dir()
        if not temp_dir.exists():
            return None
        
        # Try both original and sanitized video_id for backward compatibility
        # Files may have been downloaded with original video_id before sanitization
        search_ids = [video_id]  # Try original first for backward compatibility
        
        try:
            sanitized_id = self._sanitize_video_id(video_id)
            if sanitized_id != video_id:
                search_ids.append(sanitized_id)  # Also try sanitized if different
        except ValueError:
            pass  # If sanitization fails, just use original
        
        # Check each possible video ID
        for search_id in search_ids:
            # Check common video extensions first
            for ext in VIDEO_EXTENSIONS:
                cached_path = temp_dir / f'{search_id}.{ext}'
                if cached_path.exists() and self._is_valid_video_file(cached_path):
                    if self._check_file_stability(cached_path):
                        return str(cached_path)
            
            # Also check for any file with video_id prefix (in case extension is different)
            matching_files = [
                f for f in temp_dir.glob(f'{search_id}.*')
                if self._is_valid_video_file(f)
            ]
            
            if matching_files:
                # Get the largest file (more likely to be complete)
                candidate = max(matching_files, key=lambda f: f.stat().st_size)
                if self._check_file_stability(candidate):
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
        # Validate input path
        input_path_obj = Path(input_path)
        if not input_path_obj.exists() or not input_path_obj.is_file():
            print(f"Input file does not exist: {input_path}", file=sys.stderr)
            return False
        
        # Validate output path
        try:
            self._validate_output_path(output_path)
        except ValueError as e:
            print(f"Invalid output path: {e}", file=sys.stderr)
            return False
        
        # Get and validate ffmpeg path
        ffmpeg_path = os.environ.get('FFMPEG_PATH', 'ffmpeg')
        try:
            ffmpeg_path = self._validate_ffmpeg_path(ffmpeg_path)
        except (ValueError, FileNotFoundError) as e:
            print(f"FFmpeg validation error: {e}", file=sys.stderr)
            return False
        
        cmd = [ffmpeg_path]
        
        # When using -c copy, -ss must be before -i for accurate seeking
        if start_time is not None:
            cmd.extend(['-ss', str(start_time)])
        
        cmd.extend(['-i', str(input_path), '-c', 'copy'])
        
        if end_time is not None:
            # Calculate duration: if start_time is None, duration is just end_time
            # Otherwise, duration is end_time - start_time
            if start_time is not None:
                duration = end_time - start_time
            else:
                duration = end_time
            if duration <= 0:
                print(f"Invalid duration: start_time={start_time}, end_time={end_time}, duration={duration}", file=sys.stderr)
                return False
            cmd.extend(['-t', str(duration)])
        
        cmd.extend(['-avoid_negative_ts', 'make_zero', str(output_path), '-y'])
        
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=3600  # 1 hour timeout
            )
            return True
        except subprocess.TimeoutExpired:
            print(f"FFmpeg command timed out after 1 hour", file=sys.stderr)
            print(f"FFmpeg command: {' '.join(cmd)}", file=sys.stderr)
            return False
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)
            print(f"FFmpeg error: {error_output}", file=sys.stderr)
            print(f"FFmpeg command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Input path: {input_path}", file=sys.stderr)
            print(f"Output path: {output_path}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print(f"FFmpeg not found at: {ffmpeg_path}", file=sys.stderr)
            print(f"Please ensure FFmpeg is installed or FFMPEG_PATH environment variable is set correctly", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error cutting video: {e}", file=sys.stderr)
            print(f"FFmpeg path used: {ffmpeg_path}", file=sys.stderr)
            print(f"FFmpeg command: {' '.join(cmd)}", file=sys.stderr)
            print(f"Input path: {input_path}", file=sys.stderr)
            print(f"Output path: {output_path}", file=sys.stderr)
            return False
    
    def cut_and_concatenate_sections(
        self,
        input_path: str,
        sections: List[Tuple[Optional[int], Optional[int]]],
        output_path: str,
        video_id: str
    ) -> bool:
        """Cut multiple sections from video and concatenate them"""
        # Validate input path
        input_path_obj = Path(input_path)
        if not input_path_obj.exists() or not input_path_obj.is_file():
            print(f"Input file does not exist: {input_path}", file=sys.stderr)
            return False
        
        # Validate output path
        try:
            self._validate_output_path(output_path)
        except ValueError as e:
            print(f"Invalid output path: {e}", file=sys.stderr)
            return False
        
        # Get and validate ffmpeg path
        ffmpeg_path = os.environ.get('FFMPEG_PATH', 'ffmpeg')
        try:
            ffmpeg_path = self._validate_ffmpeg_path(ffmpeg_path)
        except (ValueError, FileNotFoundError) as e:
            print(f"FFmpeg validation error: {e}", file=sys.stderr)
            return False
        
        temp_dir = self._get_temp_dir()
        section_files: List[Path] = []
        concat_file: Optional[Path] = None
        
        try:
            # Cut each section to a temporary file
            for index, (start_time, end_time) in enumerate(sections):
                section_output = temp_dir / f'{video_id}_section_{index}.mp4'
                
                # Cut this section
                if not self.cut_video(str(input_path), str(section_output), start_time, end_time):
                    print(f"Failed to cut section {index + 1}", file=sys.stderr)
                    return False
                
                # Verify section file was created
                if not section_output.exists() or not self._is_valid_video_file(section_output):
                    print(f"Section {index + 1} file is invalid or missing", file=sys.stderr)
                    return False
                
                section_files.append(section_output)
            
            # Create concat file
            concat_file = temp_dir / f'{video_id}_concat.txt'
            with open(concat_file, 'w', encoding='utf-8') as f:
                for section_file in section_files:
                    # Use absolute path for ffmpeg concat format
                    abs_path = section_file.resolve()
                    # Convert to forward slashes for cross-platform compatibility
                    # ffmpeg concat format expects forward slashes or escaped backslashes
                    path_str = str(abs_path).replace('\\', '/')
                    f.write(f"file '{path_str}'\n")
            
            # Concatenate all sections
            cmd = [
                ffmpeg_path,
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_path),
                '-y'
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=3600  # 1 hour timeout
                )
            except subprocess.TimeoutExpired:
                print(f"FFmpeg concatenation timed out after 1 hour", file=sys.stderr)
                return False
            except subprocess.CalledProcessError as e:
                error_output = e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)
                print(f"FFmpeg concatenation error: {error_output}", file=sys.stderr)
                return False
            except FileNotFoundError:
                print(f"FFmpeg not found at: {ffmpeg_path}", file=sys.stderr)
                return False
            except Exception as e:
                print(f"Error concatenating sections: {e}", file=sys.stderr)
                return False
            
            # Verify output file was created
            if not Path(output_path).exists():
                print(f"Concatenated output file not found", file=sys.stderr)
                return False
            
            return True
            
        finally:
            # Clean up temporary section files and concat file
            for section_file in section_files:
                try:
                    if section_file.exists():
                        section_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete section file {section_file}: {e}", file=sys.stderr)
            
            if concat_file and concat_file.exists():
                try:
                    concat_file.unlink()
                except Exception as e:
                    print(f"Warning: Failed to delete concat file {concat_file}: {e}", file=sys.stderr)
    
    def download_video(
        self, 
        url: str, 
        output_path: str,
        download_from_start: bool = False,
        quality: str = 'bestvideo+bestaudio/best',
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        sections: Optional[List[Tuple[Optional[int], Optional[int]]]] = None
    ) -> DownloadResult:
        """Download a video from YouTube"""
        
        # Validate output path early
        try:
            self._validate_output_path(output_path)
        except ValueError as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message=f"Invalid output path: {str(e)}",
                video_info=None
            )
        
        # Extract video info
        video_info = self.extract_video_info(url)
        if not video_info:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message="Failed to extract video information",
                video_info=None
            )
        
        # Sanitize video ID
        try:
            sanitized_video_id = self._sanitize_video_id(video_info.id)
        except ValueError as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message=f"Invalid video ID: {str(e)}",
                video_info=video_info
            )
        
        # Check if we need to cut the video
        # Use sections if provided, otherwise fall back to single start/end time
        if sections and len(sections) > 0:
            needs_cut = True
            use_sections = True
        else:
            needs_cut = start_time is not None or end_time is not None
            use_sections = False
        
        # Initialize progress tracker
        progress_tracker = DownloadProgressTracker()
        
        # Check for cached video first (use original video_id for backward compatibility)
        cached_video_path = self._get_cached_video_path(video_info.id)
        original_file_path: Optional[Path] = None
        
        if cached_video_path:
            original_file_path = Path(cached_video_path)
            if not original_file_path.exists() or not self._is_valid_video_file(original_file_path):
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Cached video file not found or invalid",
                    video_info=video_info
                )
        else:
            # Download the video
            temp_dir = self._get_temp_dir()
            # Use original video_id for download path to match original behavior and cached files
            # The video_id is already validated from YouTube, so it should be safe
            download_output_path = str(temp_dir / f'{video_info.id}.%(ext)s')
            
            # Format selectors to try in order (most preferred first)
            format_selectors = [
                quality,  # Try user-specified format first
                'bestvideo+bestaudio/best',  # Try best video+audio combo
                'best[ext=mp4]/best[ext=webm]/best',  # Try mp4, then webm, then any
                'best',  # Fallback to any best format
            ]
            
            last_error = None
            
            # Check if SSL certificate verification should be disabled
            skip_cert_check = os.environ.get('YT_DLP_SKIP_CERT_CHECK', 'false').lower() == 'true'
            
            for format_selector in format_selectors:
                progress_hook = progress_tracker.create_hook()
                
                # Common options to help with 403 errors and ensure complete downloads
                base_opts = {
                    'outtmpl': download_output_path,
                    'format': format_selector,
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'retries': 10,
                    'fragment_retries': 10,
                    'file_access_retries': 3,
                    'sleep_interval': 1,
                    'max_sleep_interval': 5,
                    'sleep_interval_requests': 1,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],
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
                
                # Only skip certificate check if explicitly enabled via environment variable
                if skip_cert_check:
                    base_opts['nocheckcertificate'] = True
                
                # For live streams, handle download options
                if video_info.is_live and not download_from_start:
                    ydl_opts = {
                        **base_opts,
                        'live_recording_duration': 3600,  # 1 hour max for live
                        'live_from_start': False,
                    }
                else:
                    ydl_opts = {
                        **base_opts,
                        'live_from_start': download_from_start,
                    }
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                        # Wait for file operations to complete
                        time.sleep(DOWNLOAD_COMPLETION_WAIT)
                        break
                except yt_dlp.utils.DownloadError as e:
                    last_error = e
                    error_msg = str(e)
                    # If format not available, try next format selector
                    if 'Requested format is not available' in error_msg or 'format is not available' in error_msg.lower():
                        continue
                    # If 403 error, try next format selector
                    if '403' in error_msg or 'Forbidden' in error_msg:
                        continue
                    # For other download errors, re-raise
                    raise
                except Exception as e:
                    last_error = e
                    raise
            
            # Check if download succeeded
            if last_error and not original_file_path:
                # All format selectors failed
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"All format selectors failed. Last error: {last_error}",
                    video_info=video_info
                )
            
            # Find the downloaded file
            try:
                found_file = self._find_downloaded_file(
                    video_info.id,  # Use original video_id to match download path
                    temp_dir,
                    progress_tracker
                )
                
                if not found_file:
                    # Check if there are .part files (incomplete download)
                    part_files = list(temp_dir.glob(f'{video_info.id}*.part'))
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
                
                original_file_path = found_file
                
            except Exception as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"Error finding downloaded file: {str(e)}",
                    video_info=video_info
                )
        
        # Final validation of original file
        if not original_file_path or not self._is_valid_video_file(original_file_path):
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message="Downloaded file is invalid or incomplete",
                video_info=video_info
            )
        
        # Ensure the full video is stored in temp directory before processing
        # Verify the file is actually in temp directory and is stable
        temp_dir = self._get_temp_dir()
        try:
            # Check if file is in temp directory (compatible with Python < 3.9)
            original_resolved = original_file_path.resolve()
            temp_resolved = temp_dir.resolve()
            # Use path parts for more reliable comparison across platforms
            temp_parts = temp_resolved.parts
            original_parts = original_resolved.parts
            is_in_temp = len(original_parts) > len(temp_parts) and original_parts[:len(temp_parts)] == temp_parts
        except (OSError, ValueError):
            is_in_temp = False
        
        if not is_in_temp:
            # File is not in temp directory, ensure it's copied there for caching
            temp_file_path = temp_dir / f'{video_info.id}{original_file_path.suffix}'
            try:
                if not temp_file_path.exists() or not self._is_valid_video_file(temp_file_path):
                    shutil.copy2(str(original_file_path), str(temp_file_path))
                    # Verify the copy is stable
                    if not self._check_file_stability(temp_file_path):
                        return DownloadResult(
                            success=False,
                            file_path=None,
                            file_size=None,
                            error_message="Failed to store full video in temp directory",
                            video_info=video_info
                        )
                original_file_path = temp_file_path
            except (OSError, IOError, PermissionError) as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"Failed to store full video in temp directory: {str(e)}",
                    video_info=video_info
                )
        else:
            # File is already in temp, verify it's stable before proceeding
            if not self._check_file_stability(original_file_path):
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Full video file in temp directory is not stable",
                    video_info=video_info
                )
        
        # Process the video (cut or copy)
        try:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message=f"Failed to create output directory: {str(e)}",
                video_info=video_info
            )
        
        if needs_cut:
            # Verify original file exists before cutting
            if not original_file_path.exists():
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Original file in temp directory not found before cutting",
                    video_info=video_info
                )
            
            if use_sections:
                # Cut and concatenate multiple sections
                if not self.cut_and_concatenate_sections(
                    str(original_file_path),
                    sections,
                    output_path,
                    video_info.id
                ):
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        file_size=None,
                        error_message="Failed to cut and concatenate video sections",
                        video_info=video_info
                    )
            else:
                # Cut single section
                if not self.cut_video(str(original_file_path), output_path, start_time, end_time):
                    return DownloadResult(
                        success=False,
                        file_path=None,
                        file_size=None,
                        error_message="Failed to cut video",
                        video_info=video_info
                    )
            
            # Verify the cut file was created
            if not Path(output_path).exists():
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Video cut completed but output file not found",
                    video_info=video_info
                )
            
            # Verify original file still exists in temp after cutting
            if not original_file_path.exists() or not self._is_valid_video_file(original_file_path):
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Original file in temp directory was lost after cutting",
                    video_info=video_info
                )
            
            final_file_path = output_path
            # Original file in temp directory is kept for future use (caching)
        else:
            # No cutting needed, copy file from temp to user's requested location
            # Keep original in temp for caching
            try:
                shutil.copy2(str(original_file_path), output_path)
                final_file_path = output_path
                # Original file in temp directory is kept for future use (caching)
            except (OSError, IOError, PermissionError) as e:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message=f"Failed to copy file to requested location: {str(e)}",
                    video_info=video_info
                )
        
        # Verify the cached file still exists in temp directory
        cached_file_path_str = None
        if original_file_path and original_file_path.exists():
            # Verify it's still a valid video file
            if self._is_valid_video_file(original_file_path):
                cached_file_path_str = str(original_file_path)
        
        # Final validation
        final_path_obj = Path(final_file_path)
        if not final_path_obj.exists() or not final_path_obj.is_file():
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message="Final output file does not exist",
                video_info=video_info
            )
        
        try:
            file_size = final_path_obj.stat().st_size
            if file_size == 0:
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=None,
                    error_message="Final output file is empty",
                    video_info=video_info
                )
        except OSError as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=None,
                error_message=f"Failed to get file size: {str(e)}",
                video_info=video_info
            )
        
        return DownloadResult(
            success=True,
            file_path=final_file_path,
            file_size=file_size,
            error_message=None,
            video_info=video_info,
            cached_file_path=cached_file_path_str
        )
    
    def validate_url(self, url: str) -> bool:
        """Validate if URL is a valid YouTube URL"""
        if not url or not isinstance(url, str):
            return False
        
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
    
    # Check if this is a local file processing request
    if sys.argv[1] == "--local":
        if len(sys.argv) < 5:
            print("Usage: python downloader.py --local <input_path> <sections_json> <output_path>", file=sys.stderr)
            sys.exit(1)
        
        input_path = sys.argv[2]
        sections_json = sys.argv[3]
        output_path = sys.argv[4]
        
        downloader = YouTubeDownloader()
        
        try:
            # Parse sections
            sections = []
            if sections_json and sections_json.strip() and sections_json != "[]":
                try:
                    parsed_sections = json.loads(sections_json)
                    if isinstance(parsed_sections, list):
                        sections = [
                            (
                                section.get('start') if isinstance(section, dict) else None,
                                section.get('end') if isinstance(section, dict) else None
                            )
                            for section in parsed_sections
                        ]
                except json.JSONDecodeError:
                    sys.stdout.write(json.dumps({
                        'success': False,
                        'error_message': 'Invalid sections JSON'
                    }))
                    sys.stdout.flush()
                    sys.exit(1)
            
            # Process local file
            success = False
            error_message = None
            
            if sections:
                # Use a dummy video ID for temp files
                video_id = "local_video"
                success = downloader.cut_and_concatenate_sections(
                    input_path,
                    sections,
                    output_path,
                    video_id
                )
                if not success:
                    error_message = "Failed to cut and concatenate sections"
            else:
                # Just copy if no sections (or maybe we shouldn't allow this? But for completeness)
                # If no sections are defined, we probably just want to copy the file or it's a no-op?
                # The UI enforces sections usually. If sections is empty, maybe we treat it as "whole video"?
                # But for now let's assume if no sections, we just copy.
                try:
                    shutil.copy2(input_path, output_path)
                    success = True
                except Exception as e:
                    success = False
                    error_message = f"Failed to copy file: {str(e)}"
            
            # Get file size if successful
            file_size = 0
            if success and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
            
            sys.stdout.write(json.dumps({
                'success': success,
                'file_path': output_path if success else None,
                'file_size': file_size,
                'error_message': error_message
            }))
            sys.stdout.flush()
            sys.exit(0 if success else 1)
            
        except Exception as e:
            sys.stdout.write(json.dumps({
                'success': False,
                'error_message': f"Unexpected error: {str(e)}"
            }))
            sys.stdout.flush()
            sys.exit(1)

    # Regular download mode
    url = sys.argv[1]
    download_from_start = len(sys.argv) > 2 and sys.argv[2].lower() == 'true'
    quality = sys.argv[3] if len(sys.argv) > 3 else 'bestvideo+bestaudio/best'
    start_time = None
    end_time = None
    sections = None
    output_path = None
    
    # Parse arguments: 
    # Sections format (6 args): [script, url, download_from_start, quality, sections_json, output_path]
    # Legacy format (7 args): [script, url, download_from_start, quality, start_time, end_time, output_path]
    # Output path is always the last argument
    if len(sys.argv) > 1:
        output_path = sys.argv[-1].strip() if sys.argv[-1] else None
    
    # Determine format based on argument count and content
    # Sections format has 6 args total (including script name), legacy has 7
    # Also check if arg4 looks like JSON (starts with '[') to be more robust
    if len(sys.argv) == 6:
        # Sections format: arg4 is sections JSON
        if len(sys.argv) > 4 and sys.argv[4] and sys.argv[4].strip():
            arg4 = sys.argv[4].strip()
            # Check if it looks like JSON (starts with '[')
            if arg4.startswith('['):
                try:
                    parsed_sections = json.loads(arg4)
                    if isinstance(parsed_sections, list) and len(parsed_sections) > 0:
                        # Convert to list of tuples
                        sections = [
                            (
                                section.get('start') if isinstance(section, dict) else None,
                                section.get('end') if isinstance(section, dict) else None
                            )
                            for section in parsed_sections
                        ]
                    else:
                        sys.stdout.write(json.dumps({
                            'success': False,
                            'error': 'Invalid sections format: empty list or not a list'
                        }))
                        sys.stdout.flush()
                        sys.exit(1)
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    sys.stdout.write(json.dumps({
                        'success': False,
                        'error': f'Failed to parse sections JSON: {str(e)}'
                    }))
                    sys.stdout.flush()
                    sys.exit(1)
            else:
                # Not JSON, treat as legacy format (single start_time)
                try:
                    start_time = int(arg4)
                    if start_time < 0:
                        start_time = None
                except (ValueError, TypeError):
                    start_time = None
                # In this case, output_path is already set from sys.argv[-1]
    elif len(sys.argv) >= 7:
        # Legacy format: arg4 is start_time, arg5 is end_time
        if len(sys.argv) > 4 and sys.argv[4] and sys.argv[4].strip():
            try:
                start_time = int(sys.argv[4])
                if start_time < 0:
                    start_time = None
            except (ValueError, TypeError):
                start_time = None
        
        if len(sys.argv) > 5 and sys.argv[5] and sys.argv[5].strip():
            try:
                end_time = int(sys.argv[5])
                if end_time < 0:
                    end_time = None
            except (ValueError, TypeError):
                end_time = None
    
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
    result = downloader.download_video(url, output_path, download_from_start, quality, start_time, end_time, sections)
    
    # Output result as JSON
    output = {
        'success': result.success,
        'video_info': asdict(result.video_info) if result.video_info else None,
        'file_path': result.file_path,
        'file_size': result.file_size,
        'error_message': result.error_message,
        'cached_file_path': result.cached_file_path
    }
    
    sys.stdout.write(json.dumps(output, indent=2))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
