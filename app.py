from __future__ import annotations

import io
import json
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk
from PIL import Image

from i18n import LANGUAGE_NAMES, localize_known_error, translate
from strip_audio import strip_audio

from core import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION,
    DownloadSettings,
    is_spotify_url,
    load_settings,
    open_output_folder,
    platform_from_url,
    resolve_spotify_collection,
    resolve_spotify_track_info,
    save_settings,
    split_urls,
    spotify_kind,
)


BG = "#111214"
CARD = "#1e1f22"
SURFACE = "#2b2d31"
SURFACE_HOVER = "#3f4147"
BORDER = "#3f4147"
TEXT = "#f2f3f5"
MUTED = "#b5bac1"
DIM = "#949ba4"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
ACCENT_SOFT = "#353a66"
SUCCESS = "#23a55a"
ERROR = "#f23f42"
FONT = "Segoe UI"
BUTTON_RADIUS = 6
PROGRESS_MARKER = "__BI3L_MEDIA_DOWNLOADER_PROGRESS__"
WINDOWS_APP_ID = "BI3L.MediaDownloader"


def configure_windows_app_identity() -> None:
    """Keep Windows from grouping the app under pythonw.exe's icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except (AttributeError, OSError):
        pass


class MediaDownloader(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)

        self.title(APP_DISPLAY_NAME)
        self.geometry("940x850")
        self.minsize(780, 820)

        self.window_icon_photo: tk.PhotoImage | None = None
        self._apply_window_icon()
        # CustomTkinter may restore its own icon while creating the window.
        # Apply the mascot again after startup for the Windows title bar/taskbar.
        self.after(120, self._apply_window_icon)
        self.after(700, self._apply_window_icon)

        self.settings = load_settings()
        self.language = self.settings.language if self.settings.language in LANGUAGE_NAMES else "en"
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.current_process: subprocess.Popen[str] | None = None
        self.active_temp_dir = ""
        self._engine_cache: list[tuple[str, str]] = []
        self._engine_cache_time = 0.0
        self.current_url = ""
        self.download_target = ""
        self.current_platform = "Website"
        self.current_info: dict[str, Any] = {}
        self.pending_queue: list[dict[str, Any]] = []
        self.thumbnail_image: ctk.CTkImage | None = None
        self.home_icon_image: ctk.CTkImage | None = None

        self.format_value = "MP4"
        self.video_quality = "Best"
        self.audio_quality = "Best"
        self.video_no_audio = False
        self.video_buttons: dict[str, ctk.CTkButton] = {}
        self.audio_buttons: dict[str, ctk.CTkButton] = {}
        self.no_audio_button: ctk.CTkButton | None = None
        self.platform_images: dict[tuple[str, int], ctk.CTkImage] = {}
        self.playlist_info: dict[str, Any] = {}
        self.playlist_variables: dict[int, tk.BooleanVar] = {}
        self.playlist_streaming = False
        self.playlist_select_future = True
        self.playlist_return_to_queue = False

        self.output_var = tk.StringVar(value=self.settings.output_dir)
        self.also_audio_var = tk.BooleanVar(value=self.settings.also_audio)
        self.language_var = tk.StringVar(value=LANGUAGE_NAMES[self.language])

        self.stage = ctk.CTkFrame(self, fg_color="transparent")
        self.stage.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._process_events)
        self._show_home()

    def _clear_stage(self) -> None:
        for child in self.stage.winfo_children():
            child.destroy()

    def _apply_window_icon(self) -> None:
        assets = Path(__file__).resolve().parent / "assets"
        try:
            self.window_icon_photo = tk.PhotoImage(file=str(assets / "window_icon.png"))
            self.iconphoto(True, self.window_icon_photo)
            if sys.platform == "win32":
                self.iconbitmap(str(assets / "app_icon.ico"))
        except (OSError, RuntimeError, tk.TclError):
            # Some window managers do not support custom title-bar icons. The
            # full mascot still remains visible on the home card.
            pass

    def _t(self, key: str, **values: Any) -> str:
        return translate(self.language, key, **values)

    def _platform_display(self, platform: str) -> str:
        if platform == "Queue":
            return self._t("platform.queue")
        if platform == "Website":
            return self._t("platform.website")
        return platform

    def _platform_icon(self, platform: str, size: int = 18) -> ctk.CTkImage | None:
        key = (platform, size)
        if key in self.platform_images:
            return self.platform_images[key]
        path = Path(__file__).resolve().parent / "assets" / f"{platform.lower()}.png"
        try:
            with Image.open(path) as source:
                image = source.convert("RGBA")
            icon = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
            self.platform_images[key] = icon
            return icon
        except (OSError, ValueError):
            return None

    def _card(self, *, width: int, height: int, show_settings: bool = False) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self.stage,
            width=width,
            height=height,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.grid_propagate(False)
        if show_settings:
            ctk.CTkButton(
                card,
                text="⚙",
                width=38,
                height=34,
                corner_radius=BUTTON_RADIUS,
                fg_color=SURFACE,
                hover_color=SURFACE_HOVER,
                border_width=1,
                border_color=BORDER,
                text_color=MUTED,
                font=ctk.CTkFont(FONT, 16),
                command=self._open_settings,
            ).place(relx=1.0, x=-20, y=18, anchor="ne")
        return card

    def _show_home(self) -> None:
        self._clear_stage()
        self.current_info = {}
        self.download_target = ""
        card = self._card(width=620, height=415, show_settings=True)
        card.grid_columnconfigure(0, weight=1)

        try:
            with Image.open(Path(__file__).resolve().parent / "assets" / "app_icon.png") as source:
                home_icon = source.convert("RGBA")
            self.home_icon_image = ctk.CTkImage(
                light_image=home_icon,
                dark_image=home_icon,
                size=(96, 96),
            )
        except (OSError, ValueError):
            self.home_icon_image = None
        ctk.CTkLabel(
            card,
            text="" if self.home_icon_image else APP_DISPLAY_NAME,
            image=self.home_icon_image,
            width=96,
            height=96,
            fg_color="transparent",
            text_color=ACCENT,
            font=ctk.CTkFont(FONT, 13, "bold"),
        ).grid(row=0, column=0, pady=(18, 6))
        ctk.CTkLabel(
            card,
            text=self._t("home.title"),
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 21, "bold"),
        ).grid(row=1, column=0)
        input_row = ctk.CTkFrame(card, fg_color="transparent")
        # Preserve the original input position while moving the supported-sites
        # helper into the open space directly below the field.
        input_row.grid(row=3, column=0, padx=36, pady=(46, 0), sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)
        self.url_entry = ctk.CTkEntry(
            input_row,
            height=50,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
            placeholder_text="https://www.youtube.com/watch?v=...",
            placeholder_text_color=DIM,
            font=ctk.CTkFont(FONT, 13),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda _event: self._analyze())
        self.continue_button = ctk.CTkButton(
            input_row,
            text=self._t("home.continue"),
            width=132,
            height=50,
            corner_radius=BUTTON_RADIUS,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(FONT, 13, "bold"),
            command=self._analyze,
        )
        self.continue_button.grid(row=0, column=1)
        self.home_status = ctk.CTkLabel(
            card,
            text=self._t("home.supported"),
            height=38,
            wraplength=540,
            justify="center",
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 12),
        )
        self.home_status.grid(row=4, column=0, pady=(7, 0))

        chips = ctk.CTkFrame(card, fg_color="transparent")
        chips.grid(row=5, column=0, pady=(4, 0))
        for index, label in enumerate(("YouTube", "Instagram", "TikTok", "Twitch", "X", "Spotify")):
            row, column = divmod(index, 3)
            icon = self._platform_icon(label)
            ctk.CTkLabel(
                chips,
                text=f"  {label}" if icon else label,
                image=icon,
                compound="left",
                width=150,
                height=34,
                padx=9,
                corner_radius=17,
                fg_color=SURFACE,
                text_color=MUTED,
                font=ctk.CTkFont(FONT, 11),
            ).grid(row=row, column=column, padx=4, pady=4)

        self.after(150, self.url_entry.focus_set)

    def _analyze(self) -> None:
        urls = split_urls(self.url_entry.get())
        if not urls:
            self.home_status.configure(text=self._t("home.invalid_url"), text_color=ERROR)
            return
        if not self._yt_dlp_candidate_paths():
            messagebox.showerror(
                APP_DISPLAY_NAME,
                self._t("home.engine_missing"),
            )
            return

        self.current_url = urls[0]
        self.cancel_event.clear()
        self.continue_button.configure(state="disabled", text=self._t("home.checking"))
        self.home_status.configure(
            text=(
                self._t("home.reading_one")
                if len(urls) == 1
                else self._t("home.reading_many", current=1, total=len(urls))
            ),
            text_color=MUTED,
        )
        self.worker = threading.Thread(
            target=self._analyze_many_worker,
            args=(urls,),
            daemon=True,
        )
        self.worker.start()

    def _analyze_many_worker(self, urls: list[str]) -> None:
        try:
            results: list[dict[str, Any]] = []
            if len(urls) == 1 and platform_from_url(urls[0]) == "YouTube":
                result = self._analyze_youtube_stream(urls[0])
                if result is not None:
                    self.events.put(("analysis_batch_done", [result]))
                return
            for index, url in enumerate(urls, start=1):
                if len(urls) > 1:
                    self.events.put(
                        (
                            "analysis_status",
                            self._t("home.reading_many", current=index, total=len(urls)),
                        )
                    )
                results.append(self._analyze_one(url))
            self.events.put(("analysis_batch_done", results))
        except Exception as exc:
            message = localize_known_error(self.language, str(exc))
            if urls and platform_from_url(urls[min(len(results), len(urls) - 1)]) == "TikTok":
                message = self._t("analysis.tiktok_failed")
            self.events.put(("analysis_error", message or self._t("analysis.link_failed")))

    def _analyze_youtube_stream(self, url: str) -> dict[str, Any] | None:
        preferred = self._find_yt_dlp() or "yt-dlp"
        attempts = self._engine_attempt_paths(preferred)
        last_error: RuntimeError | None = None
        for attempt_number, engine in enumerate(attempts, start=1):
            if attempt_number > 1:
                self.events.put(("analysis_status", self._t("analysis.retry_engine")))
            try:
                return self._analyze_youtube_stream_once(url, engine)
            except (RuntimeError, OSError) as exc:
                last_error = exc if isinstance(exc, RuntimeError) else RuntimeError(str(exc))
                if bool(getattr(exc, "playlist_started", False)):
                    raise
        raise last_error or RuntimeError(self._t("analysis.link_failed"))

    def _analyze_youtube_stream_once(
        self,
        url: str,
        engine: str,
    ) -> dict[str, Any] | None:
        """Stream flat playlist entries so the selector can open immediately."""
        command = [
            engine,
            "--dump-json",
            "--flat-playlist",
            "--lazy-playlist",
            "--no-warnings",
            *self._js_runtime_arguments(),
            "--",
            url,
        ]
        self.current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=self._creation_flags(),
        )
        assert self.current_process.stdout is not None
        recent_lines: list[str] = []
        first_data: dict[str, Any] | None = None
        playlist_info: dict[str, Any] | None = None
        pending_entries: list[dict[str, Any]] = []
        loaded = 0

        for raw_line in self.current_process.stdout:
            if self.cancel_event.is_set():
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
                self.current_process = None
                return None
            line = raw_line.strip()
            if not line:
                continue
            recent_lines.append(line)
            recent_lines = recent_lines[-20:]
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if first_data is None:
                first_data = data
            raw_index = data.get("playlist_index")
            playlist_title = data.get("playlist_title") or data.get("playlist")
            playlist_id = data.get("playlist_id")
            is_playlist_entry = bool(raw_index is not None or playlist_title or playlist_id)
            if not is_playlist_entry:
                continue

            loaded += 1
            try:
                entry_index = int(raw_index or loaded)
            except (TypeError, ValueError):
                entry_index = loaded
            entry_id = str(data.get("id") or "")
            entry_target = str(data.get("webpage_url") or data.get("url") or "")
            if entry_id:
                entry_target = f"https://www.youtube.com/watch?v={entry_id}"
            entry = {
                "index": entry_index,
                "title": str(data.get("title") or self._t("generic.video", index=entry_index)),
                "duration": data.get("duration"),
                "target": entry_target,
                "media_id": entry_id,
            }
            if playlist_info is None:
                try:
                    expected_count = int(data.get("playlist_count") or data.get("n_entries") or 0)
                except (TypeError, ValueError):
                    expected_count = 0
                playlist_info = {
                    "title": str(playlist_title or self._t("details.playlist")),
                    "duration": None,
                    "platform": "YouTube",
                    "target": url,
                    "original_url": url,
                    "thumbnail": b"",
                    "direct_media": False,
                    "is_playlist": True,
                    "playlist_count": expected_count,
                    "playlist_entries": [entry],
                    "selected_indices": [entry_index],
                    "media_id": str(playlist_id or "playlist"),
                    "streaming": True,
                }
                self.events.put(("playlist_stream_started", dict(playlist_info)))
                continue
            pending_entries.append(entry)
            if len(pending_entries) >= 12:
                self.events.put(
                    (
                        "playlist_stream_batch",
                        {
                            "entries": pending_entries,
                            "loaded": loaded,
                            "total": playlist_info.get("playlist_count") or 0,
                        },
                    )
                )
                pending_entries = []

        return_code = self.current_process.wait()
        self.current_process = None
        if self.cancel_event.is_set():
            return None
        if return_code:
            error = RuntimeError(self._last_error("\n".join(recent_lines)))
            error.playlist_started = playlist_info is not None  # type: ignore[attr-defined]
            raise error
        if playlist_info is not None:
            if pending_entries:
                self.events.put(
                    (
                        "playlist_stream_batch",
                        {
                            "entries": pending_entries,
                            "loaded": loaded,
                            "total": playlist_info.get("playlist_count") or 0,
                        },
                    )
                )
            self.events.put(
                (
                    "playlist_stream_done",
                    {
                        "loaded": loaded,
                        # Do not hold the ready state for a decorative network
                        # request; the platform icon is used as the fallback.
                        "thumbnail": b"",
                    },
                )
            )
            return None
        if not first_data:
            raise RuntimeError(self._t("analysis.no_media"))
        thumbnail_url = str(first_data.get("thumbnail") or first_data.get("cover") or "")
        return {
            "title": str(first_data.get("title") or self._t("generic.untitled")),
            "duration": first_data.get("duration"),
            "platform": "YouTube",
            "target": str(first_data.get("webpage_url") or url),
            "original_url": url,
            "thumbnail": self._download_thumbnail(thumbnail_url),
            "direct_media": False,
            "is_playlist": False,
            "playlist_count": None,
            "playlist_entries": [],
            "selected_indices": [],
            "media_id": str(first_data.get("id") or "video"),
            "spotify_metadata": {},
            "analysis_info": first_data,
            "analysis_time": time.time(),
        }

    def _analyze_one(self, url: str) -> dict[str, Any]:
        platform = platform_from_url(url)
        target = url
        spotify_meta: dict[str, str] = {}
        if is_spotify_url(url):
            kind = spotify_kind(url)
            if kind in {"playlist", "album"}:
                collection = resolve_spotify_collection(url)
                tracks = list(collection["tracks"])
                return {
                    "title": collection["title"],
                    "duration": None,
                    "platform": "Spotify",
                    "target": url,
                    "original_url": url,
                    "thumbnail": self._download_thumbnail(str(collection.get("cover") or "")),
                    "direct_media": False,
                    "is_playlist": True,
                    "playlist_count": len(tracks),
                    "collection_kind": str(collection["kind"]),
                    "media_id": str(collection["id"]),
                    "spotify_tracks": tracks,
                    "playlist_entries": [
                        {
                            "index": int(track.get("position") or index),
                            "title": str(track.get("title") or self._t("generic.track", index=index)),
                            "duration": None,
                        }
                        for index, track in enumerate(tracks, start=1)
                    ],
                    "selected_indices": [
                        int(track.get("position") or index)
                        for index, track in enumerate(tracks, start=1)
                    ],
                }
            spotify_meta = resolve_spotify_track_info(url)
            target = spotify_meta["query"]

        command = [
            self._find_yt_dlp() or "yt-dlp",
            "-J",
            "--flat-playlist",
            "--no-warnings",
            *(["--impersonate", "chrome"] if platform == "TikTok" else []),
            *self._js_runtime_arguments(),
            "--",
            target,
        ]
        completed = self._run_capture_with_engine_fallback(command, timeout=180)
        direct_media = False
        is_playlist = False
        if completed.returncode and platform == "TikTok":
            self.events.put(("analysis_status", self._t("analysis.tiktok_retry")))
            raw_info = self._resolve_tiktok_fallback(url)
            target = str(raw_info["direct_url"])
            direct_media = True
        else:
            if completed.returncode:
                raise RuntimeError(self._last_error(completed.stderr or completed.stdout))
            raw_info = json.loads(completed.stdout)
            is_playlist = bool(
                raw_info
                and raw_info.get("_type") in {"playlist", "multi_video"}
                and platform != "Spotify"
            )
            if raw_info and raw_info.get("entries") and not is_playlist:
                raw_info = next((entry for entry in raw_info["entries"] if entry), raw_info)
        if not raw_info or not isinstance(raw_info, dict):
            raise RuntimeError(self._t("analysis.no_media"))

        raw_entries = [entry for entry in (raw_info.get("entries") or []) if isinstance(entry, dict)]
        playlist_entries: list[dict[str, Any]] = []
        for index, entry in enumerate(raw_entries, start=1):
            entry_id = str(entry.get("id") or "")
            entry_target = str(entry.get("webpage_url") or entry.get("url") or "")
            if platform == "YouTube" and entry_id:
                entry_target = f"https://www.youtube.com/watch?v={entry_id}"
            playlist_entries.append(
                {
                    "index": int(entry.get("playlist_index") or index),
                    "title": str(entry.get("title") or self._t("generic.video", index=index)),
                    "duration": entry.get("duration"),
                    "target": entry_target,
                    "media_id": entry_id,
                }
            )
        first_entry = raw_entries[0] if raw_entries else {}
        thumbnail_url = str(
            spotify_meta.get("cover")
            or raw_info.get("thumbnail")
            or raw_info.get("cover")
            or first_entry.get("thumbnail")
            or ""
        )
        title = spotify_meta.get("display") or str(raw_info.get("title") or self._t("generic.untitled"))
        count = len(playlist_entries) or raw_info.get("playlist_count") or raw_info.get("n_entries")
        return {
            "title": title,
            "duration": raw_info.get("duration"),
            "platform": platform,
            "target": target if direct_media else (url if is_playlist else raw_info.get("webpage_url") or target),
            "original_url": url,
            "thumbnail": self._download_thumbnail(thumbnail_url),
            "direct_media": direct_media,
            "is_playlist": bool(not direct_media and is_playlist),
            "playlist_count": count,
            "playlist_entries": playlist_entries,
            "selected_indices": [entry["index"] for entry in playlist_entries],
            "media_id": str(raw_info.get("id") or "video"),
            "spotify_metadata": spotify_meta,
            "analysis_info": raw_info if not is_playlist and not direct_media else {},
            "analysis_time": time.time(),
        }

    @staticmethod
    def _download_thumbnail(url: str) -> bytes:
        if not url:
            return b""
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read(3_000_000)
        except Exception:
            return b""

    @staticmethod
    def _resolve_tiktok_fallback(url: str) -> dict[str, Any]:
        """Resolve a public TikTok while the upstream yt-dlp extractor is broken."""
        boundary = f"----BI3LMediaDownloader{int(time.time() * 1000)}"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="url"\r\n\r\n'
            f"{url}\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        request = urllib.request.Request(
            "https://www.tikwm.com/api/video/task/submit",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("code") != 0 or not payload.get("data", {}).get("task_id"):
            raise RuntimeError(payload.get("msg") or "TikTok fallback rejected the link.")

        task_id = str(payload["data"]["task_id"])
        result_url = (
            "https://www.tikwm.com/api/video/task/result?task_id="
            + urllib.parse.quote(task_id, safe="")
        )
        for _attempt in range(12):
            result_request = urllib.request.Request(
                result_url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
            with urllib.request.urlopen(result_request, timeout=25) as response:
                result = json.loads(response.read().decode("utf-8"))
            data = result.get("data") or {}
            detail = data.get("detail") or {}
            if data.get("status") == 2 and detail.get("download_url"):
                direct_url = urllib.parse.urljoin(
                    "https://www.tikwm.com/",
                    str(detail["download_url"]),
                )
                parsed = urllib.parse.urlparse(direct_url)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise RuntimeError("TikTok fallback returned an invalid media link.")
                author = detail.get("author") or {}
                media_id = str(detail.get("id") or "video")
                author_name = str(author.get("unique_id") or "").strip()
                title = str(detail.get("title") or "").strip()
                if not title:
                    title = f"@{author_name} - TikTok {media_id}" if author_name else f"TikTok {media_id}"
                return {
                    "id": media_id,
                    "title": title,
                    "duration": detail.get("duration"),
                    "cover": detail.get("cover") or detail.get("cover_url"),
                    "direct_url": direct_url,
                }
            if result.get("code") not in {None, 0}:
                raise RuntimeError(result.get("msg") or "TikTok fallback failed.")
            time.sleep(1.5)
        raise RuntimeError("TikTok fallback took too long to process the video.")

    def _yt_dlp_candidate_paths(self) -> list[str]:
        app_dir = Path(__file__).resolve().parent
        candidates: list[str | None] = [
            str(app_dir / "tools" / "yt-dlp.exe"),
            str(Path.home() / ".ytDownloader" / "ytdlp.exe"),
            shutil.which("yt-dlp.exe"),
            shutil.which("yt-dlp"),
            str(Path(sys.executable).with_name("yt-dlp.exe")),
            str(app_dir / ".venv" / "Scripts" / "yt-dlp.exe"),
        ]
        paths: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            path = str(Path(candidate).resolve())
            normalized = path.casefold()
            if normalized not in seen and Path(path).is_file():
                seen.add(normalized)
                paths.append(path)
        return paths

    def _yt_dlp_version(self, executable: str) -> str:
        try:
            completed = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                creationflags=self._creation_flags(),
            )
            if completed.returncode == 0:
                return completed.stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            pass
        return "unknown"

    @staticmethod
    def _yt_dlp_version_key(version: str) -> tuple[int, ...]:
        values = tuple(int(value) for value in re.findall(r"\d+", version))
        return values or (0,)

    def _available_yt_dlp_engines(self, *, refresh: bool = False) -> list[tuple[str, str]]:
        cached = getattr(self, "_engine_cache", [])
        cached_at = float(getattr(self, "_engine_cache_time", 0.0))
        if cached and not refresh and time.time() - cached_at < 300:
            return [(path, version) for path, version in cached if Path(path).is_file()]
        discovered = [
            (path, self._yt_dlp_version(path))
            for path in self._yt_dlp_candidate_paths()
        ]
        app_tools = str((Path(__file__).resolve().parent / "tools" / "yt-dlp.exe").resolve()).casefold()
        discovered.sort(
            key=lambda item: (
                self._yt_dlp_version_key(item[1]),
                item[0].casefold() == app_tools,
            ),
            reverse=True,
        )
        self._engine_cache = discovered
        self._engine_cache_time = time.time()
        return discovered

    def _find_yt_dlp(self) -> str | None:
        engines = self._available_yt_dlp_engines()
        return engines[0][0] if engines else None

    def _engine_attempt_paths(self, preferred: str) -> list[str]:
        attempts = [preferred]
        for path, _version in getattr(self, "_engine_cache", []):
            if path.casefold() not in {item.casefold() for item in attempts} and Path(path).is_file():
                attempts.append(path)
        return attempts

    def _run_capture_with_engine_fallback(
        self,
        command: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        attempts = self._engine_attempt_paths(command[0])
        last_result: subprocess.CompletedProcess[str] | None = None
        last_error: Exception | None = None
        for attempt_number, engine in enumerate(attempts, start=1):
            attempt = list(command)
            attempt[0] = engine
            if attempt_number > 1:
                self.events.put(("analysis_status", self._t("analysis.retry_engine")))
            try:
                result = subprocess.run(
                    attempt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    creationflags=self._creation_flags(),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                last_error = exc
                continue
            last_result = result
            if result.returncode == 0:
                return result
        if last_result is not None:
            return last_result
        raise RuntimeError(str(last_error or self._t("analysis.engine_missing")))

    def _js_runtime_arguments(self) -> list[str]:
        app_dir = Path(__file__).resolve().parent
        candidates = [
            Path.home() / ".ytDownloader" / "node.exe",
            app_dir / "tools" / "node.exe",
            Path(shutil.which("node.exe") or shutil.which("node") or ""),
        ]
        for candidate in candidates:
            if candidate and candidate.is_file():
                return [
                    "--no-js-runtimes",
                    "--js-runtime",
                    f"node:{candidate}",
                ]
        return []

    @staticmethod
    def _ffmpeg_arguments() -> list[str]:
        working_app_ffmpeg = Path.home() / ".ytDownloader" / "ffmpeg" / "bin"
        if (working_app_ffmpeg / "ffmpeg.exe").is_file():
            return ["--ffmpeg-location", str(working_app_ffmpeg)]

        try:
            import imageio_ffmpeg

            return ["--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe()]
        except (ImportError, RuntimeError):
            return []

    @staticmethod
    def _creation_flags() -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)

    @staticmethod
    def _last_error(output: str) -> str:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        for line in reversed(lines):
            if "ERROR:" in line:
                return line.split("ERROR:", 1)[1].strip()
        return lines[-1] if lines else "yt-dlp could not read this link."

    @staticmethod
    def _format_duration(value: Any) -> str:
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            return ""
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"

    def _show_playlist_selector(
        self,
        info: dict[str, Any],
        *,
        return_to_queue: bool = False,
    ) -> None:
        self._clear_stage()
        self.playlist_info = info
        self.playlist_return_to_queue = return_to_queue
        entries = list(info.get("playlist_entries") or [])
        selected = set(info.get("selected_indices") or [entry.get("index") for entry in entries])
        self.playlist_variables = {}
        self.playlist_streaming = bool(info.get("streaming"))
        self.playlist_select_future = bool(entries) and len(selected) == len(entries)

        card = self._card(width=760, height=690)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            card,
            text=self._t("common.back"),
            width=92,
            height=34,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 11, "bold"),
            command=self._leave_playlist_selector,
        ).grid(row=0, column=0, sticky="w", padx=36, pady=(24, 16))

        heading = ctk.CTkFrame(card, fg_color="transparent")
        heading.grid(row=1, column=0, sticky="ew", padx=36)
        heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            heading,
            text=info.get("title") or self._t("details.playlist"),
            wraplength=470,
            justify="left",
            anchor="w",
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 18, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        self.playlist_count_label = ctk.CTkLabel(
            heading,
            text="",
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 11),
        )
        self.playlist_count_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        action_row = ctk.CTkFrame(heading, fg_color="transparent")
        action_row.grid(row=0, column=1, rowspan=2, sticky="e")
        select_all_button = ctk.CTkButton(
            action_row,
            text=self._t("common.select_all"),
            width=112 if self.language == "pt-BR" else 88,
            height=34,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            font=ctk.CTkFont(FONT, 11, "bold"),
        )
        select_all_button.grid(row=0, column=0, padx=(0, 7))
        clear_button = ctk.CTkButton(
            action_row,
            text=self._t("common.clear"),
            width=72,
            height=34,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            font=ctk.CTkFont(FONT, 11, "bold"),
        )
        clear_button.grid(row=0, column=1)

        self.playlist_listing = ctk.CTkScrollableFrame(
            card,
            height=420,
            fg_color=BG,
            border_width=1,
            border_color=BORDER,
            corner_radius=10,
            scrollbar_button_color=SURFACE_HOVER,
        )
        self.playlist_listing.grid(row=2, column=0, sticky="nsew", padx=36, pady=(18, 16))
        self.playlist_listing.grid_columnconfigure(1, weight=1)

        self.playlist_commit_button = ctk.CTkButton(
            card,
            text=self._t("common.continue"),
            height=50,
            corner_radius=BUTTON_RADIUS,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(FONT, 13, "bold"),
        )
        self.playlist_commit_button.grid(row=3, column=0, sticky="ew", padx=36, pady=(0, 24))

        select_all_button.configure(command=lambda: self._set_all_playlist_items(True))
        clear_button.configure(command=lambda: self._set_all_playlist_items(False))
        self.playlist_commit_button.configure(command=self._commit_playlist_selection)
        self._add_playlist_rows(entries, selected=selected)
        self._refresh_playlist_count()

    def _add_playlist_rows(
        self,
        entries: list[dict[str, Any]],
        *,
        selected: set[Any] | None = None,
    ) -> None:
        selected_values = selected or set()
        for entry in entries:
            row_number = len(self.playlist_variables)
            item_index = int(entry.get("index") or row_number + 1)
            is_selected = item_index in selected_values if selected is not None else self.playlist_select_future
            variable = tk.BooleanVar(value=is_selected)
            self.playlist_variables[item_index] = variable
            checkbox = ctk.CTkCheckBox(
                self.playlist_listing,
                text="",
                width=26,
                variable=variable,
                command=self._refresh_playlist_count,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                border_color=BORDER,
            )
            checkbox.grid(row=row_number, column=0, padx=(12, 4), pady=8)
            title = str(entry.get("title") or self._t("generic.item", index=item_index))
            duration = self._format_duration(entry.get("duration"))
            ctk.CTkLabel(
                self.playlist_listing,
                text=f"{item_index}.  {title}",
                wraplength=555,
                justify="left",
                anchor="w",
                text_color=TEXT,
                font=ctk.CTkFont(FONT, 12),
            ).grid(row=row_number, column=1, sticky="ew", padx=(4, 8), pady=8)
            if duration:
                ctk.CTkLabel(
                    self.playlist_listing,
                    text=duration,
                    text_color=DIM,
                    font=ctk.CTkFont(FONT, 10),
                ).grid(row=row_number, column=2, padx=(0, 12), pady=8)

    def _append_playlist_batch(self, payload: dict[str, Any]) -> None:
        entries = list(payload.get("entries") or [])
        if not entries or not self.playlist_streaming:
            return
        self.playlist_info.setdefault("playlist_entries", []).extend(entries)
        self._add_playlist_rows(entries)
        self._refresh_playlist_count()

    def _finish_playlist_stream(self, payload: dict[str, Any]) -> None:
        if not self.playlist_streaming:
            return
        self.worker = None
        self.playlist_streaming = False
        self.playlist_info["streaming"] = False
        loaded = int(payload.get("loaded") or len(self.playlist_variables))
        self.playlist_info["playlist_count"] = loaded
        self.playlist_info["thumbnail"] = payload.get("thumbnail") or b""
        self._refresh_playlist_count()

    def _set_all_playlist_items(self, value: bool) -> None:
        self.playlist_select_future = value
        for variable in self.playlist_variables.values():
            variable.set(value)
        self._refresh_playlist_count()

    def _refresh_playlist_count(self) -> None:
        chosen = sum(variable.get() for variable in self.playlist_variables.values())
        loaded = len(self.playlist_variables)
        expected = int(self.playlist_info.get("playlist_count") or 0)
        noun = self._t("playlist.item_singular" if chosen == 1 else "playlist.item_plural")
        self.playlist_commit_button.configure(
            text=self._t("playlist.continue_items", chosen=chosen, noun=noun),
            state="disabled" if self.playlist_streaming or not chosen else "normal",
        )
        if self.playlist_streaming:
            if expected:
                status = self._t(
                    "playlist.loading_selected",
                    loaded=loaded,
                    total=expected,
                    chosen=chosen,
                )
            else:
                status = self._t(
                    "playlist.loading_unknown",
                    loaded=loaded,
                    chosen=chosen,
                )
        else:
            status = self._t("playlist.selected", chosen=chosen, total=loaded)
        self.playlist_count_label.configure(text=status, text_color=MUTED)

    def _leave_playlist_selector(self) -> None:
        if self.playlist_streaming:
            self.cancel_event.set()
            if self.current_process and self.current_process.poll() is None:
                self.current_process.terminate()
        self.playlist_streaming = False
        self.playlist_info["streaming"] = False
        if self.playlist_return_to_queue:
            self._show_queue(self.pending_queue)
        else:
            self._show_home()

    def _commit_playlist_selection(self) -> None:
        self.playlist_info["selected_indices"] = [
            index for index, variable in self.playlist_variables.items() if variable.get()
        ]
        self.playlist_info["playlist_count"] = len(self.playlist_info["selected_indices"])
        if self.playlist_return_to_queue:
            self._show_queue(self.pending_queue)
        else:
            self._show_details(self.playlist_info)

    def _show_queue(self, items: list[dict[str, Any]]) -> None:
        self._clear_stage()
        self.pending_queue = items
        card = self._card(width=760, height=690)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            card,
            text=self._t("common.back"),
            width=92,
            height=34,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 11, "bold"),
            command=self._show_home,
        ).grid(row=0, column=0, sticky="w", padx=36, pady=(24, 16))
        ctk.CTkLabel(
            card,
            text=self._t("queue.title"),
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 19, "bold"),
        ).grid(row=1, column=0, sticky="w", padx=36)
        ctk.CTkLabel(
            card,
            text=self._t("queue.subtitle", count=len(items)),
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 11),
        ).grid(row=2, column=0, sticky="w", padx=36, pady=(4, 15))

        listing = ctk.CTkScrollableFrame(
            card,
            height=430,
            fg_color=BG,
            border_width=1,
            border_color=BORDER,
            corner_radius=10,
            scrollbar_button_color=SURFACE_HOVER,
        )
        listing.grid(row=3, column=0, sticky="nsew", padx=36)
        listing.grid_columnconfigure(1, weight=1)
        for row_number, info in enumerate(items):
            icon = self._platform_icon(str(info.get("platform") or "Website"), 22)
            ctk.CTkLabel(listing, text="" if icon else "•", image=icon, width=32).grid(
                row=row_number, column=0, padx=(12, 5), pady=10
            )
            text_frame = ctk.CTkFrame(listing, fg_color="transparent")
            text_frame.grid(row=row_number, column=1, sticky="ew", pady=10)
            ctk.CTkLabel(
                text_frame,
                text=str(info.get("title") or self._t("generic.untitled")),
                wraplength=465,
                justify="left",
                anchor="w",
                text_color=TEXT,
                font=ctk.CTkFont(FONT, 12, "bold"),
            ).pack(fill="x")
            selected_count = len(info.get("selected_indices") or [])
            summary = (
                self._t(
                    "queue.selected",
                    platform=self._platform_display(str(info.get("platform") or "Website")),
                    count=selected_count,
                )
                if info.get("is_playlist")
                else self._platform_display(str(info.get("platform") or "Website"))
            )
            ctk.CTkLabel(
                text_frame,
                text=summary,
                anchor="w",
                text_color=DIM,
                font=ctk.CTkFont(FONT, 10),
            ).pack(fill="x", pady=(3, 0))
            if info.get("is_playlist"):
                ctk.CTkButton(
                    listing,
                    text=self._t("queue.choose"),
                    width=76,
                    height=34,
                    corner_radius=BUTTON_RADIUS,
                    fg_color=SURFACE,
                    hover_color=SURFACE_HOVER,
                    border_width=1,
                    border_color=BORDER,
                    text_color=TEXT,
                    font=ctk.CTkFont(FONT, 10, "bold"),
                    command=lambda selected_info=info: self._show_playlist_selector(
                        selected_info, return_to_queue=True
                    ),
                ).grid(row=row_number, column=2, padx=(8, 12), pady=10)

        ctk.CTkButton(
            card,
            text=self._t("queue.continue"),
            height=50,
            corner_radius=BUTTON_RADIUS,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(FONT, 13, "bold"),
            command=lambda: self._show_details(
                {
                    "title": self._t("queue.ready", count=len(items)),
                    "duration": None,
                    "platform": "Queue",
                    "target": str(items[0].get("target") or "queue"),
                    "original_url": "",
                    "thumbnail": b"",
                    "direct_media": False,
                    "is_playlist": False,
                    "playlist_count": len(items),
                    "media_id": "queue",
                    "is_queue": True,
                    "queue_items": items,
                    "audio_only": all(item.get("platform") == "Spotify" for item in items),
                }
            ),
        ).grid(row=4, column=0, sticky="ew", padx=36, pady=(16, 24))

    def _show_details(self, info: dict[str, Any]) -> None:
        self._clear_stage()
        self.current_info = info
        self.download_target = info["target"]
        self.current_platform = info["platform"]
        self.format_value = (
            "MP3"
            if self.current_platform == "Spotify" or info.get("audio_only")
            else "MP4"
        )
        self.video_quality = "Best"
        self.audio_quality = "Best"
        self.video_no_audio = False
        self.video_buttons = {}
        self.audio_buttons = {}
        self.no_audio_button = None

        # Reserve the progress area before a download starts, so adding its
        # text and bar can never push them outside the fixed-height card.
        card = self._card(width=760, height=690)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=36, pady=(24, 0))
        top.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            top,
            text=self._t("common.back"),
            width=92,
            height=34,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 11, "bold"),
            command=self._go_back,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        thumbnail_frame = ctk.CTkFrame(top, width=136, height=78, fg_color=SURFACE, corner_radius=10)
        thumbnail_frame.grid(row=1, column=0, rowspan=3, sticky="nw", padx=(0, 18))
        thumbnail_frame.grid_propagate(False)
        if info.get("thumbnail"):
            try:
                image = Image.open(io.BytesIO(info["thumbnail"])).convert("RGB")
                self.thumbnail_image = ctk.CTkImage(light_image=image, dark_image=image, size=(136, 78))
                ctk.CTkLabel(thumbnail_frame, text="", image=self.thumbnail_image).place(relx=0.5, rely=0.5, anchor="center")
            except Exception:
                self._thumbnail_fallback(thumbnail_frame)
        else:
            self._thumbnail_fallback(thumbnail_frame)

        platform_colors = {
            "YouTube": "#ff2f45",
            "Instagram": "#be4dbe",
            "TikTok": "#2eabb2",
            "Spotify": "#1aaf5d",
            "Twitch": "#9146ff",
            "X": "#3b4358",
        }
        ctk.CTkLabel(
            top,
            text=self._platform_display(self.current_platform),
            height=25,
            padx=11,
            corner_radius=13,
            fg_color=platform_colors.get(self.current_platform, ACCENT),
            text_color="white",
            font=ctk.CTkFont(FONT, 10, "bold"),
        ).grid(row=1, column=1, sticky="w")
        ctk.CTkLabel(
            top,
            text=info["title"],
            wraplength=520,
            justify="left",
            anchor="w",
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 15, "bold"),
        ).grid(row=2, column=1, sticky="ew", pady=(7, 0))
        if info.get("is_queue"):
            detail_summary = self._t(
                "queue.summary",
                count=len(info.get("queue_items") or []),
            )
        elif info.get("is_playlist"):
            collection_label = self._t(
                "details.album"
                if info.get("collection_kind") == "album"
                else "details.playlist"
            )
            detail_summary = (
                self._t(
                    "details.collection_summary",
                    kind=collection_label,
                    count=info["playlist_count"],
                )
                if info.get("playlist_count")
                else collection_label
            )
        else:
            detail_summary = self._format_duration(info.get("duration"))
        ctk.CTkLabel(
            top,
            text=detail_summary,
            text_color=DIM,
            font=ctk.CTkFont(FONT, 11),
        ).grid(row=3, column=1, sticky="w", pady=(4, 0))

        options = ctk.CTkFrame(card, fg_color="transparent")
        options.grid(row=1, column=0, sticky="ew", padx=36, pady=(24, 0))
        options.grid_columnconfigure(0, weight=1)
        self._section_label(options, self._t("details.format"), 0)
        format_row = ctk.CTkFrame(options, fg_color="transparent")
        format_row.grid(row=1, column=0, sticky="ew", pady=(9, 18))
        format_row.grid_columnconfigure((0, 1), weight=1)
        self.mp4_button = ctk.CTkButton(
            format_row,
            text=self._t("details.mp4"),
            height=52,
            corner_radius=BUTTON_RADIUS,
            font=ctk.CTkFont(FONT, 13, "bold"),
            command=lambda: self._select_format("MP4"),
        )
        self.mp4_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.mp3_button = ctk.CTkButton(
            format_row,
            text=self._t("details.mp3"),
            height=52,
            corner_radius=BUTTON_RADIUS,
            font=ctk.CTkFont(FONT, 13, "bold"),
            command=lambda: self._select_format("MP3"),
        )
        self.mp3_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        self.video_quality_label = self._section_label(options, self._t("details.video_quality"), 2)
        self.video_quality_row = ctk.CTkFrame(options, fg_color="transparent")
        self.video_quality_row.grid(row=3, column=0, sticky="w", pady=(9, 18))
        for index, quality in enumerate(("Best", "2160p", "1440p", "1080p", "720p", "480p", "360p")):
            button = self._quality_button(self.video_quality_row, quality, lambda value=quality: self._select_video(value))
            button.grid(row=0, column=index, padx=(0, 7))
            self.video_buttons[quality] = button

        self._section_label(options, self._t("details.audio_quality"), 4)
        audio_row = ctk.CTkFrame(options, fg_color="transparent")
        audio_row.grid(row=5, column=0, sticky="w", pady=(9, 0))
        for column, quality in enumerate(("Best", "320 kbps", "256 kbps", "192 kbps", "128 kbps")):
            button = self._quality_button(audio_row, quality, lambda value=quality: self._select_audio(value))
            button.grid(row=0, column=column, padx=(0, 7))
            self.audio_buttons[quality] = button
        self.no_audio_button = ctk.CTkButton(
            audio_row,
            text=self._t("details.no_audio"),
            width=96,
            height=40,
            corner_radius=BUTTON_RADIUS,
            border_width=1,
            font=ctk.CTkFont(FONT, 11, "bold"),
            command=self._select_no_audio,
        )
        self.no_audio_button.grid(row=0, column=5)

        bottom = ctk.CTkFrame(card, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=36, pady=(24, 26))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, minsize=46)
        bottom.grid_rowconfigure(2, minsize=7)
        self.download_button = ctk.CTkButton(
            bottom,
            text=self._t("details.download"),
            height=52,
            corner_radius=BUTTON_RADIUS,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(FONT, 14, "bold"),
            command=self._download_or_cancel,
        )
        self.download_button.grid(row=0, column=0, sticky="ew")
        self.progress = ctk.CTkProgressBar(bottom, height=7, corner_radius=4, fg_color=SURFACE, progress_color=ACCENT)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew")
        self.status_label = ctk.CTkLabel(
            bottom,
            text="",
            height=36,
            anchor="w",
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 11),
        )
        self.status_label.configure(wraplength=670, justify="left")
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(7, 3))
        # Keep the room reserved without showing an empty progress area.
        self.status_label.grid_remove()
        self.progress.grid_remove()

        if self.current_platform == "Spotify" or info.get("audio_only"):
            self.mp4_button.configure(state="disabled")
        self._refresh_selection_styles()

    def _go_back(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_DISPLAY_NAME, self._t("details.cancel_active"))
            return
        if self.current_info.get("is_queue") and self.pending_queue:
            self._show_queue(self.pending_queue)
        elif self.current_info.get("is_playlist"):
            self._show_playlist_selector(self.current_info)
        else:
            self._show_home()

    def _thumbnail_fallback(self, parent: ctk.CTkFrame) -> None:
        icon = self._platform_icon(self.current_platform, 34)
        ctk.CTkLabel(
            parent,
            text="" if icon else self._platform_display(self.current_platform),
            image=icon,
            text_color=DIM,
            font=ctk.CTkFont(FONT, 12, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _section_label(self, parent: ctk.CTkFrame, text: str, row: int) -> ctk.CTkLabel:
        label = ctk.CTkLabel(parent, text=text, text_color=MUTED, font=ctk.CTkFont(FONT, 11, "bold"))
        label.grid(row=row, column=0, sticky="w")
        return label

    def _quality_button(self, parent: ctk.CTkFrame, text: str, command: Any) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=self._t("details.best") if text == "Best" else text,
            width=130 if text == "Best" and self.language == "pt-BR" else 112 if text == "Best" else 82,
            height=40,
            corner_radius=BUTTON_RADIUS,
            border_width=1,
            font=ctk.CTkFont(FONT, 11, "bold"),
            command=command,
        )

    def _select_format(self, value: str) -> None:
        if (self.current_platform == "Spotify" or self.current_info.get("audio_only")) and value == "MP4":
            return
        self.format_value = value
        self._refresh_selection_styles()

    def _select_video(self, value: str) -> None:
        if self.format_value == "MP4":
            self.video_quality = value
            self._refresh_selection_styles()

    def _select_audio(self, value: str) -> None:
        self.audio_quality = value
        self.video_no_audio = False
        self._refresh_selection_styles()

    def _select_no_audio(self) -> None:
        if self.format_value != "MP4":
            return
        self.video_no_audio = True
        self._refresh_selection_styles()

    def _style_selectable(self, button: ctk.CTkButton, selected: bool, enabled: bool = True) -> None:
        if not enabled:
            button.configure(state="disabled", fg_color=CARD, border_color=SURFACE, text_color="#5c5f66")
        elif selected:
            button.configure(state="normal", fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=ACCENT, text_color="white")
        else:
            button.configure(state="normal", fg_color=SURFACE, hover_color=SURFACE_HOVER, border_color=BORDER, text_color=MUTED)

    def _refresh_selection_styles(self) -> None:
        can_mp4 = self.current_platform != "Spotify" and not self.current_info.get("audio_only")
        self._style_selectable(self.mp4_button, self.format_value == "MP4", can_mp4)
        self._style_selectable(self.mp3_button, self.format_value == "MP3")
        if self.format_value == "MP4":
            self.video_quality_label.grid()
            self.video_quality_row.grid()
        else:
            self.video_quality_label.grid_remove()
            self.video_quality_row.grid_remove()
        for quality, button in self.video_buttons.items():
            self._style_selectable(button, quality == self.video_quality)
        for quality, button in self.audio_buttons.items():
            self._style_selectable(
                button,
                quality == self.audio_quality
                and (self.format_value == "MP3" or not self.video_no_audio),
            )
        if self.no_audio_button is not None:
            if self.format_value == "MP4":
                self.no_audio_button.grid()
                self._style_selectable(self.no_audio_button, self.video_no_audio)
            else:
                self.no_audio_button.grid_remove()

    def _download_or_cancel(self) -> None:
        if self.worker and self.worker.is_alive():
            self.cancel_event.set()
            self._terminate_current_process()
            self.download_button.configure(text=self._t("download.cancelling"), state="disabled")
        else:
            self._start_download()

    def _start_download(self) -> None:
        if not self.download_target:
            return
        output = Path(self.output_var.get()).expanduser()
        output.mkdir(parents=True, exist_ok=True)
        self.settings.output_dir = str(output)
        self.settings.media_format = self.format_value
        self.settings.video_quality = self.video_quality
        self.settings.audio_quality = self.audio_quality
        self.settings.also_audio = self.also_audio_var.get()
        save_settings(self.settings)

        self.cancel_event.clear()
        self.download_button.configure(
            text=self._t("download.cancel"),
            fg_color="#41303a",
            hover_color="#563943",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(12, 5))
        self.progress.grid(row=2, column=0, sticky="ew")
        self.status_label.configure(text=self._t("download.starting"), text_color=MUTED)
        settings_snapshot = DownloadSettings(**vars(self.settings))
        settings_snapshot.video_no_audio = self.video_no_audio
        self.worker = threading.Thread(
            target=self._download_worker,
            args=(dict(self.current_info), self.format_value, settings_snapshot),
            daemon=True,
        )
        self.worker.start()

    def _download_worker(
        self,
        info: dict[str, Any],
        selected_format: str,
        settings: DownloadSettings,
    ) -> None:
        temporary_directory: Any = None
        try:
            try:
                temporary_directory = tempfile.TemporaryDirectory(
                    prefix="BI3LMediaDownloader-"
                )
                self.active_temp_dir = temporary_directory.name
            except OSError:
                self.active_temp_dir = ""
            items = list(info.get("queue_items") or [info])
            failures = 0
            saved = 0
            completion_message: str | None = None
            for queue_index, item in enumerate(items, start=1):
                if self.cancel_event.is_set():
                    raise InterruptedError()
                item_title = str(item.get("title") or self._t("generic.item", index=queue_index))
                item_format = "MP3" if item.get("platform") == "Spotify" else selected_format
                if len(items) > 1:
                    self.events.put(("item_started", f"{queue_index}/{len(items)} · {item_title}"))
                try:
                    item_message = self._download_info(
                        item,
                        item_format,
                        settings,
                        queue_index=queue_index if len(items) > 1 else None,
                        queue_count=len(items) if len(items) > 1 else None,
                    )
                    if len(items) == 1 and item_message:
                        completion_message = item_message
                    saved += 1
                except InterruptedError:
                    raise
                except Exception as exc:
                    failures += 1
                    error = localize_known_error(self.language, str(exc)) or self._t("download.failed")
                    if len(items) == 1:
                        raise RuntimeError(error) from exc
                    self.events.put(
                        (
                            "status",
                            self._t(
                                "download.skipped",
                                current=queue_index,
                                total=len(items),
                                title=item_title,
                            ),
                        )
                    )
            if not saved:
                raise RuntimeError(self._t("download.none_saved"))
            if failures:
                message = self._t("download.queue_partial", saved=saved, total=len(items))
            elif len(items) > 1:
                message = self._t("download.queue_complete", saved=saved)
            else:
                message = completion_message
            self.events.put(("download_done", message))
        except InterruptedError:
            self.events.put(("download_cancelled", None))
        except Exception as exc:
            message = localize_known_error(self.language, str(exc))
            self.events.put(("download_error", message or self._t("download.failed")))
        finally:
            self.active_temp_dir = ""
            if temporary_directory is not None:
                try:
                    temporary_directory.cleanup()
                except OSError:
                    pass

    def _download_info(
        self,
        info: dict[str, Any],
        selected_format: str,
        settings: DownloadSettings,
        *,
        queue_index: int | None = None,
        queue_count: int | None = None,
    ) -> str | None:
        spotify_tracks = list(info.get("spotify_tracks") or [])
        if spotify_tracks:
            selected = set(info.get("selected_indices") or [])
            if selected:
                spotify_tracks = [
                    track
                    for track in spotify_tracks
                    if int(track.get("position") or 0) in selected
                ]
            return self._download_spotify_collection(
                spotify_tracks,
                settings,
                str(info.get("title") or self._t("generic.spotify_collection")),
            )

        spotify_meta = dict(info.get("spotify_metadata") or {})
        if spotify_meta:
            self._download_spotify_track(info, spotify_meta, settings)
            return None

        target = str(info.get("target") or "")
        is_playlist = bool(info.get("is_playlist"))
        selected_indices = [int(index) for index in (info.get("selected_indices") or [])]
        display_title = str(info.get("title") or "Media")
        direct_entries = [
            entry
            for entry in list(info.get("playlist_entries") or [])
            if isinstance(entry, dict) and str(entry.get("target") or "").startswith(("http://", "https://"))
        ]
        if is_playlist and info.get("platform") == "YouTube" and direct_entries:
            return self._download_direct_playlist_entries(
                info,
                direct_entries,
                selected_format,
                settings,
            )
        analysis_info = dict(info.get("analysis_info") or {})
        analysis_time = float(info.get("analysis_time") or 0.0)
        if not analysis_time or time.time() - analysis_time > 900:
            analysis_info = {}
        stage_key = "download.downloading_audio" if selected_format == "MP3" else "download.downloading_video"
        self.events.put(("status", f"{display_title} · {self._t(stage_key)}"))
        command = self._download_command(
            target,
            selected_format,
            settings,
            direct_media=bool(info.get("direct_media")),
            is_playlist=is_playlist,
            display_title=display_title,
            media_id=str(info.get("media_id") or "video"),
            playlist_items=selected_indices,
            info_json=analysis_info,
        )
        run_context = {
            "context_title": "" if is_playlist else display_title,
            "context_index": None if is_playlist else queue_index,
            "context_count": None if is_playlist else queue_count,
        }
        fresh_command = None
        if analysis_info:
            fresh_command = self._download_command(
                target,
                selected_format,
                settings,
                direct_media=bool(info.get("direct_media")),
                is_playlist=is_playlist,
                display_title=display_title,
                media_id=str(info.get("media_id") or "video"),
                playlist_items=selected_indices,
            )
        self._run_cached_or_fresh(command, fresh_command, **run_context)
        if selected_format == "MP4" and settings.also_audio:
            self.events.put(("status", self._t("download.creating_mp3")))
            audio_command = self._download_command(
                target,
                "MP3",
                settings,
                audio_suffix=" [audio]",
                direct_media=bool(info.get("direct_media")),
                is_playlist=is_playlist,
                display_title=display_title,
                media_id=str(info.get("media_id") or "video"),
                playlist_items=selected_indices,
                info_json=analysis_info,
            )
            fresh_audio_command = None
            if analysis_info:
                fresh_audio_command = self._download_command(
                    target,
                    "MP3",
                    settings,
                    audio_suffix=" [audio]",
                    direct_media=bool(info.get("direct_media")),
                    is_playlist=is_playlist,
                    display_title=display_title,
                    media_id=str(info.get("media_id") or "video"),
                    playlist_items=selected_indices,
                )
            self._run_cached_or_fresh(
                audio_command,
                fresh_audio_command,
                **run_context,
            )
        return None

    def _run_cached_or_fresh(
        self,
        command: list[str],
        fresh_command: list[str] | None,
        *,
        context_title: str = "",
        context_index: int | None = None,
        context_count: int | None = None,
    ) -> None:
        try:
            self._run_yt_dlp(
                command,
                context_title=context_title,
                context_index=context_index,
                context_count=context_count,
            )
        except RuntimeError:
            if fresh_command is None:
                raise
            self.events.put(("status", self._t("download.refreshing_link")))
            self._run_yt_dlp(
                fresh_command,
                context_title=context_title,
                context_index=context_index,
                context_count=context_count,
            )

    def _download_direct_playlist_entries(
        self,
        info: dict[str, Any],
        entries: list[dict[str, Any]],
        selected_format: str,
        settings: DownloadSettings,
    ) -> str:
        selected = {int(index) for index in (info.get("selected_indices") or [])}
        chosen = [
            entry
            for entry in entries
            if not selected or int(entry.get("index") or 0) in selected
        ]
        if not chosen:
            raise RuntimeError(self._t("download.none_saved"))
        folder = self._safe_filename(
            str(info.get("title") or self._t("details.playlist")),
            self._t("details.playlist"),
        )
        total = len(chosen)
        failures = 0
        for item_number, entry in enumerate(chosen, start=1):
            if self.cancel_event.is_set():
                raise InterruptedError()
            title = str(entry.get("title") or self._t("generic.video", index=item_number))
            original_index = int(entry.get("index") or item_number)
            target = str(entry.get("target") or "")
            self.events.put(("item_started", f"{item_number}/{total} · {title}"))
            stage_key = "download.downloading_audio" if selected_format == "MP3" else "download.downloading_video"
            self.events.put(("status", f"{item_number}/{total} · {title} · {self._t(stage_key)}"))
            template = f"{folder}/{original_index:03d} - %(title)s [%(id)s].%(ext)s"
            command = self._download_command(
                target,
                selected_format,
                settings,
                output_template=template,
            )
            try:
                self._run_yt_dlp(
                    command,
                    context_title=title,
                    context_index=item_number,
                    context_count=total,
                )
                if selected_format == "MP4" and settings.also_audio:
                    self.events.put(
                        (
                            "status",
                            f"{item_number}/{total} · {title} · {self._t('download.creating_mp3')}",
                        )
                    )
                    audio_command = self._download_command(
                        target,
                        "MP3",
                        settings,
                        audio_suffix=" [audio]",
                        output_template=template,
                    )
                    self._run_yt_dlp(
                        audio_command,
                        context_title=title,
                        context_index=item_number,
                        context_count=total,
                    )
            except RuntimeError:
                failures += 1
                self.events.put(
                    (
                        "status",
                        self._t(
                            "download.skipped",
                            current=item_number,
                            total=total,
                            title=title,
                        ),
                    )
                )
        if failures == total:
            raise RuntimeError(self._t("download.playlist_failed"))
        if failures:
            return self._t("download.playlist_partial", saved=total - failures, total=total)
        return self._t("download.playlist_complete", saved=total)

    @staticmethod
    def _safe_filename(value: str, fallback: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" ._")
        return (safe or fallback)[:140]

    def _download_spotify_collection(
        self,
        tracks: list[dict[str, Any]],
        settings: DownloadSettings,
        collection_title: str,
    ) -> str:
        folder = self._safe_filename(collection_title, self._t("generic.spotify_collection"))
        total = len(tracks)
        failures = 0
        for item_number, track in enumerate(tracks, start=1):
            if self.cancel_event.is_set():
                raise InterruptedError()
            title = str(track.get("title") or self._t("generic.track", index=item_number))
            artists = str(track.get("artists") or "").strip()
            display = f"{title} — {artists}" if artists else title
            self.events.put(("item_started", f"{item_number}/{total} · {display}"))
            safe_title = self._safe_filename(
                title,
                self._t("generic.track", index=item_number),
            )
            safe_artists = self._safe_filename(artists, "") if artists else ""
            artist_suffix = f" - {safe_artists}" if safe_artists else ""
            position = int(track.get("position") or item_number)
            template = f"{folder}/{position:03d} - {safe_title}{artist_suffix}.%(ext)s"
            self.events.put(
                (
                    "status",
                    f"{item_number}/{total} · {display} · {self._t('download.downloading_audio')}",
                )
            )
            command = self._download_command(
                str(track["query"]),
                "MP3",
                settings,
                output_template=template,
            )
            try:
                self._run_yt_dlp(
                    command,
                    context_title=display,
                    context_index=item_number,
                    context_count=total,
                )
                output_path = (
                    Path(settings.output_dir).expanduser()
                    / folder
                    / f"{position:03d} - {safe_title}{artist_suffix}.mp3"
                )
                self.events.put(
                    (
                        "status",
                        f"{item_number}/{total} · {display} · {self._t('download.tagging')}",
                    )
                )
                self._apply_spotify_metadata(
                    output_path,
                    title=title,
                    artist=artists,
                    album=str(track.get("album") or collection_title),
                    cover_url=str(track.get("cover") or ""),
                )
            except RuntimeError:
                failures += 1
                self.events.put(
                    (
                        "status",
                        self._t(
                            "download.skipped",
                            current=item_number,
                            total=total,
                            title=display,
                        ),
                    )
                )
        if failures == total:
            raise RuntimeError(self._t("download.collection_failed"))
        if failures:
            return self._t(
                "download.collection_partial",
                saved=total - failures,
                total=total,
            )
        return self._t("download.collection_complete", saved=total)

    def _download_spotify_track(
        self,
        info: dict[str, Any],
        metadata: dict[str, str],
        settings: DownloadSettings,
    ) -> None:
        title = str(metadata.get("title") or info.get("title") or self._t("generic.spotify_track"))
        artists = str(metadata.get("artists") or "")
        safe_title = self._safe_filename(title, self._t("generic.spotify_track"))
        safe_artists = self._safe_filename(artists, "") if artists else ""
        artist_suffix = f" - {safe_artists}" if safe_artists else ""
        template = f"Spotify/{safe_title}{artist_suffix}.%(ext)s"
        self.events.put(("status", f"{title} · {self._t('download.downloading_audio')}"))
        command = self._download_command(
            str(info.get("target") or metadata.get("query") or ""),
            "MP3",
            settings,
            output_template=template,
        )
        self._run_yt_dlp(command, context_title=str(metadata.get("display") or title))
        output_path = (
            Path(settings.output_dir).expanduser()
            / "Spotify"
            / f"{safe_title}{artist_suffix}.mp3"
        )
        self.events.put(("status", f"{title} · {self._t('download.tagging')}"))
        self._apply_spotify_metadata(
            output_path,
            title=title,
            artist=artists,
            album=str(metadata.get("album") or title),
            cover_url=str(metadata.get("cover") or ""),
        )

    @staticmethod
    def _find_ffmpeg_path() -> str | None:
        working = Path.home() / ".ytDownloader" / "ffmpeg" / "bin" / "ffmpeg.exe"
        if working.is_file():
            return str(working)
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            return shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")

    def _apply_spotify_metadata(
        self,
        audio_path: Path,
        *,
        title: str,
        artist: str,
        album: str,
        cover_url: str,
    ) -> None:
        ffmpeg = self._find_ffmpeg_path()
        if not ffmpeg or not audio_path.is_file():
            return
        tagged_path = audio_path.with_name(audio_path.stem + ".tagged.mp3")
        cover_path = audio_path.with_name(audio_path.stem + ".cover.jpg")
        try:
            cover_ready = False
            if cover_url:
                request = urllib.request.Request(cover_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(request, timeout=20) as response:
                    cover_path.write_bytes(response.read(8_000_000))
                cover_ready = cover_path.is_file() and cover_path.stat().st_size > 0
            command = [ffmpeg, "-y", "-i", str(audio_path)]
            if cover_ready:
                command.extend(["-i", str(cover_path), "-map", "0:a", "-map", "1:v", "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic"])
            else:
                command.extend(["-map", "0:a", "-c:a", "copy"])
            command.extend(
                [
                    "-id3v2_version",
                    "3",
                    "-metadata",
                    f"title={title}",
                    "-metadata",
                    f"artist={artist}",
                    "-metadata",
                    f"album={album}",
                    str(tagged_path),
                ]
            )
            completed = subprocess.run(
                command,
                capture_output=True,
                creationflags=self._creation_flags(),
                timeout=90,
            )
            if completed.returncode == 0 and tagged_path.is_file():
                tagged_path.replace(audio_path)
        except Exception:
            # Metadata is a finishing step; never discard a successfully saved MP3.
            pass
        finally:
            for temporary in (tagged_path, cover_path):
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

    def _write_cached_info_json(self, payload: dict[str, Any]) -> Path | None:
        temporary_root = str(getattr(self, "active_temp_dir", "") or "")
        if not temporary_root or not payload:
            return None
        try:
            path = Path(temporary_root) / f"analysis-{time.time_ns()}.info.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            return path
        except (OSError, TypeError, ValueError):
            return None

    def _download_command(
        self,
        target: str,
        selected_format: str,
        settings: DownloadSettings,
        *,
        audio_suffix: str = "",
        direct_media: bool = False,
        is_playlist: bool = False,
        display_title: str = "",
        media_id: str = "",
        output_template: str = "",
        playlist_items: list[int] | None = None,
        info_json: dict[str, Any] | None = None,
    ) -> list[str]:
        executable = self._find_yt_dlp()
        if not executable:
            raise RuntimeError(self._t("analysis.engine_missing"))

        if output_template:
            template = output_template
        elif direct_media:
            safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", display_title).strip(" ._")
            safe_id = re.sub(r"[^A-Za-z0-9_-]", "", media_id) or "video"
            template = f"{(safe_title or 'TikTok video')[:140]} [{safe_id}].%(ext)s"
        elif is_playlist:
            template = "%(playlist_title)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
        else:
            template = settings.filename_template or "%(title)s [%(id)s].%(ext)s"
        if audio_suffix:
            stem, separator, extension = template.rpartition(".")
            template = f"{stem}{audio_suffix}.{extension}" if separator else f"{template}{audio_suffix}"

        command = [
            executable,
            "--newline",
            "--progress",
            "--progress-template",
            f"download:{PROGRESS_MARKER}%(info.playlist_index)s\t%(info.playlist_count)s\t%(info.title)s\t%(progress._percent_str)s\t%(progress._speed_str)s\t%(progress._eta_str)s\t%(progress._downloaded_bytes_str)s\t%(progress._total_bytes_str)s",
            "--retries",
            "10",
            "--fragment-retries",
            "10",
            "--concurrent-fragments",
            "4",
            "-P",
            str(Path(settings.output_dir).expanduser()),
            *(
                ["-P", f"temp:{self.active_temp_dir}"]
                if str(getattr(self, "active_temp_dir", "") or "")
                else []
            ),
            "-o",
            template,
            *([] if direct_media else self._js_runtime_arguments()),
            *self._ffmpeg_arguments(),
        ]

        if is_playlist:
            command.extend(["--yes-playlist", "--no-flat-playlist", "--ignore-errors"])
            if playlist_items:
                command.extend(["--playlist-items", ",".join(str(index) for index in playlist_items)])

        if selected_format == "MP3":
            command.extend(["-x", "--audio-format", "mp3", "--embed-metadata"])
            bitrate = re.search(r"(\d+)", settings.audio_quality)
            command.extend(["--audio-quality", f"{bitrate.group(1)}K" if bitrate else "0"])
        else:
            if settings.video_no_audio:
                command.extend(["--remux-video", "mp4"])
                if not direct_media:
                    height = re.search(r"(\d+)", settings.video_quality)
                    selector = (
                        f"bv*[height<={height.group(1)}]"
                        if height
                        else "bv*"
                    )
                    command.extend(["-f", selector])
                if getattr(sys, "frozen", False):
                    helper_parts = [sys.executable, "--strip-audio"]
                else:
                    helper = Path(__file__).resolve().parent / "strip_audio.py"
                    helper_parts = [sys.executable, str(helper)]
                helper_command = subprocess.list2cmdline(helper_parts)
                temp_argument = (
                    subprocess.list2cmdline([self.active_temp_dir])
                    if str(getattr(self, "active_temp_dir", "") or "")
                    else ""
                )
                command.extend(
                    [
                        "--exec",
                        f"after_move:{helper_command} %(filepath)q"
                        + (f" {temp_argument}" if temp_argument else ""),
                    ]
                )
            elif not direct_media:
                command.extend(["--merge-output-format", "mp4"])
                height = re.search(r"(\d+)", settings.video_quality)
                if height:
                    limit = height.group(1)
                    command.extend(
                        ["-f", f"bv*[height<={limit}]+ba/b[height<={limit}]"]
                    )
        cached_info_path = self._write_cached_info_json(info_json or {})
        if cached_info_path is not None:
            command.extend(["--load-info-json", str(cached_info_path)])
        else:
            command.extend(["--", target])
        return command

    def _terminate_current_process(self) -> None:
        """Stop yt-dlp and any FFmpeg/helper process it started."""
        process = self.current_process
        if process is None or process.poll() is not None:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=self._creation_flags(),
                )
            except (OSError, subprocess.SubprocessError):
                process.terminate()
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

    def _run_yt_dlp(
        self,
        command: list[str],
        *,
        context_title: str = "",
        context_index: int | None = None,
        context_count: int | None = None,
    ) -> None:
        attempts = self._engine_attempt_paths(command[0])
        last_error: RuntimeError | None = None
        for attempt_number, engine in enumerate(attempts, start=1):
            attempt = list(command)
            attempt[0] = engine
            if attempt_number > 1:
                self.events.put(("status", self._t("download.retry_engine")))
            try:
                self._run_yt_dlp_once(
                    attempt,
                    context_title=context_title,
                    context_index=context_index,
                    context_count=context_count,
                )
                return
            except (RuntimeError, OSError) as exc:
                last_error = exc if isinstance(exc, RuntimeError) else RuntimeError(str(exc))
        raise last_error or RuntimeError(self._t("download.failed"))

    def _run_yt_dlp_once(
        self,
        command: list[str],
        *,
        context_title: str = "",
        context_index: int | None = None,
        context_count: int | None = None,
    ) -> None:
        if self.cancel_event.is_set():
            raise InterruptedError()
        self.current_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=self._creation_flags(),
        )
        recent_lines: list[str] = []
        current_item: tuple[str, str] | None = None
        current_status_base = ""
        assert self.current_process.stdout is not None
        for raw_line in self.current_process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            recent_lines.append(line)
            recent_lines = recent_lines[-20:]
            if self.cancel_event.is_set():
                self._terminate_current_process()
                self.current_process = None
                raise InterruptedError()

            if PROGRESS_MARKER in line:
                progress_text = line.partition(PROGRESS_MARKER)[2]
                fields = progress_text.split("\t", 7)
                if len(fields) == 8:
                    (
                        raw_index,
                        raw_count,
                        raw_title,
                        raw_percent,
                        raw_speed,
                        raw_eta,
                        raw_downloaded,
                        raw_total,
                    ) = fields
                    title = context_title or raw_title.strip() or self._t("generic.downloading")
                    index = str(context_index) if context_index is not None else raw_index.strip()
                    count = str(context_count) if context_count is not None else raw_count.strip()
                    if index in {"", "NA", "None"}:
                        index = ""
                    if count in {"", "NA", "None"}:
                        count = ""
                    item_key = (index, title)
                    prefix = f"{index}/{count} · " if index and count else f"{index} · " if index else ""
                    short_title = title if len(title) <= 72 else title[:69] + "…"
                    current_status_base = f"{prefix}{short_title}"
                    if item_key != current_item:
                        current_item = item_key
                        self.events.put(("item_started", current_status_base))
                    percent_match = re.search(r"(\d+(?:\.\d+)?)%", raw_percent)
                    if percent_match:
                        percentage = max(0.0, min(100.0, float(percent_match.group(1))))
                        details = [f"{percentage:g}%"]
                        speed = raw_speed.strip()
                        eta = raw_eta.strip()
                        downloaded = raw_downloaded.strip()
                        total = raw_total.strip()
                        if speed not in {"", "NA", "None", "Unknown B/s"}:
                            details.append(speed)
                        if eta not in {"", "NA", "None", "Unknown"}:
                            details.append(f"ETA {eta}")
                        if downloaded not in {"", "NA", "None"} and total not in {"", "NA", "None"}:
                            details.append(f"{downloaded} / {total}")
                        self.events.put(
                            (
                                "progress",
                                (percentage / 100, f"{prefix}{short_title} · " + " · ".join(details)),
                            )
                        )
                    continue

            match = re.search(r"(\d+(?:\.\d+)?)%", line)
            if match:
                percentage = max(0.0, min(100.0, float(match.group(1))))
                detail = line.replace("[download]", "").strip()
                self.events.put(("progress", (percentage / 100, detail)))
            elif "Merging formats" in line:
                processing = self._t("download.merging")
                status = f"{current_status_base} · {processing}" if current_status_base else processing
                self.events.put(("status", status))
            elif "ExtractAudio" in line:
                processing = self._t("download.converting_mp3")
                status = f"{current_status_base} · {processing}" if current_status_base else processing
                self.events.put(("status", status))
            elif "Fixup" in line or "Post-process" in line:
                processing = self._t("download.processing")
                status = f"{current_status_base} · {processing}" if current_status_base else processing
                self.events.put(("status", status))
            elif "Downloading item" in line:
                self.events.put(("status", line.replace("[download]", "").strip()))

        return_code = self.current_process.wait()
        self.current_process = None
        if self.cancel_event.is_set():
            raise InterruptedError()
        if return_code:
            raise RuntimeError(self._last_error("\n".join(recent_lines)))

    def _open_settings(self) -> None:
        dialog = ctk.CTkToplevel(self, fg_color=BG)
        dialog.title(self._t("settings.title"))
        dialog.geometry("520x545")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        panel = ctk.CTkFrame(dialog, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        panel.pack(fill="both", expand=True, padx=22, pady=22)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=self._t("settings.title"), text_color=TEXT, font=ctk.CTkFont(FONT, 20, "bold")).grid(row=0, column=0, sticky="w", padx=24, pady=(23, 18))
        ctk.CTkLabel(panel, text=self._t("settings.save_folder"), text_color=MUTED, font=ctk.CTkFont(FONT, 10, "bold")).grid(row=1, column=0, sticky="w", padx=24)
        folder_row = ctk.CTkFrame(panel, fg_color="transparent")
        folder_row.grid(row=2, column=0, sticky="ew", padx=24, pady=(7, 15))
        folder_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(folder_row, textvariable=self.output_var, height=42, corner_radius=BUTTON_RADIUS, fg_color=SURFACE, border_color=BORDER).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(folder_row, text=self._t("settings.browse"), width=82, height=42, corner_radius=BUTTON_RADIUS, fg_color=SURFACE, hover_color=SURFACE_HOVER, border_width=1, border_color=BORDER, command=self._choose_folder).grid(row=0, column=1)
        ctk.CTkSwitch(panel, text=self._t("settings.also_mp3"), variable=self.also_audio_var, progress_color=ACCENT, text_color=TEXT, font=ctk.CTkFont(FONT, 12)).grid(row=3, column=0, sticky="w", padx=24, pady=(8, 6))

        ctk.CTkLabel(
            panel,
            text=self._t("settings.language"),
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 10, "bold"),
        ).grid(row=4, column=0, sticky="w", padx=24, pady=(16, 0))
        language_menu = ctk.CTkOptionMenu(
            panel,
            values=list(LANGUAGE_NAMES.values()),
            variable=self.language_var,
            height=40,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            button_color=SURFACE_HOVER,
            button_hover_color=BORDER,
            dropdown_fg_color=SURFACE,
            dropdown_hover_color=SURFACE_HOVER,
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 11),
            command=lambda value: self._change_language(value, dialog),
        )
        language_menu.grid(row=5, column=0, sticky="ew", padx=24, pady=(7, 0))

        ctk.CTkLabel(
            panel,
            text=self._t("settings.engine"),
            text_color=MUTED,
            font=ctk.CTkFont(FONT, 10, "bold"),
        ).grid(row=6, column=0, sticky="w", padx=24, pady=(16, 0))
        engine_row = ctk.CTkFrame(panel, fg_color="transparent")
        engine_row.grid(row=7, column=0, sticky="ew", padx=24, pady=(7, 0))
        engine_row.grid_columnconfigure(0, weight=1)
        cached_engines = list(getattr(self, "_engine_cache", []))
        selected_version = cached_engines[0][1] if cached_engines else ""
        self.engine_status_label = ctk.CTkLabel(
            engine_row,
            text=(
                self._t("settings.engine_ready", version=selected_version)
                if selected_version
                else self._t("settings.engine_checking")
            ),
            anchor="w",
            text_color=DIM,
            font=ctk.CTkFont(FONT, 10),
        )
        self.engine_status_label.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        if not selected_version:
            threading.Thread(
                target=self._detect_engine_version_worker,
                daemon=True,
            ).start()
        self.engine_update_button = ctk.CTkButton(
            engine_row,
            text=self._t("settings.update"),
            width=152 if self.language == "pt-BR" else 140,
            height=38,
            corner_radius=BUTTON_RADIUS,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=ctk.CTkFont(FONT, 10, "bold"),
            command=self._update_downloader,
        )
        self.engine_update_button.grid(row=0, column=1)
        ctk.CTkButton(
            panel,
            text=self._t("settings.save"),
            height=46,
            corner_radius=BUTTON_RADIUS,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(FONT, 12, "bold"),
            command=lambda: self._save_settings_dialog(dialog),
        ).grid(row=8, column=0, sticky="ew", padx=24, pady=(20, 22))

    def _change_language(self, display_name: str, dialog: ctk.CTkToplevel) -> None:
        selected = next(
            (code for code, name in LANGUAGE_NAMES.items() if name == display_name),
            "en",
        )
        if selected == self.language:
            return
        self.language = selected
        self.language_var.set(LANGUAGE_NAMES[selected])
        self.settings.language = selected
        save_settings(self.settings)
        dialog.destroy()
        self._show_home()
        self.after(80, self._open_settings)

    def _update_downloader(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_DISPLAY_NAME, self._t("settings.wait"))
            return
        self.engine_update_button.configure(state="disabled", text=self._t("settings.updating"))
        self.engine_status_label.configure(text=self._t("settings.downloading_engine"), text_color=MUTED)
        self.worker = threading.Thread(target=self._update_downloader_worker, daemon=True)
        self.worker.start()

    def _detect_engine_version_worker(self) -> None:
        try:
            engines = self._available_yt_dlp_engines(refresh=True)
            version = engines[0][1] if engines else "unknown"
            self.events.put(
                (
                    "engine_status_detected",
                    self._t("settings.engine_ready", version=version),
                )
            )
        except Exception:
            self.events.put(
                (
                    "engine_status_detected",
                    self._t("settings.engine_ready", version="unknown"),
                )
            )

    def _update_downloader_worker(self) -> None:
        try:
            app_dir = Path(__file__).resolve().parent
            bundled = app_dir / "tools" / "yt-dlp.exe"
            target = bundled
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name("yt-dlp.update.exe")
            request = urllib.request.Request(
                "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.exe",
                headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
            )
            try:
                import certifi
                import ssl

                ssl_context = ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                ssl_context = None
            with urllib.request.urlopen(request, timeout=120, context=ssl_context) as response:
                with temporary.open("wb") as destination:
                    shutil.copyfileobj(response, destination)
            if temporary.stat().st_size < 1_000_000:
                raise RuntimeError(self._t("settings.incomplete_engine"))
            temporary.replace(target)
            self._engine_cache = []
            self._engine_cache_time = 0.0
            self.events.put(("engine_update_done", self._t("settings.updated")))
        except Exception as exc:
            self.events.put(
                (
                    "engine_update_error",
                    localize_known_error(self.language, str(exc))
                    or self._t("settings.update_failed"),
                )
            )

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get())
        if selected:
            self.output_var.set(selected)

    def _save_settings_dialog(self, dialog: ctk.CTkToplevel) -> None:
        self.settings.output_dir = self.output_var.get()
        self.settings.also_audio = self.also_audio_var.get()
        self.settings.language = self.language
        save_settings(self.settings)
        dialog.destroy()

    def _process_events(self) -> None:
        processed = 0
        try:
            while processed < 25:
                kind, payload = self.events.get_nowait()
                processed += 1
                if kind == "analysis_batch_done":
                    self.worker = None
                    results = list(payload or [])
                    if len(results) == 1:
                        if results[0].get("is_playlist"):
                            self._show_playlist_selector(results[0])
                        else:
                            self._show_details(results[0])
                    elif results:
                        self._show_queue(results)
                elif kind == "playlist_stream_started":
                    self._show_playlist_selector(payload)
                elif kind == "playlist_stream_batch":
                    self._append_playlist_batch(payload)
                    # Yield to Tk after each UI batch so long playlists never
                    # create every checkbox in one blocking event-loop pass.
                    break
                elif kind == "playlist_stream_done":
                    self._finish_playlist_stream(payload)
                elif kind == "analysis_done":
                    self.worker = None
                    self._show_details(payload)
                elif kind == "analysis_status":
                    self.home_status.configure(text=str(payload), text_color=MUTED)
                elif kind == "analysis_error":
                    self.worker = None
                    if self.playlist_streaming:
                        self.playlist_streaming = False
                        self.playlist_info["streaming"] = False
                        self._refresh_playlist_count()
                        self.playlist_count_label.configure(text=str(payload), text_color=ERROR)
                    else:
                        self.continue_button.configure(
                            state="normal",
                            text=self._t("home.continue"),
                        )
                        self.home_status.configure(text=payload, text_color=ERROR)
                elif kind == "progress":
                    ratio, status = payload
                    self.progress.set(max(0.0, min(1.0, ratio)))
                    self.status_label.configure(text=status, text_color=MUTED)
                elif kind == "item_started":
                    self.progress.set(0)
                    self.status_label.configure(text=str(payload), text_color=MUTED)
                elif kind == "status":
                    self.status_label.configure(text=str(payload), text_color=MUTED)
                elif kind == "download_done":
                    self.worker = None
                    self.progress.set(1)
                    self.status_label.configure(
                        text=str(payload or self._t("download.complete")),
                        text_color=SUCCESS,
                    )
                    self.download_button.configure(
                        text=self._t("download.open_folder"),
                        state="normal",
                        fg_color=ACCENT,
                        hover_color=ACCENT_HOVER,
                        command=lambda: open_output_folder(self.output_var.get()),
                    )
                elif kind == "download_cancelled":
                    self.worker = None
                    self.status_label.configure(text=self._t("download.cancelled"), text_color=MUTED)
                    self.download_button.configure(text=self._t("details.download"), state="normal", fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._download_or_cancel)
                elif kind == "download_error":
                    self.worker = None
                    self.status_label.configure(text=payload, text_color=ERROR)
                    self.download_button.configure(text=self._t("download.try_again"), state="normal", fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._download_or_cancel)
                elif kind == "engine_update_done":
                    self.worker = None
                    try:
                        self.engine_status_label.configure(text=str(payload), text_color=SUCCESS)
                        self.engine_update_button.configure(state="normal", text=self._t("settings.update"))
                    except (AttributeError, tk.TclError):
                        pass
                elif kind == "engine_status_detected":
                    try:
                        self.engine_status_label.configure(text=str(payload), text_color=DIM)
                    except (AttributeError, tk.TclError):
                        pass
                elif kind == "engine_update_error":
                    self.worker = None
                    try:
                        self.engine_status_label.configure(text=str(payload), text_color=ERROR)
                        self.engine_update_button.configure(state="normal", text=self._t("download.try_again"))
                    except (AttributeError, tk.TclError):
                        pass
        except queue.Empty:
            pass
        self.after(100, self._process_events)

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_DISPLAY_NAME, self._t("close.active")):
                return
            self.cancel_event.set()
            self._terminate_current_process()
        try:
            self.settings.output_dir = self.output_var.get()
            self.settings.also_audio = self.also_audio_var.get()
            self.settings.language = self.language
            save_settings(self.settings)
        except OSError:
            pass
        self.destroy()


if __name__ == "__main__":
    if len(sys.argv) in {3, 4} and sys.argv[1] == "--strip-audio":
        workspace = Path(sys.argv[3]) if len(sys.argv) == 4 else None
        raise SystemExit(strip_audio(Path(sys.argv[2]), workspace))
    configure_windows_app_identity()
    MediaDownloader().mainloop()
