BI3L MEDIA DOWNLOADER - OFFLINE INSTALLER BUILDER

Recommended software: Inno Setup 6
Official download: https://jrsoftware.org/isdl.php

HOW TO BUILD

1. Install Inno Setup 6 from the official website.
2. Make sure Python 3.11 or newer is installed.
3. Double-click "Build Offline Installer.bat".
4. Wait for all five build stages to finish.
5. Find the finished file in:
   Output\BI3L Media Downloader Setup.exe

The builder uses absolute source paths internally, so it works correctly when
this folder is inside a Windows user profile or any path containing spaces.

After copying the finished Setup.exe somewhere safe, the entire Offline Builder
folder can be deleted.

The build needs internet once to obtain the compiler packages and the current
yt-dlp engine. The resulting Setup.exe is a real offline installer: another
computer does not need Python and does not need internet during installation.
Media downloads naturally still require an internet connection.

WHY THIS METHOD

- PyInstaller --onedir includes the Python runtime without extracting it on
  every launch.
- Inno Setup turns the complete application into one conventional installer.
- LZMA2 solid compression minimizes the downloadable installer size.
- UPX is intentionally disabled because it commonly increases antivirus false
  positives for only a modest size reduction.

The exact installer size depends mostly on FFmpeg and yt-dlp. Those components
are essential for MP3 conversion, format merging and reliable site support.

The generated installer is not digitally signed. Windows may show "Unknown
publisher" until you sign it with a trusted code-signing certificate.
