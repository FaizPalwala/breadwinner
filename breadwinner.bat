@echo off
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%.venv\Scripts\breadwinner.exe" (
    "%SCRIPT_DIR%.venv\Scripts\breadwinner.exe" %*
) else (
    echo Error: Virtual environment not found in %SCRIPT_DIR%.venv
    echo Run 'powershell -ExecutionPolicy Bypass -File install.ps1' to set up Breadwinner.
    exit /b 1
)
