"""
反思器 - 分析比价结果，生成最优推荐

TODO: 实现
1. 对比各平台价格
2. 计算优惠叠加后的最终价格
3. 考虑配送费、配送时间等因素
4. 使用大模型生成自然语言推荐

示例输出:
{
    "best_platform": "jd",
    "best_price": 5999,
    "savings": 300,
    "reason": "京东价格最低，叠加满减后比淘宝便宜300元，且配送快"
}
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from app.models import Product, Platform, ProductType
from app.config import settings


class Reflector:
    """反思器"""
    
    def __init__(self):
        self.use_llm = bool(settings.glm5_api_key or settings.openai_api_key or settings.deepseek_api_key)
        logger.info(f"Reflector 初始化，使用大模型: {self.use_llm}")
    
    async def reflect(self, products: List[Product]) -> Dict[str, Any]:
        """
        分析商品列表，生成推荐
        """
        if not products:
            return {
                "best_deal": None,
                "summary": "未找到相关商品"
            }
        
        # 找出价格最低的商品
        best_product = None
        best_final_price = float('inf')
        
        for product in products:
            final_price = product.final_price
            # 如果是外卖，加上配送费
            if product.platform in [Platform.ELEME, Platform.MEITUAN] and product.delivery_fee:
                final_price += product.delivery_fee
            
            if final_price < best_final_price:
                best_final_price = final_price
                best_product = product
        
        if not best_product:
            return {
                "best_deal": None,
                "summary": "无法确定最佳商品"
            }
        
        # 生成对比数据
        comparison = self._generate_comparison(products, best_product)
        
        # 生成摘要
        summary = await self.generate_summary(products, {
            "best_product": best_product,
            "best_final_price": best_final_price,
            "comparison": comparison
        })
        
        return {
            "best_deal": best_product,
            "summary": summary,
            "comparison": comparison
        }
    
    def _generate_comparison(self, products: List[Product], best_product: Product) -> Dict[str, Any]:
        """生成对比数据"""
        # 按平台分组
        platforms_data = {}
        for product in products:
            platform = product.platform.value
            if platform not in platforms_data:
                platforms_data[platform] = {
                    "count": 0,
                    "min_price": float('inf'),
                    "max_price": 0,
                    "products": []
                }
            
            platforms_data[platform]["count"] += 1
            final_price = product.final_price
            if product.platform in [Platform.ELEME, Platform.MEITUAN] and product.delivery_fee:
                final_price += product.delivery_fee
            
            platforms_data[platform]["min_price"] = min(platforms_data[platform]["min_price"], final_price)
            platforms_data[platform]["max_price"] = max(platforms_data[platform]["max_price"], final_price)
            platforms_data[platform]["products"].append(product)
        
        # 计算各平台平均价格
        for platform, data in platforms_data.items():
            if data["count"] > 0:
                avg_price = (data["min_price"] + data["max_price"]) / 2
                data["avg_price"] = round(avg_price, 2)
            else:
                data["avg_price"] = 0
        
        # 找出第二便宜的平台
        second_best = None
        second_best_price = float('inf')
        
        for platform, data in platforms_data.items():
            if platform == best_product.platform.value:
                continue
            if data["min_price"] < second_best_price:
                second_best_price = data["min_price"]
                second_best = platform
        
        # 计算节省金额
        savings = 0
        if second_best and second_best_price < float('inf'):
            best_final_price = best_product.final_price
            if best_product.platform in [Platform.ELEME, Platform.MEITUAN] and best_product.delivery_fee:
                best_final_price += best_product.delivery_fee
            
            savings = round(second_best_price - best_final_price, 2)
        
        return {
            "platforms": platforms_data,
            "second_best_platform": second_best,
            "second_best_price": second_best_price,
            "savings": savings,
            "total_products": len(products)
        }
    
    async def generate_summary(self, products: List[Product], analysis: Dict[str, Any]) -> str:
        """
        生成自然语言摘要
        """
        best_product = analysis["best_product"]
        best_final_price = analysis["best_final_price"]
        comparison = analysis["comparison"]
        
        if self.use_llm:
            try:
                return await self._generate_summary_with_llm(products, analysis)
            except Exception as e:
                logger.warning(f"大模型生成摘要失败，使用规则摘要: {e}")
        
        # 规则生成摘要
        platform_names = {
            Platform.TAOBAO.value: "淘宝",
            Platform.JD.value: "京东",
            Platform.ELEME.value: "淘宝闪购",
            Platform.MEITUAN.value: "美团外卖"
        }
        
        best_platform = platform_names.get(best_product.platform.value, best_product.platform.value)
        
        # 判断查询类型
        is_food = best_product.platform in [Platform.ELEME, Platform.MEITUAN]
        
        summary_parts = []
        
        # 标题
        if is_food:
            summary_parts.append(f"📊 【{best_product.title}】外卖比价报告")
        else:
            summary_parts.append(f"📊 【{best_product.title}】购物比价报告")
        
        summary_parts.append("━━━━━━━━━━━━━━━━━━")
        
        # 平台对比
        if is_food:
            summary_parts.append("🍕 外卖平台对比:\n")
        else:
            summary_parts.append("🛒 购物平台对比:\n")
        
        # 添加对比表格
        table_lines = []
        table_lines.append("┌──────────┬─────────┬─────────┬─────────┐")
        if is_food:
            table_lines.append("│ 平台     │ 价格    │ 配送费  │ 实付    │")
        else:
            table_lines.append("│ 平台     │ 原价    │ 优惠    │ 券后价  │")
        table_lines.append("├──────────┼─────────┼─────────┼─────────┤")
        
        for platform, data in comparison["platforms"].items():
            platform_name = platform_names.get(platform, platform)
            products = data["products"][:3]  # 取前3个商品
            
            if products:
                product = products[0]
                original_price = product.original_price or product.price
                final_price = product.final_price
                
                if is_food and product.delivery_fee:
                    final_price += product.delivery_fee
                
                # 标记最优
                is_best = platform == best_product.platform.value
                best_mark = " 👑" if is_best else ""
                
                if is_food:
                    delivery_fee = product.delivery_fee or 0
                    table_lines.append(f"│ {platform_name:<8} │ ¥{original_price:<6} │ ¥{delivery_fee:<6} │ ¥{final_price:<6}{best_mark} │")
                else:
                    coupon_amount = product.coupon_amount or 0
                    table_lines.append(f"│ {platform_name:<8} │ ¥{original_price:<6} │ -{coupon_amount:<6} │ ¥{final_price:<6}{best_mark} │")
        
        table_lines.append("└──────────┴─────────┴─────────┴─────────┘")
        summary_parts.append("\n".join(table_lines))
        
        # 最优推荐
        summary_parts.append(f"\n🏆 最优推荐: {best_platform}")
        summary_parts.append(f"💰 实付价格: ¥{best_final_price}")
        
        if comparison["savings"] > 0:
            summary_parts.append(f"💸 预计节省: ¥{comparison['savings']}")
        
        # 附加信息
        if is_food and best_product.delivery_time:
            summary_parts.append(f"⏰ 预计送达: {best_product.delivery_time}")
        
        if best_product.jump_url:
            summary_parts.append(f"🔗 购买链接: {best_product.jump_url}")
        
        # 简单分析
        summary_parts.append(f"\n📝 分析:")
        if is_food:
            summary_parts.append(f"{best_platform}的价格最低")
            if best_product.coupon:
                summary_parts.append(f"可使用优惠: {best_product.coupon}")
            if best_product.delivery_fee:
                summary_parts.append(f"配送费: ¥{best_product.delivery_fee}")
        else:
            summary_parts.append(f"{best_platform}的价格最有竞争力")
            if best_product.coupon:
                summary_parts.append(f"优惠券: {best_product.coupon}")
        
        return "\n".join(summary_parts)
    
    async def _generate_summary_with_llm(self, products: List[Product], analysis: Dict[str, Any]) -> str:
        """
        使用大模型生成摘要
        """
        # 这里可以调用大模型API生成更自然的摘要
        # 由于时间关系，先返回规则生成的摘要
        best_product = analysis["best_product"]
        best_final_price = analysis["best_final_price"]
        
        platform_names = {
            Platform.TAOBAO.value: "淘宝",
            Platform.JD.value: "京东",
            Platform.ELEME.value: "淘宝闪购",
            Platform.MEITUAN.value: "美团外卖"
        }
        
        best_platform = platform_names.get(best_product.platform.value, best_product.platform.value)
        
        if best_product.platform in [Platform.ELEME, Platform.MEITUAN]:
            # 外卖
            return f"根据比价结果，{best_platform}上的{best_product.title}价格最低，实付¥{best_final_price}。推荐在{best_platform}下单。"
        else:
            # 购物
            return f"经过比价，{best_platform}上的{best_product.title}价格最优，券后价¥{best_final_price}。建议在{best_platform}购买。"
