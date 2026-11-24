@echo off
rem ==========================================================
rem  Screen Assistant — Quick Starter
rem ==========================================================
cd /d "%~dp0"

if exist "dist\WDAService.exe" (
    start "" "dist\WDAService.exe" --show
    if exist "dist\WDALauncher.exe" start "" "dist\WDALauncher.exe"
    echo Started WDAService and WDALauncher from dist\
    goto done
)

if not exist ".venv\Scripts\pythonw.exe" (
    echo Virtual environment not found. Running setup.bat first...
    call setup.bat
)

start "" ".venv\Scripts\pythonw.exe" "assistant.py" --show

:done
echo ==========================================================
echo  Screen Assistant started!
echo.
echo  SHORTCUTS (Zero Ctrl / Alt):
echo    / + 1                    :  Bring overlay to front / Launch
echo    / + S  (or F9)           :  Solve screen question (Auto MCQ/Code/Theory)
echo    / + Z  (or F10)          :  Toggle visibility (85%% ^<--^> 0%%)
echo    / + C                    :  Solve clipboard text
echo    / + D  (or F11)          :  Append next page to context
echo    / + Q                    :  Quit
echo ==========================================================
ping 127.0.0.1 -n 3 >nul
