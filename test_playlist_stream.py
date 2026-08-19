import json
import queue
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch


if "customtkinter" not in sys.modules:
    fake_ctk = types.ModuleType("customtkinter")
    fake_ctk.CTk = object
    sys.modules["customtkinter"] = fake_ctk

from app import MediaDownloader  # noqa: E402
from core import DownloadSettings  # noqa: E402
from i18n import translate  # noqa: E402


class FakeProcess:
    def __init__(self, lines):
        self.stdout = iter(lines)

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None

    def poll(self):
        return None


class PlaylistStreamTests(unittest.TestCase):
    def test_playlist_entries_are_emitted_progressively_in_batches(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "en"
        downloader.events = queue.Queue()
        downloader.cancel_event = threading.Event()
        downloader.current_process = None
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []

        lines = []
        for index in range(1, 27):
            lines.append(
                json.dumps(
                    {
                        "id": f"video-{index}",
                        "title": f"Video {index}",
                        "playlist_id": "playlist-id",
                        "playlist_title": "Example playlist",
                        "playlist_index": index,
                        "playlist_count": 26,
                    }
                )
                + "\n"
            )

        with patch("app.subprocess.Popen", return_value=FakeProcess(lines)) as popen:
            result = downloader._analyze_youtube_stream("https://youtube.com/playlist?list=x")

        self.assertIsNone(result)
        command = popen.call_args.args[0]
        self.assertIn("--flat-playlist", command)
        self.assertIn("--lazy-playlist", command)
        self.assertIn("--dump-json", command)

        events = []
        while not downloader.events.empty():
            events.append(downloader.events.get())
        self.assertEqual(events[0][0], "playlist_stream_started")
        batches = [payload for kind, payload in events if kind == "playlist_stream_batch"]
        self.assertEqual([len(batch["entries"]) for batch in batches], [12, 12, 1])
        self.assertEqual(events[-1][0], "playlist_stream_done")
        self.assertEqual(events[-1][1]["loaded"], 26)

    def test_normal_youtube_video_still_returns_single_media(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "pt-BR"
        downloader.events = queue.Queue()
        downloader.cancel_event = threading.Event()
        downloader.current_process = None
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []

        line = json.dumps(
            {
                "id": "single-video",
                "title": "Single video",
                "duration": 120,
                "webpage_url": "https://youtube.com/watch?v=single-video",
            }
        ) + "\n"
        with patch("app.subprocess.Popen", return_value=FakeProcess([line])):
            result = downloader._analyze_youtube_stream(
                "https://youtube.com/watch?v=single-video"
            )

        self.assertIsNotNone(result)
        self.assertFalse(result["is_playlist"])
        self.assertEqual(result["title"], "Single video")
        self.assertTrue(downloader.events.empty())

    def test_silent_mp4_uses_video_format_and_audio_strip_helper(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "en"
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []
        downloader._ffmpeg_arguments = lambda: []
        downloader._t = lambda key, **_values: key

        command = downloader._download_command(
            "https://youtube.com/watch?v=video",
            "MP4",
            DownloadSettings(video_quality="1080p", video_no_audio=True),
        )

        self.assertEqual(command[command.index("-f") + 1], "bv*[height<=1080]")
        self.assertIn("--remux-video", command)
        exec_value = command[command.index("--exec") + 1]
        self.assertIn("strip_audio.py", exec_value)
        self.assertNotIn("+ba", " ".join(command))

    def test_frozen_app_uses_internal_audio_strip_mode(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "en"
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []
        downloader._ffmpeg_arguments = lambda: []
        downloader._t = lambda key, **_values: key

        with patch.object(sys, "frozen", True, create=True):
            command = downloader._download_command(
                "https://youtube.com/watch?v=video",
                "MP4",
                DownloadSettings(video_quality="1080p", video_no_audio=True),
            )

        exec_value = command[command.index("--exec") + 1]
        self.assertIn("--strip-audio", exec_value)
        self.assertNotIn("strip_audio.py", exec_value)

    def test_engine_selector_prefers_the_newest_available_version(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader._engine_cache = []
        downloader._engine_cache_time = 0.0
        downloader._yt_dlp_candidate_paths = lambda: ["older.exe", "newer.exe"]
        downloader._yt_dlp_version = lambda path: {
            "older.exe": "2025.11.12",
            "newer.exe": "2026.08.18.232823",
        }[path]

        engines = downloader._available_yt_dlp_engines(refresh=True)

        self.assertEqual(engines[0], ("newer.exe", "2026.08.18.232823"))

    def test_cached_analysis_and_ssd_temp_path_are_passed_to_ytdlp(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "en"
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []
        downloader._ffmpeg_arguments = lambda: []
        downloader._t = lambda key, **values: translate("en", key, **values)

        with tempfile.TemporaryDirectory() as directory:
            downloader.active_temp_dir = directory
            command = downloader._download_command(
                "https://youtube.com/watch?v=video",
                "MP4",
                DownloadSettings(),
                info_json={"id": "video", "title": "Cached video"},
            )
            info_path = Path(command[command.index("--load-info-json") + 1])
            self.assertTrue(info_path.is_file())
            self.assertEqual(info_path.parent, Path(directory))
            self.assertIn(f"temp:{directory}", command)
            self.assertEqual(command[command.index("--concurrent-fragments") + 1], "4")
            self.assertNotIn("https://youtube.com/watch?v=video", command)

    def test_selected_playlist_entries_download_without_reopening_playlist(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.language = "en"
        downloader.cancel_event = threading.Event()
        downloader.events = queue.Queue()
        downloader.active_temp_dir = ""
        downloader._engine_cache = []
        downloader._find_yt_dlp = lambda: "yt-dlp"
        downloader._js_runtime_arguments = lambda: []
        downloader._ffmpeg_arguments = lambda: []
        downloader._t = lambda key, **values: translate("en", key, **values)
        commands = []
        downloader._run_yt_dlp = lambda command, **_context: commands.append(command)
        info = {
            "title": "Fast playlist",
            "platform": "YouTube",
            "target": "https://youtube.com/playlist?list=playlist",
            "is_playlist": True,
            "selected_indices": [2],
            "playlist_entries": [
                {"index": 1, "title": "One", "target": "https://youtube.com/watch?v=one"},
                {"index": 2, "title": "Two", "target": "https://youtube.com/watch?v=two"},
            ],
        }

        message = downloader._download_info(info, "MP4", DownloadSettings())

        self.assertEqual(len(commands), 1)
        self.assertIn("https://youtube.com/watch?v=two", commands[0])
        self.assertNotIn("https://youtube.com/playlist?list=playlist", commands[0])
        self.assertEqual(message, "Download complete · 1 videos saved")


if __name__ == "__main__":
    unittest.main()
