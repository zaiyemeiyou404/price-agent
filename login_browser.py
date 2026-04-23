#!/usr/bin/env python3
"""
京东/淘宝登录工具 - 可视化操作

用法:
    python login_browser.py jd      # 登录京东
    python login_browser.py taobao  # 登录淘宝
    
登录成功后Cookie会自动保存，下次搜索时自动使用。
"""
import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def login_jd():
    """登录京东"""
    print("\n" + "="*60)
    print("京东登录")
    print("="*60)
    print("\n请在浏览器中完成登录：")
    print("1. 扫码登录 或")
    print("2. 账号密码登录")
    print("\n登录成功后按回车键保存Cookie并关闭浏览器...")
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
        
        # 访问京东登录页
        await page.goto("https://passport.jd.com/new/login.aspx")
        logger.info("已打开京东登录页")
        
        # 等待用户输入
        input("\n>>> 登录完成后按回车键继续...")
        
        # 保存Cookie
        cookies = await context.cookies()
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Cookie已保存: {cookie_file}")
        print(f"✓ 共保存 {len(cookies)} 条Cookie")
        
        await browser.close()
        print("✓ 登录完成！")


async def login_taobao():
    """登录淘宝"""
    print("\n" + "="*60)
    print("淘宝登录")
    print("="*60)
    print("\n请在浏览器中完成登录：")
    print("1. 扫码登录 或")
    print("2. 账号密码登录")
    print("\n登录成功后按回车键保存Cookie并关闭浏览器...")
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
        
        # 访问淘宝登录页
        await page.goto("https://login.taobao.com/")
        logger.info("已打开淘宝登录页")
        
        # 等待用户输入
        input("\n>>> 登录完成后按回车键继续...")
        
        # 保存Cookie
        cookies = await context.cookies()
        cookie_file = COOKIE_DIR / "taobao_cookies.json"
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ Cookie已保存: {cookie_file}")
        print(f"✓ 共保存 {len(cookies)} 条Cookie")
        
        await browser.close()
        print("✓ 登录完成！")


async def search_jd(query: str):
    """搜索京东商品（使用已保存的Cookie）"""
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
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            logger.info(f"已加载 {len(cookies)} 条Cookie")
        else:
            logger.error("未找到Cookie文件，请先运行: python login_browser.py jd")
            return []
        
        page = await context.new_page()
        
        # 搜索
        from urllib.parse import quote
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"访问: {url}")
        
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        # 滚动加载
        for _ in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # 解析商品
        items = await page.query_selector_all(".gl-item[data-sku]")
        logger.info(f"找到 {len(items)} 个商品元素")
        
        products = []
        for item in items[:20]:
            try:
                # 商品ID
                sku_id = await item.get_attribute("data-sku")
                
                # 标题
                title_el = await item.query_selector(".p-name em")
                title = await title_el.inner_text() if title_el else ""
                
                # 价格
                price_el = await item.query_selector(".p-price i")
                price_text = await price_el.inner_text() if price_el else "0"
                import re
                price_match = re.search(r'(\d+\.?\d*)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                
                # 店铺
                shop_el = await item.query_selector(".p-shop a")
                shop = await shop_el.inner_text() if shop_el else "京东"
                
                if title and price > 0:
                    products.append({
                        "title": title.strip()[:50],
                        "price": price,
                        "shop": shop.strip(),
                        "url": f"https://item.jd.com/{sku_id}.html"
                    })
            except Exception as e:
                continue
        
        await browser.close()
        
        # 显示结果
        if products:
            print(f"\n找到 {len(products)} 个商品:\n")
            for i, p in enumerate(products[:10], 1):
                print(f"[{i}] {p['title']}")
                print(f"    价格: {p['price']} | 店铺: {p['shop']}\n")
            
            # 保存
            output = COOKIE_DIR / f"jd_{query}_products.json"
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"结果已保存: {output}")
        else:
            print("未找到商品，Cookie可能已过期，请重新登录")
        
        return products


def main():
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python login_browser.py jd        # 登录京东")
        print("  python login_browser.py taobao    # 登录淘宝")
        print("  python login_browser.py jd search # 搜索京东（登录后）")
        print("\n示例:")
        print("  python login_browser.py jd")
        print("  python login_browser.py jd search iPhone 15")
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
        print(f"不支持的平台: {platform}")


if __name__ == "__main__":
    main()
