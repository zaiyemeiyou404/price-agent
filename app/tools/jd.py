"""
京东爬虫工具 - 改进版

特性:
- 多选择器备选，页面变化时自动切换
- 完整的反爬指纹伪装
- Cookie持久化支持
- 支持PC端和移动端
- 智能重试
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


class JDTool(BaseTool, BaseCrawler):
    """京东爬虫工具"""
    
    platform = Platform.JD
    name = "京东"
    description = "京东商品搜索和比价"
    platform_name = "jd"
    
    # 商品列表选择器 - 2026年更新
    LIST_SELECTORS = [
        "[class*='J-goods-list']",
        "[class*='goods-list']",
        "#J_goodsList",
        ".goods-list-v2",
        "#search-list",
    ]
    
    # 商品项选择器 - 2026年更新
    ITEM_SELECTORS = [
        ".gl-item[data-sku]",
        ".J-goods-list .gl-item",
        "li.gl-item",
        ".goods-list-v2 li",
        "#J_goodsList .gl-item",
        ".goods-v2 li",
        "li[data-sku]",
    ]
    
    # 标题选择器
    TITLE_SELECTORS = [
        "[class*='p-name'] a",
        "[class*='p-name'] em",
        ".p-name a",
        ".p-name em",
        "[class*='name']",
        "h3",
    ]
    
    # 价格选择器
    PRICE_SELECTORS = [
        "[class*='p-price'] i",
        ".p-price i",
        "[class*='price']",
        ".price",
    ]
    
    def __init__(self):
        BaseTool.__init__(self)
        BaseCrawler.__init__(
            self,
            proxy=settings.crawler_proxy,
            headless=True,
            timeout=settings.crawler_timeout * 1000,
            use_mobile=False  # 使用PC端获取更多信息
        )
    
    @retry_with_backoff(max_attempts=3, backoff=[2, 4, 8])
    async def search(self, query: str, max_results: int = 20, **kwargs) -> List[Product]:
        """
        搜索京东商品
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            商品列表
        """
        logger.info(f"[京东] 开始搜索: {query}")
        
        try:
            page = await self._create_page()
            
            # 加载Cookie
            cookies_loaded = await self._load_cookies()
            if not cookies_loaded:
                logger.warning("[京东] ⚠ 未加载Cookie，搜索结果可能受限")
                logger.warning("[京东] 请运行: python login.py jd qr")
            
            # 访问京东首页建立会话
            try:
                await page.goto("https://www.jd.com", wait_until="domcontentloaded", timeout=60000)
                await self._random_delay(2, 3)
            except Exception as e:
                logger.warning(f"[京东] 访问首页超时: {e}")
            
            # 检测是否需要登录
            if await self._check_login_required():
                logger.warning("[京东] ⚠ 检测到需要登录！")
                logger.warning("[京东] 请运行: python login.py jd qr")
            
            # 搜索URL
            url = f"https://search.jd.com/Search?keyword={quote(query)}"
            logger.info(f"[京东] 访问: {url}")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self._random_delay(3, 5)
            except Exception as e:
                logger.warning(f"[京东] 访问搜索页超时: {e}")
                await self._random_delay(2, 3)
            
            # 等待商品列表
            list_selector = await self._wait_for_selectors(self.LIST_SELECTORS, timeout=15000)
            
            # 京东需要滚动加载
            await self._scroll_page(times=5, delay=1.0)
            
            # 额外滚动确保加载
            for _ in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
            
            await self._save_cookies()
            
            # 解析商品
            products = await self._parse_products(query, max_results)
            
            logger.info(f"[京东] 搜索完成，获取 {len(products)} 个商品")
            return products
            
        except Exception as e:
            logger.error(f"[京东] 搜索失败: {e}")
            return []
        finally:
            await self.close()
    
    async def _parse_products(self, query: str, max_results: int) -> List[Product]:
        """解析商品列表"""
        products = []
        
        # 尝试不同的商品项选择器
        items = []
        for selector in self.ITEM_SELECTORS:
            found = await self._page.query_selector_all(selector)
            if found and len(found) > 0:
                items = found
                logger.info(f"[京东] 使用选择器 '{selector}' 找到 {len(items)} 个商品")
                break
        
        if not items:
            # 尝试更多选择器
            items = await self._page.query_selector_all("li[data-sku]")
            if items:
                logger.info(f"[京东] 通过 data-sku 找到 {len(items)} 个商品")
        
        if not items:
            # 最后尝试 - 但需要确保是商品元素
            items = await self._page.query_selector_all(".gl-item, li[data-sku]")
            if items:
                logger.info(f"[京东] 通过备选选择器找到 {len(items)} 个商品")
        
        if not items:
            logger.warning("[京东] 未找到任何商品元素，页面可能需要登录或验证码")
            return []
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_item(item, query, i)
                if product:
                    # 价格可能为0，也保留
                    products.append(product)
                    logger.debug(f"[京东] 商品 {i}: 价格={product.price}, 标题={product.title[:30]}")
            except Exception as e:
                logger.debug(f"[京东] 解析商品 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析单个商品"""
        try:
            # 商品ID
            product_id = await item.get_attribute("data-sku")
            if not product_id:
                # 尝试从链接提取
                link_el = await item.query_selector("a")
                if link_el:
                    href = await link_el.get_attribute("href") or ""
                    match = re.search(r"/(\d+)\.html", href)
                    if match:
                        product_id = match.group(1)
            
            if not product_id:
                product_id = f"jd_{index}"
            
            # 标题
            title = ""
            for selector in self.TITLE_SELECTORS:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break
            
            if not title:
                return None
            
            # 价格
            price_text = ""
            price = 0.0
            
            for selector in self.PRICE_SELECTORS:
                price_el = await item.query_selector(selector)
                if price_el:
                    price_text = await price_el.inner_text()
                    if price_text:
                        # 直接解析价格
                        try:
                            # 提取数字
                            match = re.search(r'(\d+\.?\d*)', price_text.replace(',', ''))
                            if match:
                                price = float(match.group(1))
                                if 0.01 <= price <= 999999:
                                    break
                        except:
                            pass
            
            # 如果价格解析失败，尝试调用价格接口
            if price <= 0:
                price = await self._fetch_price_from_api(product_id)
            
            # 店铺名
            shop_name = "京东自营"
            shop_el = await item.query_selector(".p-shop a, .p-shop")
            if shop_el:
                shop_text = await shop_el.inner_text()
                if shop_text:
                    shop_name = shop_text
            
            # 图片
            image_url = ""
            img_el = await item.query_selector(".p-img img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-lazy-img")
                if image_url:
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
            
            # 链接
            jump_url = f"https://item.jd.com/{product_id}.html"
            link_el = await item.query_selector(".p-img a")
            if link_el:
                href = await link_el.get_attribute("href")
                if href:
                    if href.startswith("//"):
                        jump_url = "https:" + href
                    elif href.startswith("/"):
                        jump_url = "https://item.jd.com" + href
                    elif href.startswith("http"):
                        jump_url = href
            
            # 销量/评价数
            sales = 0
            sales_el = await item.query_selector(".p-commit strong a, .p-commit")
            if sales_el:
                sales_text = await sales_el.inner_text()
                sales = self._parse_sales(sales_text)
            
            # 优惠券
            coupon = None
            coupon_el = await item.query_selector(".p-icons [class*='coupon'], .coupon")
            if coupon_el:
                coupon = await coupon_el.inner_text()
            
            # 判断是否自营
            is_self_operated = False
            icons_el = await item.query_selector(".p-icons")
            if icons_el:
                icons_text = await icons_el.inner_text()
                is_self_operated = "自营" in icons_text
            
            return Product(
                platform=Platform.JD,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                coupon=coupon,
                shop_name=shop_name.strip() if shop_name else "京东",
                sales=sales,
                jump_url=jump_url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.debug(f"[京东] 解析商品详情失败: {e}")
            return None
    
    async def _fetch_price_from_api(self, product_id: str) -> float:
        """
        从京东价格接口获取价格
        
        Args:
            product_id: 商品ID
        
        Returns:
            价格
        """
        try:
            # 京东价格接口
            price_url = f"https://p.3.cn/prices/mgets?skuIds=J_{product_id}"
            
            response = await self._page.evaluate(f'''
                fetch("{price_url}")
                    .then(r => r.json())
                    .then(data => data)
                    .catch(() => null)
            ''')
            
            if response and len(response) > 0:
                price_str = response[0].get("p", "0")
                return float(price_str)
            
        except Exception as e:
            logger.debug(f"[京东] 价格接口获取失败: {e}")
        
        return 0.0
    
    def _parse_price(self, price_text: str) -> float:
        """解析价格"""
        try:
            cleaned = re.sub(r"[^\d.]", "", price_text)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_sales(self, sales_text: str) -> int:
        """解析销量/评价数"""
        try:
            # 处理 "10万+" 格式
            if "万" in sales_text:
                match = re.search(r"(\d+\.?\d*)万", sales_text)
                if match:
                    return int(float(match.group(1)) * 10000)
            
            # 提取数字
            match = re.search(r"(\d+)", sales_text.replace(",", ""))
            return int(match.group(1)) if match else 0
        except Exception:
            return 0
    
    @retry_with_backoff(max_attempts=2, backoff=[2, 4])
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """
        获取商品详情
        
        Args:
            product_id: 商品ID
        
        Returns:
            商品详情
        """
        logger.info(f"[京东] 获取商品详情: {product_id}")
        
        try:
            page = await self._create_page()
            await self._load_cookies()
            
            url = f"https://item.jd.com/{product_id}.html"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取标题
            title = ""
            title_selectors = [
                ".sku-name",
                ".itemInfo-wrap .item-name",
                "h1",
            ]
            for selector in title_selectors:
                title_el = await page.query_selector(selector)
                if title_el:
                    title = await title_el.inner_text()
                    if title:
                        break
            
            # 提取价格
            price = await self._fetch_price_from_api(product_id)
            if price <= 0:
                price_el = await page.query_selector(".p-price .price")
                if price_el:
                    price_text = await price_el.inner_text()
                    price = self._parse_price(price_text)
            
            # 店铺信息
            shop_name = "京东自营"
            shop_el = await page.query_selector(".name a, .shopName a")
            if shop_el:
                shop_name = await shop_el.inner_text()
            
            # 图片
            image_url = ""
            img_el = await page.query_selector("#preview img, .preview-wrap img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-origin")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            # 优惠券
            coupon = None
            coupon_el = await page.query_selector(".quotation-item .coupon")
            if coupon_el:
                coupon = await coupon_el.inner_text()
            
            await self._save_cookies()
            
            return Product(
                platform=Platform.JD,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                coupon=coupon,
                shop_name=shop_name.strip(),
                jump_url=url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.error(f"[京东] 获取商品详情失败: {e}")
            return None
        finally:
            await self.close()


# 导出
__all__ = ["JDTool"]
