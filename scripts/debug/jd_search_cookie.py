#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东搜索 - 使用已保存的Cookie"""
import asyncio
import json
import re
import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"
QUERY = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"


async def main():
    print("=" * 60)
    print(f"京东搜索: {QUERY}")
    print("=" * 60)
    
    # 检查Cookie文件
    cookie_file = COOKIE_DIR / "jd_cookies.json"
    if not cookie_file.exists():
        print("错误: 未找到Cookie文件，请先运行 python scripts/login/jd_login.py 登录")
        return
    
    with open(cookie_file, 'r', encoding='utf-8') as f:
        saved_cookies = json.load(f)
    print(f"加载 {len(saved_cookies)} 条Cookie")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        # 加载Cookie
        await context.add_cookies(saved_cookies)
        
        page = await context.new_page()
        
        # 先访问首页验证登录
        print("\n[1] 验证登录状态...")
        await page.goto("https://www.jd.com", timeout=30000)
        await asyncio.sleep(2)
        
        try:
            user_el = await page.query_selector(".nickname")
            if user_el:
                name = await user_el.inner_text()
                print(f"    已登录: {name}")
            else:
                print("    未检测到登录状态")
        except:
            print("    状态检测失败")
        
        # 访问搜索页
        search_url = f"https://search.jd.com/Search?keyword={quote(QUERY)}"
        print(f"\n[2] 访问搜索页...")
        await page.goto(search_url, timeout=30000)
        
        # 等待更长时间
        print("    等待页面加载...")
        await asyncio.sleep(5)
        
        # 检查URL
        current_url = page.url
        title = await page.title()
        print(f"    URL: {current_url[:60]}...")
        print(f"    标题: {title}")
        
        # 如果被重定向到登录页
        if "passport.jd.com" in current_url or "login" in current_url.lower():
            print("\n    被重定向到登录页！Cookie可能已失效")
            print("    请在新打开的浏览器窗口中手动登录，然后按Enter继续...")
            
            # 等待用户操作
            await asyncio.sleep(60)  # 给用户60秒登录
            
            # 重新访问
            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(5)
            current_url = page.url
            print(f"    当前URL: {current_url[:60]}...")
        
        # 滚动加载
        print("\n[3] 滚动加载商品...")
        for i in range(5):
            await page.evaluate(f"window.scrollTo(0, {1000 * (i+1)})")
            await asyncio.sleep(0.8)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_search.png"))
        
        # 保存HTML
        html = await page.content()
        with open(COOKIE_DIR / "jd_search.html", 'w', encoding='utf-8') as f:
            f.write(html)
        print("    HTML已保存: jd_search.html")
        
        # 检查HTML中是否有商品数据
        if "gl-item" in html or "data-sku" in html:
            print("    HTML中包含商品数据")
        else:
            print("    HTML中未检测到商品数据")
            if "验证" in html or "slider" in html.lower():
                print("    可能需要验证码！")
        
        # 获取商品元素
        items = await page.query_selector_all("[data-sku], .gl-item, #J_goodsList .gl-item")
        print(f"\n[4] 找到 {len(items)} 个商品元素")
        
        products = []
        for item in items[:30]:
            try:
                sku = await item.get_attribute("data-sku")
                title_el = await item.query_selector(".p-name em, .p-name a em")
                title = await title_el.inner_text() if title_el else ""
                price_el = await item.query_selector(".p-price i")
                price_text = await price_el.inner_text() if price_el else "0"
                price_match = re.search(r'(\d+\.?\d*)', price_text)
                price = float(price_match.group(1)) if price_match else 0
                
                if title and price > 0:
                    products.append({
                        "platform": "京东",
                        "title": title.strip()[:80],
                        "price": price,
                        "url": f"https://item.jd.com/{sku}.html" if sku else ""
                    })
            except:
                continue
        
        # 更新Cookie
        cookies = await context.cookies()
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        
        # 输出结果
        if products:
            products.sort(key=lambda x: x['price'])
            with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*60}")
            print(f"京东找到 {len(products)} 个商品:")
            print("=" * 60)
            for i, p in enumerate(products[:10], 1):
                print(f"[{i:2d}] ¥{p['price']:>8.2f}  {p['title'][:40]}...")
        else:
            print(f"\n未找到商品")
            print("请检查: jd_search.png 和 jd_search.html")


if __name__ == "__main__":
    asyncio.run(main())
