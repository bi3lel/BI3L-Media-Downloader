from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


APP_NAME = "BI3L Media Downloader"
APP_DISPLAY_NAME = APP_NAME
LEGACY_APP_NAMES = ("Downloader", "MediaDock")
APP_VERSION = "2.6.0"


@dataclass
class DownloadSettings:
    output_dir: str = str(Path.home() / "Downloads" / APP_NAME)
    media_format: str = "MP4"
    video_quality: str = "1080p"
    audio_quality: str = "320 kbps"
    also_audio: bool = False
    video_no_audio: bool = False
    language: str = "en"
    filename_template: str = "%(title)s [%(id)s].%(ext)s"


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME


def settings_file() -> Path:
    return app_data_dir() / "settings.json"


def legacy_settings_files() -> list[Path]:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [base / name / "settings.json" for name in LEGACY_APP_NAMES]


def load_settings() -> DownloadSettings:
    path = settings_file()
    if not path.is_file():
        path = next((candidate for candidate in legacy_settings_files() if candidate.is_file()), path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return DownloadSettings()

    valid = {item.name for item in fields(DownloadSettings)}
    filtered = {key: value for key, value in payload.items() if key in valid}
    try:
        return DownloadSettings(**filtered)
    except TypeError:
        return DownloadSettings()


def save_settings(settings: DownloadSettings) -> None:
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def split_urls(raw: str) -> list[str]:
    """Return unique HTTP(S) URLs while preserving the pasted order."""
    candidates = re.split(r"[\s,]+", raw.strip())
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = candidate.strip().strip("<>\"'")
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def platform_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    if host in {"drive.google.com", "docs.google.com"}:
        return "Google Drive"
    if host in {"youtu.be", "youtube.com", "music.youtube.com", "m.youtube.com"} or host.endswith(".youtube.com"):
        return "YouTube"
    if host == "instagram.com" or host.endswith(".instagram.com"):
        return "Instagram"
    if host == "tiktok.com" or host.endswith(".tiktok.com"):
        return "TikTok"
    if host == "twitch.tv" or host.endswith(".twitch.tv"):
        return "Twitch"
    if host in {"x.com", "twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):
        return "X"
    if host == "spotify.com" or host.endswith(".spotify.com"):
        return "Spotify"
    return "Website"


def is_spotify_url(url: str) -> bool:
    return platform_from_url(url) == "Spotify"


def spotify_kind(url: str) -> str:
    path_parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    if path_parts and path_parts[0].lower().startswith("intl-"):
        path_parts = path_parts[1:]
    return path_parts[0].lower() if path_parts else "unknown"


def _spotify_content_id(url: str, expected_kind: str) -> str:
    path_parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    if path_parts and path_parts[0].lower().startswith("intl-"):
        path_parts = path_parts[1:]
    if len(path_parts) < 2 or path_parts[0].lower() != expected_kind:
        raise ValueError(f"This is not a Spotify {expected_kind} link.")
    content_id = re.sub(r"[^A-Za-z0-9]", "", path_parts[1])
    if not content_id:
        raise ValueError("The Spotify link is missing its content ID.")
    return content_id


def _deep_find_track_list(value: Any, depth: int = 0) -> dict[str, Any] | None:
    if depth > 8:
        return None
    if isinstance(value, dict):
        if isinstance(value.get("trackList"), list):
            return value
        for child in value.values():
            found = _deep_find_track_list(child, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _deep_find_track_list(child, depth + 1)
            if found:
                return found
    return None


def resolve_spotify_collection(url: str, timeout: int = 30) -> dict[str, Any]:
    """Read public playlist/album metadata without accessing Spotify audio."""
    kind = spotify_kind(url)
    if kind not in {"playlist", "album"}:
        raise ValueError("Paste a Spotify playlist or album link.")
    content_id = _spotify_content_id(url, kind)
    embed_url = f"https://open.spotify.com/embed/{kind}/{content_id}"
    request = urllib.request.Request(
        embed_url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    )
    try:
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_context = ssl.create_default_context()

    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        page = response.read(15_000_000).decode("utf-8", errors="replace")
    match = re.search(
        r'<script[^>]*\bid=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Spotify did not return the public track list.")
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("Spotify returned an unreadable track list.") from exc

    entity = _deep_find_track_list(payload)
    if not entity:
        raise ValueError("Spotify did not expose tracks for this public collection.")

    collection_title = str(entity.get("name") or entity.get("title") or "Spotify collection")
    cover_url = ""
    sources = (entity.get("coverArt") or {}).get("sources") or []
    if sources and isinstance(sources[-1], dict):
        cover_url = str(sources[-1].get("url") or "")
    if not cover_url:
        images = (entity.get("visualIdentity") or {}).get("image") or []
        if images and isinstance(images[-1], dict):
            cover_url = str(images[-1].get("url") or "")

    tracks: list[dict[str, Any]] = []
    for position, item in enumerate(entity.get("trackList") or [], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        artists_value = item.get("subtitle") or item.get("artists") or ""
        if isinstance(artists_value, list):
            artists = ", ".join(
                str(artist.get("name") or "").strip()
                for artist in artists_value
                if isinstance(artist, dict) and artist.get("name")
            )
        else:
            artists = str(artists_value).strip()
        if not title:
            continue
        uri = str(item.get("uri") or "")
        track_id = uri.rsplit(":", 1)[-1] if uri.startswith("spotify:track:") else str(position)
        search_terms = " ".join(part for part in (title, artists, "official audio") if part)
        tracks.append(
            {
                "id": track_id,
                "position": position,
                "title": title,
                "artists": artists,
                "query": f"ytsearch8:{search_terms}",
                "duration": float(item.get("duration") or 0) / 1000,
                "album": collection_title,
                "cover": cover_url,
            }
        )
    if not tracks:
        raise ValueError("No public tracks were found in this Spotify collection.")
    return {
        "id": content_id,
        "kind": kind,
        "title": collection_title,
        "cover": cover_url,
        "tracks": tracks,
    }


def resolve_spotify_track_info(url: str, timeout: int = 15) -> dict[str, Any]:
    """Resolve public Spotify track metadata for a matching yt-dlp search.

    No Spotify audio stream is accessed. The returned query is intended to match
    the track against a source handled by yt-dlp.
    """
    kind = spotify_kind(url)
    if kind != "track":
        raise ValueError(
            "Paste a Spotify track, public playlist, or public album link."
        )

    track_id = _spotify_content_id(url, "track")
    try:
        return _spotify_embed_track(track_id, timeout)
    except (OSError, ValueError, KeyError, TypeError):
        # oEmbed can omit artists/duration. Such tracks MUST require selection.
        pass
    endpoint = "https://open.spotify.com/oembed?" + urllib.parse.urlencode({"url": url})
    request = urllib.request.Request(
        endpoint,
        headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
    )
    try:
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_context = ssl.create_default_context()

    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
        payload = json.loads(response.read().decode("utf-8"))

    title = str(payload.get("title", "")).strip()
    author = str(payload.get("author_name", "")).strip()
    if author.casefold() == "spotify":
        author = ""
    if not title:
        raise ValueError("Spotify did not return enough track metadata.")

    display = f"{title} — {author}" if author else title
    query = f"ytsearch8:{title} {author} official audio".strip()
    return {
        "query": query,
        "display": display,
        "title": title,
        "artists": author,
        "album": title,
        "cover": str(payload.get("thumbnail_url") or ""),
        "id": track_id,
        "duration": None,
    }


def _spotify_embed_track(track_id: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(f"https://open.spotify.com/embed/track/{track_id}",
                                     headers={"User-Agent": "Mozilla/5.0"})
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        page = response.read(15_000_000).decode("utf-8")
    match = re.search(r'<script[^>]*\bid=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', page, re.S)
    if not match:
        raise ValueError("Spotify track metadata unavailable")
    payload = json.loads(match.group(1))

    def find(value):
        if isinstance(value, dict):
            if value.get("uri") == f"spotify:track:{track_id}" and (value.get("artists") or value.get("subtitle")):
                return value
            for child in value.values():
                found = find(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find(child)
                if found:
                    return found
        return None

    entity = find(payload)
    if not entity:
        raise ValueError("Spotify did not return metadata for the requested track ID")
    title = str(entity.get("title") or entity.get("name") or "").strip()
    artist_values = entity.get("artists") or []
    artists = ", ".join(a["name"] for a in artist_values if isinstance(a, dict) and a.get("name"))
    artists = artists or str(entity.get("subtitle") or "")
    if not title:
        raise ValueError("Spotify did not return a track title")
    sources = (entity.get("coverArt") or {}).get("sources") or []
    album = entity.get("album") or {}
    return {"id": track_id, "title": title, "artists": artists,
            "duration": float(entity.get("duration") or 0) / 1000 or None,
            "album": str(album.get("name") or "") if isinstance(album, dict) else str(album),
            "cover": str(sources[-1].get("url") or "") if sources else "",
            "display": f"{title} — {artists}" if artists else title,
            "query": f"ytsearch8:{title} {artists} official audio"}


def resolve_spotify_track(url: str, timeout: int = 15) -> tuple[str, str]:
    """Backward-compatible tuple wrapper for older integrations."""
    info = resolve_spotify_track_info(url, timeout)
    return info["query"], info["display"]


def open_output_folder(path: str) -> None:
    target = str(Path(path).expanduser())
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        import subprocess

        subprocess.Popen(["open", target])
    else:
        import subprocess

        subprocess.Popen(["xdg-open", target])
