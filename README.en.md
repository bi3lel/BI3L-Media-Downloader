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

- **Portable ZIP:** extract it and run `BI3L Media Downloader.exe`. Python 3.11+ and a first-run internet connection are required.
- **Offline Setup:** when attached to a Release, it installs a self-contained build without requiring Python or internet during installation.

The default download directory is `%USERPROFILE%\Downloads\BI3L Media Downloader` and can be changed in Settings.

## Spotify note

The application does not download or decrypt protected Spotify audio. It reads public link metadata and searches for a matching public source supported by yt-dlp.

## Source

Run `setup.bat`, then `run.bat` on Windows 10/11 with Python 3.11+. See [BUILDING.md](BUILDING.md) for build instructions.

This project has no telemetry. See [PRIVACY.md](PRIVACY.md), [DISCLAIMER.md](DISCLAIMER.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Source code is licensed under [GNU GPL v3.0](LICENSE). Copyright © 2026 BI3L.
