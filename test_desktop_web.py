import json
import queue
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock, patch

from core import DownloadSettings
from desktop_web import Bridge, Engine, make_server


class WebBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = Bridge(Engine())
        self.bridge.engine.settings = DownloadSettings()

    def test_drive_download_only_uses_server_side_selected_files(self):
        b = self.bridge
        b.items = [{"title": "Drive", "drive_files": [1, 2], "playlist_entries": [
            {"index": 1, "title": "one"}, {"index": 2, "title": "two"}], "selected_indices": []}]
        with patch.object(b, "launch") as launch, patch("desktop_web.save_settings"):
            with self.assertRaises(ValueError):
                b.command("download", {"generation": 0, "selected": {"0": [3]}})
            with self.assertRaises(ValueError):
                b.command("download", {"generation": 0, "selected": {"0": []}})
            b.command("download", {"generation": 0, "selected": {"0": [2]}})
            self.assertEqual(launch.call_args.args[1]["queue_items"][0]["selected_indices"], [2])
            self.assertEqual(b.items[0]["selected_indices"], [])

    def test_spotify_choice_is_bound_to_current_request(self):
        b = self.bridge
        answers = queue.Queue()
        b.engine.events.put(("spotify_choose", {"track": {"title": "Song"}, "candidates": [{"title": "Match"}], "answer": answers}))
        snapshot = b.snapshot()
        self.assertNotIn("answer", snapshot["choice"])
        with self.assertRaises(ValueError):
            b.command("choose", {"id": "stale", "index": 0})
        b.command("choose", {"id": snapshot["choice"]["id"], "index": 0})
        self.assertEqual(answers.get_nowait(), 0)

    def test_streaming_playlist_accumulates_and_finishes(self):
        b = self.bridge
        b.engine.events.put(("playlist_stream_started", {"playlist_entries": [{"index": 1}], "selected_indices": [1]}))
        b.engine.events.put(("playlist_stream_batch", {"entries": [{"index": 2}], "loaded": 2}))
        b.engine.events.put(("playlist_stream_done", {}))
        snapshot = b.snapshot()
        self.assertEqual(snapshot["phase"], "ready")
        self.assertEqual(snapshot["items"][0]["selected"], [1, 2])

    def test_cancelled_analysis_reaches_terminal_state(self):
        b = self.bridge
        b.phase = "analyzing"
        def analyze():
            b.engine.cancel_event.wait(2)
        b.launch(analyze)
        with patch.object(b.engine, "_terminate_current_process"):
            b.command("cancel", {})
            b.worker.join(3)
        self.assertEqual(b.snapshot()["phase"], "cancelled")

    def test_native_window_controls_and_folder_selection(self):
        b = self.bridge
        b.window = Mock()
        b.command("minimize", {})
        b.window.minimize.assert_called_once()
        b.command("maximize", {})
        b.window.maximize.assert_called_once()
        self.assertTrue(b.snapshot()["maximized"])
        b.command("maximize", {})
        b.window.restore.assert_called_once()
        self.assertFalse(b.snapshot()["maximized"])
        b.window.create_file_dialog.return_value = [str(Path.cwd())]
        with patch("desktop_web.save_settings"):
            b.command("browse", {})
        self.assertEqual(b.engine.settings.output_dir, str(Path.cwd()))
        with patch("desktop_web.threading.Timer") as timer:
            b.command("close", {})
            timer.assert_called_once_with(0.15, b.window.destroy)

    def test_browser_mode_cannot_control_native_window(self):
        with self.assertRaises(ValueError):
            self.bridge.command("maximize", {})

    def test_http_requires_session_and_blocks_cross_origin_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("local UI")
            (Path(temp) / "private.txt").write_text("private")
            server, token = make_server(self.bridge, dist)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                self.assertEqual(urllib.request.urlopen(base).read(), b"local UI")
                for path, headers in [("/api/state", {}), ("/api/state", {"X-BI3L-Token": token, "Origin": "https://external.example"}), ("/../private.txt", {})]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(urllib.request.Request(base + path, headers=headers))
                    self.assertIn(error.exception.code, (403, 404))
                result = urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers={"X-BI3L-Token": token}))
                self.assertEqual(json.load(result)["phase"], "idle")
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
