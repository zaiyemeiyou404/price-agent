"""
工具基类

所有平台爬虫工具继承此类
"""
from abc import ABC, abstractmethod
from typing import Optional
from app.models import Product, Platform


class BaseTool(ABC):
    """工具基类"""
    
    platform: Platform
    name: str
    description: str
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[Product]:
        """
        搜索商品
        
        Args:
            query: 搜索关键词
            **kwargs: 额外参数 (如定位、筛选条件等)
        
        Returns:
            商品列表
        
        TODO: 子类实现具体爬虫逻辑
        """
        pass
    
    @abstractmethod
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """
        获取商品详情
        
        Args:
            product_id: 商品ID
        
        Returns:
            商品详情
        """
        pass
    
    async def close(self):
        """关闭资源（如浏览器）"""
        pass
