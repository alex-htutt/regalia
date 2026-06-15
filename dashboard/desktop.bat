@echo off
rem Launch the Regalia dashboard as a native desktop window (pywebview).
rem   desktop.bat          -> normal use, no console window (uses pythonw)
rem   desktop.bat debug    -> visible console with Flask logs + startup errors
if /i "%~1"=="debug" goto debug

rem Windowless: pythonw has no console, so nothing lingers behind the app window.
start "" pythonw "%~dp0desktop.py"
goto :eof

:debug
python "%~dp0desktop.py"
if errorlevel 1 pause
