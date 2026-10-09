@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup.bat first to install the Python dependencies.
    pause
    exit /b 1
)
if not exist "webui\dist\index.html" (
    pushd webui
    call npm.cmd ci
    if errorlevel 1 exit /b 1
    call npm.cmd run build
    if errorlevel 1 exit /b 1
    popd
)
".venv\Scripts\python.exe" desktop_web.py
if errorlevel 1 pause
