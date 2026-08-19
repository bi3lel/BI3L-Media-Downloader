import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import (
    DownloadSettings,
    load_settings,
    platform_from_url,
    resolve_spotify_collection,
    resolve_spotify_track_info,
    split_urls,
    spotify_kind,
)
from i18n import LANGUAGE_NAMES, TRANSLATIONS, translate


class CoreTests(unittest.TestCase):
    def test_split_urls_deduplicates_and_ignores_text(self):
        raw = "hello https://youtu.be/abc\nhttps://youtu.be/abc, https://tiktok.com/@a/video/1"
        self.assertEqual(
            split_urls(raw),
            ["https://youtu.be/abc", "https://tiktok.com/@a/video/1"],
        )

    def test_platform_detection(self):
        self.assertEqual(platform_from_url("https://www.youtube.com/watch?v=x"), "YouTube")
        self.assertEqual(platform_from_url("https://open.spotify.com/track/123"), "Spotify")
        self.assertEqual(platform_from_url("https://www.instagram.com/reel/x/"), "Instagram")
        self.assertEqual(platform_from_url("https://clips.twitch.tv/FaintLightGullWholeWheat"), "Twitch")
        self.assertEqual(platform_from_url("https://www.twitch.tv/example/clip/FaintLightGullWholeWheat"), "Twitch")
        self.assertEqual(platform_from_url("https://x.com/user/status/123"), "X")

    def test_spotify_kind(self):
        self.assertEqual(spotify_kind("https://open.spotify.com/track/123?si=x"), "track")
        self.assertEqual(spotify_kind("https://open.spotify.com/playlist/123"), "playlist")
        self.assertEqual(spotify_kind("https://open.spotify.com/intl-fr/album/123"), "album")

    def test_spotify_collection_uses_public_embed_metadata(self):
        payload = {
            "props": {
                "pageProps": {
                    "state": {
                        "data": {
                            "entity": {
                                "name": "Road Trip",
                                "coverArt": {"sources": [{"url": "https://img.example/cover.jpg"}]},
                                "trackList": [
                                    {
                                        "uri": "spotify:track:abc123",
                                        "title": "First Song",
                                        "subtitle": "Example Artist",
                                    },
                                    {
                                        "uri": "spotify:track:def456",
                                        "title": "Second Song",
                                        "artists": [{"name": "Another Artist"}],
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }
        page = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'

        class Reply:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return page.encode("utf-8")

        with patch("core.urllib.request.urlopen", return_value=Reply()):
            collection = resolve_spotify_collection(
                "https://open.spotify.com/playlist/playlist123"
            )
        self.assertEqual(collection["title"], "Road Trip")
        self.assertEqual(len(collection["tracks"]), 2)
        self.assertEqual(collection["tracks"][0]["position"], 1)
        self.assertIn("First Song Example Artist", collection["tracks"][0]["query"])
        self.assertEqual(collection["tracks"][0]["album"], "Road Trip")
        self.assertEqual(collection["tracks"][0]["cover"], "https://img.example/cover.jpg")

    def test_spotify_track_keeps_metadata_and_cover(self):
        payload = {
            "title": "A Song",
            "author_name": "An Artist",
            "thumbnail_url": "https://img.example/song.jpg",
        }

        class Reply:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return json.dumps(payload).encode("utf-8")

        with patch("core.urllib.request.urlopen", return_value=Reply()):
            info = resolve_spotify_track_info("https://open.spotify.com/track/track123")
        self.assertEqual(info["title"], "A Song")
        self.assertEqual(info["artists"], "An Artist")
        self.assertEqual(info["cover"], "https://img.example/song.jpg")
        self.assertIn("A Song An Artist", info["query"])

    def test_settings_stay_small_and_user_facing(self):
        settings = DownloadSettings(
            video_quality="720p",
            audio_quality="192 kbps",
            video_no_audio=True,
            language="pt-BR",
        )
        self.assertEqual(settings.video_quality, "720p")
        self.assertEqual(settings.audio_quality, "192 kbps")
        self.assertTrue(settings.video_no_audio)
        self.assertEqual(settings.language, "pt-BR")

    def test_old_downloader_settings_are_migrated_on_load(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            legacy = base / "Downloader" / "settings.json"
            legacy.parent.mkdir()
            legacy.write_text(
                json.dumps({"language": "pt-BR", "video_quality": "720p"}),
                encoding="utf-8",
            )
            with (
                patch("core.settings_file", return_value=base / "BI3L Media Downloader" / "settings.json"),
                patch("core.legacy_settings_files", return_value=[legacy]),
            ):
                settings = load_settings()
        self.assertEqual(settings.language, "pt-BR")
        self.assertEqual(settings.video_quality, "720p")

    def test_translations_have_identical_keys(self):
        self.assertEqual(set(LANGUAGE_NAMES), {"en", "pt-BR"})
        self.assertEqual(set(TRANSLATIONS["en"]), set(TRANSLATIONS["pt-BR"]))
        self.assertEqual(
            translate("pt-BR", "home.title"),
            "Cole qualquer link para começar",
        )
        self.assertEqual(
            translate("pt-BR", "playlist.continue_items", chosen=2, noun="itens"),
            "Continuar com 2 itens",
        )


if __name__ == "__main__":
    unittest.main()
