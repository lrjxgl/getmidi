@echo off
setlocal
cd /d "%~dp0"

where conda >nul 2>nul
if %errorlevel%==0 (
    conda run -n py310 --no-capture-output python -m app.main
    if not errorlevel 1 goto :eof
)

if exist "F:\program\miniconda3\envs\py310\python.exe" (
    "F:\program\miniconda3\envs\py310\python.exe" -m app.main
    goto :check
)

python -m app.main

:check
if errorlevel 1 (
    echo.
    echo [GetMIDI] 启动失败。请确认已安装 conda 环境 py310 并执行：
    echo     pip install -r requirements.txt
    pause
)
