@echo off
chcp 65001 >nul
title Text Calculator
cd /d "%~dp0"

rem Prefer pythonw to avoid console window
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0calculator.py"
    exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0calculator.py"
    exit /b
)

echo Python not found. Please install Python 3.10+ and check "Add to PATH".
pause
