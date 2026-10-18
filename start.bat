@echo off
setlocal
cd /d "%~dp0"
title campus-radar

set "PYTHON_CMD="
python --version >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py -3 --version >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD goto :no_python

if not exist ".venv\Scripts\python.exe" (
    echo [campus-radar] Creating the Python environment, first run only...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :setup_failed
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :setup_failed
)

if not exist ".venv\.campus-radar-ready" (
    echo [campus-radar] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :setup_failed
    ".venv\Scripts\python.exe" -c "from pathlib import Path; Path('.venv/.campus-radar-ready').write_text('ok', encoding='utf-8')"
    if errorlevel 1 goto :setup_failed
)

echo [campus-radar] Starting...
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
    echo.
    echo [campus-radar] The service stopped with an error. Check the message above.
    pause
)
exit /b 0

:no_python
echo.
echo Python was not found.
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo During installation, enable "Add Python to PATH", then run this file again.
echo.
pause
exit /b 1

:setup_failed
echo.
echo Dependency setup failed. Check your network connection and Python version.
echo You can delete the .venv folder and run this file again.
echo.
pause
exit /b 1
