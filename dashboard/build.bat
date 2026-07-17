@echo off
rem Build the standalone Regalia app (Windows). Output: dist\Regalia.exe (onefile)
cd /d "%~dp0"
pip install -r requirements.txt -r requirements-dev.txt || exit /b 1
pyinstaller --noconfirm regalia.spec || exit /b 1
echo.
echo Built ^> dist\Regalia.exe
