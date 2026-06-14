@echo off
rem Launch the Work Vault dashboard and open it in the default browser.
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start "" http://localhost:5000"
python "%~dp0app.py"
