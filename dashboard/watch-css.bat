@echo off
REM Live rebuild while you edit markup: recompiles static/tailwind.css on save.
REM Leave this running in its own window during frontend work; Ctrl+C to stop.
cd /d "%~dp0"
if not exist tools\tailwindcss.exe (
  echo Tailwind CLI not found. Run get-tailwind.bat first.
  exit /b 1
)
tools\tailwindcss.exe -i tailwind.input.css -o static\tailwind.css --watch
