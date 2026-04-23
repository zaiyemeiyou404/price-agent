#!/usr/bin/env python3
"""
Windows 启动脚本
"""
import sys
import asyncio

print(f"Python 版本: {sys.version}")
print(f"平台: {sys.platform}")

if __name__ == "__main__":
    print("\n启动 Price Agent 服务...")
    print("访问 http://localhost:8000/docs 查看 API 文档")
    print("访问 http://localhost:8000/health 检查服务状态")
    print("按 Ctrl+C 停止服务\n")
    
    # 直接运行，不通过 uvicorn.run()
    import uvicorn
    from app.main import app
    
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8000,
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
