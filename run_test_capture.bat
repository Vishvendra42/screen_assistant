@echo off
rem ==========================================================
rem  Screen Assistant — Test Capture & Optimizer Launcher
rem ==========================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Running setup.bat first...
    call setup.bat
)

echo Starting Screen Assistant Capture & OCR Diagnostics...
.venv\Scripts\python.exe test_capture.py
pause
