@echo off
rem ==========================================================
rem  Screen Assistant — Full Stealth Build & Setup
rem  Compiles WDAService.exe & WDALauncher.exe with Windows
rem  metadata disguise and installs Start Menu / Startup shortcuts.
rem ==========================================================
cd /d "%~dp0"

echo.
echo [1/6] Stopping any running instance...
powershell -NoProfile -Command ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*assistant.py*' -or $_.CommandLine -like '*launcher.py*' -or $_.Name -eq 'WDAService.exe' -or $_.Name -eq 'WDALauncher.exe' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; 'Stopped' } else { 'None running' }"

echo.
echo [2/6] Checking PyInstaller...
.venv\Scripts\pip install pyinstaller --quiet

echo.
echo [3/6] Building WDAService.exe...
.venv\Scripts\pyinstaller ^
  --onefile ^
  --windowed ^
  --name "WDAService" ^
  --version-file "version_info.txt" ^
  --add-data ".env;." ^
  --hidden-import "winocr" ^
  --hidden-import "PIL" ^
  --hidden-import "PIL.ImageGrab" ^
  --hidden-import "groq" ^
  --hidden-import "dotenv" ^
  --hidden-import "requests" ^
  --hidden-import "bs4" ^
  --hidden-import "uiautomation" ^
  --clean ^
  --noconfirm ^
  assistant.py

if errorlevel 1 (
    echo.
    echo [ERROR] WDAService build FAILED.
    pause
    exit /b 1
)

echo.
echo [4/6] Building WDALauncher.exe (/+1 Global Listener)...
.venv\Scripts\pyinstaller ^
  --onefile ^
  --windowed ^
  --name "WDALauncher" ^
  --version-file "version_info_launcher.txt" ^
  --clean ^
  --noconfirm ^
  launcher.py

if errorlevel 1 (
    echo.
    echo [ERROR] WDALauncher build FAILED.
    pause
    exit /b 1
)

echo.
echo [5/6] Copying config files to dist\...
copy /Y ".env" "dist\.env" >nul 2>&1
if exist ".env.example" copy /Y ".env.example" "dist\.env.example" >nul 2>&1

echo.
echo [6/6] Installing Start Menu and Startup shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -File "install_shortcuts.ps1"

echo.
echo ============================================================
echo  Build and Installation Complete!
echo ============================================================
echo  Main Service : %~dp0dist\WDAService.exe
echo  Background   : %~dp0dist\WDALauncher.exe
echo  Config       : %~dp0dist\.env
echo.
echo  Start Menu   : "System Diagnostics Tool" (disguised icon)
echo  Startup Boot : "WindowsDriverAssistant" (auto-runs at login)
echo.
echo  Hotkeys (Zero Ctrl/Alt):
echo    / + 1                    :  Launch / Show overlay
echo    / + S  (or F9)           :  Solve screen question
echo    / + Z  (or F10)          :  Toggle visibility
echo    / + C                    :  Solve clipboard
echo    / + D  (or F11)          :  Append page
echo    / + Q                    :  Quit
echo ============================================================
echo.
if not "%1"=="--nopause" pause
