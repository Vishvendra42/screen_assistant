@echo off
rem ==========================================================
rem  Screen Assistant — Process Stopper
rem ==========================================================
cd /d "%~dp0"

powershell -NoProfile -Command ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*assistant.py*' -or $_.CommandLine -like '*launcher.py*' -or $_.Name -eq 'WDAService.exe' -or $_.Name -eq 'WDALauncher.exe' }; if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Host 'All Screen Assistant services stopped.' } else { Write-Host 'None running.' }"

if exist ".drv.pid" del ".drv.pid" >nul 2>&1
if exist "dist\.drv.pid" del "dist\.drv.pid" >nul 2>&1
if exist ".assistant.pid" del ".assistant.pid" >nul 2>&1
exit /b 0
