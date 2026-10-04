@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo 请先运行 INSTALL.bat
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
pause
