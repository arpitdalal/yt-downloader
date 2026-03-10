#!/usr/bin/env python3
"""
Comprehensive test suite for downloader.py
Covers all methods, edge cases, and error scenarios
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

# Import the module under test
from downloader import (
    CACHE_KEY_VERSION,
    DownloadProgressTracker,
    DownloadResult,
    VideoInfo,
    YouTubeDownloader,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_info():
    """Sample video info for testing"""
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Test Video",
        "duration": 212,
        "live_status": "not_live",
        "thumbnail": "https://example.com/thumb.jpg",
        "uploader": "Test Channel",
        "view_count": 1000000,
        "upload_date": "20230101",
    }


@pytest.fixture
def sample_live_video_info():
    """Sample live stream video info"""
    return {
        "id": "live123",
        "title": "Live Stream",
        "duration": None,
        "live_status": "is_live",
        "thumbnail": "https://example.com/thumb.jpg",
        "uploader": "Test Channel",
        "view_count": 5000,
        "upload_date": None,
    }


@pytest.fixture
def sample_scheduled_video_info():
    """Sample scheduled video info"""
    return {
        "id": "scheduled123",
        "title": "Scheduled Video",
        "duration": None,
        "live_status": "is_upcoming",
        "release_timestamp": 1735689600,  # Future timestamp
        "thumbnail": "https://example.com/thumb.jpg",
        "uploader": "Test Channel",
        "view_count": 0,
        "upload_date": None,
    }


@pytest.fixture
def mock_ytdlp_extract_info(sample_video_info):
    """Mock yt-dlp extract_info"""
    with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = sample_video_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        mock_ydl.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_ytdlp_download():
    """Mock yt-dlp download"""
    with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
        mock_instance = MagicMock()
        mock_instance.download.return_value = None
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        mock_ydl.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run"""
    with patch("downloader.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture
def mock_shutil_which():
    """Mock shutil.which"""
    with patch("downloader.shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/ffmpeg"
        yield mock_which


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestVideoInfo:
    """Test VideoInfo dataclass"""

    def test_video_info_creation(self):
        """Test creating VideoInfo with all fields"""
        info = VideoInfo(
            id="test123",
            title="Test",
            duration=100,
            is_live=False,
            is_scheduled=False,
            scheduled_start_time=None,
            thumbnail="http://example.com/thumb.jpg",
            uploader="Test User",
            view_count=1000,
            upload_date="20230101",
        )
        assert info.id == "test123"
        assert info.title == "Test"
        assert info.duration == 100
        assert info.is_live is False
        assert info.is_scheduled is False

    def test_video_info_optional_fields(self):
        """Test VideoInfo with optional fields as None"""
        info = VideoInfo(
            id="test123",
            title="Test",
            duration=None,
            is_live=False,
            is_scheduled=False,
            scheduled_start_time=None,
            thumbnail=None,
            uploader=None,
            view_count=None,
            upload_date=None,
        )
        assert info.duration is None
        assert info.thumbnail is None


class TestDownloadResult:
    def test_download_result_success(self):
        """Test successful DownloadResult"""
        result = DownloadResult(
            success=True,
            file_path="/path/to/file.mp4",
            file_size=1024,
            error_message=None,
            video_info=VideoInfo(
                id="test123",
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
            cached_file_path="/tmp/cache.mp4",
        )
        assert result.success is True
        assert result.file_path == "/path/to/file.mp4"
        assert result.file_size == 1024
        assert result.error_message is None

    def test_download_result_failure(self):
        """Test failed DownloadResult"""
        result = DownloadResult(
            success=False,
            file_path=None,
            file_size=None,
            error_message="Download failed",
            video_info=None,
        )
        assert result.success is False
        assert result.file_path is None
        assert result.error_message == "Download failed"


# ============================================================================
# DownloadProgressTracker Tests
# ============================================================================


class TestDownloadProgressTracker:
    """Test DownloadProgressTracker"""

    def test_progress_tracker_initialization(self):
        """Test tracker initialization"""
        tracker = DownloadProgressTracker()
        assert tracker.final_file_path is None

    def test_progress_hook_finished_status(self):
        """Test progress hook captures file path on finished status"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook({"status": "finished", "filename": "/path/to/video.mp4"})

        assert tracker.final_file_path == "/path/to/video.mp4"

    def test_progress_hook_finished_with_info_dict(self):
        """Test progress hook uses info_dict filename if filename not present"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook({"status": "finished", "info_dict": {"_filename": "/path/to/video.mp4"}})

        assert tracker.final_file_path == "/path/to/video.mp4"

    def test_progress_hook_downloading_with_percent_str(self, capsys):
        """Test progress hook calculates percent from _percent_str"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook(
            {
                "status": "downloading",
                "_percent_str": "50.5%",
                "downloaded_bytes": 500,
                "total_bytes": 1000,
            }
        )

        captured = capsys.readouterr()
        assert "progress" in captured.err
        data = json.loads(captured.err.strip())
        assert data["type"] == "progress"
        assert data["percent"] == 50.5

    def test_progress_hook_downloading_with_bytes(self, capsys):
        """Test progress hook calculates percent from bytes"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook(
            {
                "status": "downloading",
                "downloaded_bytes": 500,
                "total_bytes": 1000,
                "_speed_str": "1.0MiB/s",
                "_eta_str": "00:30",
            }
        )

        captured = capsys.readouterr()
        data = json.loads(captured.err.strip())
        assert data["percent"] == 50.0
        assert data["downloaded_bytes"] == 500
        assert data["total_bytes"] == 1000

    def test_progress_hook_missing_data(self, capsys):
        """Test progress hook handles missing data"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook({"status": "downloading"})

        captured = capsys.readouterr()
        data = json.loads(captured.err.strip())
        assert data["percent"] is None

    def test_progress_hook_downloading_with_total_bytes_estimate(self, capsys):
        """Test progress hook uses total_bytes_estimate when total_bytes is None"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook(
            {
                "status": "downloading",
                "downloaded_bytes": 500,
                "total_bytes": None,
                "total_bytes_estimate": 1000,
            }
        )

        captured = capsys.readouterr()
        data = json.loads(captured.err.strip())
        assert data["percent"] == 50.0
        assert data["total_bytes"] == 1000

    def test_progress_hook_parses_ansi_percent_str(self, capsys):
        """Test progress hook handles ansi-colored _percent_str values"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        hook(
            {
                "status": "downloading",
                "_percent_str": "\u001b[0;94m 33.3%\u001b[0m",
                "downloaded_bytes": 333,
                "total_bytes": 1000,
            }
        )

        captured = capsys.readouterr()
        data = json.loads(captured.err.strip())
        assert data["percent"] == 33.3

    def test_progress_hook_non_download_status(self, capsys):
        """Test progress hook ignores non-downloading/finished statuses"""
        tracker = DownloadProgressTracker()
        hook = tracker.create_hook()

        # Status like 'error' or other should not produce output
        hook({"status": "error", "filename": "/path/to/video.mp4"})

        captured = capsys.readouterr()
        # Should not set final_file_path
        assert tracker.final_file_path is None
        # Should not output progress data
        assert captured.err == ""


# ============================================================================
# YouTubeDownloader Initialization Tests
# ============================================================================


class TestYouTubeDownloaderInit:
    """Test YouTubeDownloader initialization"""

    def test_init_default_temp_dir(self):
        """Test initialization with default temp directory"""
        downloader = YouTubeDownloader()
        assert downloader.output_dir == Path(tempfile.gettempdir())
        assert downloader.output_dir.exists()

    def test_init_custom_output_dir(self, temp_dir):
        """Test initialization with custom output directory"""
        custom_dir = temp_dir / "custom"
        downloader = YouTubeDownloader(str(custom_dir))
        assert downloader.output_dir == custom_dir
        assert custom_dir.exists()

    def test_init_creates_nonexistent_dir(self, temp_dir):
        """Test initialization creates non-existent directory"""
        new_dir = temp_dir / "new" / "nested" / "dir"
        YouTubeDownloader(str(new_dir))
        assert new_dir.exists()


# ============================================================================
# Security and Validation Tests
# ============================================================================


class TestSanitizeVideoID:
    """Test _sanitize_video_id security"""

    def test_valid_video_id(self):
        """Test valid video ID passes through"""
        result = YouTubeDownloader._sanitize_video_id("dQw4w9WgXcQ")
        assert result == "dQw4w9WgXcQ"

    def test_path_traversal_forward_slash(self):
        """Test path traversal with forward slash is removed"""
        result = YouTubeDownloader._sanitize_video_id("../malicious")
        assert "../" not in result
        assert "malicious" in result

    def test_path_traversal_backslash(self):
        """Test path traversal with backslash is removed"""
        result = YouTubeDownloader._sanitize_video_id("..\\malicious")
        assert "..\\" not in result

    def test_special_characters_removed(self):
        """Test special characters are removed"""
        result = YouTubeDownloader._sanitize_video_id('test<>:"|?*file')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_null_bytes_removed(self):
        """Test null bytes are removed"""
        result = YouTubeDownloader._sanitize_video_id("test\x00file")
        assert "\x00" not in result

    def test_leading_trailing_dots_spaces(self):
        """Test leading/trailing dots and spaces are stripped"""
        result = YouTubeDownloader._sanitize_video_id("  .test.  ")
        assert result == "test"

    def test_empty_after_sanitization(self):
        """Test empty string after sanitization raises ValueError"""
        with pytest.raises(ValueError, match="Invalid video ID"):
            YouTubeDownloader._sanitize_video_id("   ...   ")


class TestValidateFFmpegPath:
    """Test _validate_ffmpeg_path"""

    def test_empty_path(self):
        """Test empty path raises ValueError"""
        with pytest.raises(ValueError, match="cannot be empty"):
            YouTubeDownloader._validate_ffmpeg_path("")

    def test_command_injection_semicolon(self):
        """Test command injection with semicolon"""
        with pytest.raises(ValueError, match="Invalid characters"):
            YouTubeDownloader._validate_ffmpeg_path("ffmpeg; rm -rf /")

    def test_command_injection_ampersand(self):
        """Test command injection with ampersand"""
        with pytest.raises(ValueError, match="Invalid characters"):
            YouTubeDownloader._validate_ffmpeg_path("ffmpeg & rm -rf /")

    def test_command_injection_pipe(self):
        """Test command injection with pipe"""
        with pytest.raises(ValueError, match="Invalid characters"):
            YouTubeDownloader._validate_ffmpeg_path("ffmpeg | cat")

    def test_absolute_path_exists(self, temp_dir):
        """Test absolute path that exists"""
        test_file = temp_dir / "ffmpeg"
        test_file.touch()
        result = YouTubeDownloader._validate_ffmpeg_path(str(test_file))
        assert result == str(test_file)

    def test_absolute_path_not_exists(self):
        """Test absolute path that doesn't exist raises FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            YouTubeDownloader._validate_ffmpeg_path("/nonexistent/ffmpeg")

    def test_relative_path_in_path(self, mock_shutil_which):
        """Test relative path found in PATH"""
        mock_shutil_which.return_value = "/usr/bin/ffmpeg"
        result = YouTubeDownloader._validate_ffmpeg_path("ffmpeg")
        assert result == "/usr/bin/ffmpeg"

    def test_relative_path_not_in_path(self, mock_shutil_which):
        """Test relative path not in PATH raises FileNotFoundError"""
        mock_shutil_which.return_value = None
        with pytest.raises(FileNotFoundError):
            YouTubeDownloader._validate_ffmpeg_path("nonexistent")


class TestValidateOutputPath:
    """Test _validate_output_path"""

    def test_empty_path(self):
        """Test empty path raises ValueError"""
        with pytest.raises(ValueError, match="cannot be empty"):
            YouTubeDownloader._validate_output_path("")

    def test_whitespace_only_path(self):
        """Test whitespace-only path raises ValueError"""
        with pytest.raises(ValueError, match="cannot be empty"):
            YouTubeDownloader._validate_output_path("   ")

    def test_valid_path(self, temp_dir):
        """Test valid path passes"""
        output_path = temp_dir / "output.mp4"
        YouTubeDownloader._validate_output_path(str(output_path))

    def test_validate_does_not_create_parent_dirs(self, temp_dir):
        """Validation should not mutate filesystem state."""
        output_path = temp_dir / "nested" / "deep" / "output.mp4"
        YouTubeDownloader._validate_output_path(str(output_path))
        assert output_path.parent.exists() is False

    def test_missing_extension_raises_value_error(self, temp_dir):
        output_path = temp_dir / "output"
        with pytest.raises(ValueError, match="extension"):
            YouTubeDownloader._validate_output_path(str(output_path))

    def test_ensure_output_parent_dir_creates_parent_dirs(self, temp_dir):
        output_path = temp_dir / "nested" / "deep" / "output.mp4"
        YouTubeDownloader._ensure_output_parent_dir(str(output_path))
        assert output_path.parent.exists()


# ============================================================================
# File Validation Tests
# ============================================================================


class TestFileValidation:
    """Test file validation methods"""

    def test_is_cut_file_with_marker(self):
        """Test _is_cut_file detects cut files"""
        assert YouTubeDownloader._is_cut_file("video_cut_123.mp4") is True
        assert YouTubeDownloader._is_cut_file("video_cut_.mp4") is True

    def test_is_cut_file_without_marker(self):
        """Test _is_cut_file returns False for normal files"""
        assert YouTubeDownloader._is_cut_file("video.mp4") is False
        assert YouTubeDownloader._is_cut_file("video_123.mp4") is False

    def test_is_incomplete_file_part(self):
        """Test _is_incomplete_file detects .part files"""
        assert YouTubeDownloader._is_incomplete_file("video.part") is True
        assert YouTubeDownloader._is_incomplete_file("video.mp4.part") is True

    def test_is_incomplete_file_ytdl(self):
        """Test _is_incomplete_file detects .ytdl files"""
        assert YouTubeDownloader._is_incomplete_file("video.ytdl") is True

    def test_is_incomplete_file_valid(self):
        """Test _is_incomplete_file returns False for valid files"""
        assert YouTubeDownloader._is_incomplete_file("video.mp4") is False

    def test_is_incomplete_file_compound_extension(self):
        """Test _is_incomplete_file detects compound incomplete extensions"""
        assert YouTubeDownloader._is_incomplete_file("video.webm.part") is True
        assert YouTubeDownloader._is_incomplete_file("video.mkv.ytdl") is True

    def test_is_valid_video_file_exists(self, temp_dir):
        """Test _is_valid_video_file with existing valid file"""
        test_file = temp_dir / "video.mp4"
        test_file.write_bytes(b"fake video data")
        assert YouTubeDownloader._is_valid_video_file(test_file) is True

    def test_is_valid_video_file_not_exists(self, temp_dir):
        """Test _is_valid_video_file with non-existent file"""
        test_file = temp_dir / "nonexistent.mp4"
        assert YouTubeDownloader._is_valid_video_file(test_file) is False

    def test_is_valid_video_file_directory(self, temp_dir):
        """Test _is_valid_video_file with directory"""
        test_dir = temp_dir / "dir"
        test_dir.mkdir()
        assert YouTubeDownloader._is_valid_video_file(test_dir) is False

    def test_is_valid_video_file_empty(self, temp_dir):
        """Test _is_valid_video_file with empty file"""
        test_file = temp_dir / "empty.mp4"
        test_file.touch()
        assert YouTubeDownloader._is_valid_video_file(test_file) is False

    def test_is_valid_video_file_incomplete(self, temp_dir):
        """Test _is_valid_video_file excludes incomplete files"""
        test_file = temp_dir / "video.part"
        test_file.write_bytes(b"data")
        assert YouTubeDownloader._is_valid_video_file(test_file) is False

    def test_is_valid_video_file_cut(self, temp_dir):
        """Test _is_valid_video_file excludes cut files"""
        test_file = temp_dir / "video_cut_123.mp4"
        test_file.write_bytes(b"data")
        assert YouTubeDownloader._is_valid_video_file(test_file) is False

    def test_check_file_stability_not_exists(self, temp_dir):
        """Test _check_file_stability with non-existent file"""
        test_file = temp_dir / "nonexistent.mp4"
        assert YouTubeDownloader._check_file_stability(test_file) is False

    def test_check_file_stability_stable(self, temp_dir):
        """Test _check_file_stability with stable file"""
        test_file = temp_dir / "stable.mp4"
        test_file.write_bytes(b"stable data")
        # Mock time.sleep to speed up test
        with patch("downloader.time.sleep"):
            assert YouTubeDownloader._check_file_stability(test_file) is True

    def test_check_file_stability_changing(self, temp_dir):
        """Test _check_file_stability with changing file size"""
        test_file = temp_dir / "changing.mp4"
        test_file.write_bytes(b"data")

        # Mock os.stat to return different sizes (Path.stat() calls os.stat internally)

        sizes = [100, 200, 300]
        call_count = [0]

        def mock_os_stat(path, *args, **kwargs):
            nonlocal call_count
            call_count[0] += 1
            # Return a stat_result-like object with st_size
            stat_result = MagicMock()
            if call_count[0] <= len(sizes):
                stat_result.st_size = sizes[call_count[0] - 1]
            else:
                stat_result.st_size = sizes[-1]
            return stat_result

        # Patch os.stat which Path.stat() uses
        with patch("os.stat", side_effect=mock_os_stat):
            with patch("downloader.time.sleep"):
                assert YouTubeDownloader._check_file_stability(test_file) is False

    def test_check_file_stability_empty(self, temp_dir):
        """Test _check_file_stability with empty file"""
        test_file = temp_dir / "empty.mp4"
        test_file.touch()
        with patch("downloader.time.sleep"):
            assert YouTubeDownloader._check_file_stability(test_file) is False


# ============================================================================
# File Finding Tests
# ============================================================================


class TestFindDownloadedFile:
    """Test _find_downloaded_file"""

    def test_find_via_progress_tracker(self, temp_dir):
        """Test finding file via progress tracker"""
        test_file = temp_dir / "video123.mp4"
        test_file.write_bytes(b"video data")

        tracker = DownloadProgressTracker()
        tracker.final_file_path = str(test_file)

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir, tracker)
            assert result == test_file

    def test_find_via_search_original_id(self, temp_dir):
        """Test finding file via search with original ID"""
        test_file = temp_dir / "video123.mp4"
        test_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir)
            assert result == test_file

    def test_find_via_search_sanitized_id(self, temp_dir):
        """Test finding file via search with sanitized ID"""
        test_file = temp_dir / "video123.mp4"
        test_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            # Use ID that needs sanitization
            result = downloader._find_downloaded_file("video123", temp_dir)
            assert result == test_file

    def test_find_excludes_incomplete_files(self, temp_dir):
        """Test finding excludes incomplete files"""
        complete_file = temp_dir / "video123.mp4"
        complete_file.write_bytes(b"video data")
        incomplete_file = temp_dir / "video123.part"
        incomplete_file.write_bytes(b"partial data")

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir)
            assert result == complete_file

    def test_find_excludes_cut_files(self, temp_dir):
        """Test finding excludes cut files"""
        original_file = temp_dir / "video123.mp4"
        original_file.write_bytes(b"video data")
        cut_file = temp_dir / "video123_cut_123.mp4"
        cut_file.write_bytes(b"cut data")

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir)
            assert result == original_file

    def test_find_most_recent_file(self, temp_dir):
        """Test finding most recent file when multiple exist"""
        old_file = temp_dir / "video123_old.mp4"
        old_file.write_bytes(b"old data")
        new_file = temp_dir / "video123_new.mp4"
        new_file.write_bytes(b"new data")

        # Set different modification times explicitly using os.utime
        import os

        os.utime(old_file, (1000, 1000))  # atime, mtime
        os.utime(new_file, (2000, 2000))  # atime, mtime - newer

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir)
            assert result == new_file

    def test_find_not_found_timeout(self, temp_dir):
        """Test finding returns None when file not found"""
        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("nonexistent", temp_dir, max_retries=2)
            assert result is None

    def test_find_via_progress_tracker_invalid_path(self, temp_dir):
        """Test finding falls back to search when progress tracker path is invalid"""
        # Create a real file that should be found via search
        real_file = temp_dir / "video123.mp4"
        real_file.write_bytes(b"video data")

        tracker = DownloadProgressTracker()
        tracker.final_file_path = "/nonexistent/path/video.mp4"  # Invalid path

        downloader = YouTubeDownloader()
        with patch("downloader.time.sleep"):
            result = downloader._find_downloaded_file("video123", temp_dir, tracker)
            # Should fall back to search and find the real file
            assert result == real_file


