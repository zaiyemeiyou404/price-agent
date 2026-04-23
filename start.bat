@echo off
echo 启动 Price Agent 服务...
echo 访问 http://localhost:8000/docs 查看 API 文档
echo 按 Ctrl+C 停止服务
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
