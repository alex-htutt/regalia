@echo off
REM Re-download the Tailwind standalone CLI (gitignored; ~108MB, no Node needed).
cd /d "%~dp0"
if not exist tools mkdir tools
echo Downloading Tailwind standalone CLI to tools\tailwindcss.exe ...
curl -L -o tools\tailwindcss.exe https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe
echo Done. Now run build-css.bat (one-off) or watch-css.bat (live rebuild).
