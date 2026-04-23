"""
工具注册中心（纯爬虫模式）
"""
from typing import Dict, Type

from app.config import settings
from app.tools.base import BaseTool
from app.models import Platform

# ========== 爬虫工具 ==========
from app.tools.taobao import TaobaoTool as TaobaoCrawler
from app.tools.jd import JDTool as JDCrawler
from app.tools.eleme import ElemeTool as ElemeCrawler
from app.tools.meituan import MeituanTool as MeituanCrawler
from app.tools.pdd import PDDTool as PDDCrawler  # 拼多多

# ========== 工具注册表 ==========
CRAWLER_TOOLS: Dict[Platform, Type[BaseTool]] = {
    Platform.TAOBAO: TaobaoCrawler,
    Platform.JD: JDCrawler,
    Platform.ELEME: ElemeCrawler,
    Platform.MEITUAN: MeituanCrawler,
    Platform.PDD: PDDCrawler,  # 拼多多
}

# 原始工具注册表（兼容性）
TOOLS: Dict[Platform, Type[BaseTool]] = CRAWLER_TOOLS


def get_tool(platform: Platform) -> BaseTool:
    """获取工具实例（仅爬虫）"""
    if settings.taobao_only_mode and platform != Platform.TAOBAO:
        platform = Platform.TAOBAO

    tool_class = CRAWLER_TOOLS.get(platform)
    if not tool_class:
        raise ValueError(f"Unknown platform: {platform}")
    return tool_class()


def get_tools(platforms: list[Platform] = None) -> list[BaseTool]:
    """获取多个工具实例"""
    if platforms is None:
        platforms = list(CRAWLER_TOOLS.keys())
    return [get_tool(p) for p in platforms]


def get_available_platforms() -> list[Platform]:
    """获取可用的平台列表"""
    return list(CRAWLER_TOOLS.keys())


# 导出
__all__ = [
    "TOOLS",
    "get_tool",
    "get_tools",
    "get_available_platforms",
    "TaobaoCrawler", "JDCrawler", "ElemeCrawler", "MeituanCrawler", "PDDCrawler",
]
