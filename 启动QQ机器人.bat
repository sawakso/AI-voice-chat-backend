@echo off
chcp 65001 >nul
title QQ Bot - NapCat 客户端

cd /d "%~dp0"

if not exist ".env" (
    echo [错误] 未找到 .env 文件！
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行启动LLM对话服务.bat
    pause
    exit /b 1
)

echo ========================================
echo   QQ Bot 启动中...
echo   连接 NapCat: ws://127.0.0.1:3001
echo ========================================
echo.
echo 按 Ctrl+C 可停止
echo.

.venv\Scripts\python -u -m qq_bot.main
pause