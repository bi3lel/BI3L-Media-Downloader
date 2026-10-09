@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BI3L Media Downloader - Offline Installer Builder
set "ROOT=%CD%"

if not exist "App\app.py" (
    echo ERROR: The App folder is incomplete.
    echo Extract the complete Offline Builder ZIP before running this file.
    if not defined CI pause
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Inno Setup 6 is required to create the final installer.
    echo Its official download page will open now. Install it, then run this file again.
    if not defined CI start "" "https://jrsoftware.org/isdl.php"
    if not defined CI pause
    exit /b 1
)

where py >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is required only to build the installer.
    echo Install it from https://www.python.org/downloads/windows/ and enable Add Python to PATH.
    if not defined CI pause
    exit /b 1
)

if not exist "_build\venv\Scripts\python.exe" (
    echo [1/5] Creating a clean build environment...
    py -3 -m venv "_build\venv"
    if errorlevel 1 goto :error
) else (
    echo [1/5] Reusing the clean build environment...
)

echo [2/5] Installing the Windows build tools and runtime packages...
"_build\venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :error
"_build\venv\Scripts\python.exe" -m pip install --disable-pip-version-check "pyinstaller>=6.11,<7" "customtkinter>=5.2.2,<6" "Pillow>=10.4,<13" "imageio-ffmpeg>=0.6,<1" "certifi>=2025.8.3" "gdown==6.4.2"
if errorlevel 1 goto :error

if not exist "_build\tools" mkdir "_build\tools"
echo [3/5] Downloading the current standalone yt-dlp engine for the offline package...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.exe' -OutFile '_build\tools\yt-dlp.exe'"
if errorlevel 1 goto :error

if not exist "_build\spec" mkdir "_build\spec"
echo [4/5] Building the self-contained Windows application...
"_build\venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --windowed ^
    --onedir ^
    --noupx ^
    --optimize 2 ^
    --name "BI3L Media Downloader" ^
    --contents-directory "App" ^
    --icon "%ROOT%\App\assets\app_icon.ico" ^
    --version-file "%ROOT%\Builder Files\version_info.txt" ^
    --paths "%ROOT%\App" ^
    --hidden-import "strip_audio" ^
    --copy-metadata "gdown" ^
    --collect-data "customtkinter" ^
    --collect-binaries "imageio_ffmpeg" ^
    --add-data "%ROOT%\App\assets;assets" ^
    --add-binary "%ROOT%\_build\tools\yt-dlp.exe;tools" ^
    --distpath "%ROOT%\_build\dist" ^
    --workpath "%ROOT%\_build\work" ^
    --specpath "%ROOT%\_build\spec" ^
    "%ROOT%\App\app.py"
if errorlevel 1 goto :error

echo [5/5] Compressing the offline installer with LZMA2...
if not exist "Output" mkdir "Output"
"%ISCC%" "Builder Files\BI3L Media Downloader Installer.iss"
if errorlevel 1 goto :error

echo Cleaning temporary build files...
rmdir /s /q "_build" >nul 2>nul

echo.
echo Offline installer created successfully:
echo %CD%\Output\BI3L Media Downloader Setup.exe
echo.
echo The Output installer no longer needs Python or internet during installation.
if not defined CI explorer /select,"%CD%\Output\BI3L Media Downloader Setup.exe"
exit /b 0

:error
echo.
echo The installer build did not finish. Read the error above, then run this file again.
if not defined CI pause
exit /b 1
