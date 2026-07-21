@echo off
rem Double-click bootstrap for Regalia. Runs install.ps1 with an execution policy
rem bypass for THIS process only (it does not change any system-wide policy), so
rem users don't have to fiddle with PowerShell settings to run the installer.
rem
rem Pass-through args work too, e.g.:  install.bat -All
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
