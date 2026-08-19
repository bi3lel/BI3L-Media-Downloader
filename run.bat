@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    call setup.bat
    exit /b %errorlevel%
)

start "" ".venv\Scripts\pythonw.exe" app.py
