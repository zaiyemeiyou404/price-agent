#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东搜索 - 手动登录版"""
import asyncio
import json
import re
import sys
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    
    print("=" * 60)
    print(f"京东搜索: {query}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        if cookie_file.exists():
            with open(cookie_file, 'r', encoding='utf-8') as f:
                await context.add_cookies(json.load(f))
            print("已加载Cookie")
        
        page = await context.new_page()
        
        # 直接访问搜索页
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        print(f"访问: {url}")
        
        await page.goto(url, timeout=30000)
        await asyncio.sleep(2)
        
        # 检查是否在登录页
        if "passport.jd.com" in page.url or "login" in page.url:
            print("\n" + "!" * 60)
            print("请在浏览器窗口中扫码登录！")
            print("登录成功后会自动继续...")
            print("!" * 60 + "\n")
            
            # 等待登录成功（最多2分钟）
            for i in range(120):
                await asyncio.sleep(1)
                if "search.jd.com" in page.url:
                    print("登录成功！正在加载商品...")
                    await asyncio.sleep(3)
                    break
                if i % 30 == 0 and i > 0:
                    print(f"等待中...（已等待{i}秒）")
        else:
            print("页面已加载")
        
        # 滚动加载
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
            await asyncio.sleep(1)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"))
        print("截图已保存")
        
        # 获取商品
        items = await page.query_selector_all("[data-sku], .gl-item")
        print(f"找到 {len(items)} 个商品元素")
        
        products = []
        for item in items[:30]:
            try:
                sku = await item.get_attribute("data-sku")
                if not sku:
                    sku_el = await item.query_selector("[data-sku]")
                    sku = await sku_el.get_attribute("data-sku") if sku_el else ""
                
                title_el = await item.query_selector(".p-name em, .p-name a em, em")
                title = await title_el.inner_text() if title_el else ""
                
                price_el = await item.query_selector(".p-price i, .p-price")
                price_text = await price_el.inner_text() if price_el else "0"
                price = float(re.search(r'(\d+\.?\d*)', price_text).group(1)) if price_text else 0
                
                if title and price > 0:
                    products.append({
                        "platform": "京东",
                        "title": title.strip()[:80],
                        "price": price,
                        "url": f"https://item.jd.com/{sku}.html" if sku else ""
                    })
            except:
                continue
        
        # 保存Cookie
        cookies = await context.cookies()
        with open(COOKIE_DIR / "jd_cookies.json", 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        await browser.close()
        
        # 保存结果
        if products:
            products.sort(key=lambda x: x['price'])
            with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            
            print(f"\n找到 {len(products)} 个商品:")
            print("-" * 60)
            for i, p in enumerate(products[:10], 1):
                print(f"[{i:2d}] ¥{p['price']:>8.2f}  {p['title'][:40]}...")
            print(f"\n结果已保存: {COOKIE_DIR}/jd_products.json")
        else:
            print("\n未找到商品。可能原因：")
            print("1. 登录未完成 - 请确保扫码后点击确认")
            print("2. 页面未加载 - 请查看截图 jd_result.png")
            print("3. 选择器失效 - 京东页面结构可能已更新")


if __name__ == "__main__":
    asyncio.run(main())
