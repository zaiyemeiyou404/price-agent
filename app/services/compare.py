"""
比价服务

TODO: 实现
1. 调用多个平台工具并发获取数据
2. 数据标准化处理
3. 缓存机制
4. 返回比价结果
"""
import asyncio
from typing import Optional
from datetime import timedelta
from loguru import logger

from app.models import CompareRequest, CompareResult, Product, Platform
from app.tools import get_tools
from app.agent import Agent
from app.services.cache import CacheService
from app.config import settings


class CompareService:
    """比价服务"""
    
    def __init__(self):
        self.agent = Agent()
        self.cache = CacheService()
        logger.info("CompareService 初始化完成")
    
    async def compare(self, request: CompareRequest) -> CompareResult:
        """
        执行比价
        
        步骤:
        1. 检查缓存
        2. 调用 Agent 执行
        3. 缓存结果
        4. 返回结果
        """
        logger.info(f"比较请求: query={request.query}, type={request.type}, platforms={request.platforms}")
        
        # 确定要使用的平台
        platforms = request.platforms
        if settings.taobao_only_mode:
            if platforms and Platform.TAOBAO not in platforms:
                logger.warning(f"淘宝单平台模式启用，忽略请求平台: {platforms}")
            platforms = [Platform.TAOBAO]
        elif not platforms:
            # 如果没有指定平台，使用规划器决定
            from app.agent import Planner
            planner = Planner()
            platforms = await planner.plan(request.query)

        # 构造生效请求，确保 Agent 不会绕过平台约束
        effective_request = request.model_copy(update={"platforms": platforms})
        
        # 生成缓存key
        cache_key = self.cache.make_key(request.query, platforms)
        
        # 1. 检查缓存
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            logger.info(f"缓存命中: {cache_key}")
            
            # 确保缓存的类型正确
            if isinstance(cached_result, CompareResult):
                return cached_result
            elif isinstance(cached_result, dict):
                # 尝试从字典恢复
                try:
                    return CompareResult(**cached_result)
                except Exception as e:
                    logger.warning(f"缓存数据解析失败: {e}")
        
        logger.info(f"缓存未命中，开始执行比价: {cache_key}")
        
        # 2. 调用 Agent 执行比价
        try:
            result = await self.agent.run(effective_request)
            
            # 3. 缓存结果
            if result and result.products:
                # 根据查询类型设置不同的缓存时间
                if request.type == "shopping":
                    ttl = timedelta(minutes=10)  # 购物结果缓存10分钟
                else:
                    ttl = timedelta(minutes=5)   # 外卖结果缓存5分钟（价格变化快）
                
                await self.cache.set(cache_key, result, ttl)
                logger.info(f"结果已缓存: {cache_key}, TTL: {ttl}")
            else:
                # 如果没有结果，缓存空结果1分钟
                await self.cache.set(cache_key, result, timedelta(minutes=1))
                logger.info(f"空结果已缓存: {cache_key}")
            
            return result
            
        except Exception as e:
            logger.error(f"比价执行失败: {e}")
            
            # 返回错误结果
            return CompareResult(
                query=request.query,
                type=request.type,
                products=[],
                summary=f"比价失败: {str(e)}"
            )
    
    async def fetch_products(self, query: str, platforms: list[Platform], **kwargs) -> list[Product]:
        """
        并发获取多平台商品数据
        
        注意: 这个方法现在主要被 Agent 使用，这里保留作为备用
        """
        logger.info(f"直接获取商品: query={query}, platforms={platforms}")
        
        tools = []
        all_products = []
        
        try:
            # 获取工具实例
            for platform in platforms:
                try:
                    tool = get_tools([platform])[0]
                    tools.append(tool)
                except Exception as e:
                    logger.warning(f"获取工具 {platform} 失败: {e}")
            
            if not tools:
                logger.error("没有可用的工具")
                return []
            
            # 并发执行搜索
            tasks = []
            for tool in tools:
                # 根据平台类型传递不同参数
                if tool.platform in [Platform.ELEME, Platform.MEITUAN]:
                    # 外卖平台需要定位信息
                    location = kwargs.get('location')
                    task = tool.search(query, location=location)
                else:
                    # 购物平台
                    task = tool.search(query)
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for i, result in enumerate(results):
                tool = tools[i]
                if isinstance(result, Exception):
                    logger.error(f"工具 {tool.name} 搜索失败: {result}")
                    continue
                
                if result:
                    all_products.extend(result)
                    logger.info(f"工具 {tool.name} 返回 {len(result)} 个商品")
            
            logger.info(f"总共获取到 {len(all_products)} 个商品")
            
            # 按最终价格排序
            all_products.sort(key=lambda p: p.final_price)
            
            # 限制返回数量
            return all_products[:50]  # 最多返回50个商品
            
        finally:
            # 清理资源
            for tool in tools:
                try:
                    await tool.close()
                except Exception as e:
                    logger.warning(f"关闭工具 {tool.name} 失败: {e}")
