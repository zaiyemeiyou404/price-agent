#!/usr/bin/env python3
"""
京东/淘宝登录工具 - 自动检测登录成功

用法:
    python login_auto.py jd      # 登录京东
    python login_auto.py taobao  # 登录淘宝

登录成功后会自动保存Cookie。
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def login_jd():
    """登录京东 - 自动检测登录成功"""
    print("\n" + "="*60)
    print("京东登录 - 自动检测")
    print("="*60)
    print("\n请在浏览器中扫码或输入账号密码登录")
    print("登录成功后会自动保存Cookie\n")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 访问京东首页
        await page.goto("https://www.jd.com")
        logger.info("已打开京东首页")
        
        # 点击登录按钮
        try:
            login_btn = await page.query_selector(".link-login, a[href*='login']")
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(2)
        except:
            pass
        
        # 轮询检测登录状态
        logger.info("等待登录...")
        
        for i in range(120):  # 最多等待2分钟
            await asyncio.sleep(1)
            
            # 检查是否登录成功
            # 方法1: 检查URL是否跳转回首页
            current_url = page.url
            if "jd.com" in current_url and "login" not in current_url.lower():
                # 方法2: 检查是否有用户名元素
                try:
                    user_el = await page.query_selector(".nickname, .user-name, [class*='username']")
                    if user_el:
                        username = await user_el.inner_text()
                        if username and len(username) > 0:
                            logger.info(f"检测到登录用户: {username}")
                            
                            # 保存Cookie
                            cookies = await context.cookies()
                            cookie_file = COOKIE_DIR / "jd_cookies.json"
                            with open(cookie_file, 'w', encoding='utf-8') as f:
                                json.dump(cookies, f, ensure_ascii=False, indent=2)
                            
                            print(f"\n{'='*60}")
                            print(f"登录成功！")
                            print(f"用户: {username}")
                            print(f"Cookie已保存: {cookie_file}")
                            print(f"共 {len(cookies)} 条")
                            print("="*60 + "\n")
                            
                            await asyncio.sleep(2)
                            await browser.close()
                            return True
                except:
                    pass
            
            if i % 10 == 0:
                logger.info(f"等待中... ({i}秒)")
        
        logger.warning("登录超时，请重试")
        await browser.close()
        return False


async def login_taobao():
    """登录淘宝 - 自动检测登录成功"""
    print("\n" + "="*60)
    print("淘宝登录 - 自动检测")
    print("="*60)
    print("\n请在浏览器中扫码或输入账号密码登录")
    print("登录成功后会自动保存Cookie\n")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 访问淘宝首页
        await page.goto("https://www.taobao.com")
        logger.info("已打开淘宝首页")
        
        # 轮询检测登录状态
        logger.info("等待登录...")
        
        for i in range(120):
            await asyncio.sleep(1)
            
            try:
                # 检查登录状态
                user_el = await page.query_selector(".site-nav-user, .member-nickname, [class*='username']")
                if user_el:
                    username = await user_el.inner_text()
                    if username and "登录" not in username:
                        logger.info(f"检测到登录用户: {username}")
                        
                        # 保存Cookie
                        cookies = await context.cookies()
                        cookie_file = COOKIE_DIR / "taobao_cookies.json"
                        with open(cookie_file, 'w', encoding='utf-8') as f:
                            json.dump(cookies, f, ensure_ascii=False, indent=2)
                        
                        print(f"\n{'='*60}")
                        print(f"登录成功！")
                        print(f"用户: {username}")
                        print(f"Cookie已保存: {cookie_file}")
                        print(f"共 {len(cookies)} 条")
                        print("="*60 + "\n")
                        
                        await asyncio.sleep(2)
                        await browser.close()
                        return True
            except:
                pass
            
            if i % 10 == 0:
                logger.info(f"等待中... ({i}秒)")
        
        logger.warning("登录超时，请重试")
        await browser.close()
        return False


async def search_jd(query: str):
    """搜索京东商品"""
    print("\n" + "="*60)
    print(f"京东搜索: {query}")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        if not cookie_file.exists():
            print("错误: 未找到Cookie，请先登录")
            print("运行: python login_auto.py jd")
            return []
        
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        logger.info(f"已加载 {len(cookies)} 条Cookie")
        
        page = await context.new_page()
        
        # 搜索
        from urllib.parse import quote
        import re
        
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"访问: {url}")
        
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # 滚动
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # 解析
        items = await page.query_selector_all(".gl-item[data-sku]")
        logger.info(f"找到 {len(items)} 个商品")
        
        products = []
        for item in items[:20]:
            try:
                sku_id = await item.get_attribute("data-sku")
                title_el = await item.query_selector(".p-name em")
                title = await title_el.inner_text() if title_el else ""
                price_el = await item.query_selector(".p-price i")
                price_text = await price_el.inner_text() if price_el else "0"
                price_match = re.search(r'(\d+\.?\d*)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                shop_el = await item.query_selector(".p-shop a")
                shop = await shop_el.inner_text() if shop_el else "京东"
                
                if title and price > 0:
                    products.append({
                        "title": title.strip()[:50],
                        "price": price,
                        "shop": shop.strip(),
                        "url": f"https://item.jd.com/{sku_id}.html"
                    })
            except:
                continue
        
        await browser.close()
        
        if products:
            print(f"\n找到 {len(products)} 个商品:\n")
            for i, p in enumerate(products[:10], 1):
                print(f"[{i}] {p['title']}")
                print(f"    价格: {p['price']} | 店铺: {p['shop']}\n")
            
            output = COOKIE_DIR / f"jd_products.json"
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"结果已保存: {output}")
        else:
            print("未找到商品，Cookie可能已过期")
            print("请重新运行: python login_auto.py jd")
        
        return products


def main():
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python login_auto.py jd        # 登录京东")
        print("  python login_auto.py taobao    # 登录淘宝")
        print("  python login_auto.py jd search iPhone 15  # 搜索")
        return
    
    platform = sys.argv[1].lower()
    
    if platform == "jd":
        if len(sys.argv) >= 3 and sys.argv[2] == "search":
            query = " ".join(sys.argv[3:]) or "iPhone 15"
            asyncio.run(search_jd(query))
        else:
            asyncio.run(login_jd())
    elif platform == "taobao":
        asyncio.run(login_taobao())
    else:
        print(f"不支持: {platform}")


if __name__ == "__main__":
    main()
