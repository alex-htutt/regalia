@echo off
rem Launch the Regalia dashboard and open it in the default browser.
rem   start.bat          -> normal use, no console window (uses pythonw)
rem   start.bat debug    -> visible console with Flask logs (Ctrl-C to stop)
rem Note: in windowless mode the server keeps running with no console — stop it
rem from Task Manager (end the pythonw.exe process), or just use `start.bat debug`.
if /i "%~1"=="debug" goto debug

start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://localhost:5000"
start "" pythonw "%~dp0app.py"
goto :eof

:debug
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://localhost:5000"
python "%~dp0app.py"
