@echo off
rem ==========================================================
rem  Screen Assistant — Debug Runner (Console Window)
rem ==========================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup.bat first...
    call setup.bat
)

echo Starting Screen Assistant in debug console mode...
.venv\Scripts\python.exe assistant.py
pause
