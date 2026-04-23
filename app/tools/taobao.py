"""
淘宝爬虫工具 - 改进版

特性:
- 多选择器备选，页面变化时自动切换
- 完整的反爬指纹伪装
- Cookie持久化支持
- 验证码检测
- 智能重试
"""
import asyncio
import re
from typing import Optional, List
from urllib.parse import quote, urljoin
from pathlib import Path
from datetime import datetime
from loguru import logger

from app.tools.base import BaseTool
from app.tools.base_crawler import BaseCrawler, retry_with_backoff
from app.models import Product, Platform
from app.config import settings


class TaobaoTool(BaseTool, BaseCrawler):
    """淘宝爬虫工具"""
    
    platform = Platform.TAOBAO
    name = "淘宝搜索"
    description = "在淘宝搜索商品并返回比价信息"
    platform_name = "taobao"
    
    # 商品列表选择器（多套备选 - 2026年更新）
    LIST_SELECTORS = [
        "[class*='Content--']",
        "[class*='itemList']",
        "[class*='Item--']", 
        ".Content--contentInner--QFC1q4J",
        "#mainsrp-itemlist",
        ".m-itemlist",
        ".items .item",
    ]
    
    # 商品项选择器
    ITEM_SELECTORS = [
        ".doubleCard--gO3Bz6bu",
        "[class*='doubleCard--']",
        "[class*='Card--']",
        "[class*='Item--']",
        "[data-spm-anchor-id]",
        ".Card--doubleCardWrapper--L2XFE73",
        ".item",
        "a[href*='item.taobao.com']",
        "a[href*='item.htm']",
    ]
    
    # 商品内部选择器
    TITLE_SELECTORS = [
        "[class*='title--']",
        "[class*='Title--']",
        ".Title--title--jCOPvpf",
        ".title",
        ".J_ClickStat",
        "h3",
        "a[title]",
    ]
    
    PRICE_SELECTORS = [
        "[class*='priceInt']",
        "[class*='priceFloat']",
        ".Price--priceInt--Z0S8aDr",
        ".Price--price--",
        "[class*='Price--price']:not([class*='origin'])",
        ".g_price-highlight",
        ".priceWap",
        ".price",
    ]
    
    def __init__(self):
        BaseTool.__init__(self)
        BaseCrawler.__init__(
            self,
            proxy=settings.crawler_proxy,
            headless=True,
            timeout=settings.crawler_timeout * 1000,
            use_mobile=False
        )
        self._search_lock = asyncio.Lock()
    
    @retry_with_backoff(max_attempts=1, backoff=[1])
    async def search(self, query: str, max_results: int = 20, **kwargs) -> List[Product]:
        """
        搜索淘宝商品
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
        
        Returns:
            商品列表
        """
        logger.info(f"[淘宝] 开始搜索: {query}")
        if self._search_lock.locked():
            logger.warning("[淘宝] 当前已有搜索在执行，拒绝并发请求（单窗口串行）")
            return []

        async with self._search_lock:
            # 严格单窗口串行：默认不做二次尝试，避免重复验证码窗口
            allow_headful_fallback = kwargs.get("allow_headful_fallback", False)
            # 默认优先有头，先人工接管，再搜索
            primary_headless = kwargs.get("headless", False)
            manual_captcha_timeout = int(kwargs.get("manual_captcha_timeout", 60))
            allow_manual_captcha = kwargs.get("allow_manual_captcha", True)
            enable_preheat = kwargs.get("enable_preheat", True)
            preheat_seconds = int(kwargs.get("preheat_seconds", 15))
            pre_search_manual_gate = kwargs.get("pre_search_manual_gate", True)
            manual_gate_timeout = int(kwargs.get("manual_gate_timeout", 30))

            products = await self._search_once(
                query=query,
                max_results=max_results,
                headless=primary_headless,
                attempt_tag="headless" if primary_headless else "headful",
                manual_captcha_timeout=manual_captcha_timeout,
                allow_manual_captcha=allow_manual_captcha,
                enable_preheat=enable_preheat,
                preheat_seconds=preheat_seconds,
                pre_search_manual_gate=pre_search_manual_gate,
                manual_gate_timeout=manual_gate_timeout,
            )
            if products:
                return products

            # 无头抓取为空时，自动切换有头重试
            if allow_headful_fallback and primary_headless:
                logger.warning("[淘宝] 无头模式未获取到商品，切换有头模式重试")
                products = await self._search_once(
                    query=query,
                    max_results=max_results,
                    headless=False,
                    attempt_tag="headful_fallback",
                    manual_captcha_timeout=manual_captcha_timeout,
                    allow_manual_captcha=allow_manual_captcha,
                    enable_preheat=enable_preheat,
                    preheat_seconds=preheat_seconds,
                    pre_search_manual_gate=pre_search_manual_gate,
                    manual_gate_timeout=manual_gate_timeout,
                )
                if products:
                    return products

            return []

    async def _search_once(
        self,
        query: str,
        max_results: int,
        headless: bool,
        attempt_tag: str,
        manual_captcha_timeout: int = 60,
        allow_manual_captcha: bool = False,
        enable_preheat: bool = True,
        preheat_seconds: int = 15,
        pre_search_manual_gate: bool = True,
        manual_gate_timeout: int = 30,
    ) -> List[Product]:
        """单次搜索执行，失败时输出调试产物"""
        original_headless = self.headless
        self.headless = headless

        try:
            page = await self._create_page()

            cookies_loaded = await self._load_cookies()
            if not cookies_loaded:
                logger.warning("[淘宝] ⚠ 未加载Cookie，搜索结果可能受限")
                logger.warning("[淘宝] 请运行: python scripts/login/login.py taobao qr")

            try:
                await page.goto("https://www.taobao.com", wait_until="domcontentloaded", timeout=60000)
                if enable_preheat and preheat_seconds > 0 and self.headless:
                    logger.info(f"[淘宝] 首页预热中: 保持 {preheat_seconds}s 后再搜索")
                    await asyncio.sleep(preheat_seconds)
                else:
                    await self._random_delay(2, 3)
            except Exception as e:
                logger.warning(f"[淘宝] 访问首页超时: {e}")

            if await self._check_login_required():
                logger.warning("[淘宝] ⚠ 检测到需要登录，结果可能为空")
                await self._capture_debug_artifacts(query, f"{attempt_tag}_login_required")

            # 人工接管窗口：先处理登录/验证，再进入搜索
            if pre_search_manual_gate and not self.headless:
                await self._wait_for_manual_gate(timeout_seconds=manual_gate_timeout)

            url = f"https://s.taobao.com/search?q={quote(query)}"
            logger.info(f"[淘宝] ({attempt_tag}) 访问: {url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self._random_delay(3, 5)
            except Exception as e:
                logger.warning(f"[淘宝] 访问搜索页超时: {e}")
                await self._random_delay(2, 3)

            has_captcha = await self._detect_captcha()
            if not has_captcha:
                has_captcha = await self._detect_captcha_by_content()

            if has_captcha:
                # 人工接管模式下不做截图，避免验证码页被干扰导致无法拖动
                if allow_manual_captcha:
                    logger.warning("[淘宝] 检测到验证码，进入人工接管模式（不自动截图）")
                else:
                    await self._handle_captcha()
                    await self._capture_debug_artifacts(query, f"{attempt_tag}_captcha")

                if not allow_manual_captcha:
                    logger.warning("[淘宝] 检测到验证码，按快速失败模式返回（未启用人工验证码等待）")
                    return []

                # 仅有头模式可人工处理验证码
                if self.headless:
                    logger.warning("[淘宝] 无头模式命中验证码，无法人工处理，将进入后续回退流程")
                    return []

                logger.warning(
                    f"[淘宝] 检测到验证码，等待人工处理（最多 {manual_captcha_timeout} 秒）..."
                )
                verified = await self._wait_for_manual_captcha(
                    timeout_seconds=manual_captcha_timeout,
                    query=query,
                    attempt_tag=attempt_tag,
                )
                if not verified:
                    logger.warning("[淘宝] 验证码等待超时，结束本次抓取")
                    return []

                logger.info("[淘宝] 人工验证完成，继续执行解析")
                await self._random_delay(1, 2)

            # 等待真实结果渲染，避免只解析到骨架屏
            ready = await self._wait_for_real_results(query=query, timeout_seconds=40)
            if not ready:
                logger.warning("[淘宝] 等待渲染超时（单窗口模式下不自动刷新重试）")

            list_selector = await self._wait_for_selectors(self.LIST_SELECTORS, timeout=15000)
            if not list_selector:
                logger.warning("[淘宝] 未找到商品列表，尝试直接解析")
                await self._capture_debug_artifacts(query, f"{attempt_tag}_list_not_found")

            # 严格单窗口串行：页面关闭即终止本轮，不再重开页面
            if self._page.is_closed():
                logger.warning("[淘宝] 页面已关闭，结束本轮抓取（不自动重开）")
                return []

            await self._scroll_page(times=4, delay=1.5)
            await self._save_cookies()

            products = await self._parse_products(query, max_results)
            logger.info(f"[淘宝] ({attempt_tag}) 搜索完成，获取 {len(products)} 个商品")

            if not products:
                await self._capture_debug_artifacts(query, f"{attempt_tag}_empty")

            return products

        except Exception as e:
            logger.error(f"[淘宝] ({attempt_tag}) 搜索失败: {e}")
            await self._capture_debug_artifacts(query, f"{attempt_tag}_exception")
            return []
        finally:
            self.headless = original_headless
            await self.close()

    async def _wait_for_manual_gate(self, timeout_seconds: int = 30) -> bool:
        """
        搜索前人工接管窗口。
        只在有头模式下启用，等待用户完成登录或验证码，再继续搜索。
        """
        if not self._page:
            return False

        logger.warning(f"[淘宝] 进入人工接管窗口，请完成登录/验证（最多 {timeout_seconds}s）")
        start = asyncio.get_event_loop().time()
        next_log_mark = 30

        while True:
            elapsed = int(asyncio.get_event_loop().time() - start)
            if elapsed >= timeout_seconds:
                logger.warning("[淘宝] 人工接管窗口超时，继续尝试搜索")
                return False

            need_login = await self._check_login_required()
            has_search_box = await self._has_search_input()

            # 人工接管阶段只关注登录是否完成，避免验证码误判导致长时间卡住
            if not need_login or has_search_box:
                logger.info("[淘宝] 人工接管完成，开始执行搜索")
                await self._save_cookies()
                return True

            if elapsed >= next_log_mark:
                logger.info(
                    f"[淘宝] 等待人工处理中... 已等待 {elapsed}s / {timeout_seconds}s"
                )
                next_log_mark += 30

            await asyncio.sleep(2)

    async def _has_search_input(self) -> bool:
        """判断页面是否已具备可搜索状态"""
        if not self._page:
            return False
        selectors = [
            "input[name='q']",
            "#q",
            "[class*='search'] input",
            "form[action*='search'] input[type='text']",
        ]
        for selector in selectors:
            try:
                el = await self._page.query_selector(selector)
                if el:
                    return True
            except Exception:
                continue
        return False

    async def _wait_for_real_results(self, query: str, timeout_seconds: int = 40) -> bool:
        """
        等待页面从骨架屏切换到真实商品列表。
        返回 True 表示检测到可解析商品文本。
        """
        if not self._page:
            return False

        start = asyncio.get_event_loop().time()
        while True:
            elapsed = int(asyncio.get_event_loop().time() - start)
            if elapsed >= timeout_seconds:
                await self._capture_debug_artifacts(query, "render_timeout")
                return False

            # 先看是否已有真实商品文本
            if await self._has_real_item_text():
                return True

            # 若仍在骨架屏，继续等待
            if await self._has_skeleton_loading():
                await asyncio.sleep(2)
                continue

            await asyncio.sleep(1.5)

    async def _has_skeleton_loading(self) -> bool:
        """检测是否仍处于骨架加载状态"""
        if not self._page:
            return False
        selectors = [
            "[class*='skeleton']",
            "[class*='Skeleton']",
            "[class*='placeholder']",
            "[class*='loading']",
        ]
        try:
            for selector in selectors:
                nodes = await self._page.query_selector_all(selector)
                if len(nodes) >= 10:
                    return True
        except Exception:
            return False
        return False

    async def _has_real_item_text(self) -> bool:
        """检测是否出现可解析的真实商品文本"""
        if not self._page:
            return False
        try:
            items = []
            for selector in self.ITEM_SELECTORS:
                found = await self._page.query_selector_all(selector)
                if found:
                    items = found
                    break

            # 兜底选择器
            if not items:
                items = await self._page.query_selector_all("[data-index], li, div")

            for item in items[:30]:
                text = (await item.inner_text() or "").strip()
                if len(text) >= 10 and "搜索" not in text and "加载" not in text:
                    # 至少包含一些中文或英文词，避免纯占位
                    if re.search(r"[\u4e00-\u9fffA-Za-z]{3,}", text):
                        return True
        except Exception:
            return False
        return False

    async def _detect_captcha_by_content(self) -> bool:
        """基于页面源码识别验证码弹层（兜底）"""
        if not self._page:
            return False
        try:
            content = (await self._page.content()).lower()
            markers = [
                "action=captcha",
                "_____tmd_____",
                "punish?",
                "滑动验证",
                "请完成安全验证",
                "验证码",
            ]
            return any(m.lower() in content for m in markers)
        except Exception:
            return False

    async def _wait_for_manual_captcha(
        self,
        timeout_seconds: int,
        query: str,
        attempt_tag: str,
    ) -> bool:
        """
        等待人工处理验证码。
        返回:
            True  验证码已消失（可继续抓取）
            False 超时或页面异常
        """
        if not self._page:
            return False

        start = asyncio.get_event_loop().time()
        next_log_mark = 30

        while True:
            elapsed = int(asyncio.get_event_loop().time() - start)
            if elapsed >= timeout_seconds:
                await self._capture_debug_artifacts(query, f"{attempt_tag}_captcha_timeout")
                return False

            try:
                captcha_exists = await self._detect_captcha()
            except Exception:
                captcha_exists = True

            if not captcha_exists:
                # 验证码已通过，保存最新会话
                await self._save_cookies()
                return True

            if elapsed >= next_log_mark:
                logger.info(
                    f"[淘宝] 仍在等待人工完成验证码... 已等待 {elapsed}s / {timeout_seconds}s"
                )
                next_log_mark += 30

            await asyncio.sleep(2)

    async def _capture_debug_artifacts(self, query: str, stage: str):
        """保存失败现场，便于定位反爬、登录态和选择器问题"""
        if not self._page:
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_query = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", query)[:30]
            debug_dir = Path(__file__).resolve().parents[2] / "debug_output" / "taobao"
            debug_dir.mkdir(parents=True, exist_ok=True)

            screenshot_path = debug_dir / f"{timestamp}_{safe_query}_{stage}.png"
            html_path = debug_dir / f"{timestamp}_{safe_query}_{stage}.html"

            await self._page.screenshot(path=str(screenshot_path), full_page=True)
            html_content = await self._page.content()
            html_path.write_text(html_content, encoding="utf-8")
            logger.info(f"[淘宝] 调试文件已保存: {screenshot_path.name}, {html_path.name}")
        except Exception as e:
            logger.warning(f"[淘宝] 保存调试文件失败: {e}")
    
    async def _parse_products(self, query: str, max_results: int) -> List[Product]:
        """解析商品列表"""
        products = []
        
        # 尝试不同的商品项选择器
        items = []
        for selector in self.ITEM_SELECTORS:
            found = await self._page.query_selector_all(selector)
            if found:
                items = found
                logger.info(f"[淘宝] 使用选择器 '{selector}' 找到 {len(items)} 个商品")
                break
        
        if not items:
            items = await self._page.query_selector_all("[data-index]")
        
        for i, item in enumerate(items[:max_results]):
            try:
                product = await self._parse_item(item, query, i)
                if product:
                    products.append(product)
                    logger.info(f"[淘宝] 商品 {i}: 价格={product.price}, 标题={product.title[:30]}")
                else:
                    logger.debug(f"[淘宝] 商品 {i} 解析返回None")
            except Exception as e:
                logger.warning(f"[淘宝] 解析商品 {i} 失败: {e}")
                continue
        
        return products
    
    async def _parse_item(self, item, query: str, index: int) -> Optional[Product]:
        """解析单个商品"""
        try:
            # 标题
            title = ""
            for selector in self.TITLE_SELECTORS:
                title = await self._safe_extract_text(item, selector)
                if title:
                    break

            # 兜底1: 从链接属性提取标题
            if not title:
                try:
                    link_el = await item.query_selector("a")
                    if link_el:
                        title = (
                            await link_el.get_attribute("title")
                            or await link_el.get_attribute("aria-label")
                            or await link_el.get_attribute("data-title")
                            or ""
                        )
                except Exception:
                    pass

            # 兜底2: 使用商品块全文本首行（过滤掉明显噪音）
            if not title:
                try:
                    raw_text = await item.inner_text()
                    lines = [x.strip() for x in raw_text.splitlines() if x and x.strip()]
                    for line in lines:
                        if len(line) >= 6 and not re.fullmatch(r"[¥￥\d\.\s]+", line):
                            title = line
                            break
                except Exception:
                    pass
            
            if not title:
                logger.debug(f"[淘宝] 商品 {index} 无标题，跳过")
                return None
            
            # 价格 - 改进提取逻辑
            price = 0.0
            all_text = ""

            # 方法0: 组合 priceInt + priceFloat（参考 scripts/debug/taobao_only.py）
            try:
                price_int = await self._safe_extract_text(item, "[class*='priceInt']")
                price_float = await self._safe_extract_text(item, "[class*='priceFloat']")
                if price_int:
                    price = self._parse_price(f"{price_int}{price_float}")
            except Exception:
                pass
            
            # 方法1: 尝试特定选择器
            for selector in self.PRICE_SELECTORS:
                try:
                    price_el = await item.query_selector(selector)
                    if price_el:
                        price_text = await price_el.inner_text()
                        price = self._parse_price(price_text)
                        if 0.01 <= price <= 999999:
                            break
                except:
                    continue
            
            # 方法2: 如果方法1失败，尝试查找包含 ¥ 或 ￥ 的文本
            if price <= 0 or price > 999999:
                try:
                    all_text = await item.inner_text()
                    price_matches = re.findall(r'[¥￥]\s*(\d+\.?\d*)', all_text)
                    if price_matches:
                        for pm in price_matches:
                            p = float(pm)
                            if 0.01 <= p <= 999999:
                                price = p
                                break
                except:
                    pass
            
            # 方法3: 如果还是失败，尝试查找纯数字（合理的价格范围）
            if price <= 0 or price > 999999:
                try:
                    if not all_text:
                        all_text = await item.inner_text()
                    numbers = re.findall(r'\b(\d+\.?\d*)\b', all_text)
                    for n in numbers:
                        p = float(n)
                        if 1000 <= p <= 20000:  # 合理价格范围
                            price = p
                            break
                except:
                    pass
            
            logger.debug(f"[淘宝] 商品 {index}: 标题={title[:30] if title else 'N/A'}, 价格={price}")
            
            # 原价
            original_price = None
            original_price_el = await item.query_selector("[class*='originPrice']")
            if original_price_el:
                op_text = await original_price_el.inner_text()
                original_price = self._parse_price(op_text)
            
            # 店铺名
            shop_name = "淘宝店铺"
            shop_selectors = [
                ".ShopInfo--TextAndPic--yH0HfxQ a",
                ".shopname a",
                ".shop a",
                "[class*='shopName']",
                "[class*='shop']",
            ]
            for selector in shop_selectors:
                shop_text = await self._safe_extract_text(item, selector)
                if shop_text:
                    shop_name = shop_text
                    break
            
            # 销量
            sales = 0
            sales_selectors = [
                ".Price--realSales--FhTZc7U",
                ".deal-cnt",
                "[class*='sales']",
            ]
            for selector in sales_selectors:
                sales_text = await self._safe_extract_text(item, selector)
                if sales_text:
                    sales = self._parse_sales(sales_text)
                    break
            
            # 商品链接
            href = await self._safe_extract_attr(item, "href", "a")
            if href:
                if href.startswith("//"):
                    jump_url = "https:" + href
                elif href.startswith("/"):
                    jump_url = "https://s.taobao.com" + href
                else:
                    jump_url = href
            else:
                jump_url = ""
            
            # 商品ID
            product_id = ""
            if "id=" in jump_url:
                match = re.search(r"id=(\d+)", jump_url)
                if match:
                    product_id = match.group(1)
            elif href:
                match = re.search(r"/i(\d+)", href)
                if match:
                    product_id = match.group(1)
            
            if not product_id:
                product_id = f"tb_{hash(title) % 10000000}"
            
            # 图片
            image_url = ""
            img_el = await item.query_selector("img")
            if img_el:
                image_url = await img_el.get_attribute("src") or await img_el.get_attribute("data-src")
                if image_url:
                    if image_url.startswith("//"):
                        image_url = "https:" + image_url
                    elif not image_url.startswith("http"):
                        image_url = "https:" + image_url
            
            # 优惠券信息
            coupon = None
            coupon_el = await item.query_selector("[class*='coupon'], [class*='Coupon']")
            if coupon_el:
                coupon = await coupon_el.inner_text()
            
            return Product(
                platform=Platform.TAOBAO,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=original_price or price,
                coupon=coupon,
                shop_name=shop_name.strip(),
                sales=sales,
                jump_url=jump_url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.debug(f"[淘宝] 解析商品详情失败: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> float:
        """解析价格"""
        try:
            price_text = price_text.replace('￥', '').replace('¥', '').replace('元', '')
            price_text = price_text.replace(',', '').replace(' ', '').strip()
            
            matches = re.findall(r'\d+\.?\d*', price_text)
            
            if matches:
                price = float(matches[0])
                if 0.01 <= price <= 999999:
                    return price
                for m in matches:
                    p = float(m)
                    if 0.01 <= p <= 999999:
                        return p
            
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
            
            match = re.search(r"(\d+)", sales_text)
            return int(match.group(1)) if match else 0
        except Exception:
            return 0
    
    @retry_with_backoff(max_attempts=2, backoff=[2, 4])
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """获取商品详情"""
        logger.info(f"[淘宝] 获取商品详情: {product_id}")
        
        try:
            page = await self._create_page()
            await self._load_cookies()
            
            url = f"https://item.taobao.com/item.htm?id={product_id}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            if await self._detect_captcha():
                await self._handle_captcha()
                return None
            
            await self._wait_for_selectors(self.PRICE_SELECTORS, timeout=10000)
            
            title = ""
            title_selectors = [
                ".Title--title--jCOPvpf",
                ".tb-main-title",
                "h1",
                "[class*='title']",
            ]
            for selector in title_selectors:
                title_el = await page.query_selector(selector)
                if title_el:
                    title = await title_el.inner_text()
                    if title:
                        break
            
            price = 0.0
            for selector in self.PRICE_SELECTORS:
                price_el = await page.query_selector(selector)
                if price_el:
                    price_text = await price_el.inner_text()
                    price = self._parse_price(price_text)
                    if price > 0:
                        break
            
            image_url = ""
            img_el = await page.query_selector(".PicGallery--mainPic--iRoUoAD img, #J_ImgBooth img, .tb-img img")
            if img_el:
                image_url = await img_el.get_attribute("src")
                if image_url and image_url.startswith("//"):
                    image_url = "https:" + image_url
            
            await self._save_cookies()
            
            return Product(
                platform=Platform.TAOBAO,
                product_id=product_id,
                title=title.strip(),
                price=price,
                original_price=price,
                jump_url=url,
                image_url=image_url,
            )
            
        except Exception as e:
            logger.error(f"[淘宝] 获取商品详情失败: {e}")
            return None
        finally:
            await self.close()


# 导出
__all__ = ["TaobaoTool"]
