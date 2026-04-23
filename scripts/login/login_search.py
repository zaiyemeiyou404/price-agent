#!/usr/bin/env python3
"""
京东登录工具 - 改进版

特点：
1. 检测多种登录成功标志
2. 登录成功后自动跳转到搜索页测试
3. 保存截图帮助调试
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger
import re

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def login_and_search():
    """登录并搜索测试"""
    print("\n" + "="*60)
    print("京东登录 + 搜索测试")
    print("="*60)
    print("\n请在浏览器中完成登录（扫码或账号密码）")
    print("登录后我会自动检测并开始搜索\n")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # Step 1: 访问京东首页
        logger.info("Step 1: 访问京东首页...")
        await page.goto("https://www.jd.com", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查是否已登录
        logged_in = False
        
        for i in range(60):
            await asyncio.sleep(1)
            
            # 尝试多种方式检测登录状态
            try:
                # 方式1: 检查用户名
                user_el = await page.query_selector(".nickname, [class*='username'], .user-name")
                if user_el:
                    text = await user_el.inner_text()
                    if text and len(text) > 0 and "登录" not in text:
                        logger.info(f"检测到用户: {text}")
                        logged_in = True
                        break
                
                # 方式2: 检查登录按钮是否消失
                login_btn = await page.query_selector(".link-login, a[href*='login']")
                if not login_btn:
                    # 可能已登录，检查其他元素
                    cart_el = await page.query_selector("[class*='cart']")
                    if cart_el:
                        logger.info("登录按钮消失，可能已登录")
                        logged_in = True
                        break
                        
            except Exception as e:
                logger.debug(f"检测错误: {e}")
            
            if i % 10 == 0:
                logger.info(f"等待登录... ({i}秒)")
        
        if not logged_in:
            # 继续等待，让用户完成登录
            logger.warning("未检测到登录状态，请在浏览器中完成登录...")
            
            for i in range(60):
                await asyncio.sleep(1)
                try:
                    user_el = await page.query_selector(".nickname, [class*='username']")
                    if user_el:
                        text = await user_el.inner_text()
                        if text and len(text) > 0:
                            logged_in = True
                            break
                except:
                    pass
        
        # Step 2: 保存Cookie
        cookies = await context.cookies()
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookie已保存: {len(cookies)} 条")
        
        # Step 3: 测试搜索
        query = "iPhone 15"
        logger.info(f"\nStep 3: 搜索测试: {query}")
        
        search_url = f"https://search.jd.com/Search?keyword={query}"
        await page.goto(search_url, timeout=30000)
        await asyncio.sleep(3)
        
        # 滚动加载
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # 截图
        screenshot_path = COOKIE_DIR / "jd_search_result.png"
        await page.screenshot(path=str(screenshot_path))
        logger.info(f"截图已保存: {screenshot_path}")
        
        # 解析商品
        items = await page.query_selector_all(".gl-item[data-sku]")
        logger.info(f"找到 {len(items)} 个商品元素")
        
        if items:
            products = []
            for item in items[:10]:
                try:
                    sku_id = await item.get_attribute("data-sku")
                    title_el = await item.query_selector(".p-name em, .p-name a")
                    title = await title_el.inner_text() if title_el else ""
                    price_el = await item.query_selector(".p-price i, [class*='price'] i")
                    price_text = await price_el.inner_text() if price_el else "0"
                    price_match = re.search(r'(\d+\.?\d*)', price_text)
                    price = float(price_match.group(1)) if price_match else 0
                    
                    if title and price > 0:
                        products.append({"title": title[:50], "price": price})
                except:
                    continue
            
            if products:
                print("\n" + "="*60)
                print("搜索成功！找到商品:")
                print("="*60)
                for i, p in enumerate(products, 1):
                    print(f"[{i}] {p['title']}")
                    print(f"    价格: {p['price']}")
                print("="*60 + "\n")
                
                # 保存结果
                output = COOKIE_DIR / "jd_products.json"
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                logger.info(f"结果已保存: {output}")
            else:
                logger.warning("解析商品失败，查看截图确认页面状态")
        else:
            logger.warning("未找到商品，查看截图确认页面状态")
        
        # 保持浏览器打开一会
        logger.info("\n浏览器将在5秒后关闭...")
        await asyncio.sleep(5)
        
        await browser.close()
        print("\n完成！")


if __name__ == "__main__":
    asyncio.run(login_and_search())
