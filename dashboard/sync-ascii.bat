@echo off
REM Deploy the ASCII hero background: Assets/ascii_js.js -> static/ascii-dither-background.js
REM Run this after re-exporting the ASCII art (the static/ copy is what Flask serves).
cd /d "%~dp0"
if not exist "Assets\ascii_js.js" (
  echo Source not found: Assets\ascii_js.js
  exit /b 1
)
copy /y "Assets\ascii_js.js" "static\ascii-dither-background.js" >nul
if errorlevel 1 (
  echo Copy failed.
  exit /b 1
)
echo Synced Assets\ascii_js.js -^> static\ascii-dither-background.js
