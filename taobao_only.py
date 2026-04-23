#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""淘宝搜索 - 简化版"""
import asyncio
import json
import re
import sys
import os

# 强制UTF-8输出
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def search_taobao(query: str):
    """淘宝搜索"""
    print(f"\n淘宝搜索: {query}")
    print("=" * 50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "taobao_cookies.json"
        if cookie_file.exists():
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"加载 {len(cookies)} 条Cookie")
        
        page = await context.new_page()
        url = f"https://s.taobao.com/search?q={quote(query)}"
        
        await page.goto(url, timeout=30000)
        await asyncio.sleep(3)
        
        # 滚动加载
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
            await asyncio.sleep(1)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "taobao_result.png"))
        
        # 获取商品
        items = await page.query_selector_all(".doubleCard--gO3Bz6bu")
        print(f"找到 {len(items)} 个商品卡片")
        
        products = []
        for item in items[:30]:
            try:
                # 标题
                title_el = await item.query_selector("[class*='title--']")
                title = await title_el.inner_text() if title_el else ""
                
                # 价格整数部分
                price_int_el = await item.query_selector("[class*='priceInt']")
                price_int = await price_int_el.inner_text() if price_int_el else "0"
                
                # 价格小数部分
                price_float_el = await item.query_selector("[class*='priceFloat']")
                price_float = await price_float_el.inner_text() if price_float_el else ""
                
                # 组合价格
                price_str = price_int + price_float
                price = float(re.search(r'(\d+\.?\d*)', price_str).group(1)) if price_str else 0
                
                # 链接
                link_el = await item.query_selector("a")
                href = await link_el.get_attribute("href") if link_el else ""
                
                if title and price > 0:
                    products.append({
                        "platform": "taobao",
                        "title": title.strip()[:80],
                        "price": price,
                        "url": href
                    })
            except Exception as e:
                continue
        
        await browser.close()
        
        # 保存结果
        if products:
            # 按价格排序
            products.sort(key=lambda x: x['price'])
            
            with open(COOKIE_DIR / "taobao_products.json", 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            
            print(f"\n找到 {len(products)} 个商品（已保存）")
            print("-" * 50)
            for i, p in enumerate(products[:10], 1):
                print(f"[{i}] 价格: {p['price']:.2f} 元")
                print(f"    {p['title'][:50]}")
            
            return products
        else:
            print("未找到商品")
            return []


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    asyncio.run(search_taobao(query))
