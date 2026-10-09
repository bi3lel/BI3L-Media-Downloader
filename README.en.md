# BI3L Media Downloader

A simple Windows media downloader with a dark interface available in English and Brazilian Portuguese.

[Download the latest release](../../releases/latest)

Use it only for content you own, public-domain content, or media you have permission to save. Respect platform terms and applicable law.

## New interface in 2.6.0

The original BI3L logo and title are preserved. Settings are opened by the cogwheel at the bottom left; the destination folder is shown only inside the centered Settings dialog. Native minimize, maximize/restore and close controls are at the top right. The new interface supports the existing queue, Drive, playlist, Spotify and conversion features.

## Highlights

- YouTube, Instagram, TikTok, Twitch Clips, X, and public Spotify links
- MP4 video with or without audio
- MP3 audio at 320, 256, 192, or 128 kbps
- Video quality from 360p to 2160p or Best available
- Multi-link queues and selectable playlist items
- Progressive loading for large playlists
- Per-item title, percentage, speed, size, and ETA
- English and Brazilian Portuguese interface

## Install

Open [Releases](../../releases/latest):

- **`BI3L.Media.Downloader.zip`:** extract it and run `BI3L Media Downloader.exe`. Python 3.11+, Microsoft WebView2 Runtime and a first-run internet connection are required. The release includes the built interface; Node.js is not needed.
- **`BI3L.Media.Downloader.Setup.exe`:** installs a self-contained build without requiring Python or internet during installation.

The default download directory is `%USERPROFILE%\Downloads\BI3L Media Downloader` and can be changed in Settings.

## Google Drive and other websites

Paste a public Google Drive file or folder link. Folders are listed without downloading their files; check only the files you want, then Download. Subfolders keep their relative structure. Drive files are saved in their original format under `Google Drive`, with their IDs in the filenames; existing files are not overwritten. Google documents use the export format provided by gdown. Private/sign-in-only links and Google quota restrictions are not bypassed.

The home screen keeps the BI3L logo, heading and URL controls; service icons and explanations are omitted. Service explanations are kept here. Supported sites are not limited to a fixed list. Other public pages, direct media URLs, and supported HLS/DASH streams are handled by yt-dlp's site extractors and generic extractor. Unknown resolution metadata no longer rejects direct links. Compatibility depends on the website; DRM, login-only content, and sites with no discoverable media are not universally supported.

## Faster MP4 conversion

The app tests NVIDIA NVENC, Intel Quick Sync, and AMD AMF with a small real encode. It uses the first working H.264 encoder and retries on CPU if a full video fails on hardware. The CPU fallback uses the faster `veryfast` preset. Output remains 8-bit H.264 with constant frame rate and AAC stereo audio. Speed and output size depend on hardware and content; GPU quality settings are not identical to x264 CRF. Converting a file still takes time and disk space.

## MP4 compatibility with VEGAS and other editors

MP4 downloads are now converted automatically to H.264 High profile, 8-bit 4:2:0 video with constant frame rate and AAC-LC stereo audio at 48 kHz. Silent downloads use the same video conversion without an audio track. This also applies to direct links and playlists.

An MP4 extension alone does not guarantee compatible codecs: older downloads could contain AV1, VP9 or Opus. The app converts the streams even when the source is already MP4. Conversion takes extra time, needs space for a second copy, and may increase file size; it uses high-quality lossy encoding (CPU: CRF 18; GPU: encoder-specific quality settings). Wait for the conversion stage to finish. If it fails, the original download is kept and an error is shown.

Previously downloaded files are not changed automatically. Download them again with this version, or back up an existing MP4 and run `python video_compat.py "path/to/video.mp4"` from the source installation. Add `--silent` to remove audio. Very old editors may still have resolution/frame-rate limits; choose a lower download quality if needed. HDR-to-SDR tone mapping is not included.

## Spotify note

The application does not download or decrypt protected Spotify audio. It resolves public metadata for the exact Spotify track ID and compares multiple public candidates by title, artist, duration and version, plus album data when available. Automatic selection also requires an artist channel match. Missing metadata, ambiguous results or a near tie open a selection dialog; nothing downloads until you choose, and you can skip the song. This applies to tracks and selected playlist/album items. A Spotify ID identifies metadata, not a downloadable Spotify audio stream; public matches cannot be guaranteed identical.

## Source

Run `setup.bat`, then `run.bat` on Windows 10/11 with Python 3.11+, WebView2 and Node.js 22.12+ to build the interface from a source checkout. See [BUILDING.md](BUILDING.md) for build instructions.

This project has no telemetry. See [PRIVACY.md](PRIVACY.md), [DISCLAIMER.md](DISCLAIMER.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Source code is licensed under [GNU GPL v3.0](LICENSE). Copyright © 2026 BI3L.
