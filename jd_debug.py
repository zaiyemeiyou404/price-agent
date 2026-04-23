#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东调试 - 保存页面内容"""
import asyncio
import json
import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"


async def main():
    cookie_file = COOKIE_DIR / "jd_cookies.json"
    with open(cookie_file, 'r', encoding='utf-8') as f:
        saved_cookies = json.load(f)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        await context.add_cookies(saved_cookies)
        
        page = await context.new_page()
        
        # 访问搜索页
        url = "https://search.jd.com/Search?keyword=iPhone%2015"
        print(f"访问: {url}")
        await page.goto(url, timeout=30000)
        await asyncio.sleep(5)
        
        # 检查
        print(f"标题: {await page.title()}")
        print(f"URL: {page.url[:60]}...")
        
        # 滚动
        for i in range(5):
            await page.evaluate(f"window.scrollTo(0, {1000 * (i+1)})")
            await asyncio.sleep(0.5)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_page.png"))
        print("截图: jd_page.png")
        
        # 保存HTML
        html = await page.content()
        with open(COOKIE_DIR / "jd_page.html", 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"HTML: jd_page.html ({len(html)} 字符)")
        
        # 检查关键内容
        if "gl-item" in html:
            print("包含 gl-item")
        if "data-sku" in html:
            print("包含 data-sku")
        if "J_goodsList" in html:
            print("包含 J_goodsList")
        if "slider" in html.lower() or "验证" in html:
            print("可能需要验证")
        
        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
