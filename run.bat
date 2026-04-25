@echo off
chcp 65001 >nul
title 智能价格比价系统

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║     🔍 智能价格比价系统 - 启动中...          ║
echo  ╚════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检查 Python 环境... ✓

:: 安装依赖
echo [2/3] 安装/更新依赖...
pip install -q pydantic-settings loguru fastapi uvicorn playwright fake-useragent
if errorlevel 1 (
    echo ⚠️ 依赖安装可能有问题，尝试继续...
)

echo [3/3] 启动服务...
echo.
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  📡 API地址: http://127.0.0.1:8000
echo  📖 API文档: http://127.0.0.1:8000/docs
echo  🖥️  前端页面: 请打开 simple-ui.html
echo  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo  按 Ctrl+C 停止服务
echo.

python -m uvicorn app.main:app --reload --port 8000 ^
  --reload-exclude "cookies/*" ^
  --reload-exclude "debug_output/*" ^
  --reload-exclude "scripts/login/cookies/*" ^
  --reload-exclude "__pycache__/*"

if errorlevel 1 (
    echo.
    echo ❌ 启动失败，请检查错误信息
    pause
)
