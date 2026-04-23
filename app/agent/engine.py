"""
ReAct Agent 引擎

TODO: 实现 ReAct 循环
1. 规划(Plan) - 解析用户需求，决定调用哪些工具
2. 行动(Act) - 执行工具调用
3. 观察(Observe) - 收集工具返回结果
4. 反思(Reflect) - 分析结果，优化推荐

示例流程:
用户: "帮我比价iPhone 15"
  → Plan: 需要调用淘宝和京东工具
  → Act: 调用 taobao_search("iPhone 15"), jd_search("iPhone 15")
  → Observe: 收集两个平台的商品列表
  → Reflect: 对比价格，生成最优推荐
"""
import asyncio
from typing import List, Optional
from loguru import logger

from app.models import CompareRequest, CompareResult, Product, Platform, ProductType
from app.agent.planner import Planner
from app.agent.reflector import Reflector
from app.agent.analyzer import FailureAnalyzer
from app.tools import get_tools, BaseTool


class Agent:
    """ReAct Agent"""
    
    def __init__(self):
        self.planner = Planner()
        self.reflector = Reflector()
        self.analyzer = FailureAnalyzer()
        logger.info("Agent 初始化完成")
    
    async def run(self, request: CompareRequest) -> CompareResult:
        """
        执行比价任务
        """
        logger.info(f"Agent 开始处理请求: {request.query}, 类型: {request.type}")
        
        try:
            # 1. 规划阶段 (Plan)
            platforms = await self.plan(request)
            logger.info(f"规划结果: 需要调用 {len(platforms)} 个平台: {platforms}")
            
            # 2. 行动阶段 (Act) - 并发调用工具
            products = await self.act(request.query, platforms, request.type, request.location)
            logger.info(f"行动结果: 获取到 {len(products)} 个商品")
            
            if not products:
                analysis = self.analyzer.analyze(platforms, request.query)
                return CompareResult(
                    query=request.query,
                    type=request.type,
                    products=[],
                    summary=analysis.get("summary", "未找到相关商品")
                )
            
            # 3. 反思阶段 (Reflect) - 分析结果并生成推荐
            reflection = await self.reflect(products)
            best_deal_obj = reflection.get("best_deal")
            best_platform = None
            if best_deal_obj:
                best_platform = (
                    best_deal_obj.platform.value
                    if hasattr(best_deal_obj, "platform") and hasattr(best_deal_obj.platform, "value")
                    else str(best_deal_obj)
                )
            logger.info(f"反思完成，最佳平台: {best_platform or '无'}")
            
            # 构建结果
            best_deal = reflection.get("best_deal")
            
            return CompareResult(
                query=request.query,
                type=request.type,
                products=products,
                best_deal=best_deal,
                summary=reflection.get("summary", "分析完成")
            )
            
        except Exception as e:
            logger.error(f"Agent 执行失败: {e}")
            return CompareResult(
                query=request.query,
                type=request.type,
                products=[],
                summary=f"比价失败: {str(e)}"
            )
    
    async def plan(self, request: CompareRequest) -> List[Platform]:
        """规划需要调用的工具"""
        # 如果请求中指定了平台，使用指定的平台
        if request.platforms:
            return request.platforms
        
        # 否则使用规划器分析
        return await self.planner.plan(request.query)
    
    async def act(self, query: str, platforms: List[Platform], product_type: ProductType, location: Optional[str] = None) -> List[Product]:
        """
        并发调用工具获取商品数据
        """
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
    
    async def reflect(self, products: List[Product]) -> dict:
        """反思并生成推荐"""
        return await self.reflector.reflect(products)
