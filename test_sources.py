import json
import queue
import subprocess
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from test_playlist_stream import MediaDownloader
from core import DownloadSettings, _spotify_embed_track, platform_from_url
from drive_support import list_public_drive, safe_relative_path, drive_link, main as drive_main
from spotify_match import rank_candidates, automatic_candidate
from video_compat import available_encoder, make_editor_mp4


class DriveTests(unittest.TestCase):
    def test_folder_listing_does_not_download_or_select_files(self):
        files = [types.SimpleNamespace(id='abc', path='clips/video.mp4'), types.SimpleNamespace(id='def', path='other.txt')]
        with patch('drive_support.gdown.download_folder', return_value=files) as listing, patch('drive_support.gdown.download') as download:
            info = list_public_drive('https://drive.google.com/drive/folders/folder123')
        self.assertTrue(listing.call_args.kwargs['skip_download'])
        self.assertFalse(listing.call_args.kwargs['use_cookies'])
        download.assert_not_called()
        self.assertEqual(info['selected_indices'], [])
        self.assertEqual(len(info['drive_files']), 2)

    def test_single_file_listing_only_reads_metadata(self):
        with patch('drive_support.gdown.download', return_value=types.SimpleNamespace(id='abc', path='video.mp4')) as download:
            info = list_public_drive('https://drive.google.com/file/d/abc/view')
        self.assertTrue(download.call_args.kwargs['skip_download'])
        self.assertEqual(info['selected_indices'], [1])
        self.assertEqual(info['title'], 'video.mp4')

    def test_link_variants_and_host_validation(self):
        for url in ('https://drive.google.com/file/d/abc/view', 'https://drive.google.com/open?id=abc', 'https://drive.google.com/uc?id=abc'):
            self.assertEqual(drive_link(url), ('abc', False))
            self.assertEqual(platform_from_url(url), 'Google Drive')
        with self.assertRaises(ValueError):
            drive_link('https://evil.example/file/d/abc/view')

    def test_windows_filenames_cannot_escape_output(self):
        for name in ('../../evil.mp4', r'C:\Users\evil.mp4', '/tmp/file.mp4', 'CON.txt', r'a\..\NUL'):
            result = safe_relative_path(name, 'abc')
            self.assertFalse(result.is_absolute())
            self.assertNotIn('..', result.parts)
            self.assertNotIn(':', str(result))
            self.assertIn('[abc]', result.name)

    def test_download_only_selected_files_and_preserve_existing(self):
        app = MediaDownloader.__new__(MediaDownloader)
        app.events = queue.Queue()
        app.cancel_event = threading.Event()
        app.language = 'en'
        with tempfile.TemporaryDirectory() as directory:
            app.active_temp_dir = directory
            root = Path(directory) / 'out'
            info = {'selected_indices': [2], 'drive_files': [
                {'index': 1, 'title': 'one.mp4', 'media_id': 'one', 'target': 'https://drive.google.com/file/d/one/view'},
                {'index': 2, 'title': 'two.mp4', 'media_id': 'two', 'target': 'https://drive.google.com/file/d/two/view'}]}
            existing = root / 'Google Drive' / 'two [two].mp4'
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b'existing')
            commands = []
            def run(command):
                commands.append(command)
                Path(command[-1]).write_bytes(b'new')
            app._run_yt_dlp_once = run
            app._download_info(info, 'MP4', DownloadSettings(output_dir=str(root)))
            self.assertEqual(len(commands), 1)
            self.assertIn('/two/view', commands[0][-2])
            self.assertEqual(existing.read_bytes(), b'existing')
            self.assertEqual(existing.with_name('two [two] (2).mp4').read_bytes(), b'new')

    def test_cleared_selection_downloads_nothing(self):
        app = MediaDownloader.__new__(MediaDownloader)
        app.language = 'en'
        with self.assertRaises(RuntimeError):
            app._download_drive_files({'selected_indices': [], 'drive_files': [{'index': 1}]}, DownloadSettings())

    def test_helper_download_uses_supported_gdown_api(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'download'
            def download(**kwargs):
                output.write_bytes(b'data')
                kwargs['progress'](4, 4)
                return str(output)
            with patch('drive_support.gdown.download', side_effect=download, autospec=True) as mocked:
                self.assertEqual(drive_main(['https://drive.google.com/file/d/abc/view', str(output)]), 0)
                self.assertFalse(mocked.call_args.kwargs['use_cookies'])


class SpotifyMatchingTests(unittest.TestCase):
    def setUp(self):
        self.track = {'title': 'Hello', 'artists': 'Adele', 'duration': 295, 'id': 'spotify-id'}
        self.good = {'id': '12345678901', 'title': 'Adele - Hello (Official Audio)', 'channel': 'Adele', 'duration': 295}
        self.wrong = {'id': '12345678902', 'title': 'Lionel Richie - Hello', 'channel': 'Lionel Richie', 'duration': 295}

    def test_same_title_different_artist_not_automatic(self):
        self.assertIsNone(automatic_candidate(rank_candidates(self.track, [self.wrong])))
        ranked = rank_candidates(self.track, [self.wrong, self.good])
        self.assertEqual(automatic_candidate(ranked)['id'], self.good['id'])

    def test_missing_artist_or_duration_requires_choice(self):
        for field in ('artists', 'duration'):
            track = dict(self.track)
            track.pop(field)
            self.assertIsNone(automatic_candidate(rank_candidates(track, [self.good])))

    def test_wrong_duration_and_versions_require_choice(self):
        self.assertIsNone(automatic_candidate(rank_candidates(self.track, [{**self.good, 'duration': 180}])))
        for version in ('Live', 'Remix', 'Cover', 'Sped Up', 'Acoustic'):
            self.assertIsNone(automatic_candidate(rank_candidates(self.track, [{**self.good, 'title': 'Adele - Hello ' + version}])))

    def test_tied_candidates_require_choice(self):
        self.assertIsNone(automatic_candidate(rank_candidates(self.track, [self.good, {**self.good, 'id': '12345678903'}])))

    def test_unavailable_entries_and_unofficial_uploads(self):
        self.assertEqual(rank_candidates(self.track, [None]), [])
        unofficial = {**self.good, 'channel': 'Random uploads'}
        self.assertIsNone(automatic_candidate(rank_candidates(self.track, [unofficial])))

    def test_spotify_embed_selects_exact_id_not_related_track(self):
        payload = {'related': {'uri': 'spotify:track:other', 'title': 'Wrong', 'artists': [{'name': 'Other'}]},
                   'entity': {'uri': 'spotify:track:correct', 'title': 'Hello', 'artists': [{'name': 'Adele'}], 'duration': 295000}}
        page = '<script id="__NEXT_DATA__">' + json.dumps(payload) + '</script>'
        with patch('core.urllib.request.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value = page.encode()
            result = _spotify_embed_track('correct', 10)
        self.assertEqual(result['id'], 'correct')
        self.assertEqual(result['artists'], 'Adele')
        self.assertEqual(result['duration'], 295)

    def test_single_track_download_uses_chosen_url_not_search(self):
        app = MediaDownloader.__new__(MediaDownloader)
        app.events = queue.Queue()
        app.language = 'en'
        app._spotify_source = lambda metadata: 'https://www.youtube.com/watch?v=12345678901'
        app._download_command = lambda target, *args, **kwargs: [target]
        commands = []
        app._run_yt_dlp = lambda command, **kwargs: commands.append(command)
        app._apply_spotify_metadata = lambda *args, **kwargs: None
        app._download_spotify_track({'target': 'ytsearch1:Hello'}, self.track, DownloadSettings())
        self.assertEqual(commands, [['https://www.youtube.com/watch?v=12345678901']])

    def test_collection_matches_each_selected_track_and_skips_uncertain(self):
        app = MediaDownloader.__new__(MediaDownloader)
        app.events = queue.Queue()
        app.cancel_event = threading.Event()
        app.language = 'en'
        app._download_command = lambda target, *args, **kwargs: [target]
        commands = []
        app._run_yt_dlp = lambda command, **kwargs: commands.append(command)
        app._apply_spotify_metadata = lambda *args, **kwargs: None
        with patch.object(app, '_spotify_source', side_effect=[RuntimeError('Skipped'), 'https://www.youtube.com/watch?v=12345678901']) as match:
            message = app._download_spotify_collection([self.track, self.track], DownloadSettings(), 'Playlist')
        self.assertEqual(match.call_count, 2)
        self.assertEqual(len(commands), 1)
        self.assertIn('1/2', message)

    def test_selection_dialog_response_controls_target(self):
        app = MediaDownloader.__new__(MediaDownloader)
        app.events = queue.Queue()
        app.cancel_event = threading.Event()
        app.language = 'en'
        app._find_yt_dlp = lambda: 'yt-dlp'
        app._js_runtime_arguments = lambda: []
        result = {}
        class Process:
            returncode = 0
            def communicate(self, **kwargs):
                return json.dumps({'entries': [self_candidate]}), ''
            def poll(self):
                return 0
        self_candidate = self.wrong
        def worker():
            try:
                result['target'] = app._spotify_source(self.track)
            except Exception as exc:
                result['error'] = exc
        with patch('app.subprocess.Popen', return_value=Process()):
            thread = threading.Thread(target=worker)
            thread.start()
            try:
                kind, payload = app.events.get(timeout=3)
                self.assertEqual(kind, 'status')
                kind, payload = app.events.get(timeout=3)
                self.assertEqual(kind, 'spotify_choose')
                payload['answer'].put(0)
                thread.join(timeout=3)
                self.assertEqual(result['target'], 'https://www.youtube.com/watch?v=12345678902')
            finally:
                app.cancel_event.set()
                thread.join(timeout=3)


class HardwareTests(unittest.TestCase):
    def tearDown(self):
        available_encoder.cache_clear()

    def test_probe_falls_through_to_working_hardware(self):
        for working in ('h264_nvenc', 'h264_qsv', 'h264_amf', 'libx264'):
            available_encoder.cache_clear()
            def run(command, **kwargs):
                encoder = command[command.index('-c:v') + 1]
                return subprocess.CompletedProcess(command, 0 if encoder == working else 1)
            with patch('video_compat.subprocess.run', side_effect=run):
                self.assertEqual(available_encoder('ffmpeg'), working)

    def test_full_hardware_failure_retries_cpu_from_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'video.mp4'
            source.write_bytes(b'original')
            commands = []
            def run(command, **kwargs):
                commands.append(list(command))
                self.assertEqual(source.read_bytes(), b'original')
                Path(command[-1]).write_bytes(b'encoded')
                return subprocess.CompletedProcess(command, 1 if len(commands) == 1 else 0, stderr='hardware failure')
            with patch('video_compat.available_encoder', return_value='h264_nvenc'), patch('video_compat._ffmpeg_path', return_value='ffmpeg'), patch('video_compat.subprocess.run', side_effect=run):
                self.assertEqual(make_editor_mp4(source), 0)
            self.assertEqual(len(commands), 2)
            self.assertIn('h264_nvenc', commands[0])
            self.assertIn('libx264', commands[1])
            self.assertNotIn('-cq', commands[1])
            self.assertEqual(source.read_bytes(), b'encoded')


if __name__ == '__main__':
    unittest.main()
