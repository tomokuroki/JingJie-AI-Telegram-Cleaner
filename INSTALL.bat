@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [净界] 创建 Python 虚拟环境...
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
if errorlevel 1 goto :error

echo [净界] 安装依赖...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist .env copy /Y .env.example .env >nul

echo.
echo 安装完成。双击 RUN.bat 启动。
pause
exit /b 0

:error
echo.
echo 安装失败。请确认已安装 Python 3.11+ 并加入 PATH。
pause
exit /b 1
