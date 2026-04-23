"""
FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import compare, websocket
from app.config import settings

app = FastAPI(
    title="Price Agent",
    description="多平台比价系统",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(compare.router, prefix="/api/v1", tags=["比价"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])


@app.get("/")
async def root():
    return {"message": "Price Agent API", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "ok"}
