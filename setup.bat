@echo off
setlocal
cd /d "%~dp0"
title BI3L Media Downloader Setup

where py >nul 2>nul
if errorlevel 1 (
    echo Python is not installed.
    echo.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
    echo During setup, enable "Add Python to PATH", then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating BI3L Media Downloader environment...
    py -3 -m venv .venv
    if errorlevel 1 goto :error
)

echo Installing and updating the download engine...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto :error

if not exist "tools" mkdir "tools"
echo Updating the standalone yt-dlp nightly engine...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest 'https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.exe' -OutFile 'tools\yt-dlp.new.exe'; Move-Item -Force 'tools\yt-dlp.new.exe' 'tools\yt-dlp.exe' } catch { if (Test-Path 'tools\yt-dlp.new.exe') { Remove-Item 'tools\yt-dlp.new.exe' -Force }; exit 1 }"
if errorlevel 1 (
    if exist "tools\yt-dlp.exe" (
        echo Nightly engine update was unavailable. The existing standalone engine will be used.
    ) else (
        echo Standalone engine download failed. Installing the Python fallback engine...
        ".venv\Scripts\python.exe" -m pip install --upgrade "yt-dlp[default,curl-cffi]"
        if errorlevel 1 goto :error
    )
)

echo.
echo BI3L Media Downloader is ready. Opening it now...
start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:error
echo.
echo Setup did not finish. Check your internet connection and try again.
pause
exit /b 1
