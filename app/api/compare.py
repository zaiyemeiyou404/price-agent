"""
比价 API 接口
"""
from fastapi import APIRouter, HTTPException
from app.models import CompareRequest, CompareResult
from app.services import CompareService
from app.config import settings
from app.models import Platform
from app.agent.project_analyzer import ProjectAnalyzerAgent

router = APIRouter()

# TODO: 改为依赖注入
compare_service = CompareService()
project_analyzer = ProjectAnalyzerAgent()


@router.post("/compare", response_model=CompareResult)
async def compare(request: CompareRequest):
    """
    比价接口
    
    示例请求:
    {
        "query": "iPhone 15",
        "type": "shopping",
        "platforms": ["taobao", "jd"]
    }
    """
    try:
        result = await compare_service.compare(request)
        return result
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="功能开发中")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platforms")
async def get_platforms():
    """获取支持的平台列表"""
    if settings.taobao_only_mode:
        return {
            "shopping": ["taobao"],
            "food": []
        }

    return {
        "shopping": ["taobao", "jd", "pdd"],
        "food": ["eleme", "meituan"]
    }


@router.get("/capabilities")
async def get_capabilities():
    """获取平台能力和前端渲染元数据"""
    all_platforms = [p.value for p in Platform]

    if settings.taobao_only_mode:
        enabled_platforms = [Platform.TAOBAO.value]
    else:
        # 购物/外卖分组按当前系统能力声明
        enabled_platforms = [
            Platform.TAOBAO.value,
            Platform.JD.value,
            Platform.PDD.value,
            Platform.ELEME.value,
            Platform.MEITUAN.value,
        ]

    platform_meta = {
        Platform.TAOBAO.value: {
            "label": "淘宝",
            "group": "shopping",
            "color": "#ff5a1f",
            "icon": "TB",
        },
        Platform.JD.value: {
            "label": "京东",
            "group": "shopping",
            "color": "#e1251b",
            "icon": "JD",
        },
        Platform.PDD.value: {
            "label": "拼多多",
            "group": "shopping",
            "color": "#e02e24",
            "icon": "PD",
        },
        Platform.ELEME.value: {
            "label": "饿了么/闪购",
            "group": "food",
            "color": "#1677ff",
            "icon": "EL",
        },
        Platform.MEITUAN.value: {
            "label": "美团",
            "group": "food",
            "color": "#f7b500",
            "icon": "MT",
        },
    }

    return {
        "mode": {
            "taobao_only_mode": settings.taobao_only_mode,
            "api_mode": settings.api_mode,
        },
        "enabled_platforms": enabled_platforms,
        "all_platforms": all_platforms,
        "platform_meta": platform_meta,
    }


@router.get("/analyze/project")
async def analyze_project():
    """项目运行状态分析"""
    return project_analyzer.analyze()
