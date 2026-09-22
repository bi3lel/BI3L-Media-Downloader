# BI3L Media Downloader

A simple Windows media downloader with a dark interface available in English and Brazilian Portuguese.

[Download the latest release](../../releases/latest)

Use it only for content you own, public-domain content, or media you have permission to save. Respect platform terms and applicable law.

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

- **`BI3L.Media.Downloader.zip`:** extract it and run `BI3L Media Downloader.exe`. Python 3.11+ and a first-run internet connection are required.
- **`BI3L.Media.Downloader.Setup.exe`:** installs a self-contained build without requiring Python or internet during installation.

The default download directory is `%USERPROFILE%\Downloads\BI3L Media Downloader` and can be changed in Settings.

## MP4 compatibility with VEGAS and other editors

MP4 downloads are now converted automatically to H.264 High profile, 8-bit 4:2:0 video with constant frame rate and AAC-LC stereo audio at 48 kHz. Silent downloads use the same video conversion without an audio track. This also applies to direct links and playlists.

An MP4 extension alone does not guarantee compatible codecs: older downloads could contain AV1, VP9 or Opus. Version 2.4.1 converts the streams even when the source is already MP4. Conversion takes extra time, needs space for a second copy, and may increase file size; it uses high-quality lossy encoding (CRF 18). Wait for the conversion stage to finish. If it fails, the original download is kept and an error is shown.

Previously downloaded files are not changed automatically. Download them again with this version, or back up an existing MP4 and run `python video_compat.py "path/to/video.mp4"` from the source installation. Add `--silent` to remove audio. Very old editors may still have resolution/frame-rate limits; choose a lower download quality if needed. HDR-to-SDR tone mapping is not included.

## Spotify note

The application does not download or decrypt protected Spotify audio. It reads public link metadata and searches for a matching public source supported by yt-dlp.

## Source

Run `setup.bat`, then `run.bat` on Windows 10/11 with Python 3.11+. See [BUILDING.md](BUILDING.md) for build instructions.

This project has no telemetry. See [PRIVACY.md](PRIVACY.md), [DISCLAIMER.md](DISCLAIMER.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Source code is licensed under [GNU GPL v3.0](LICENSE). Copyright © 2026 BI3L.
