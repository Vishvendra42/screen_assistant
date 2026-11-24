@echo off
rem ==========================================================
rem  Screen Assistant — Setup Script
rem ==========================================================
cd /d "%~dp0"

echo [1/3] Checking Python installation...
where python >nul 2>&1
if errorlevel 1 (
    echo Error: Python was not found on PATH.
    echo Please install Python 3.10-3.12 from python.org and tick "Add to PATH".
    pause
    exit /b 1
)

echo [2/3] Setting up virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
)

echo [3/3] Installing lightweight dependencies...
call .venv\Scripts\pip.exe install --upgrade pip >nul 2>&1
call .venv\Scripts\pip.exe install -r requirements.txt

if not exist ".env" (
    copy .env.example .env >nul 2>&1
)

echo.
echo ==========================================================
echo  Setup Complete!
echo  Double-click start.bat to launch in background.
echo  Double-click run_debug.bat to run with console logs.
echo ==========================================================
pause
