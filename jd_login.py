#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东登录工具 - 自动等待版"""
import asyncio
import json
import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"
QUERY = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"


async def main():
    print("=" * 60)
    print("京东登录 + 搜索工具")
    print("=" * 60)
    print(f"\n搜索关键词: {QUERY}")
    print("\n请在浏览器窗口中完成以下操作：")
    print("1. 点击'你好，请登录'")
    print("2. 扫码登录")
    print("3. 等待登录成功（最多等待2分钟）")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 访问京东首页
        print("\n[1] 访问京东首页...")
        await page.goto("https://www.jd.com", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查初始登录状态
        try:
            user_el = await page.query_selector(".nickname")
            if user_el:
                name = await user_el.inner_text()
                print(f"    已登录: {name}")
            else:
                print("    未登录，等待扫码...")
        except:
            print("    未登录，等待扫码...")
        
        # 等待登录（最多2分钟）
        print("\n[2] 等待登录（120秒）...")
        logged_in = False
        for i in range(120):
            await asyncio.sleep(1)
            try:
                user_el = await page.query_selector(".nickname")
                if user_el:
                    name = await user_el.inner_text()
                    if name and "请登录" not in name:
                        print(f"\n    登录成功: {name}")
                        logged_in = True
                        break
            except:
                pass
            
            if i % 30 == 0 and i > 0:
                print(f"    等待中... ({i}秒)")
        
        if not logged_in:
            print("\n    未检测到登录，继续尝试...")
        
        # 保存Cookie
        cookies = await context.cookies()
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"\n[3] 已保存 {len(cookies)} 条Cookie")
        
        # 访问搜索页
        from urllib.parse import quote
        search_url = f"https://search.jd.com/Search?keyword={quote(QUERY)}"
        print(f"\n[4] 访问搜索页...")
        
        await page.goto(search_url, timeout=30000)
        await asyncio.sleep(3)
        
        # 检查URL
        current_url = page.url
        print(f"    当前URL: {current_url[:60]}...")
        
        # 如果还在登录页，等待跳转
        if "passport.jd.com" in current_url or "login" in current_url:
            print("    仍在登录页，等待跳转...")
            for i in range(30):
                await asyncio.sleep(1)
                current_url = page.url
                if "search.jd.com" in current_url:
                    print(f"    已跳转到搜索页")
                    break
        
        # 滚动加载
        for i in range(5):
            await page.evaluate(f"window.scrollTo(0, {1000 * (i+1)})")
            await asyncio.sleep(0.5)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"))
        print(f"\n[5] 截图已保存")
        
        # 获取商品
        items = await page.query_selector_all("[data-sku], .gl-item")
        print(f"    找到 {len(items)} 个商品元素")
        
        products = []
        import re
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
            print(f"\n未找到商品。请查看截图: {COOKIE_DIR}/jd_result.png")


if __name__ == "__main__":
    asyncio.run(main())
