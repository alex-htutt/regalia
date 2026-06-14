@echo off
rem Launch the Work Vault dashboard as a native desktop window (pywebview).
rem Falls back with a clear message if pywebview isn't installed yet.
python "%~dp0desktop.py"
if errorlevel 1 pause