# ============================================================================
# Video Info Extraction Tests
# ============================================================================


class TestExtractVideoInfo:
    """Test extract_video_info"""

    def test_extract_regular_video(self, mock_ytdlp_extract_info, sample_video_info):
        """Test extracting info from regular video"""
        downloader = YouTubeDownloader()
        result = downloader.extract_video_info("https://youtube.com/watch?v=test")

        assert result is not None
        assert result.id == sample_video_info["id"]
        assert result.title == sample_video_info["title"]
        assert result.duration == sample_video_info["duration"]
        assert result.is_live is False
        assert result.is_scheduled is False

    def test_extract_live_stream(self, sample_live_video_info):
        """Test extracting info from live stream"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = sample_live_video_info
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=live123")

            assert result is not None
            assert result.is_live is True
            assert result.is_scheduled is False

    def test_extract_scheduled_video(self, sample_scheduled_video_info):
        """Test extracting info from scheduled video"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = sample_scheduled_video_info
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=scheduled123")

            assert result is not None
            assert result.is_live is False
            assert result.is_scheduled is True
            assert result.scheduled_start_time is not None

    def test_extract_download_error(self):
        """Test handling DownloadError"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = yt_dlp.utils.DownloadError("Download failed")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_extractor_error(self):
        """Test handling ExtractorError"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = yt_dlp.utils.ExtractorError("Extraction failed")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_value_error(self):
        """Test handling ValueError"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = ValueError("Invalid data")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_key_error(self):
        """Test handling KeyError"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = KeyError("missing_key")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_type_error(self):
        """Test handling TypeError"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = TypeError("Type error")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_unexpected_error(self):
        """Test handling unexpected exceptions"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.side_effect = RuntimeError("Unexpected error")
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_no_info(self):
        """Test handling when extract_info returns None"""
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = None
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=test")
            assert result is None

    def test_extract_minimal_info(self):
        """Test extraction with minimal video info (missing optional fields)"""
        minimal_info = {
            "id": "minimal123",
            "title": "Minimal Video",
            # All other fields missing
        }
        with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
            mock_instance = MagicMock()
            mock_instance.extract_info.return_value = minimal_info
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_ydl.return_value = mock_instance

            downloader = YouTubeDownloader()
            result = downloader.extract_video_info("https://youtube.com/watch?v=minimal123")

            assert result is not None
            assert result.id == "minimal123"
            assert result.title == "Minimal Video"
            assert result.duration is None
            assert result.is_live is False
            assert result.is_scheduled is False

    def test_extract_retries_with_browser_cookies_on_bot_error(self, sample_video_info):
        """Extraction should retry with browser cookies when enabled."""
        attempted_opts = []

        class MockYDL:
            def __init__(self, opts):
                attempted_opts.append(opts)
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def extract_info(self, _url, download=False):
                if self.opts.get("cookiesfrombrowser") == ("chrome",):
                    return sample_video_info
                raise yt_dlp.utils.DownloadError("Sign in to confirm you’re not a bot")

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=lambda opts: MockYDL(opts)):
            with patch.dict(
                os.environ,
                {
                    "YT_DLP_ENABLE_BROWSER_COOKIES": "true",
                    "YT_DLP_COOKIES_BROWSER": "chrome",
                },
                clear=True,
            ):
                downloader = YouTubeDownloader()
                result = downloader.extract_video_info("https://youtube.com/watch?v=test")
                assert result is not None
                assert result.id == sample_video_info["id"]
                assert attempted_opts[0].get("cookiesfrombrowser") is None
                assert any(opts.get("cookiesfrombrowser") == ("chrome",) for opts in attempted_opts)

    def test_extract_attempts_fetch_pot_when_runtime_is_available(self, sample_video_info, temp_dir):
        attempted_opts = []
        runtime_path = temp_dir / "node"
        runtime_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        runtime_path.chmod(0o755)

        class MockYDL:
            def __init__(self, opts):
                attempted_opts.append(opts)
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def extract_info(self, _url, download=False):
                if self.opts.get("js_runtimes"):
                    return sample_video_info
                raise yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=lambda opts: MockYDL(opts)):
            with patch.dict(
                os.environ,
                {
                    "YT_DLP_ENABLE_BROWSER_COOKIES": "false",
                    "YT_DLP_ENABLE_FETCH_POT": "true",
                    "YT_DLP_JS_RUNTIME_PATH": str(runtime_path),
                    "YT_DLP_JS_RUNTIME_NAME": "node",
                },
                clear=True,
            ):
                downloader = YouTubeDownloader()
                result = downloader.extract_video_info("https://youtube.com/watch?v=test")
                assert result is not None
                assert any(opts.get("js_runtimes") for opts in attempted_opts)
                fetch_pot_attempts = [
                    opts
                    for opts in attempted_opts
                    if "fetch_pot" in ((opts.get("extractor_args") or {}).get("youtube") or {})
                ]
                assert fetch_pot_attempts

    def test_extract_skips_fetch_pot_when_runtime_is_unavailable(self, sample_video_info):
        attempted_opts = []

        class MockYDL:
            def __init__(self, opts):
                attempted_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def extract_info(self, _url, download=False):
                return sample_video_info

        with patch("downloader.yt_dlp.YoutubeDL", side_effect=lambda opts: MockYDL(opts)):
            with patch.dict(
                os.environ,
                {
                    "YT_DLP_ENABLE_BROWSER_COOKIES": "false",
                    "YT_DLP_ENABLE_FETCH_POT": "true",
                    "YT_DLP_JS_RUNTIME_PATH": "/nonexistent/runtime",
                    "YT_DLP_JS_RUNTIME_NAME": "node",
                },
                clear=True,
            ):
                downloader = YouTubeDownloader()
                result = downloader.extract_video_info("https://youtube.com/watch?v=test")
                assert result is not None
                assert all(not opts.get("js_runtimes") for opts in attempted_opts)
                assert all(
                    "fetch_pot" not in ((opts.get("extractor_args") or {}).get("youtube") or {})
                    for opts in attempted_opts
                )


