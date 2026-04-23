"""
规划器 - 解析用户需求，决定调用哪些工具

TODO: 实现
1. 使用大模型解析用户意图
2. 识别查询类型（购物/外卖）
3. 决定需要调用的平台工具

示例:
输入: "帮我比价iPhone 15，哪个平台便宜"
输出: ["taobao", "jd"]

输入: "附近肯德基套餐哪家外卖便宜"
输出: ["eleme", "meituan"]
"""
import re
from typing import Optional
from loguru import logger

from app.models import Platform, ProductType
from app.config import settings


class Planner:
    """规划器"""
    
    # 购物关键词
    SHOPPING_KEYWORDS = [
        "手机", "电脑", "平板", "电视", "家电", "服装", "鞋子", "包包",
        "化妆品", "护肤品", "数码", "耳机", "手表", "iPhone", "华为", "小米",
        "三星", "联想", "戴尔", "买", "购买", "购物", "商品", "产品"
    ]
    
    # 外卖关键词
    FOOD_KEYWORDS = [
        "外卖", "餐厅", "饭店", "餐馆", "快餐", "套餐", "汉堡", "炸鸡",
        "披萨", "面条", "米饭", "炒菜", "火锅", "烧烤", "奶茶", "咖啡",
        "肯德基", "麦当劳", "必胜客", "星巴克", "饿了么", "美团", "配送",
        "送餐", "就餐", "吃饭", "午餐", "晚餐", "早餐"
    ]
    
    # 平台关键词映射
    PLATFORM_KEYWORDS = {
        Platform.TAOBAO: ["淘宝", "天猫", "taobao", "tmall"],
        Platform.JD: ["京东", "jd", "京东商城"],
        Platform.ELEME: ["饿了么", "淘宝闪购", "eleme", "饿了吗"],
        Platform.MEITUAN: ["美团", "美团外卖", "meituan"],
        Platform.PDD: ["拼多多", "pdd", "pinduoduo"],
    }
    
    def __init__(self):
        self.use_llm = bool(settings.glm5_api_key or settings.openai_api_key or settings.deepseek_api_key)
        logger.info(f"Planner 初始化，使用大模型: {self.use_llm}")
    
    async def plan(self, query: str, platforms: Optional[list[Platform]] = None) -> list[Platform]:
        """
        分析查询，返回需要调用的工具列表
        """
        # 稳定模式：仅使用淘宝
        if settings.taobao_only_mode:
            logger.info("淘宝单平台模式已启用，规划结果固定为 taobao")
            return [Platform.TAOBAO]

        if platforms:
            # 如果指定了平台，直接返回
            return platforms
        
        query_lower = query.lower()
        
        # 检测查询类型
        query_type = await self.detect_type(query)
        
        # 根据类型决定默认平台
        if query_type == "shopping":
            default_platforms = [Platform.TAOBAO, Platform.JD, Platform.PDD]
        elif query_type == "food":
            default_platforms = [Platform.ELEME, Platform.MEITUAN]
        else:
            # 默认为购物
            default_platforms = [Platform.TAOBAO, Platform.JD]
        
        # 检查查询中是否提到特定平台
        mentioned_platforms = []
        for platform, keywords in self.PLATFORM_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    mentioned_platforms.append(platform)
                    break
        
        if mentioned_platforms:
            # 如果提到了特定平台，只使用提到的平台
            result = list(set(mentioned_platforms))
        else:
            result = default_platforms
        
        # 如果使用大模型，可以进一步优化
        if self.use_llm:
            try:
                llm_result = await self._plan_with_llm(query, query_type, result)
                if llm_result:
                    result = llm_result
            except Exception as e:
                logger.warning(f"大模型规划失败，使用规则结果: {e}")
        
        logger.info(f"规划结果: 查询='{query}', 类型={query_type}, 平台={result}")
        return result
    
    async def detect_type(self, query: str) -> str:
        """检测查询类型: shopping / food"""
        query_lower = query.lower()
        
        # 统计关键词出现次数
        shopping_score = 0
        food_score = 0
        
        for keyword in self.SHOPPING_KEYWORDS:
            if keyword.lower() in query_lower:
                shopping_score += 1
        
        for keyword in self.FOOD_KEYWORDS:
            if keyword.lower() in query_lower:
                food_score += 1
        
        # 如果明确提到"外卖"，优先认为是外卖
        if "外卖" in query_lower:
            food_score += 2
        
        # 如果明确提到"购物"或"买"，优先认为是购物
        if "购物" in query_lower or "买" in query_lower:
            shopping_score += 2
        
        if food_score > shopping_score:
            return "food"
        elif shopping_score > food_score:
            return "shopping"
        else:
            # 如果分数相等，使用大模型判断（如果可用）
            if self.use_llm:
                try:
                    return await self._detect_type_with_llm(query)
                except Exception as e:
                    logger.warning(f"大模型类型检测失败: {e}")
            
            # 默认购物
            return "shopping"
    
    async def _plan_with_llm(self, query: str, query_type: str, default_platforms: list[Platform]) -> Optional[list[Platform]]:
        """
        使用大模型进行规划
        """
        # 这里可以调用大模型API进行更精准的规划
        # 由于时间关系，先返回默认结果
        # 实际实现时可以调用 GLM-5 或 GPT-4o-mini
        return default_platforms
    
    async def _detect_type_with_llm(self, query: str) -> str:
        """
        使用大模型检测类型
        """
        # 这里可以调用大模型API进行类型检测
        # 简单实现：基于关键词的规则
        query_lower = query.lower()
        
        # 简单规则
        food_indicators = ["外卖", "餐厅", "饭店", "餐馆", "快餐", "套餐", "汉堡", "炸鸡", "披萨", "饿了么", "美团"]
        shopping_indicators = ["手机", "电脑", "电视", "家电", "服装", "鞋子", "包包", "化妆品", "买", "购买", "购物"]
        
        food_count = sum(1 for indicator in food_indicators if indicator in query_lower)
        shopping_count = sum(1 for indicator in shopping_indicators if indicator in query_lower)
        
        if food_count > shopping_count:
            return "food"
        else:
            return "shopping"
