# Script to install Start Menu and Startup shortcuts for WDAService & WDALauncher
$ErrorActionPreference = "Stop"

$distDir = "c:\Users\ASUS\Downloads\prev onw\screen_assistant\screen_assistant\dist"
$serviceExe = Join-Path $distDir "WDAService.exe"
$launcherExe = Join-Path $distDir "WDALauncher.exe"

$programsDir = [Environment]::GetFolderPath('Programs')
$startupDir  = [Environment]::GetFolderPath('Startup')

$wshShell = New-Object -ComObject WScript.Shell

# 1. Start Menu Shortcut (Disguised as "System Diagnostics Tool")
$startMenuShortcutPath = Join-Path $programsDir "System Diagnostics Tool.lnk"
$shortcut = $wshShell.CreateShortcut($startMenuShortcutPath)
$shortcut.TargetPath = $serviceExe
$shortcut.Arguments = "--show"
$shortcut.WorkingDirectory = $distDir
$shortcut.Description = "Windows System Diagnostics and Performance Monitor"
# Use a native system icon from shell32.dll (index 15 is computer/diagnostics icon, or imageres.dll index 109)
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll, 15"
$shortcut.Save()
Write-Host "Created Start Menu shortcut: $startMenuShortcutPath"

# 2. Startup Shortcut (WDALauncher runs silently on Windows login)
# This keeps Space+1 active even after a reboot or if WDAService is closed.
$startupShortcutPath = Join-Path $startupDir "WindowsDriverAssistant.lnk"
$startupShortcut = $wshShell.CreateShortcut($startupShortcutPath)
$startupShortcut.TargetPath = $launcherExe
$startupShortcut.WorkingDirectory = $distDir
$startupShortcut.Description = "Windows Driver Assistant Host Service"
$startupShortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll, 15"
$startupShortcut.Save()
Write-Host "Created Startup shortcut: $startupShortcutPath"
