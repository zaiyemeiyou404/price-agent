"""
饿了么/淘宝闪购爬虫工具 - 改进版

特性:
- 多选择器备选，页面变化时自动切换
- 地理定位支持
- Cookie持久化
- 智能重试
- 支持淘宝闪购入口（更稳定）
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


class ElemeTool(BaseTool, BaseCrawler):
    """饿了么/淘宝闪购爬虫工具"""
    
    platform = Platform.ELEME
    name = "淘宝闪购"
    description = "饿了么/淘宝闪购外卖搜索和比价"
    platform_name = "eleme"
    
    # 餐厅/商品列表选择器
    LIST_SELECTORS = [
        ".shop-list",
        ".restaurant-list",
        "#search-list",
        "[class*='shop-list']",
        "[class*='restaurant-list']",
    ]
    
    # 商品项选择器
    ITEM_SELECTORS = [
        ".shop-list li",
        ".shop-item",
        ".list-item",
        "[class*='shop-item']",
        "li[data-shopid]",
    ]
    
    def __init__(self):
        BaseTool.__init__(self)
        BaseCrawler.__init__(
            self,
            proxy=settings.crawler_proxy,
            headless=True,
            timeout=settings.crawler_timeout * 1000,
            use_mobile=True
        )
        self.lat = settings.meituan_lat
        self.lng = settings.meituan_lng
    
    async def _create_context_with_geo(self):
        """创建带地理位置的上下文"""
        browser = await self._browser_manager.get_browser(self.proxy, self.headless)
        
        context_options = {
            "viewport": {"width": 375, "height": 667},
            "user_agent": self._get_random_ua(),
            "locale": "zh-CN",
            "geolocation": {
                "latitude": self.lat,
                "longitude": self.lng
            },
            "permissions": ["geolocation"]
        }
        
        self._context = await browser.new_context(**context_options)
        
        # 注入反检测脚本
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)
        
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.timeout)
        
        return self._page
    
    @retry_with_backoff(max_attempts=3, backoff=[2, 4, 8])
    async def search(
        self, 
        query: str, 
        location: str = None,
        max_results: int = 15,
        **kwargs
    ) -> List[Product]:
        """
        搜索外卖
        
        Args:
            query: 搜索关键词
            location: 定位地址
            max_results: 最大结果数
        """
        logger.info(f"[饿了么] 开始搜索: {query}, 定位: ({self.lat}, {self.lng})")
        
        try:
            # 创建带定位的页面
            await self._create_context_with_geo()
            await self._load_cookies()
            
            # 尝试淘宝闪购入口（更稳定）
            success = await self._try_taobao_flash(query, max_results)
            if success:
                return success
            
            # 回退到饿了么
            products = await self._try_eleme(query, max_results)
            
            return products
            
        except Exception as e:
            logger.error(f"[饿了么] 搜索失败: {e}")
            return []
        finally:
            await self.close()
    
    async def _try_taobao_flash(self, query: str, max_results: int) -> Optional[List[Product]]:
        """
        尝试通过淘宝闪购入口搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            商品列表或None
        """
        try:
            # 淘宝闪购 URL
            url = f"https://s.taobao.com/search?q={quote(query)}&tab=flash"
            logger.info(f"[淘宝闪购] 访问: {url}")
            
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 检查是否有闪购结果
            await asyncio.sleep(2)
            
            # 尝试找到闪购商品
            flash_selectors = [
                "[class*='flash']",
                "[class*='Flash']",
                ".Content--contentInner",
            ]
            
            found_selector = await self._wait_for_selectors(flash_selectors, timeout=5000)
            
            if not found_selector:
                return None
            
            # 滚动加载
            await self._scroll_page(times=3, delay=1.5)
            
            # 解析商品
            products = await self._parse_taobao_flash_products(query, max_results)
            
            if products:
                logger.info(f"[淘宝闪购] 搜索完成，获取 {len(products)} 个商品")
                return products
            
            return None
            
        except Exception as e:
            logger.debug(f"[淘宝闪购] 搜索失败: {e}")
            return None
    
    async def _parse_taobao_flash_products(self, query: str, max_results: int) -> List[Product]:
        """解析淘宝闪购商品"""
        products = []
        
        # 使用淘宝的选择器
        item_selectors = [
            ".Card--doubleCardWrapper--L2XFE73",
            "[class*='Card--doubleCard']",
            ".item",
        ]
        
        items = []
        for selector in item_selectors:
            found = await self._page.query_selector_all(selector)
            if found:
                items = found
                break
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_taobao_flash_item(item, query, i)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                logger.debug(f"[淘宝闪购] 解析商品 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_taobao_flash_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析淘宝闪购商品项"""
        try:
            # 标题
            title = ""
            title_selectors = [".Title--title--jCOPvpf", "[class*='title']", "h3"]
            for selector in title_selectors:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break
            
            if not title:
                return None
            
            # 价格
            price = 0.0
            price_selectors = [".Price--priceInt--Z0S8aDr", "[class*='price']", "strong"]
            for selector in price_selectors:
                price_text = await self._safe_extract_text(item, selector)
                if price_text:
                    price = self._parse_price(price_text)
                    if price > 0:
                        break
            
            # 店铺
            shop_name = ""
            shop_selectors = [".ShopInfo--TextAndPic--yH0HfxQ a", "[class*='shop']"]
            for selector in shop_selectors:
                shop_name = await self._safe_extract_text(item, selector)
                if shop_name:
                    break
            
            if not shop_name:
                shop_name = "饿了么商家"
            
            # 链接和ID
            href = await self._safe_extract_attr(item, "href", "a")
            product_id = f"eleme_{index}"
            jump_url = ""
            
            if href:
                if href.startswith("//"):
                    jump_url = "https:" + href
                elif href.startswith("/"):
                    jump_url = "https://s.taobao.com" + href
                else:
                    jump_url = href
                
                # 提取ID
                match = re.search(r"id=(\d+)", href)
                if match:
                    product_id = match.group(1)
            
            # 图片
            image_url = ""
            img_el = await item.query_selector("img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            # 配送时间标记
            delivery_time = ""
            time_el = await item.query_selector("[class*='delivery'], [class*='配送']")
            if time_el:
                delivery_time = await time_el.inner_text()
            
            return Product(
                platform=Platform.ELEME,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                shop_name=shop_name.strip(),
                image_url=image_url,
                jump_url=jump_url,
                delivery_time=delivery_time,
                location=f"{self.lat},{self.lng}"
            )
            
        except Exception as e:
            logger.debug(f"[淘宝闪购] 解析详情失败: {e}")
            return None
    
    async def _try_eleme(self, query: str, max_results: int) -> List[Product]:
        """
        使用饿了么官网搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        """
        try:
            # 饿了么 URL
            url = "https://www.ele.me/"
            logger.info(f"[饿了么] 访问: {url}")
            
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 处理定位弹窗
            await self._handle_location_popup()
            
            # 执行搜索
            search_success = await self._perform_search(query)
            
            if not search_success:
                # 直接访问搜索URL
                search_url = f"https://www.ele.me/search?keyword={quote(query)}"
                await self._page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # 等待结果
            await self._wait_for_selectors(self.LIST_SELECTORS, timeout=10000)
            await self._scroll_page(times=3, delay=2.0)
            
            await self._save_cookies()
            
            # 解析结果
            products = await self._parse_eleme_products(query, max_results)
            
            logger.info(f"[饿了么] 搜索完成，获取 {len(products)} 个结果")
            return products
            
        except Exception as e:
            logger.error(f"[饿了么] 搜索失败: {e}")
            return []
    
    async def _handle_location_popup(self):
        """处理定位弹窗"""
        try:
            await asyncio.sleep(2)
            
            allow_selectors = [
                "button:has-text('允许')",
                "button:has-text('确定')",
                ".location-confirm-btn",
            ]
            
            for selector in allow_selectors:
                try:
                    btn = await self._page.query_selector(selector)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue
                    
        except Exception:
            pass
    
    async def _perform_search(self, query: str) -> bool:
        """执行搜索"""
        try:
            search_selectors = [
                "input[type='search']",
                ".search-input",
                "#search-input",
                "[class*='search'] input",
            ]
            
            for selector in search_selectors:
                search_box = await self._page.query_selector(selector)
                if search_box:
                    await search_box.click()
                    await self._random_delay(0.5, 1)
                    await search_box.fill(query)
                    await self._random_delay(0.3, 0.5)
                    await search_box.press("Enter")
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def _parse_eleme_products(self, query: str, max_results: int) -> List[Product]:
        """解析饿了么商品列表"""
        products = []
        
        items = []
        for selector in self.ITEM_SELECTORS:
            found = await self._page.query_selector_all(selector)
            if found and len(found) > 0:
                items = found
                break
        
        if not items:
            items = await self._page.query_selector_all("li[class*='item'], div[class*='item']")
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_eleme_item(item, query, i)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug(f"[饿了么] 解析项 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_eleme_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析饿了么商品项"""
        try:
            # 提取ID
            product_id = f"eleme_{index}"
            
            link_el = await item.query_selector("a")
            href = ""
            if link_el:
                href = await link_el.get_attribute("href") or ""
                
                match = re.search(r"/shop/(\d+)", href)
                if match:
                    product_id = match.group(1)
            
            # 标题
            title = ""
            title_selectors = [".shop-name", "[class*='name']", "h3"]
            for selector in title_selectors:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break
            
            if not title:
                title = query
            
            # 价格
            price = 30.0
            price_selectors = [".price", ".avg-price", "[class*='price']"]
            for selector in price_selectors:
                price_text = await self._safe_extract_text(item, selector)
                if price_text:
                    parsed = self._parse_price(price_text)
                    if parsed > 0:
                        price = parsed
                        break
            
            # 店铺名
            shop_name = ""
            shop_el = await item.query_selector("[class*='shop'], [class*='store']")
            if shop_el:
                shop_name = await shop_el.inner_text()
            
            if not shop_name:
                shop_name = title
            
            # 图片
            image_url = ""
            img_el = await item.query_selector("img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            # 链接
            jump_url = ""
            if href:
                if href.startswith("//"):
                    jump_url = "https:" + href
                elif href.startswith("/"):
                    jump_url = "https://www.ele.me" + href
                elif href.startswith("http"):
                    jump_url = href
            
            if not jump_url:
                jump_url = f"https://www.ele.me/shop/{product_id}"
            
            # 配送费
            delivery_fee = 0.0
            fee_el = await item.query_selector("[class*='delivery-fee'], [class*='fee']")
            if fee_el:
                delivery_fee = self._parse_price(await fee_el.inner_text())
            
            # 配送时间
            delivery_time = ""
            time_el = await item.query_selector("[class*='delivery-time'], [class*='time']")
            if time_el:
                delivery_time = await time_el.inner_text()
            
            # 优惠券
            coupon = None
            coupon_el = await item.query_selector("[class*='coupon'], [class*='discount']")
            if coupon_el:
                coupon = await coupon_el.inner_text()
            
            return Product(
                platform=Platform.ELEME,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                coupon=coupon,
                shop_name=shop_name.strip(),
                image_url=image_url,
                jump_url=jump_url,
                delivery_fee=delivery_fee,
                delivery_time=delivery_time,
                location=f"{self.lat},{self.lng}"
            )
            
        except Exception as e:
            logger.debug(f"[饿了么] 解析详情失败: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> float:
        """解析价格"""
        try:
            cleaned = re.sub(r"[^\d.]", "", price_text)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    @retry_with_backoff(max_attempts=2, backoff=[2, 4])
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """获取餐厅/商品详情"""
        logger.info(f"[饿了么] 获取详情: {product_id}")
        
        try:
            await self._create_context_with_geo()
            await self._load_cookies()
            
            url = f"https://www.ele.me/shop/{product_id}"
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取餐厅名
            title = ""
            title_el = await self._page.query_selector(".shop-name, h1, [class*='name']")
            if title_el:
                title = await title_el.inner_text()
            
            # 平均价格
            price = 30.0
            price_el = await self._page.query_selector("[class*='avg-price'], [class*='price']")
            if price_el:
                price = self._parse_price(await price_el.inner_text()) or price
            
            # 配送信息
            delivery_fee = 0.0
            delivery_time = ""
            
            fee_el = await self._page.query_selector("[class*='delivery-fee']")
            if fee_el:
                delivery_fee = self._parse_price(await fee_el.inner_text())
            
            time_el = await self._page.query_selector("[class*='delivery-time']")
            if time_el:
                delivery_time = await time_el.inner_text()
            
            await self._save_cookies()
            
            return Product(
                platform=Platform.ELEME,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                shop_name=title.strip(),
                jump_url=url,
                delivery_fee=delivery_fee,
                delivery_time=delivery_time,
                location=f"{self.lat},{self.lng}"
            )
            
        except Exception as e:
            logger.error(f"[饿了么] 获取详情失败: {e}")
            return None
        finally:
            await self.close()


# 导出
__all__ = ["ElemeTool"]
