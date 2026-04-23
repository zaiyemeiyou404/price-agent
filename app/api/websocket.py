"""
WebSocket 推送

TODO: 实现实时进度推送
1. 客户端连接后创建任务
2. 实时推送进度：
   - {"stage": "fetching", "platform": "taobao", "progress": 30}
   - {"stage": "analyzing", "progress": 60}
   - {"stage": "completed", "result": {...}}
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/compare")
async def websocket_compare(websocket: WebSocket):
    """
    WebSocket 比价接口
    
    TODO: 让 DeepSeek 实现
    1. 接收查询请求
    2. 实时推送进度
    3. 返回最终结果
    """
    await websocket.accept()
    
    try:
        # 接收查询
        data = await websocket.receive_json()
        query = data.get("query")
        
        # TODO: 执行比价，推送进度
        await websocket.send_json({"stage": "started", "query": query})
        
        # 模拟进度
        await websocket.send_json({"stage": "fetching", "platform": "taobao", "progress": 25})
        await websocket.send_json({"stage": "fetching", "platform": "jd", "progress": 50})
        await websocket.send_json({"stage": "analyzing", "progress": 75})
        
        # TODO: 返回真实结果
        await websocket.send_json({"stage": "completed", "result": {}})
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"stage": "error", "message": str(e)})
