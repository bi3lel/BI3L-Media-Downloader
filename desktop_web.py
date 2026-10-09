"""Local browser interface for the existing BI3L download engine.

Build webui first, then run this file. No media or settings leave this machine
except requests made to the media providers by the existing download engine.
"""
from __future__ import annotations

import base64
import copy
import json
import mimetypes
import queue
import secrets
import sys
import threading
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from app import MediaDownloader
from core import DownloadSettings, load_settings, save_settings, split_urls, open_output_folder

VIDEO = ("Best", "2160p", "1440p", "1080p", "720p", "480p", "360p")
AUDIO = ("Best", "320 kbps", "256 kbps", "192 kbps", "128 kbps")


class Engine(MediaDownloader):
    """Use the existing workers without constructing a Tk window."""
    def __init__(self):
        self.settings = load_settings()
        self.language = self.settings.language
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.current_process = None
        self.active_temp_dir = ""
        self._engine_cache = []
        self._engine_cache_time = 0.0

    def __getattr__(self, name):
        raise AttributeError(name)


class Bridge:
    def __init__(self, engine=None):
        self.engine = engine or Engine()
        self.lock = threading.RLock()
        self.worker = None
        self.updater = None
        self.items = []
        self.choice = None
        self.phase = "idle"
        self.status = ""
        self.progress = 0
        self.engine_status = ""
        self.active_title = ""
        self.generation = 0
        self.window = None
        self.maximized = False

    def stop(self):
        self.engine.cancel_event.set()
        self.engine._terminate_current_process()
        if self.worker:
            self.worker.join(timeout=8)

    def busy(self):
        return self.worker is not None and self.worker.is_alive()

    def launch(self, target, *args):
        if self.busy() or (self.updater and self.updater.is_alive()):
            raise ValueError("Wait for the current operation to finish.")
        self.engine.cancel_event.clear()
        def work():
            try:
                target(*args)
            finally:
                if self.engine.cancel_event.is_set():
                    self.engine.events.put(("download_cancelled", None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def drain(self):
        while True:
            try:
                kind, value = self.engine.events.get_nowait()
            except queue.Empty:
                break
            if kind == "analysis_batch_done":
                self.items = value
                self.phase = "ready"
                self.status = ""
                self.generation += 1
            elif kind == "playlist_stream_started":
                self.items = [value]
                self.generation += 1
            elif kind == "playlist_stream_batch" and self.items:
                self.items[0].setdefault("playlist_entries", []).extend(value["entries"])
                self.items[0].setdefault("selected_indices", []).extend(e["index"] for e in value["entries"])
                self.status = str(value.get("loaded", ""))
            elif kind == "playlist_stream_done" and self.items:
                self.items[0]["streaming"] = False
                self.items[0]["thumbnail"] = value.get("thumbnail", b"")
                self.phase = "ready"
                self.status = ""
            elif kind in {"analysis_error", "download_error"}:
                self.phase = "cancelled" if self.engine.cancel_event.is_set() else "error"
                self.status = value or "Operation failed."
            elif kind == "progress":
                self.progress, self.status = value
            elif kind == "item_started":
                self.active_title = str(value)
                self.progress = 0
            elif kind in {"status", "analysis_status"}:
                self.status = str(value)
            elif kind == "download_done":
                self.phase = "complete"
                self.progress = 1
                self.status = value or ""
            elif kind == "download_cancelled":
                self.phase = "cancelled"
                self.status = ""
                self.choice = None
            elif kind == "spotify_choose":
                self.choice = {**value, "id": secrets.token_hex(12)}
            elif kind in {"engine_status_detected", "engine_update_done", "engine_update_error"}:
                self.engine_status = str(value)

    def snapshot(self):
        with self.lock:
            self.drain()
            items = []
            for index, item in enumerate(self.items):
                thumb = item.get("thumbnail")
                items.append({"id": index, "title": item.get("title", ""),
                    "platform": item.get("platform", "Website"), "duration": item.get("duration"),
                    "drive": bool(item.get("drive_files")),
                    "thumbnail": "data:image/jpeg;base64," + base64.b64encode(thumb).decode() if isinstance(thumb, bytes) and thumb else "",
                    "entries": [{"index": e["index"], "title": e.get("title", ""), "duration": e.get("duration")} for e in item.get("playlist_entries", [])],
                    "selected": item.get("selected_indices", [])})
            choice = None
            if self.choice:
                choice = {k: self.choice[k] for k in ("id", "track", "candidates")}
            return {"phase": self.phase, "status": self.status, "progress": self.progress,
                "busy": self.busy(), "items": items, "generation": self.generation,
                "settings": asdict(self.engine.settings), "choice": choice,
                "engineStatus": self.engine_status, "updating": bool(self.updater and self.updater.is_alive()),
                "activeTitle": self.active_title, "native": self.window is not None,
                "maximized": self.maximized}

    def configure(self, data):
        settings = copy.copy(self.engine.settings)
        for key, allowed in {"media_format": ("MP4", "MP3"), "video_quality": VIDEO,
                             "audio_quality": AUDIO, "language": ("en", "pt-BR")}.items():
            if key in data:
                if data[key] not in allowed:
                    raise ValueError(f"Invalid {key}.")
                setattr(settings, key, data[key])
        for key in ("also_audio", "video_no_audio"):
            if key in data:
                if not isinstance(data[key], bool):
                    raise ValueError(f"Invalid {key}.")
                setattr(settings, key, data[key])
        if "output_dir" in data:
            path = Path(str(data["output_dir"]))
            if not path.is_absolute():
                raise ValueError("Choose an absolute destination folder.")
            settings.output_dir = str(path)
        self.engine.settings = settings
        self.engine.language = settings.language
        save_settings(settings)

    def command(self, action, data):
        with self.lock:
            self.drain()
            if action in {"minimize", "maximize", "close"}:
                if self.window is None:
                    raise ValueError("Window controls are available in the desktop app.")
                if action == "minimize":
                    self.window.minimize()
                elif action == "maximize":
                    was_maximized = self.maximized
                    self.maximized = not was_maximized
                    if was_maximized:
                        self.window.restore()
                    else:
                        self.window.maximize()
                else:
                    threading.Timer(0.15, self.window.destroy).start()
                return
            if action == "cancel":
                self.engine.cancel_event.set()
                threading.Thread(target=self.engine._terminate_current_process, daemon=True).start()
                self.choice = None
                return
            if action == "choose":
                if not self.choice or data.get("id") != self.choice["id"]:
                    raise ValueError("This choice is no longer active.")
                index = data.get("index")
                if index is not None and (type(index) is not int or not 0 <= index < len(self.choice["candidates"])):
                    raise ValueError("Invalid candidate.")
                self.choice["answer"].put_nowait(index)
                self.choice = None
                return
            if action == "open-folder":
                open_output_folder(self.engine.settings.output_dir)
                return
            if self.busy() or (self.updater and self.updater.is_alive()):
                raise ValueError("Wait for the current operation to finish.")
            if action == "analyze":
                urls = split_urls(str(data.get("urls", "")))
                if not urls or len(urls) > 100:
                    raise ValueError("Paste between 1 and 100 valid media URLs.")
                self.items = []
                self.choice = None
                self.status = ""
                self.phase = "analyzing"
                self.progress = 0
                self.launch(self.engine._analyze_many_worker, urls)
            elif action == "settings":
                self.configure(data)
            elif action == "browse":
                if self.window is not None:
                    import webview
                    folders = self.window.create_file_dialog(webview.FileDialog.FOLDER,
                        directory=self.engine.settings.output_dir)
                    if folders:
                        self.configure({"output_dir": folders[0]})
                    return
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                try:
                    folder = filedialog.askdirectory(parent=root, initialdir=self.engine.settings.output_dir)
                    if folder:
                        self.configure({"output_dir": folder})
                finally:
                    root.destroy()
            elif action == "download":
                if data.get("generation") != self.generation or not self.items:
                    raise ValueError("Analyze the links before downloading.")
                selected = data.get("selected", {})
                items = []
                for i, original in enumerate(self.items):
                    if str(i) not in selected:
                        continue
                    item = copy.copy(original)
                    entries = item.get("playlist_entries", [])
                    if entries:
                        indices = selected[str(i)]
                        allowed = {e["index"] for e in entries}
                        if not isinstance(indices, list) or any(type(n) is not int or n not in allowed for n in indices):
                            raise ValueError("Invalid file selection.")
                        if not indices:
                            continue
                        item["selected_indices"] = list(dict.fromkeys(indices))
                    items.append(item)
                if not items:
                    raise ValueError("Select at least one item.")
                self.configure(data.get("settings", {}))
                settings = copy.copy(self.engine.settings)
                self.phase = "downloading"
                self.status = ""
                self.progress = 0
                self.active_title = items[0].get("title", "")
                self.launch(self.engine._download_worker, {"queue_items": items}, settings.media_format, settings)
            elif action == "reset":
                self.items = []
                self.phase = "idle"
                self.status = ""
                self.choice = None
                self.generation += 1
            elif action == "update-engine":
                self.updater = threading.Thread(target=self.engine._update_downloader_worker, daemon=True)
                self.updater.start()
            else:
                raise ValueError("Unknown action.")


def make_server(bridge, dist, port=0):
    token = secrets.token_urlsafe(32)
    dist = Path(dist).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            return (self.headers.get("Host") == expected
                and self.headers.get("Origin", f"http://{expected}") == f"http://{expected}"
                and secrets.compare_digest(self.headers.get("X-BI3L-Token", ""), token))

        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith("/api/"):
                if not self.authorized():
                    self.send(403, b'{"error":"Unauthorized session."}')
                elif path == "/api/state":
                    self.send(200, json.dumps(bridge.snapshot(), default=str).encode())
                else:
                    self.send(404, b"{}")
                return
            target = (dist / unquote(path).lstrip("/")).resolve() if path != "/" else dist / "index.html"
            if not target.is_relative_to(dist) or not target.is_file():
                self.send(404, b"Not found", "text/plain")
                return
            self.send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

        def do_POST(self):
            if not self.authorized():
                self.send(403, b'{"error":"Unauthorized session."}')
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000:
                    raise ValueError("Invalid request size.")
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Invalid request.")
                action = self.path.removeprefix("/api/")
                bridge.command(action, data)
                self.send(200, json.dumps(bridge.snapshot(), default=str).encode())
            except (ValueError, TypeError, OSError) as exc:
                self.send(400, json.dumps({"error": str(exc)}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, token


def main():
    dist = Path(__file__).parent / "webui" / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("Build the interface first: cd webui && npm ci && npm run build")
    bridge = Bridge()
    server, token = make_server(bridge, dist)
    url = f"http://127.0.0.1:{server.server_port}/#{token}"
    try:
        if "--browser" in sys.argv:
            print(f"BI3L Media Downloader is running locally. Close this terminal to stop.\n{url}", flush=True)
            webbrowser.open(url)
            server.serve_forever()
        else:
            import webview
            from app import configure_windows_app_identity
            configure_windows_app_identity()
            webview.settings["ALLOW_FILE_URLS"] = False
            webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True
            bridge.window = webview.create_window("BI3L Media Downloader", url,
                width=940, height=650, min_size=(780, 580), frameless=False,
                easy_drag=False, resizable=True, shadow=True, background_color="#191c1f")
            def maximized():
                bridge.maximized = True
            def restored():
                bridge.maximized = False
            bridge.window.events.maximized += maximized
            bridge.window.events.restored += restored
            threading.Thread(target=server.serve_forever, daemon=True).start()
            webview.start(gui="edgechromium" if sys.platform == "win32" else None,
                icon=str(Path(__file__).parent / "assets" / "app_icon.ico"))
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        if "--browser" not in sys.argv:
            server.shutdown()
        server.server_close()


if __name__ == "__main__":
    from app import dispatch_helper
    dispatch_helper()
    main()