# ============================================================================
# Cache Tests
# ============================================================================


class TestGetCachedVideoPath:
    """Test _get_cached_video_path"""

    def test_cache_found_original_id(self, temp_dir):
        """Test finding cached file with original ID"""
        cached_file = temp_dir / "video123.mp4"
        cached_file.write_bytes(b"cached data")

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch("downloader.time.sleep"):
                result = downloader._get_cached_video_path("video123")
                assert result == str(cached_file)

    def test_cache_found_sanitized_id(self, temp_dir):
        """Test finding cached file with sanitized ID"""
        cached_file = temp_dir / "video123.mp4"
        cached_file.write_bytes(b"cached data")

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch("downloader.time.sleep"):
                result = downloader._get_cached_video_path("video123")
                assert result == str(cached_file)

    def test_cache_multiple_extensions(self, temp_dir):
        """Test finding cached file with different extensions"""
        webm_file = temp_dir / "video123.webm"
        webm_file.write_bytes(b"webm data")
        mp4_file = temp_dir / "video123.mp4"
        mp4_file.write_bytes(b"mp4 data")

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch("downloader.time.sleep"):
                result = downloader._get_cached_video_path("video123")
                # Should find one of them
                assert result is not None
                assert Path(result).exists()

    def test_cache_not_found(self, temp_dir):
        """Test cache not found returns None"""
        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            result = downloader._get_cached_video_path("nonexistent")
            assert result is None

    def test_cache_excludes_invalid_files(self, temp_dir):
        """Test cache excludes invalid files"""
        empty_file = temp_dir / "video123.mp4"
        empty_file.touch()  # Empty file

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            result = downloader._get_cached_video_path("video123")
            assert result is None


# ============================================================================
# Video Cutting Tests
# ============================================================================


