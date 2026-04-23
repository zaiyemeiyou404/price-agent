#!/usr/bin/env python3
"""
详细调试脚本 - 查看商品元素的实际内容
"""
import asyncio
import sys
from pathlib import Path
import json
import re

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright


async def debug():
    query = "iPhone 15"
    print(f"搜索关键词: {query}")
    
    cookie_dir = Path(__file__).parent / "cookies"
    cookie_file = cookie_dir / "taobao_cookies.json"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 加载Cookie
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"已加载 {len(cookies)} 条Cookie")
        
        # 访问淘宝搜索
        from urllib.parse import quote
        url = f"https://s.taobao.com/search?q={quote(query)}"
        print(f"访问: {url}")
        
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # 滚动
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/3})")
            await asyncio.sleep(1)
        
        # 查找商品元素
        items = await page.query_selector_all("[class*='Card--']")
        print(f"\n找到 {len(items)} 个商品元素")
        
        if items:
            # 获取第一个商品的详细信息
            item = items[0]
            
            # 获取文本
            text = await item.inner_text()
            print(f"\n=== 第一个商品文本 ===")
            print(text[:800])
            
            # 尝试找价格
            print(f"\n=== 尝试查找价格 ===")
            
            # 方法1: 查找包含 price 的元素
            price_els = await item.query_selector_all("[class*='price']")
            for i, el in enumerate(price_els):
                el_text = await el.inner_text()
                el_class = await el.get_attribute("class")
                print(f"价格元素 {i}: class={el_class}, text={el_text}")
            
            # 方法2: 直接查找文本中的价格
            price_matches = re.findall(r'[¥￥]?\s*(\d+\.?\d*)', text)
            print(f"\n从文本提取的数字: {price_matches[:10]}")
            
            # 方法3: 保存HTML到文件
            html = await item.inner_html()
            html_file = cookie_dir / "debug_item.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"\nHTML已保存到: {html_file}")
        
        await browser.close()
        print("\n调试完成!")


if __name__ == "__main__":
    asyncio.run(debug())
