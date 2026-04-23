"""
美团外卖爬虫工具 - 改进版

特性:
- 多选择器备选，页面变化时自动切换
- 地理定位支持
- Cookie持久化
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


class MeituanTool(BaseTool, BaseCrawler):
    """美团外卖爬虫工具"""
    
    platform = Platform.MEITUAN
    name = "美团外卖"
    description = "美团外卖搜索和比价"
    platform_name = "meituan"
    
    # 餐厅/商品列表选择器
    LIST_SELECTORS = [
        ".restaurant-list",
        ".shop-list",
        "#search-list",
        "[class*='restaurant']",
        "[class*='shop-list']",
    ]
    
    # 商品项选择器
    ITEM_SELECTORS = [
        ".restaurant-list li",
        ".shop-item",
        ".list-item",
        "[class*='shop-item']",
        "[class*='restaurant-item']",
    ]
    
    def __init__(self):
        BaseTool.__init__(self)
        BaseCrawler.__init__(
            self,
            proxy=settings.crawler_proxy,
            headless=True,
            timeout=settings.crawler_timeout * 1000,
            use_mobile=True  # 美团外卖使用移动端视图
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
        lat: float = None, 
        lng: float = None,
        max_results: int = 15,
        **kwargs
    ) -> List[Product]:
        """
        搜索外卖
        
        Args:
            query: 搜索关键词
            location: 定位地址（可选）
            lat: 纬度（可选）
            lng: 经度（可选）
            max_results: 最大结果数
        """
        # 使用传入的定位或默认定位
        if lat is not None and lng is not None:
            self.lat = lat
            self.lng = lng
        
        logger.info(f"[美团] 开始搜索: {query}, 定位: ({self.lat}, {self.lng})")
        
        try:
            # 创建带定位的页面
            await self._create_context_with_geo()
            await self._load_cookies()
            
            # 访问美团外卖首页
            url = "https://waimai.meituan.com/"
            logger.info(f"[美团] 访问: {url}")
            
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 处理可能的定位弹窗
            await self._handle_location_popup()
            
            # 执行搜索
            search_success = await self._perform_search(query)
            
            if not search_success:
                logger.warning("[美团] 搜索入口未找到，尝试直接访问搜索URL")
                search_url = f"https://waimai.meituan.com/search?keyword={quote(query)}"
                await self._page.goto(search_url, wait_until="networkidle", timeout=30000)
            
            # 等待结果
            await self._wait_for_selectors(self.LIST_SELECTORS, timeout=10000)
            await self._scroll_page(times=3, delay=2.0)
            
            await self._save_cookies()
            
            # 解析结果
            products = await self._parse_products(query, max_results)
            
            logger.info(f"[美团] 搜索完成，获取 {len(products)} 个结果")
            return products
            
        except Exception as e:
            logger.error(f"[美团] 搜索失败: {e}")
            return []
        finally:
            await self.close()
    
    async def _handle_location_popup(self):
        """处理定位弹窗"""
        try:
            await asyncio.sleep(2)
            
            # 尝试点击允许定位
            allow_selectors = [
                "button:has-text('允许')",
                "button:has-text('确定')",
                ".location-confirm-btn",
                "[class*='allow']",
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
                    
        except Exception as e:
            logger.debug(f"[美团] 处理定位弹窗: {e}")
    
    async def _perform_search(self, query: str) -> bool:
        """执行搜索"""
        try:
            # 查找搜索框
            search_selectors = [
                "input[type='search']",
                ".search-input",
                "#search-input",
                "[class*='search'] input",
            ]
            
            search_box = None
            for selector in search_selectors:
                found = await self._page.query_selector(selector)
                if found:
                    search_box = found
                    break
            
            if search_box:
                await search_box.click()
                await self._random_delay(0.5, 1)
                await search_box.fill(query)
                await self._random_delay(0.3, 0.5)
                await search_box.press("Enter")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"[美团] 执行搜索失败: {e}")
            return False
    
    async def _parse_products(self, query: str, max_results: int) -> List[Product]:
        """解析商品/餐厅列表"""
        products = []
        
        # 尝试不同的选择器
        items = []
        for selector in self.ITEM_SELECTORS:
            found = await self._page.query_selector_all(selector)
            if found and len(found) > 0:
                items = found
                logger.info(f"[美团] 使用选择器 '{selector}' 找到 {len(items)} 个结果")
                break
        
        if not items:
            # 尝试通用的列表项
            items = await self._page.query_selector_all("li[class*='item'], div[class*='item']")
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_item(item, query, i)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug(f"[美团] 解析项 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析单个商品/餐厅"""
        try:
            # 判断是餐厅还是菜品
            is_restaurant = await self._detect_restaurant(item)
            
            # 提取ID
            product_id = await self._extract_id(item, index)
            
            # 提取标题
            title = ""
            title_selectors = [
                ".shop-name",
                ".restaurant-name",
                ".name",
                "[class*='name']",
                "h3",
            ]
            for selector in title_selectors:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break
            
            if not title:
                title = query
            
            # 提取价格
            price = 35.0  # 默认价格
            price_selectors = [
                ".price",
                ".avg-price",
                "[class*='price']",
            ]
            for selector in price_selectors:
                price_text = await self._safe_extract_text(item, selector)
                if price_text:
                    price = self._parse_price(price_text)
                    if price > 0:
                        break
            
            # 原价
            original_price = price
            original_el = await item.query_selector("[class*='original-price'], [class*='del']")
            if original_el:
                original_price = self._parse_price(await original_el.inner_text()) or price
            
            # 店铺名
            shop_name = title if is_restaurant else ""
            if not is_restaurant:
                shop_el = await item.query_selector("[class*='shop'], [class*='store']")
                if shop_el:
                    shop_name = await shop_el.inner_text()
            
            # 图片
            image_url = ""
            img_el = await item.query_selector("img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            # 链接
            jump_url = ""
            link_el = await item.query_selector("a")
            if link_el:
                href = await link_el.get_attribute("href") or ""
                if href.startswith("//"):
                    jump_url = "https:" + href
                elif href.startswith("/"):
                    jump_url = "https://waimai.meituan.com" + href
                elif href.startswith("http"):
                    jump_url = href
            
            if not jump_url:
                jump_url = f"https://waimai.meituan.com/shop/{product_id}"
            
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
            
            # 评分
            rating = None
            rating_el = await item.query_selector("[class*='rating'], [class*='score']")
            if rating_el:
                rating_text = await rating_el.inner_text()
                try:
                    rating = float(re.search(r"(\d+\.?\d*)", rating_text).group(1))
                except Exception:
                    pass
            
            # 优惠券
            coupon = None
            coupon_el = await item.query_selector("[class*='coupon'], [class*='discount']")
            if coupon_el:
                coupon = await coupon_el.inner_text()
            
            return Product(
                platform=Platform.MEITUAN,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=original_price,
                coupon=coupon,
                shop_name=shop_name.strip(),
                image_url=image_url,
                jump_url=jump_url,
                delivery_fee=delivery_fee,
                delivery_time=delivery_time,
                rating=rating,
                location=f"{self.lat},{self.lng}"
            )
            
        except Exception as e:
            logger.debug(f"[美团] 解析详情失败: {e}")
            return None
    
    async def _detect_restaurant(self, item) -> bool:
        """检测是否是餐厅（而非菜品）"""
        try:
            # 餐厅通常有评分、配送费等信息
            has_rating = await item.query_selector("[class*='rating'], [class*='score']")
            has_delivery = await item.query_selector("[class*='delivery'], [class*='配送']")
            
            return bool(has_rating or has_delivery)
        except Exception:
            return True
    
    async def _extract_id(self, item, index: int) -> str:
        """提取商品/餐厅ID"""
        try:
            # 从链接提取
            link_el = await item.query_selector("a")
            if link_el:
                href = await link_el.get_attribute("href") or ""
                
                # /shop/123456 格式
                match = re.search(r"/shop/(\d+)", href)
                if match:
                    return match.group(1)
                
                # id=123456 格式
                match = re.search(r"id=(\d+)", href)
                if match:
                    return match.group(1)
            
            # 从data属性提取
            data_id = await item.get_attribute("data-id") or await item.get_attribute("data-shopid")
            if data_id:
                return data_id
            
            return f"meituan_{index}"
            
        except Exception:
            return f"meituan_{index}"
    
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
        logger.info(f"[美团] 获取详情: {product_id}")
        
        try:
            await self._create_context_with_geo()
            await self._load_cookies()
            
            url = f"https://waimai.meituan.com/shop/{product_id}"
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 提取餐厅名
            title = ""
            title_el = await self._page.query_selector(".shop-name, h1, [class*='name']")
            if title_el:
                title = await title_el.inner_text()
            
            # 平均价格
            price = 35.0
            price_el = await self._page.query_selector("[class*='avg-price'], [class*='price']")
            if price_el:
                price = self._parse_price(await price_el.inner_text()) or price
            
            # 评分
            rating = None
            rating_el = await self._page.query_selector("[class*='rating'], [class*='score']")
            if rating_el:
                rating_text = await rating_el.inner_text()
                try:
                    rating = float(re.search(r"(\d+\.?\d*)", rating_text).group(1))
                except Exception:
                    pass
            
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
                platform=Platform.MEITUAN,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                shop_name=title.strip(),
                jump_url=url,
                delivery_fee=delivery_fee,
                delivery_time=delivery_time,
                rating=rating,
                location=f"{self.lat},{self.lng}"
            )
            
        except Exception as e:
            logger.error(f"[美团] 获取详情失败: {e}")
            return None
        finally:
            await self.close()


# 导出
__all__ = ["MeituanTool"]
