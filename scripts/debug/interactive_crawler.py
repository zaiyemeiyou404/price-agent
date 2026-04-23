#!/usr/bin/env python3
"""
交互式爬虫 - 支持手动处理验证码

特点:
- 检测到验证码时暂停，等待用户处理
- 登录成功后自动保存Cookie
- 下次运行自动加载Cookie

用法:
    python interactive_crawler.py taobao "iPhone 15"
    python interactive_crawler.py jd "华为手机"
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright, Page
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


class InteractiveCrawler:
    """交互式爬虫 - 支持手动验证码"""
    
    def __init__(self, platform: str, headless: bool = False):
        self.platform = platform
        self.headless = headless
        self.browser = None
        self.context = None
        self.page: Page = None
        
    async def init(self):
        """初始化浏览器"""
        playwright = await async_playwright().start()
        
        # 非headless模式更容易通过验证
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        
        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        logger.info("浏览器已启动")
        
        # 加载已有Cookie
        await self._load_cookies()
    
    async def _load_cookies(self):
        """加载Cookie"""
        cookie_file = COOKIE_DIR / f"{self.platform}_cookies.json"
        if cookie_file.exists():
            try:
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                logger.info(f"已加载 {len(cookies)} 条Cookie")
            except Exception as e:
                logger.warning(f"加载Cookie失败: {e}")
    
    async def _save_cookies(self):
        """保存Cookie"""
        try:
            cookies = await self.context.cookies()
            cookie_file = COOKIE_DIR / f"{self.platform}_cookies.json"
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookie已保存: {cookie_file}")
        except Exception as e:
            logger.error(f"保存Cookie失败: {e}")
    
    async def _wait_for_user(self, message: str, timeout: int = 120):
        """等待用户操作"""
        logger.warning(f"⚠️ {message}")
        logger.info(f"请在浏览器中完成操作，等待中...（超时{timeout}秒）")
        
        # 等待用户输入
        for i in range(timeout):
            await asyncio.sleep(1)
            if i % 10 == 0:
                logger.info(f"已等待 {i} 秒...")
    
    async def _check_and_handle_captcha(self) -> bool:
        """检查并处理验证码"""
        page_text = await self.page.inner_text("body")
        
        # 检查常见验证码关键词
        captcha_keywords = ["验证码", "滑动验证", "拼图", "安全验证", "人机验证"]
        for keyword in captcha_keywords:
            if keyword in page_text:
                await self._wait_for_user(f"检测到验证码：{keyword}，请在浏览器中完成验证")
                return True
        
        return False
    
    async def _check_and_handle_login(self) -> bool:
        """检查并处理登录"""
        page_text = await self.page.inner_text("body")
        url = self.page.url
        
        # 检查是否在登录页
        if "login" in url.lower() or "登录" in page_text[:100]:
            await self._wait_for_user("检测到需要登录，请在浏览器中扫码或输入账号密码登录")
            await self._save_cookies()
            return True
        
        return False
    
    async def crawl_taobao(self, query: str) -> list:
        """爬取淘宝"""
        logger.info(f"[淘宝] 开始搜索: {query}")
        
        # 先访问首页
        logger.info("访问淘宝首页...")
        await self.page.goto("https://www.taobao.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查登录/验证码
        await self._check_and_handle_login()
        await self._check_and_handle_captcha()
        
        # 搜索
        search_url = f"https://s.taobao.com/search?q={quote(query)}"
        logger.info(f"搜索: {search_url}")
        await self.page.goto(search_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # 再次检查
        await self._check_and_handle_login()
        await self._check_and_handle_captcha()
        
        # 保存Cookie
        await self._save_cookies()
        
        # 解析商品
        products = await self._parse_taobao_products()
        
        return products
    
    async def _parse_taobao_products(self) -> list:
        """解析淘宝商品"""
        products = []
        
        # 等待商品列表
        try:
            await self.page.wait_for_selector(".m-itemlist, .items, [class*='item']", timeout=10000)
        except:
            logger.warning("未找到商品列表")
        
        # 滚动加载
        for _ in range(3):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # 查找商品元素
        selectors = [
            ".m-itemlist .item",
            ".items .item",
            "[class*='Card--doubleCard']",
            "[class*='item']",
        ]
        
        items = []
        for sel in selectors:
            found = await self.page.query_selector_all(sel)
            if found and len(found) > 0:
                items = found
                logger.info(f"找到 {len(items)} 个商品元素")
                break
        
        if not items:
            logger.warning("未找到商品，可能需要登录或验证码")
            await self.page.screenshot(path=str(COOKIE_DIR / "taobao_error.png"))
            return []
        
        # 解析
        for i, item in enumerate(items[:20]):
            try:
                # 标题
                title_el = await item.query_selector("[class*='title'], .title, a[title]")
                title = ""
                if title_el:
                    title = await title_el.inner_text()
                    if not title:
                        title = await title_el.get_attribute("title") or ""
                
                # 价格
                price_el = await item.query_selector("[class*='price'], .price")
                price_text = await price_el.inner_text() if price_el else "0"
                price_match = re.search(r'(\d+\.?\d*)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                
                # 店铺
                shop_el = await item.query_selector("[class*='shop'], .shop")
                shop = await shop_el.inner_text() if shop_el else "淘宝店铺"
                
                # 链接
                link_el = await item.query_selector("a[href*='item']")
                url = await link_el.get_attribute("href") if link_el else ""
                
                if title and price > 0:
                    products.append({
                        "title": title.strip()[:50],
                        "price": price,
                        "shop": shop.strip()[:20],
                        "url": url,
                    })
                    
            except Exception as e:
                logger.debug(f"解析商品失败: {e}")
                continue
        
        logger.info(f"解析到 {len(products)} 个商品")
        return products
    
    async def crawl_jd(self, query: str) -> list:
        """爬取京东"""
        logger.info(f"[京东] 开始搜索: {query}")
        
        # 先访问首页
        logger.info("访问京东首页...")
        await self.page.goto("https://www.jd.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查登录/验证码
        await self._check_and_handle_login()
        await self._check_and_handle_captcha()
        
        # 搜索
        search_url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"搜索: {search_url}")
        await self.page.goto(search_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # 再次检查
        await self._check_and_handle_login()
        await self._check_and_handle_captcha()
        
        # 保存Cookie
        await self._save_cookies()
        
        # 解析商品
        products = await self._parse_jd_products()
        
        return products
    
    async def _parse_jd_products(self) -> list:
        """解析京东商品"""
        products = []
        
        # 等待商品列表
        try:
            await self.page.wait_for_selector(".gl-item, #J_goodsList", timeout=10000)
        except:
            logger.warning("未找到商品列表")
        
        # 滚动加载
        for _ in range(5):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # 查找商品元素
        items = await self.page.query_selector_all(".gl-item[data-sku], li[data-sku]")
        logger.info(f"找到 {len(items)} 个商品元素")
        
        if not items:
            logger.warning("未找到商品，可能需要登录或验证码")
            await self.page.screenshot(path=str(COOKIE_DIR / "jd_error.png"))
            return []
        
        # 解析
        for i, item in enumerate(items[:20]):
            try:
                # 商品ID
                sku_id = await item.get_attribute("data-sku") or f"jd_{i}"
                
                # 标题
                title_el = await item.query_selector(".p-name em, .p-name a, [class*='p-name']")
                title = await title_el.inner_text() if title_el else ""
                
                # 价格
                price_el = await item.query_selector(".p-price i, [class*='p-price'] i")
                price_text = await price_el.inner_text() if price_el else "0"
                price_match = re.search(r'(\d+\.?\d*)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                
                # 店铺
                shop_el = await item.query_selector(".p-shop a")
                shop = await shop_el.inner_text() if shop_el else "京东"
                
                # 链接
                url = f"https://item.jd.com/{sku_id}.html"
                
                if title and price > 0:
                    products.append({
                        "title": title.strip()[:50],
                        "price": price,
                        "shop": shop.strip()[:20],
                        "url": url,
                    })
                    
            except Exception as e:
                logger.debug(f"解析商品失败: {e}")
                continue
        
        logger.info(f"解析到 {len(products)} 个商品")
        return products
    
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            logger.info("浏览器已关闭")


async def main():
    if len(sys.argv) < 3:
        print("用法: python interactive_crawler.py <平台> <关键词>")
        print("平台: taobao, jd")
        print("示例: python interactive_crawler.py taobao \"iPhone 15\"")
        return
    
    platform = sys.argv[1]
    query = sys.argv[2]
    
    print("\n" + "="*60)
    print("交互式爬虫 - 支持手动验证码")
    print("="*60)
    print(f"平台: {platform}")
    print(f"关键词: {query}")
    print("="*60 + "\n")
    
    crawler = InteractiveCrawler(platform, headless=False)
    
    try:
        await crawler.init()
        
        if platform == "taobao":
            products = await crawler.crawl_taobao(query)
        elif platform == "jd":
            products = await crawler.crawl_jd(query)
        else:
            logger.error(f"不支持的平台: {platform}")
            return
        
        # 显示结果
        if products:
            print("\n" + "="*60)
            print(f"找到 {len(products)} 个商品:")
            print("="*60)
            for i, p in enumerate(products[:10], 1):
                print(f"\n[{i}] {p['title']}")
                print(f"    价格: ¥{p['price']} | 店铺: {p['shop']}")
            
            # 保存结果
            output_file = COOKIE_DIR / f"{platform}_{query}_products.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存: {output_file}")
        else:
            print("\n未找到商品，请检查浏览器中的页面状态")
        
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
