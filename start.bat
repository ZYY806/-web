@echo off
chcp 936 >nul
title DeZhou Travel - AI Tourism Website
cd /d "%~dp0"

rem ============================================================
rem  一键启动脚本（无需数据库）
rem  本站数据全部内置在 data_store.py，帖子/留言存在 data/store.json
rem  只依赖 Flask + python-dotenv，不用装 MySQL、不用手动建库
rem ============================================================

rem ---- 端口 5000 已在服务就直接开浏览器 ----
netstat -ano | findstr ":5000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [INFO] 网站已在运行，打开浏览器...
    start "" http://127.0.0.1:5000
    timeout /t 3 >nul
    exit /b
)

echo ==========================================================
echo    DeZhou Travel  ^|  AI Tourism Website
echo ----------------------------------------------------------
echo    Starting server, please wait a few seconds...
echo    Then open:  http://127.0.0.1:5000
echo.
echo    KEEP THIS WINDOW OPEN while using the site.
echo    Close this window (or press Ctrl+C) to stop the server.
echo ==========================================================
echo.

rem ---- 选一个装了 Flask 的 Python ----
set "PY=D:\Users\dell\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Flask is not installed for this Python:
    echo         %PY%
    echo.
    echo Please run:  "%PY%" -m pip install -r requirements.txt
    echo.
    pause
    exit /b
)

rem ---- 稍后自动开浏览器，然后启动服务 ----
start "" /min cmd /c "timeout /t 6 >nul && start http://127.0.0.1:5000"

"%PY%" app.py

echo.
echo Server stopped.
pause
