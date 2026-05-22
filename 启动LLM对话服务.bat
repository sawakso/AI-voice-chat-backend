@echo off
chcp 65001 >nul
title AI 语音对话 - 后端 API

cd /d "%~dp0"

if not exist ".env" (
    echo [错误] 未找到 .env 文件！
    echo 请复制 .env.example 为 .env 并填入配置后重试
    pause
    exit /b 1
)

:: 读取 .env 里的端口，默认 8000
set BACKEND_PORT=8000
for /f "tokens=2 delims==" %%a in ('findstr "BACKEND_PORT" .env') do set BACKEND_PORT=%%a

if not exist ".venv\Scripts\python.exe" (
    echo [首次运行] 创建虚拟环境并安装依赖，请稍候...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt -q
    echo [完成] 环境就绪
)

echo ========================================
echo   AI 语音对话后端 API
echo   地址: http://127.0.0.1:%BACKEND_PORT%
echo   文档: http://127.0.0.1:%BACKEND_PORT%/docs
echo ========================================
echo.

.venv\Scripts\python backend_api.py

pause