@echo off
REM One-off compile: tailwind.input.css -> static/tailwind.css (minified).
cd /d "%~dp0"
if not exist tools\tailwindcss.exe (
  echo Tailwind CLI not found. Run get-tailwind.bat first.
  exit /b 1
)
tools\tailwindcss.exe -i tailwind.input.css -o static\tailwind.css --minify
