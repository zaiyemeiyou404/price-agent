"""
拼多多爬虫工具

特性:
- 多选择器备选
- 完整的反爬指纹伪装
- Cookie持久化
- 智能重试

注意: 拼多多反爬严格，建议使用多多进宝API
"""
import asyncio
import re
from typing import Optional, List
from urllib.parse import quote
from loguru import logger

from app.tools.base import BaseTool
from app.tools.base_crawler import BaseCrawler, retry_with_backoff
from app.models import Product, Platform
from app.config import settings


class PDDTool(BaseTool, BaseCrawler):
    """拼多多爬虫工具"""
    
    # 注意：拼多多没有在 Platform 枚举中，这里使用扩展方式
    # 如果需要正式支持，请在 models 中添加 Platform.PDD
    
    name = "拼多多"
    description = "拼多多商品搜索和比价"
    platform_name = "pdd"
    
    # 商品列表选择器
    LIST_SELECTORS = [
        "#mallSearchList",
        ".goods-list",
        "[class*='goods-list']",
        "[class*='search-result']",
    ]
    
    # 商品项选择器
    ITEM_SELECTORS = [
        ".goods-item",
        "[class*='goods-item']",
        "[data-gid]",
        "li[class*='item']",
    ]
    
    def __init__(self):
        BaseTool.__init__(self)
        BaseCrawler.__init__(
            self,
            proxy=settings.crawler_proxy,
            headless=True,
            timeout=settings.crawler_timeout * 1000,
            use_mobile=True  # 拼多多移动端更友好
        )
    
    @retry_with_backoff(max_attempts=3, backoff=[2, 4, 8])
    async def search(self, query: str, max_results: int = 20, **kwargs) -> List[Product]:
        """
        搜索拼多多商品
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            商品列表
        """
        logger.info(f"[拼多多] 开始搜索: {query}")
        
        try:
            page = await self._create_page()
            await self._load_cookies()
            
            # 拼多多搜索 URL (H5页面)
            url = f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(query)}"
            logger.info(f"[拼多多] 访问: {url}")
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 检测验证码
            if await self._detect_captcha():
                logger.warning("[拼多多] 检测到验证码，跳过")
                return []
            
            # 等待商品列表
            await self._wait_for_selectors(self.LIST_SELECTORS, timeout=15000)
            
            # 滚动加载
            await self._scroll_page(times=5, delay=1.5)
            
            await self._save_cookies()
            
            # 解析商品
            products = await self._parse_products(query, max_results)
            
            logger.info(f"[拼多多] 搜索完成，获取 {len(products)} 个商品")
            return products
            
        except Exception as e:
            logger.error(f"[拼多多] 搜索失败: {e}")
            return []
        finally:
            await self.close()
    
    async def _parse_products(self, query: str, max_results: int) -> List[Product]:
        """解析商品列表"""
        products = []
        
        items = []
        for selector in self.ITEM_SELECTORS:
            found = await self._page.query_selector_all(selector)
            if found and len(found) > 0:
                items = found
                logger.info(f"[拼多多] 使用选择器 '{selector}' 找到 {len(items)} 个商品")
                break
        
        if not items:
            # 尝试通用选择器
            items = await self._page.query_selector_all("a[href*='goods_id']")
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_item(item, query, i)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                logger.debug(f"[拼多多] 解析商品 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析单个商品"""
        try:
            # 商品ID
            product_id = ""
            href = await self._safe_extract_attr(item, "href") or ""
            
            if "goods_id=" in href:
                match = re.search(r"goods_id=(\d+)", href)
                if match:
                    product_id = match.group(1)
            
            if not product_id:
                product_id = f"pdd_{index}"
            
            # 标题
            title = ""
            title_selectors = [
                "[class*='title']",
                "[class*='goods-name']",
                "h3",
                "p",
            ]
            for selector in title_selectors:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break
            
            if not title:
                # 尝试获取文本内容
                title = await self._safe_extract_text(item)
            
            if not title:
                return None
            
            # 价格
            price = 0.0
            price_selectors = [
                "[class*='price']",
                "[class*='Price']",
            ]
            for selector in price_selectors:
                price_text = await self._safe_extract_text(item, selector)
                if price_text:
                    price = self._parse_price(price_text)
                    if price > 0:
                        break
            
            # 如果价格还是0，尝试提取数字
            if price <= 0:
                all_text = await item.inner_text()
                price = self._parse_price(all_text)
            
            # 店铺名
            shop_name = "拼多多店铺"
            shop_el = await item.query_selector("[class*='mall'], [class*='shop']")
            if shop_el:
                shop_name = await shop_el.inner_text()
            
            # 图片
            image_url = ""
            img_el = await item.query_selector("img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src")
                if image_url:
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
            
            # 链接
            jump_url = ""
            if href:
                if href.startswith("//"):
                    jump_url = "https:" + href
                elif href.startswith("/"):
                    jump_url = "https://mobile.yangkeduo.com" + href
                elif href.startswith("http"):
                    jump_url = href
            
            if not jump_url and product_id:
                jump_url = f"https://mobile.yangkeduo.com/goods.html?goods_id={product_id}"
            
            # 销量
            sales = 0
            sales_el = await item.query_selector("[class*='sales'], [class*='sold']")
            if sales_el:
                sales_text = await sales_el.inner_text()
                sales = self._parse_sales(sales_text)
            
            return Product(
                platform=Platform.PDD,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                shop_name=shop_name.strip(),
                sales=sales,
                jump_url=jump_url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.debug(f"[拼多多] 解析商品详情失败: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> float:
        """解析价格"""
        try:
            # 提取数字
            match = re.search(r"(\d+\.?\d*)", price_text.replace("￥", "").replace("¥", ""))
            if match:
                return float(match.group(1))
            return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_sales(self, sales_text: str) -> int:
        """解析销量"""
        try:
            if "万" in sales_text:
                match = re.search(r"(\d+\.?\d*)万", sales_text)
                if match:
                    return int(float(match.group(1)) * 10000)
            
            match = re.search(r"(\d+)", sales_text.replace(",", ""))
            return int(match.group(1)) if match else 0
        except Exception:
            return 0
    
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """获取商品详情"""
        logger.info(f"[拼多多] 获取商品详情: {product_id}")
        
        try:
            page = await self._create_page()
            await self._load_cookies()
            
            url = f"https://mobile.yangkeduo.com/goods.html?goods_id={product_id}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取标题
            title = ""
            title_el = await page.query_selector("[class*='title'], h1")
            if title_el:
                title = await title_el.inner_text()
            
            # 提取价格
            price = 0.0
            price_el = await page.query_selector("[class*='price']")
            if price_el:
                price_text = await price_el.inner_text()
                price = self._parse_price(price_text)
            
            # 图片
            image_url = ""
            img_el = await page.query_selector("img[class*='main'], img[class*='detail']")
            if img_el:
                image_url = await img_el.get_attribute("src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            await self._save_cookies()
            
            return Product(
                platform=Platform.PDD,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                jump_url=url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.error(f"[拼多多] 获取商品详情失败: {e}")
            return None
        finally:
            await self.close()


# 导出
__all__ = ["PDDTool"]