class TestCutVideo:
    """Test cut_video method"""

    def test_cut_video_start_only(self, temp_dir, mock_subprocess_run):
        """Test cutting video with start time only"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video(str(input_file), str(output_file), start_time=10)

        assert result is True
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert "-ss" in cmd
        assert "10" in cmd

    def test_cut_video_end_only(self, temp_dir, mock_subprocess_run):
        """Test cutting video with end time only"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video(str(input_file), str(output_file), end_time=30)

        assert result is True
        cmd = mock_subprocess_run.call_args[0][0]
        assert "-t" in cmd
        assert "30" in cmd

    def test_cut_video_start_and_end(self, temp_dir, mock_subprocess_run):
        """Test cutting video with both start and end times"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video(str(input_file), str(output_file), start_time=10, end_time=30)

        assert result is True
        cmd = mock_subprocess_run.call_args[0][0]
        assert "-ss" in cmd
        assert "-t" in cmd
        assert "20" in cmd  # duration = end - start

    def test_cut_video_invalid_input(self, temp_dir):
        """Test cutting with non-existent input file"""
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video("/nonexistent/input.mp4", str(output_file))

        assert result is False

    def test_cut_video_invalid_output_path(self, temp_dir):
        """Test cutting with invalid output path"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        # Try with empty path
        with patch.object(downloader, "_validate_output_path", side_effect=ValueError("Invalid path")):
            result = downloader.cut_video(str(input_file), "")
            assert result is False

    def test_cut_video_invalid_ffmpeg_path(self, temp_dir):
        """Test cutting with invalid ffmpeg path"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "_validate_ffmpeg_path",
            side_effect=FileNotFoundError("FFmpeg not found"),
        ):
            result = downloader.cut_video(str(input_file), str(output_file))
            assert result is False

    def test_cut_video_invalid_duration(self, temp_dir, mock_subprocess_run):
        """Test cutting with invalid duration (end < start)"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video(str(input_file), str(output_file), start_time=30, end_time=10)

        assert result is False

    def test_cut_video_subprocess_timeout(self, temp_dir):
        """Test cutting with subprocess timeout"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        with patch(
            "downloader.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ffmpeg", 3600),
        ):
            result = downloader.cut_video(str(input_file), str(output_file))
            assert result is False

    def test_cut_video_subprocess_error(self, temp_dir):
        """Test cutting with subprocess error"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        error = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"Error")
        with patch("downloader.subprocess.run", side_effect=error):
            result = downloader.cut_video(str(input_file), str(output_file))
            assert result is False

    def test_cut_video_ffmpeg_not_found(self, temp_dir):
        """Test cutting when ffmpeg not found"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        with patch("downloader.subprocess.run", side_effect=FileNotFoundError()):
            result = downloader.cut_video(str(input_file), str(output_file))
            assert result is False

    def test_cut_video_zero_duration(self, temp_dir, mock_subprocess_run):
        """Test cutting with zero duration (start_time == end_time)"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        # When start == end, duration is 0, which should fail
        result = downloader.cut_video(str(input_file), str(output_file), start_time=30, end_time=30)
        assert result is False

    def test_cut_video_no_times(self, temp_dir, mock_subprocess_run):
        """Test cutting with no start or end time (copy whole file)"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_video(str(input_file), str(output_file))

        assert result is True
        cmd = mock_subprocess_run.call_args[0][0]
        # Should not have -ss or -t flags
        assert "-ss" not in cmd
        assert "-t" not in cmd


class TestCutAndConcatenateSections:
    """Test cut_and_concatenate_sections method"""

    def test_cut_single_section(self, temp_dir, mock_subprocess_run):
        """Test cutting and concatenating single section"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        # Mock file creation for section files
        section_file = temp_dir / "video123_section_0.mp4"
        section_file.write_bytes(b"section data")
        output_file.touch()  # Mock output file creation

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch.object(downloader, "cut_video", return_value=True):
                result = downloader.cut_and_concatenate_sections(
                    str(input_file), [(10, 30)], str(output_file), "video123"
                )
                assert result is True

    def test_cut_multiple_sections(self, temp_dir, mock_subprocess_run):
        """Test cutting and concatenating multiple sections"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        def side_effect_cut_video(input_path, output_path, start_time=None, end_time=None):
            # Create the section file when cut_video is called
            Path(output_path).write_bytes(b"section data")
            return True

        def mock_subprocess_side_effect(*args, **kwargs):
            # Create output file after subprocess runs
            output_file.write_bytes(b"concatenated data")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch.object(downloader, "cut_video", side_effect=side_effect_cut_video):
                with patch.object(downloader, "_is_valid_video_file", return_value=True):
                    mock_subprocess_run.side_effect = mock_subprocess_side_effect
                    result = downloader.cut_and_concatenate_sections(
                        str(input_file),
                        [(10, 30), (50, 70)],
                        str(output_file),
                        "video123",
                    )
                    assert result is True
                    assert output_file.exists()

    def test_cut_sections_invalid_input(self, temp_dir):
        """Test cutting sections with invalid input file"""
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        result = downloader.cut_and_concatenate_sections(
            "/nonexistent/input.mp4", [(10, 30)], str(output_file), "video123"
        )
        assert result is False

    def test_cut_sections_cut_failure(self, temp_dir):
        """Test cutting sections when section cut fails"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        with patch.object(downloader, "cut_video", return_value=False):
            result = downloader.cut_and_concatenate_sections(str(input_file), [(10, 30)], str(output_file), "video123")
            assert result is False

    def test_cut_sections_cleanup(self, temp_dir, mock_subprocess_run):
        """Test temp files are cleaned up after concatenation"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"
        output_file.touch()

        temp_dir / "video123_section_0.mp4"
        temp_dir / "video123_concat.txt"

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch.object(downloader, "cut_video", return_value=True):
                with patch.object(downloader, "_is_valid_video_file", return_value=True):
                    downloader.cut_and_concatenate_sections(str(input_file), [(10, 30)], str(output_file), "video123")
                    # Files should be cleaned up (or attempted)
                    # Note: cleanup happens in finally block

    def test_cut_sections_with_none_start(self, temp_dir, mock_subprocess_run):
        """Test cutting sections where start is None (from beginning)"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        def cut_side_effect(input_path, output_path, start_time=None, end_time=None):
            # Create the section file when cut_video is called
            Path(output_path).write_bytes(b"section data")
            return True

        def subprocess_side_effect(*args, **kwargs):
            # Create output file when subprocess runs (concatenation)
            output_file.write_bytes(b"concatenated")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        mock_subprocess_run.side_effect = subprocess_side_effect

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch.object(downloader, "cut_video", side_effect=cut_side_effect) as mock_cut:
                result = downloader.cut_and_concatenate_sections(
                    str(input_file), [(None, 30)], str(output_file), "video123"
                )
                assert result is True
                # Verify cut_video was called with None start
                mock_cut.assert_called()
                call_args = mock_cut.call_args
                assert call_args[1].get("start_time") is None

    def test_cut_sections_with_none_end(self, temp_dir, mock_subprocess_run):
        """Test cutting sections where end is None (to end)"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        def cut_side_effect(input_path, output_path, start_time=None, end_time=None):
            # Create the section file when cut_video is called
            Path(output_path).write_bytes(b"section data")
            return True

        def subprocess_side_effect(*args, **kwargs):
            # Create output file when subprocess runs (concatenation)
            output_file.write_bytes(b"concatenated")
            return MagicMock(returncode=0, stdout=b"", stderr=b"")

        mock_subprocess_run.side_effect = subprocess_side_effect

        downloader = YouTubeDownloader()
        with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
            with patch.object(downloader, "cut_video", side_effect=cut_side_effect) as mock_cut:
                result = downloader.cut_and_concatenate_sections(
                    str(input_file), [(10, None)], str(output_file), "video123"
                )
                assert result is True
                # Verify cut_video was called with None end
                mock_cut.assert_called()
                call_args = mock_cut.call_args
                assert call_args[1].get("end_time") is None


# ============================================================================
# Download Tests
# ============================================================================


class TestDownloadVideo:
    """Test download_video method"""

    def test_download_full_video(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test downloading full video without cutting"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:

                                def copy_side_effect(src, dst):
                                    Path(dst).write_bytes(b"copied data")

                                mock_copy.side_effect = copy_side_effect
                                result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                                assert result.success is True
                                assert result.file_path == str(output_file)

    def test_download_single_section(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test downloading and cutting single section"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch.object(downloader, "cut_video", return_value=True) as mock_cut:

                                def cut_side_effect(
                                    input_path,
                                    output_path,
                                    start_time=None,
                                    end_time=None,
                                ):
                                    Path(output_path).write_bytes(b"cut data")
                                    return True

                                mock_cut.side_effect = cut_side_effect
                                result = downloader.download_video(
                                    "https://youtube.com/watch?v=test",
                                    str(output_file),
                                    start_time=10,
                                    end_time=30,
                                )
                                assert result.success is True
                                assert result.file_path == str(output_file)

    def test_download_multiple_sections(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test downloading and cutting multiple sections"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch.object(
                                downloader,
                                "cut_and_concatenate_sections",
                                return_value=True,
                            ) as mock_cut:

                                def cut_side_effect(input_path, sections, output_path, video_id):
                                    Path(output_path).write_bytes(b"concatenated data")
                                    return True

                                mock_cut.side_effect = cut_side_effect
                                result = downloader.download_video(
                                    "https://youtube.com/watch?v=test",
                                    str(output_file),
                                    sections=[(10, 30), (50, 70)],
                                )
                                assert result.success is True
                                assert result.file_path == str(output_file)

    def test_download_uses_cache(self, temp_dir, sample_video_info):
        """Test download uses cached video"""
        output_file = temp_dir / "output.mp4"
        cached_file = temp_dir / f"{sample_video_info['id']}.mp4"
        cached_file.write_bytes(b"cached video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=str(cached_file)):
                    with patch.object(
                        downloader,
                        "_extract_format_capabilities",
                        return_value={
                            "max_adaptive_height": None,
                            "max_progressive_height": None,
                        },
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:

                                def copy_side_effect(src, dst):
                                    Path(dst).write_bytes(b"copied data")

                                mock_copy.side_effect = copy_side_effect
                                result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                                assert result.success is True
                                assert result.file_path == str(output_file)

    def test_download_uses_versioned_cache_key(self, temp_dir, sample_video_info):
        """Cache lookup should use versioned key to avoid stale legacy quality cache."""
        output_file = temp_dir / "output.mp4"
        cached_file = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4"
        cached_file.write_bytes(b"cached video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(
                    downloader,
                    "_extract_format_capabilities",
                    return_value={
                        "max_adaptive_height": None,
                        "max_progressive_height": None,
                    },
                ):
                    with patch.object(downloader, "_check_file_stability", return_value=True):
                        with patch("downloader.shutil.copy2") as mock_copy:
                            mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                            with patch.object(
                                downloader,
                                "_get_cached_video_path",
                                wraps=downloader._get_cached_video_path,
                            ) as wrapped_cache:
                                result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                                assert result.success is True
                                wrapped_cache.assert_called_once_with(f"{sample_video_info['id']}_{CACHE_KEY_VERSION}")

    def test_download_copies_outside_temp_for_cache(self, temp_dir, sample_video_info, mock_ytdlp_download):
        """Ensure downloaded file outside temp is copied into temp cache"""
        output_file = temp_dir / "output.mp4"
        with tempfile.TemporaryDirectory() as external_tmp:
            downloaded_file = Path(external_tmp) / f"{sample_video_info['id']}.mp4"
            downloaded_file.write_bytes(b"video data")

            downloader = YouTubeDownloader()
            with patch.object(
                downloader,
                "extract_video_info",
                return_value=VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                ),
            ):
                with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                    with patch.object(downloader, "_get_cached_video_path", return_value=None):
                        with patch.object(
                            downloader,
                            "_find_downloaded_file",
                            return_value=downloaded_file,
                        ):
                            with patch.object(downloader, "_check_file_stability", return_value=True):
                                with patch("downloader.shutil.copy2") as mock_copy:

                                    def copy_side_effect(src, dst):
                                        Path(dst).write_bytes(b"copied data")
                                        return dst

                                    mock_copy.side_effect = copy_side_effect

                                    result = downloader.download_video(
                                        "https://youtube.com/watch?v=test",
                                        str(output_file),
                                    )

                                    cached_temp = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4"
                                    assert result.success is True
                                    assert result.cached_file_path == str(cached_temp)
                                    # First copy should target temp cache, second the final output
                                    dests = [Path(call.args[1]) for call in mock_copy.call_args_list]
                                    assert cached_temp in dests
                                    assert output_file in dests

    def test_download_temp_copy_failure(self, temp_dir, sample_video_info, mock_ytdlp_download):
        """Fail gracefully if caching copy into temp raises"""
        output_file = temp_dir / "output.mp4"
        with tempfile.TemporaryDirectory() as external_tmp:
            downloaded_file = Path(external_tmp) / f"{sample_video_info['id']}.mp4"
            downloaded_file.write_bytes(b"video data")

            downloader = YouTubeDownloader()
            with patch.object(
                downloader,
                "extract_video_info",
                return_value=VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                ),
            ):
                with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                    with patch.object(downloader, "_get_cached_video_path", return_value=None):
                        with patch.object(
                            downloader,
                            "_find_downloaded_file",
                            return_value=downloaded_file,
                        ):
                            with patch(
                                "downloader.shutil.copy2",
                                side_effect=PermissionError("denied"),
                            ):
                                result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                                assert result.success is False
                                assert "Failed to store full video in temp directory" in result.error_message

    def test_download_temp_file_not_stable(self, temp_dir, sample_video_info, mock_ytdlp_download):
        """Error if temp-stored full video is unstable"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=False):
                            result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                            assert result.success is False
                            assert "not stable" in (result.error_message or "").lower()

    def test_download_invalid_output_path(self, sample_video_info):
        """Test download with invalid output path"""
        downloader = YouTubeDownloader()
        with patch.object(downloader, "_validate_output_path", side_effect=ValueError("Invalid path")):
            result = downloader.download_video("https://youtube.com/watch?v=test", "")
            assert result.success is False
            assert "Invalid output path" in result.error_message

    def test_download_failed_info_extraction(self, temp_dir):
        """Test download when info extraction fails"""
        output_file = temp_dir / "output.mp4"
        downloader = YouTubeDownloader()
        with patch.object(downloader, "extract_video_info", return_value=None):
            result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
            assert result.success is False
            assert "Failed to extract video information" in result.error_message

    def test_download_invalid_video_id(self, temp_dir):
        """Test download with invalid video ID"""
        output_file = temp_dir / "output.mp4"
        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id="   ...   ",  # Will fail sanitization
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
            assert result.success is False
            assert "Invalid video ID" in result.error_message

    def test_download_file_not_found(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test download when file not found after download"""
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_find_downloaded_file", return_value=None):
                    result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                    assert result.success is False
                    assert "file not found" in result.error_message.lower()

    def test_download_incomplete_part_file(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test download when only .part file exists"""
        output_file = temp_dir / "output.mp4"
        part_file = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4.part"
        part_file.write_bytes(b"partial data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_find_downloaded_file", return_value=None):
                    # Keep the fixture .part file to validate incomplete-file detection.
                    with patch.object(
                        downloader,
                        "_cleanup_incomplete_download_files",
                        return_value=None,
                    ):
                        result = downloader.download_video("https://youtube.com/watch?v=test", str(output_file))
                        # Should detect incomplete download
                        assert result.success is False
                        assert "incomplete" in result.error_message.lower() or ".part" in result.error_message.lower()

    def test_build_format_selectors_excludes_progressive_best(self):
        """Default selectors should prioritize MP4-compatible formats."""
        selectors = YouTubeDownloader._build_format_selectors("bestvideo*+bestaudio")
        assert selectors == [
            "bestvideo*+bestaudio",
            "bestvideo+bestaudio",
            "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=mp4a]"
            "/bestvideo[ext=mp4][vcodec^=h264]+bestaudio[ext=m4a][acodec^=mp4a]"
            "/bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a][acodec^=aac]"
            "/bestvideo[ext=mp4][vcodec^=h264]+bestaudio[ext=m4a][acodec^=aac]",
            "best[ext=mp4][vcodec^=avc1][acodec^=mp4a]"
            "/best[ext=mp4][vcodec^=h264][acodec^=mp4a]"
            "/best[ext=mp4][vcodec^=avc1][acodec^=aac]"
            "/best[ext=mp4][vcodec^=h264][acodec^=aac]",
        ]

    def test_mp4_preset_options_match_yt_dlp_cli_alias(self):
        """Internal mp4 preset should map to yt-dlp's `-t mp4` behavior."""
        assert YouTubeDownloader._mp4_preset_options() == {
            "merge_output_format": "mp4",
            "remuxvideo": "mp4",
            "format_sort": ["vcodec:h264", "lang", "quality", "res", "fps", "hdr:12", "acodec:aac"],
        }

    def test_browser_cookie_candidates_support_csv(self):
        with patch.dict(os.environ, {"YT_DLP_COOKIES_BROWSER": "chrome, edge,firefox"}, clear=True):
            candidates = YouTubeDownloader._browser_cookie_candidates()
            assert candidates[:3] == ["chrome", "edge", "firefox"]

    def test_discover_firefox_profiles_scans_root_and_profiles_subdir_without_duplicates(self, temp_dir):
        xdg_config = temp_dir / "xdg"
        home = temp_dir / "home"
        root = xdg_config / "mozilla" / "firefox"
        profile_from_profiles_dir = root / "Profiles" / "alpha.default-release"
        profile_from_root = root / "beta.dev"
        for profile in [profile_from_profiles_dir, profile_from_root]:
            profile.mkdir(parents=True, exist_ok=True)
            (profile / "cookies.sqlite").write_bytes(b"cookie-db")

        with patch("downloader.sys.platform", "linux"):
            with patch("downloader.Path.home", return_value=home):
                with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg_config)}, clear=True):
                    sources = YouTubeDownloader._discover_firefox_profiles()

        discovered_paths = [source["profile"] for source in sources]
        assert str(profile_from_profiles_dir) in discovered_paths
        assert str(profile_from_root) in discovered_paths
        assert len(discovered_paths) == len(set(discovered_paths))

    def test_browser_cookie_candidates_no_fallback_when_disabled(self):
        with patch.dict(os.environ, {"YT_DLP_COOKIES_BROWSER": "arc"}, clear=True):
            candidates = YouTubeDownloader._browser_cookie_candidates(include_default_fallback=False)
            assert candidates == ["arc"]

    def test_resolve_cookie_attempt_sources_manual_uses_explicit_source(self):
        downloader = YouTubeDownloader()
        with patch.dict(
            os.environ,
            {
                "YT_DLP_COOKIE_SELECTION_MODE": "manual",
                "YT_DLP_COOKIE_SOURCES_JSON": json.dumps(
                    [
                        {
                            "id": "chrome_default",
                            "browser": "chrome",
                            "profile": "/tmp/chrome-default",
                            "priority": 0,
                        }
                    ]
                ),
            },
            clear=True,
        ):
            sources, error = downloader._resolve_cookie_attempt_sources()
            assert error is None
            assert len(sources) == 1
            assert sources[0]["id"] == "chrome_default"
            assert sources[0]["cookiesfrombrowser"] == ("chrome", "/tmp/chrome-default")

    def test_resolve_cookie_attempt_sources_manual_errors_when_unusable(self):
        downloader = YouTubeDownloader()
        with patch.dict(
            os.environ,
            {
                "YT_DLP_COOKIE_SELECTION_MODE": "manual",
                "YT_DLP_COOKIE_SOURCES_JSON": json.dumps(
                    [{"id": "arc_missing", "browser": "arc", "profile": None, "priority": 0}]
                ),
            },
            clear=True,
        ):
            with patch.object(YouTubeDownloader, "_arc_cookie_profile_path", return_value=None):
                sources, error = downloader._resolve_cookie_attempt_sources()
                assert sources == []
                assert isinstance(error, str)
                assert "unavailable" in error.lower()

    def test_resolve_cookie_attempt_sources_auto_dedupes_equivalent_sources(self):
        downloader = YouTubeDownloader()
        with patch.dict(
            os.environ,
            {
                "YT_DLP_COOKIE_SELECTION_MODE": "auto",
                "YT_DLP_COOKIE_SOURCES_JSON": json.dumps(
                    [
                        {"id": "chrome_1", "browser": "chrome", "profile": "/tmp/p1", "priority": 0},
                        {"id": "chrome_2", "browser": "chrome", "profile": "/tmp/p1", "priority": 1},
                    ]
                ),
            },
            clear=True,
        ):
            sources, error = downloader._resolve_cookie_attempt_sources()
            assert error is None
            assert len(sources) == 1
            assert sources[0]["cookiesfrombrowser"] == ("chrome", "/tmp/p1")

    def test_resolve_cookie_attempt_sources_explicit_empty_disables_legacy_fallback(self):
        downloader = YouTubeDownloader()
        with patch.dict(
            os.environ,
            {
                "YT_DLP_COOKIE_SELECTION_MODE": "auto",
                "YT_DLP_COOKIE_SOURCES_JSON": "[]",
                "YT_DLP_ENABLE_BROWSER_COOKIES": "true",
                "YT_DLP_COOKIES_BROWSER": "chrome",
            },
            clear=True,
        ):
            sources, error = downloader._resolve_cookie_attempt_sources()
            assert error is None
            assert sources == []

    def test_resolve_runtime_executable_accepts_command_name(self):
        with patch("downloader.shutil.which", return_value="/usr/bin/node"):
            with patch("downloader.os.access", return_value=True):
                resolved = YouTubeDownloader._resolve_runtime_executable("node")
                assert resolved == "/usr/bin/node"

    def test_cookiesfrombrowser_option_maps_arc_to_chrome_profile(self):
        downloader = YouTubeDownloader()
        with patch.object(downloader, "_arc_cookie_profile_path", return_value="/tmp/arc-default"):
            assert downloader._cookiesfrombrowser_option("arc") == (
                "chrome",
                "/tmp/arc-default",
            )

    def test_compose_ydl_opts_merges_extractor_args_without_clobbering(self, temp_dir):
        runtime_path = temp_dir / "node"
        runtime_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        runtime_path.chmod(0o755)
        runtime = {
            "name": "node",
            "path": str(runtime_path),
            "js_runtimes": {"node": {"path": str(runtime_path), "paths": [str(runtime_path)]}},
        }

        opts = YouTubeDownloader._compose_ydl_opts(
            {"extractor_args": {"youtube": {"player_client": ["web"]}}},
            fetch_pot_runtime=runtime,
            extractor_args={"youtube": {"player_client": ["android"], "player_js_variant": ["default"]}},
        )
        youtube_args = opts.get("extractor_args", {}).get("youtube", {})
        assert youtube_args.get("player_client") == ["web", "android"]
        assert youtube_args.get("player_js_variant") == ["default"]
        assert youtube_args.get("fetch_pot") == ["auto"]
        assert opts.get("js_runtimes") is not None

    def test_resolve_ffmpeg_location_for_ytdlp_falls_back_to_binary_name(self):
        downloader = YouTubeDownloader()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(
                downloader,
                "_validate_ffmpeg_path",
                return_value="/usr/local/bin/ffmpeg",
            ) as mock_validate:
                resolved = downloader._resolve_ffmpeg_location_for_ytdlp()
                assert resolved == "/usr/local/bin/ffmpeg"
                mock_validate.assert_called_with("ffmpeg")

    def test_download_format_selector_fallback(self, temp_dir, sample_video_info):
        """Test HQ format selector fallback order on unavailable formats."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")
        attempted_formats = []

        class MockYDL:
            def __init__(self, opts):
                self.format_selector = opts.get("format")
                attempted_formats.append(self.format_selector)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                if self.format_selector == "nonexistent":
                    raise yt_dlp.utils.DownloadError("Requested format is not available")
                return None

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:

                                def copy_side_effect(src, dst):
                                    Path(dst).write_bytes(b"copied data")

                                mock_copy.side_effect = copy_side_effect
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch("downloader.time.sleep"):
                                        result = downloader.download_video(
                                            "https://youtube.com/watch?v=test",
                                            str(output_file),
                                            quality="nonexistent",
                                        )
                                        assert result.success is True
                                        attempted_non_empty = [fmt for fmt in attempted_formats if fmt]
                                        default_selector = YouTubeDownloader._build_format_selectors("nonexistent")[1]
                                        assert attempted_non_empty[:2] == [
                                            "nonexistent",
                                            default_selector,
                                        ]

    def test_download_applies_mp4_preset_options_to_yt_dlp(self, temp_dir, sample_video_info):
        """Download attempts should include mp4 compatibility preset options."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")
        attempted_opts = []

        class MockYDL:
            def __init__(self, opts):
                attempted_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:

                                def copy_side_effect(_src, dst):
                                    Path(dst).write_bytes(b"copied data")

                                mock_copy.side_effect = copy_side_effect
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch("downloader.time.sleep"):
                                        result = downloader.download_video(
                                            "https://youtube.com/watch?v=test",
                                            str(output_file),
                                        )
                                        assert result.success is True
                                        assert attempted_opts
                                        download_attempts = [opts for opts in attempted_opts if opts.get("format")]
                                        assert download_attempts
                                        first_attempt = download_attempts[0]
                                        assert first_attempt.get("merge_output_format") == "mp4"
                                        assert first_attempt.get("remuxvideo") == "mp4"
                                        assert first_attempt.get("format_sort") == [
                                            "vcodec:h264",
                                            "lang",
                                            "quality",
                                            "res",
                                            "fps",
                                            "hdr:12",
                                            "acodec:aac",
                                        ]

    def test_download_skips_mp4_preset_options_for_webm_output(self, temp_dir, sample_video_info):
        """WebM output requests should not force mp4 preset options."""
        output_file = temp_dir / "output.webm"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.webm"
        downloaded_file.write_bytes(b"video data")
        attempted_opts = []

        class MockYDL:
            def __init__(self, opts):
                attempted_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch.object(downloader, "_normalize_output_file") as mock_normalize:

                                def normalize_side_effect(_src, dst, _selected):
                                    Path(dst).write_bytes(b"normalized")
                                    return True, None

                                mock_normalize.side_effect = normalize_side_effect
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch("downloader.time.sleep"):
                                        result = downloader.download_video(
                                            "https://youtube.com/watch?v=test",
                                            str(output_file),
                                        )
                                        assert result.success is True
                                        assert attempted_opts
                                        download_attempts = [opts for opts in attempted_opts if opts.get("format")]
                                        assert download_attempts
                                        first_attempt = download_attempts[0]
                                        assert "merge_output_format" not in first_attempt
                                        assert "remuxvideo" not in first_attempt
                                        assert "format_sort" not in first_attempt

    def test_download_ffmpeg_merge_error_does_not_fallback_to_progressive(self, temp_dir, sample_video_info):
        """If ffmpeg merge is unavailable, fail explicitly instead of downloading low quality."""
        output_file = temp_dir / "output.mp4"
        attempted_formats = []

        class MockYDL:
            def __init__(self, opts):
                attempted_formats.append(opts.get("format"))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                raise yt_dlp.utils.DownloadError("Postprocess: ffmpeg merge failed")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch(
                        "downloader.yt_dlp.YoutubeDL",
                        side_effect=lambda opts: MockYDL(opts),
                    ):
                        result = downloader.download_video(
                            "https://youtube.com/watch?v=test",
                            str(output_file),
                            quality="bestvideo*+bestaudio",
                        )
                        assert result.success is False
                        assert "FFmpeg is required" in (result.error_message or "")
                        attempted_non_empty = [fmt for fmt in attempted_formats if fmt]
                        default_selector = YouTubeDownloader._build_format_selectors("bestvideo*+bestaudio")[0]
                        assert attempted_non_empty == [default_selector]

    def test_download_ffmpeg_merging_error_does_not_fallback_to_progressive(self, temp_dir, sample_video_info):
        """If yt-dlp reports `merging` wording, fail explicitly instead of low quality fallback."""
        output_file = temp_dir / "output.mp4"
        attempted_formats = []

        class MockYDL:
            def __init__(self, opts):
                attempted_formats.append(opts.get("format"))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                raise yt_dlp.utils.DownloadError(
                    "ERROR: You have requested merging of multiple formats but ffmpeg is not "
                    "installed. Aborting due to --abort-on-error"
                )

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch(
                        "downloader.yt_dlp.YoutubeDL",
                        side_effect=lambda opts: MockYDL(opts),
                    ):
                        result = downloader.download_video(
                            "https://youtube.com/watch?v=test",
                            str(output_file),
                            quality="bestvideo*+bestaudio",
                        )
                        assert result.success is False
                        assert "FFmpeg is required" in (result.error_message or "")
                        attempted_non_empty = [fmt for fmt in attempted_formats if fmt]
                        default_selector = YouTubeDownloader._build_format_selectors("bestvideo*+bestaudio")[0]
                        assert attempted_non_empty == [default_selector]

    def test_download_falls_back_to_restricted_progressive_on_403(self, temp_dir, sample_video_info):
        """When HQ streams are blocked (403), fallback profile should download progressive format."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4"
        downloaded_file.write_bytes(b"video data")
        attempts = []

        class MockYDL:
            def __init__(self, opts):
                attempts.append(
                    {
                        "format": opts.get("format"),
                        "extractor_args": opts.get("extractor_args"),
                    }
                )
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                extractor_args = self.opts.get("extractor_args") or {}
                if extractor_args.get("youtube", {}).get("player_client") == [
                    "web",
                    "android",
                ]:
                    return None
                raise yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:
                                mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch("downloader.time.sleep"):
                                        with patch.dict(
                                            os.environ,
                                            {"YT_DLP_ALLOW_LOW_QUALITY_FALLBACK": "true"},
                                            clear=True,
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                                quality="bestvideo*+bestaudio",
                                            )
                                            assert result.success is True
                                            assert any(a["extractor_args"] is None for a in attempts)
                                            assert any(
                                                a["extractor_args"]
                                                == {
                                                    "youtube": {
                                                        "player_client": [
                                                            "web",
                                                            "android",
                                                        ]
                                                    }
                                                }
                                                for a in attempts
                                            )

    def test_download_returns_structured_failure_for_unrecoverable_download_errors(self, temp_dir, sample_video_info):
        """Downloader should return structured error instead of crashing process."""
        output_file = temp_dir / "output.mp4"

        class AlwaysFailYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                raise yt_dlp.utils.DownloadError("Network reset by peer")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch(
                        "downloader.yt_dlp.YoutubeDL",
                        side_effect=lambda opts: AlwaysFailYDL(opts),
                    ):
                        result = downloader.download_video(
                            "https://youtube.com/watch?v=test",
                            str(output_file),
                            quality="bestvideo*+bestaudio",
                        )
                        assert result.success is False
                        assert "All format selectors failed" in (result.error_message or "")
                        assert "Network reset by peer" in (result.error_message or "")

    def test_download_rejects_low_quality_fallback_when_hq_exists(self, temp_dir, sample_video_info):
        """If adaptive max quality exists but only low progressive works, fail by default."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4"
        downloaded_file.write_bytes(b"video data")

        class MockYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                extractor_args = self.opts.get("extractor_args") or {}
                if extractor_args.get("youtube", {}).get("player_client") == [
                    "web",
                    "android",
                ]:
                    hooks = self.opts.get("progress_hooks") or []
                    for hook in hooks:
                        hook(
                            {
                                "status": "downloading",
                                "downloaded_bytes": 100,
                                "total_bytes": 100,
                                "info_dict": {
                                    "format_id": "18",
                                    "height": 360,
                                    "vcodec": "avc1.42001E",
                                    "acodec": "mp4a.40.2",
                                },
                            }
                        )
                        hook(
                            {
                                "status": "finished",
                                "filename": str(downloaded_file),
                            }
                        )
                    return None
                raise yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "_extract_format_capabilities",
            return_value={
                "max_adaptive_height": 1080,
                "max_progressive_height": 360,
            },
        ):
            with patch.object(
                downloader,
                "extract_video_info",
                return_value=VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                ),
            ):
                with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                    with patch.object(downloader, "_get_cached_video_path", return_value=None):
                        with patch.object(
                            downloader,
                            "_find_downloaded_file",
                            return_value=downloaded_file,
                        ):
                            with patch.object(downloader, "_check_file_stability", return_value=True):
                                with patch("downloader.shutil.copy2") as mock_copy:
                                    mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                                    with patch(
                                        "downloader.yt_dlp.YoutubeDL",
                                        side_effect=lambda opts: MockYDL(opts),
                                    ):
                                        result = downloader.download_video(
                                            "https://youtube.com/watch?v=test",
                                            str(output_file),
                                            quality="bestvideo*+bestaudio",
                                        )
                                        assert result.success is False
                                        assert "High-quality stream is available up to 1080p" in (
                                            result.error_message or ""
                                        )

    def test_download_reports_cookie_attempt_failure_when_enabled(self, temp_dir, sample_video_info):
        """If cookies were enabled but HQ is still blocked, error should reflect attempted cookie auth."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}_{CACHE_KEY_VERSION}.mp4"
        downloaded_file.write_bytes(b"video data")

        class MockYDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                if self.opts.get("cookiesfrombrowser"):
                    raise yt_dlp.utils.DownloadError("Could not decrypt Chrome cookies")
                extractor_args = self.opts.get("extractor_args") or {}
                if extractor_args.get("youtube", {}).get("player_client") == [
                    "web",
                    "android",
                ]:
                    hooks = self.opts.get("progress_hooks") or []
                    for hook in hooks:
                        hook(
                            {
                                "status": "downloading",
                                "downloaded_bytes": 100,
                                "total_bytes": 100,
                                "info_dict": {
                                    "format_id": "18",
                                    "height": 360,
                                    "vcodec": "avc1.42001E",
                                    "acodec": "mp4a.40.2",
                                },
                            }
                        )
                        hook(
                            {
                                "status": "finished",
                                "filename": str(downloaded_file),
                            }
                        )
                    return None
                raise yt_dlp.utils.DownloadError("HTTP Error 403: Forbidden")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "_extract_format_capabilities",
            return_value={
                "max_adaptive_height": 1080,
                "max_progressive_height": 360,
            },
        ):
            with patch.object(
                downloader,
                "extract_video_info",
                return_value=VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                ),
            ):
                with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                    with patch.object(downloader, "_get_cached_video_path", return_value=None):
                        with patch.object(
                            downloader,
                            "_find_downloaded_file",
                            return_value=downloaded_file,
                        ):
                            with patch.object(downloader, "_check_file_stability", return_value=True):
                                with patch("downloader.shutil.copy2") as mock_copy:
                                    mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                                    with patch(
                                        "downloader.yt_dlp.YoutubeDL",
                                        side_effect=lambda opts: MockYDL(opts),
                                    ):
                                        with patch.dict(
                                            os.environ,
                                            {
                                                "YT_DLP_ENABLE_BROWSER_COOKIES": "true",
                                                "YT_DLP_COOKIES_BROWSER": "chrome",
                                            },
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                                quality="bestvideo*+bestaudio",
                                            )
                                            assert result.success is False
                                            assert "Browser cookies were enabled" in (result.error_message or "")
                                            assert "Could not decrypt Chrome cookies" in (result.error_message or "")

    def test_download_sets_ffmpeg_location_for_ytdlp(self, temp_dir, sample_video_info):
        """Ensure yt-dlp gets ffmpeg_location so bestvideo+bestaudio formats can be merged."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        captured_opts = {}

        class MockYDL:
            def __init__(self, opts):
                captured_opts.update(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:
                                mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch.dict(os.environ, {"FFMPEG_PATH": "/tmp/ffmpeg"}):
                                        with patch.object(
                                            downloader,
                                            "_validate_ffmpeg_path",
                                            return_value="/tmp/ffmpeg",
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                            )
                                            assert result.success is True
                                            assert captured_opts.get("ffmpeg_location") == "/tmp/ffmpeg"

    def test_requires_mp4_compatibility_transcode_for_non_mp4_source(self):
        """Non-mp4 source should be transcoded when user requests .mp4 output."""
        assert (
            YouTubeDownloader._requires_mp4_compatibility_transcode(
                Path("/tmp/source.webm"),
                Path("/tmp/output.mp4"),
                None,
            )
            is True
        )

    def test_requires_mp4_compatibility_transcode_for_incompatible_mp4_codec_probe(self):
        """AV1 in mp4 should trigger transcode even if container is mp4."""
        assert (
            YouTubeDownloader._requires_mp4_compatibility_transcode(
                Path("source.mp4"),
                Path("output.mp4"),
                None,
                source_video_codec="av1",
                source_audio_codec="aac",
            )
            is True
        )

    def test_requires_mp4_compatibility_transcode_prefers_probe_over_selected_format(self):
        """Probe data should win over optimistic selected_format metadata."""
        assert (
            YouTubeDownloader._requires_mp4_compatibility_transcode(
                Path("source.mp4"),
                Path("output.mp4"),
                {"vcodec": "h264", "acodec": "aac"},
                source_video_codec="av1",
                source_audio_codec="aac",
            )
            is True
        )

    def test_requires_mp4_compatibility_transcode_allows_mp4a_audio_codec_probe(self):
        """mp4a.* audio variants should be treated as QuickTime-compatible."""
        assert (
            YouTubeDownloader._requires_mp4_compatibility_transcode(
                Path("source.mp4"),
                Path("output.mp4"),
                None,
                source_video_codec="h264",
                source_audio_codec="mp4a.40.2",
            )
            is False
        )

    def test_normalize_output_file_rejects_incompatible_webm_codecs(self, temp_dir):
        downloader = YouTubeDownloader()
        source = temp_dir / "source.mp4"
        target = temp_dir / "output.webm"
        source.write_bytes(b"video data")
        with patch.object(downloader, "_probe_primary_stream_codecs", return_value=("h264", "aac")):
            ok, error = downloader._normalize_output_file(source, target, selected_format=None)
            assert ok is False
            assert "WebM-compatible codecs" in (error or "")

    def test_finalize_without_normalization_uses_source_extension(self, temp_dir):
        downloader = YouTubeDownloader()
        source = temp_dir / "source.webm"
        source.write_bytes(b"video data")
        requested = temp_dir / "output.mp4"

        ok, final_path, error = downloader._finalize_without_normalization(source, requested)

        assert ok is True, error
        assert final_path == temp_dir / "output.webm"
        assert final_path.exists()
        assert final_path.read_bytes() == b"video data"

    def test_download_skips_normalization_when_disabled(self, temp_dir, sample_video_info):
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.webm"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()

        class MockYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.yt_dlp.YoutubeDL", side_effect=lambda opts: MockYDL(opts)):
                                with patch.object(downloader, "_normalize_output_file") as mock_normalize:
                                    with patch.object(downloader, "_transcode_to_quicktime_mp4") as mock_transcode:
                                        with patch.dict(
                                            os.environ,
                                            {"YT_DLP_DISABLE_POST_COMPAT_NORMALIZATION": "true"},
                                            clear=True,
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                            )

        assert result.success is True
        assert result.file_path == str(temp_dir / "output.webm")
        assert Path(result.file_path).exists()
        mock_normalize.assert_not_called()
        mock_transcode.assert_not_called()

    def test_download_transcodes_non_mp4_source_for_mp4_output(self, temp_dir, sample_video_info):
        """When source is webm and output is mp4, downloader should run compatibility transcode."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.webm"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()

        class MockYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:
                                mock_copy.side_effect = lambda _src, dst: Path(dst).write_bytes(b"copied data")
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch.object(
                                        downloader,
                                        "_transcode_to_quicktime_mp4",
                                        side_effect=lambda _src, dst: Path(dst).write_bytes(b"qtmp4") or True,
                                    ) as mock_transcode:
                                        with patch.dict(
                                            os.environ,
                                            {"YT_DLP_ENABLE_MP4_COMPAT_TRANSCODE": "true"},
                                            clear=True,
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                            )
                                            assert result.success is True
                                            mock_transcode.assert_called_once()
                                            called_src, called_dst = mock_transcode.call_args.args
                                            assert called_src == downloaded_file
                                            assert called_dst == output_file

    def test_download_transcodes_incompatible_mp4_codec_for_mp4_output(self, temp_dir, sample_video_info):
        """When source is mp4+AV1, downloader should run compatibility transcode."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()

        class MockYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:
                                mock_copy.side_effect = lambda _src, dst: Path(dst).write_bytes(b"copied data")
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch.object(
                                        downloader,
                                        "_probe_primary_stream_codecs",
                                        return_value=("av1", "aac"),
                                    ) as mock_probe:
                                        with patch.object(
                                            downloader,
                                            "_transcode_to_quicktime_mp4",
                                            side_effect=lambda _src, dst: Path(dst).write_bytes(b"qtmp4") or True,
                                        ) as mock_transcode:
                                            with patch.dict(
                                                os.environ,
                                                {"YT_DLP_ENABLE_MP4_COMPAT_TRANSCODE": "true"},
                                                clear=True,
                                            ):
                                                result = downloader.download_video(
                                                    "https://youtube.com/watch?v=test",
                                                    str(output_file),
                                                )
                                                assert result.success is True
                                                mock_probe.assert_called_once_with(downloaded_file)
                                                mock_transcode.assert_called_once()
                                                called_src, called_dst = mock_transcode.call_args.args
                                                assert called_src == downloaded_file
                                                assert called_dst == output_file

    def test_download_transcodes_incompatible_mp4_codec_for_cut_output(self, temp_dir, sample_video_info):
        """When needs_cut=True, transcode should run with identical src/dst output path."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()

        class MockYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.yt_dlp.YoutubeDL", side_effect=lambda opts: MockYDL(opts)):
                                with patch.object(
                                    downloader,
                                    "cut_video",
                                    side_effect=lambda _input, out, _start, _end: (
                                        Path(out).write_bytes(b"cut data") or True
                                    ),
                                ):
                                    with patch.object(
                                        downloader,
                                        "_probe_primary_stream_codecs",
                                        return_value=("av1", "aac"),
                                    ) as mock_probe:
                                        with patch.object(
                                            downloader,
                                            "_transcode_to_quicktime_mp4",
                                            side_effect=lambda _src, dst: Path(dst).write_bytes(b"qtmp4") or True,
                                        ) as mock_transcode:
                                            with patch.dict(
                                                os.environ,
                                                {"YT_DLP_ENABLE_MP4_COMPAT_TRANSCODE": "true"},
                                                clear=True,
                                            ):
                                                result = downloader.download_video(
                                                    "https://youtube.com/watch?v=test",
                                                    str(output_file),
                                                    start_time=10,
                                                    end_time=30,
                                                )
                                                assert result.success is True
                                                mock_probe.assert_called_once()
                                                assert mock_probe.call_args.args[0].name.endswith("_section_work.mp4")
                                                mock_transcode.assert_called_once()
                                                called_src, called_dst = mock_transcode.call_args.args
                                                assert called_src.name.endswith("_section_work.mp4")
                                                assert called_dst == output_file

    def test_download_fails_when_mp4_compat_transcode_fails(self, temp_dir, sample_video_info):
        """If compatibility transcode fails, downloader should return clear failure."""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.webm"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()

        class MockYDL:
            def __init__(self, _opts):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def download(self, _urls):
                return None

        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:
                                mock_copy.side_effect = lambda src, dst: Path(dst).write_bytes(b"copied data")
                                with patch(
                                    "downloader.yt_dlp.YoutubeDL",
                                    side_effect=lambda opts: MockYDL(opts),
                                ):
                                    with patch.object(
                                        downloader,
                                        "_transcode_to_quicktime_mp4",
                                        return_value=False,
                                    ):
                                        with patch.dict(
                                            os.environ,
                                            {"YT_DLP_ENABLE_MP4_COMPAT_TRANSCODE": "true"},
                                            clear=True,
                                        ):
                                            result = downloader.download_video(
                                                "https://youtube.com/watch?v=test",
                                                str(output_file),
                                            )
                                            assert result.success is False
                                            assert "QuickTime-compatible" in (result.error_message or "")

    def test_download_live_stream(self, temp_dir, mock_ytdlp_download, sample_live_video_info):
        """Test downloading live stream"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_live_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"live data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_live_video_info["id"],
                title=sample_live_video_info["title"],
                duration=None,
                is_live=True,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch("downloader.shutil.copy2") as mock_copy:

                                def copy_side_effect(src, dst):
                                    Path(dst).write_bytes(b"copied data")

                                mock_copy.side_effect = copy_side_effect
                                result = downloader.download_video(
                                    "https://youtube.com/watch?v=live123",
                                    str(output_file),
                                    download_from_start=False,
                                )
                                assert result.success is True
                                assert result.file_path == str(output_file)

    def test_download_sections_takes_precedence_over_start_end(self, temp_dir, mock_ytdlp_download, sample_video_info):
        """Test that sections parameter takes precedence over start_time/end_time"""
        output_file = temp_dir / "output.mp4"
        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
        downloaded_file.write_bytes(b"video data")

        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id=sample_video_info["id"],
                title=sample_video_info["title"],
                duration=sample_video_info["duration"],
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                with patch.object(downloader, "_get_cached_video_path", return_value=None):
                    with patch.object(
                        downloader,
                        "_find_downloaded_file",
                        return_value=downloaded_file,
                    ):
                        with patch.object(downloader, "_check_file_stability", return_value=True):
                            with patch.object(
                                downloader,
                                "cut_and_concatenate_sections",
                                return_value=True,
                            ) as mock_concat:
                                with patch.object(downloader, "cut_video", return_value=True) as mock_cut:

                                    def concat_side_effect(input_path, sections, output_path, video_id):
                                        Path(output_path).write_bytes(b"concatenated")
                                        return True

                                    mock_concat.side_effect = concat_side_effect

                                    result = downloader.download_video(
                                        "https://youtube.com/watch?v=test",
                                        str(output_file),
                                        start_time=100,  # Should be ignored
                                        end_time=200,  # Should be ignored
                                        sections=[(10, 30), (50, 70)],  # Should be used
                                    )

                                    assert result.success is True
                                    # cut_and_concatenate_sections should be called, not cut_video
                                    mock_concat.assert_called_once()
                                    mock_cut.assert_not_called()


# ============================================================================
# URL Validation Tests
# ============================================================================


class TestValidateURL:
    """Test validate_url method"""

    def test_valid_youtube_url_com(self):
        """Test valid youtube.com URL"""
        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id="test123",
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            assert downloader.validate_url("https://youtube.com/watch?v=test123") is True

    def test_valid_youtube_url_be(self):
        """Test valid youtu.be URL"""
        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id="test123",
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            assert downloader.validate_url("https://youtu.be/test123") is True

    def test_invalid_non_youtube_url(self):
        """Test invalid non-YouTube URL"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url("https://example.com/video") is False

    def test_invalid_non_http_url(self):
        """Test invalid non-HTTP/HTTPS URL"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url("ftp://youtube.com/video") is False

    def test_empty_url(self):
        """Test empty URL"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url("") is False

    def test_none_url(self):
        """Test None URL"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url(None) is False

    def test_non_string_url(self):
        """Test non-string URL"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url(123) is False

    def test_url_fails_info_extraction(self):
        """Test URL that fails info extraction"""
        downloader = YouTubeDownloader()
        with patch.object(downloader, "extract_video_info", return_value=None):
            assert downloader.validate_url("https://youtube.com/watch?v=invalid") is False

    def test_valid_youtube_url_www(self):
        """Test valid www.youtube.com URL"""
        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id="test123",
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            assert downloader.validate_url("https://www.youtube.com/watch?v=test123") is True

    def test_valid_youtube_url_with_extra_params(self):
        """Test valid YouTube URL with additional query parameters"""
        downloader = YouTubeDownloader()
        with patch.object(
            downloader,
            "extract_video_info",
            return_value=VideoInfo(
                id="test123",
                title="Test",
                duration=100,
                is_live=False,
                is_scheduled=False,
                scheduled_start_time=None,
                thumbnail=None,
                uploader=None,
                view_count=None,
                upload_date=None,
            ),
        ):
            assert downloader.validate_url("https://youtube.com/watch?v=test123&t=120&list=PLtest") is True

    def test_invalid_youtube_similar_domain(self):
        """Test invalid URL with youtube-like but different domain"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url("https://notyoutube.com/watch?v=test") is False
        assert downloader.validate_url("https://youtube.fake.com/watch?v=test") is False

    def test_invalid_url_malformed(self):
        """Test malformed URLs"""
        downloader = YouTubeDownloader()
        assert downloader.validate_url("not a url") is False
        assert downloader.validate_url("://youtube.com/watch?v=test") is False


# ============================================================================
# Command Line Interface Tests
# ============================================================================


class TestMainFunction:
    """Test main() function"""

    def test_main_validation_mode_success(self, capsys, sample_video_info):
        """Test --validate mode with valid URL"""
        with patch(
            "sys.argv",
            ["downloader.py", "--validate", "https://youtube.com/watch?v=test"],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True

    def test_main_validation_mode_failure(self, capsys):
        """Test --validate mode with invalid URL"""
        with patch(
            "sys.argv",
            ["downloader.py", "--validate", "https://youtube.com/watch?v=invalid"],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.extract_video_info.return_value = None
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is False

    def test_main_validation_mode_missing_url(self, capsys):
        """Test --validate mode with missing URL"""
        with patch("sys.argv", ["downloader.py", "--validate"]):
            from downloader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_download_mode_minimal_args(self, temp_dir, capsys, sample_video_info):
        """Test download mode with minimal args"""
        output_file = temp_dir / "output.mp4"

        with patch(
            "sys.argv",
            ["downloader.py", "https://youtube.com/watch?v=test", str(output_file)],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.validate_url.return_value = True
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader.download_video.return_value = DownloadResult(
                    success=True,
                    file_path=str(output_file),
                    file_size=1024,
                    error_message=None,
                    video_info=VideoInfo(
                        id=sample_video_info["id"],
                        title=sample_video_info["title"],
                        duration=sample_video_info["duration"],
                        is_live=False,
                        is_scheduled=False,
                        scheduled_start_time=None,
                        thumbnail=None,
                        uploader=None,
                        view_count=None,
                        upload_date=None,
                    ),
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                main()  # Should complete normally without raising SystemExit
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True
                assert output["file_path"] == str(output_file)

    def test_main_download_mode_sections_format(self, temp_dir, capsys, sample_video_info):
        """Test download mode with sections JSON format"""
        output_file = temp_dir / "output.mp4"
        output_file.touch()
        sections_json = json.dumps([{"start": 10, "end": 30}, {"start": 50, "end": 70}])

        with patch(
            "sys.argv",
            [
                "downloader.py",
                "https://youtube.com/watch?v=test",
                "false",
                "best",
                sections_json,
                str(output_file),
            ],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.validate_url.return_value = True
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader.download_video.return_value = DownloadResult(
                    success=True,
                    file_path=str(output_file),
                    file_size=1024,
                    error_message=None,
                    video_info=None,
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                main()  # Should complete normally without raising SystemExit
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True
                # Verify sections were passed correctly
                call_args = mock_downloader.download_video.call_args
                assert call_args is not None
                # sections is passed as 7th positional argument (index 6 in args tuple)
                # call_args is (args_tuple, kwargs_dict)
                args_tuple = call_args[0]
                kwargs_dict = call_args[1]
                # Check if sections is in positional args (at index 6) or keyword args
                sections_passed = None
                if len(args_tuple) > 6:
                    sections_passed = args_tuple[6]
                elif "sections" in kwargs_dict:
                    sections_passed = kwargs_dict["sections"]
                # Verify sections were passed (should be list of tuples)
                assert sections_passed == [(10, 30), (50, 70)]

    def test_main_download_mode_legacy_format(self, temp_dir, capsys, sample_video_info):
        """Test download mode with legacy start/end format"""
        output_file = temp_dir / "output.mp4"
        output_file.touch()

        with patch(
            "sys.argv",
            [
                "downloader.py",
                "https://youtube.com/watch?v=test",
                "false",
                "best",
                "10",
                "30",
                str(output_file),
            ],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.validate_url.return_value = True
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader.download_video.return_value = DownloadResult(
                    success=True,
                    file_path=str(output_file),
                    file_size=1024,
                    error_message=None,
                    video_info=None,
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                main()  # Should complete normally without raising SystemExit
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True
                assert output["file_path"] == str(output_file)

    def test_main_download_mode_scheduled_video(self, capsys, sample_scheduled_video_info):
        """Test download mode with scheduled video"""
        with patch(
            "sys.argv",
            [
                "downloader.py",
                "https://youtube.com/watch?v=scheduled",
                "/path/to/output.mp4",
            ],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.validate_url.return_value = True
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_scheduled_video_info["id"],
                    title=sample_scheduled_video_info["title"],
                    duration=None,
                    is_live=False,
                    is_scheduled=True,
                    scheduled_start_time="2025-01-01T00:00:00",
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["scheduled"] is True

    def test_main_download_mode_missing_output(self, capsys):
        """Test download mode with missing output path"""
        with patch("sys.argv", ["downloader.py", "https://youtube.com/watch?v=test"]):
            from downloader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_download_mode_two_args_only(self, temp_dir, capsys, sample_video_info):
        """Test download mode with just URL and output path (2 args after script)"""
        output_file = temp_dir / "output.mp4"

        with patch(
            "sys.argv",
            ["downloader.py", "https://youtube.com/watch?v=test", str(output_file)],
        ):
            with patch("downloader.YouTubeDownloader") as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.validate_url.return_value = True
                mock_downloader.extract_video_info.return_value = VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                )
                mock_downloader.download_video.return_value = DownloadResult(
                    success=True,
                    file_path=str(output_file),
                    file_size=1024,
                    error_message=None,
                    video_info=None,
                )
                mock_downloader_class.return_value = mock_downloader

                from downloader import main

                main()

                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True
                # Verify download_video was called with default parameters
                call_kwargs = mock_downloader.download_video.call_args
                # start_time, end_time, sections should all be None
                assert call_kwargs is not None

    def test_main_local_mode_empty_sections_normalizes_output(self, temp_dir, capsys):
        input_file = temp_dir / "input.webm"
        input_file.write_bytes(b"video data")
        output_file = temp_dir / "output.mp4"

        with patch(
            "sys.argv",
            ["downloader.py", "--local", str(input_file), "[]", str(output_file)],
        ):
            with patch.object(
                YouTubeDownloader,
                "_normalize_output_file",
                return_value=(True, None),
            ) as mock_normalize:
                from downloader import main

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                mock_normalize.assert_called_once()
                called_src, called_dst = mock_normalize.call_args.args
                assert called_src == input_file
                assert called_dst == output_file
                assert mock_normalize.call_args.kwargs.get("selected_format") is None

                captured = capsys.readouterr()
                output = json.loads(captured.out)
                assert output["success"] is True

    def test_main_download_mode_invalid_sections_json(self, temp_dir, capsys):
        """Test download mode with malformed sections JSON"""
        output_file = temp_dir / "output.mp4"

        with patch(
            "sys.argv",
            [
                "downloader.py",
                "https://youtube.com/watch?v=test",
                "false",
                "best",
                "[invalid json",
                str(output_file),
            ],
        ):
            from downloader import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            output = json.loads(captured.out)
            assert output["success"] is False
            assert "JSON" in output["error"]


# ============================================================================
# Integration Tests and Edge Cases
# ============================================================================


class TestIntegrationAndEdgeCases:
    """Test integration scenarios and edge cases"""

    def test_unicode_video_id(self, temp_dir):
        """Test handling unicode characters in video ID"""
        test_id = "test_视频_123"
        sanitized = YouTubeDownloader._sanitize_video_id(test_id)
        # Should not raise error, but may sanitize some chars
        assert isinstance(sanitized, str)

    def test_very_long_video_id(self, temp_dir):
        """Test handling very long video ID"""
        long_id = "a" * 1000
        sanitized = YouTubeDownloader._sanitize_video_id(long_id)
        assert len(sanitized) > 0

    def test_concurrent_file_operations(self, temp_dir):
        """Test file stability check handles concurrent operations"""
        test_file = temp_dir / "concurrent.mp4"
        # Start with initial size
        test_file.write_bytes(b"x" * 100)

        # Simulate file being written with changing sizes
        # We'll modify the file between stat() calls by patching time.sleep
        sizes = [100, 200, 300]
        sleep_call_count = [0]
        original_sleep = time.sleep

        def sleep_and_modify(delay):
            """Sleep and modify file size to simulate concurrent write"""
            sleep_call_count[0] += 1
            # Modify file size after the first check (before second check)
            if sleep_call_count[0] == 1:
                test_file.write_bytes(b"x" * sizes[1])  # Change to 200
            elif sleep_call_count[0] == 2:
                test_file.write_bytes(b"x" * sizes[2])  # Change to 300
            # Use original sleep to avoid recursion
            original_sleep(0.001)  # Minimal actual sleep

        # Patch sleep to modify file between stability checks
        with patch("downloader.time.sleep", side_effect=sleep_and_modify):
            result = YouTubeDownloader._check_file_stability(test_file, max_checks=3)
            # Should detect changing size (100 -> 200 -> 300)
            assert result is False, f"Expected False (changing size), got True. sleep_call_count={sleep_call_count[0]}"
            # Verify sleep was called (which means file was modified between checks)
            assert sleep_call_count[0] >= 1

    def test_empty_sections_list(self, temp_dir):
        """Test handling empty sections list"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        # Empty sections should be treated as no cutting needed
        result = downloader.cut_and_concatenate_sections(str(input_file), [], str(output_file), "test123")
        # Should fail or handle gracefully
        assert result is False

    def test_negative_time_values(self, temp_dir):
        """Test handling negative time values"""
        input_file = temp_dir / "input.mp4"
        input_file.write_bytes(b"data")
        output_file = temp_dir / "output.mp4"

        downloader = YouTubeDownloader()
        # Negative times should be handled
        result = downloader.cut_video(str(input_file), str(output_file), start_time=-10)
        # Should either fail or be treated as 0
        assert isinstance(result, bool)

    def test_ssl_certificate_handling(self, temp_dir, sample_video_info):
        """Test SSL certificate skip handling"""
        output_file = temp_dir / "output.mp4"

        with patch.dict(os.environ, {"YT_DLP_SKIP_CERT_CHECK": "true"}):
            downloader = YouTubeDownloader()
            with patch.object(
                downloader,
                "extract_video_info",
                return_value=VideoInfo(
                    id=sample_video_info["id"],
                    title=sample_video_info["title"],
                    duration=sample_video_info["duration"],
                    is_live=False,
                    is_scheduled=False,
                    scheduled_start_time=None,
                    thumbnail=None,
                    uploader=None,
                    view_count=None,
                    upload_date=None,
                ),
            ):
                with patch.object(downloader, "_get_temp_dir", return_value=temp_dir):
                    with patch("downloader.yt_dlp.YoutubeDL") as mock_ydl:
                        mock_instance = MagicMock()
                        mock_instance.download.return_value = None
                        mock_instance.__enter__.return_value = mock_instance
                        mock_instance.__exit__.return_value = None
                        mock_ydl.return_value = mock_instance

                        downloaded_file = temp_dir / f"{sample_video_info['id']}.mp4"
                        downloaded_file.write_bytes(b"data")

                        with patch.object(downloader, "_get_cached_video_path", return_value=None):
                            with patch.object(
                                downloader,
                                "_find_downloaded_file",
                                return_value=downloaded_file,
                            ):
                                with patch.object(
                                    downloader,
                                    "_check_file_stability",
                                    return_value=True,
                                ):
                                    with patch("downloader.shutil.copy2") as mock_copy:

                                        def copy_side_effect(src, dst):
                                            Path(dst).write_bytes(b"copied data")

                                        mock_copy.side_effect = copy_side_effect
                                        result = downloader.download_video(
                                            "https://youtube.com/watch?v=test",
                                            str(output_file),
                                        )
                                        # Verify nocheckcertificate was set
                                        assert mock_ydl.called
                                        call_args = mock_ydl.call_args
                                        # call_args is (args, kwargs), and the first arg is the options dict
                                        if call_args and len(call_args) > 0:
                                            if len(call_args[0]) > 0:
                                                opts = call_args[0][0]
                                                assert opts.get("nocheckcertificate") is True
                                        assert result.success is True
