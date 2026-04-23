#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东搜索 - 稳定版"""
import asyncio
import json
import re
import os
import sys

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright, Error as PlaywrightError

COOKIE_DIR = Path(__file__).parent / "cookies"
QUERY = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"


async def main():
    print("=" * 60)
    print(f"京东搜索: {QUERY}")
    print("=" * 60)
    
    cookie_file = COOKIE_DIR / "jd_cookies.json"
    if not cookie_file.exists():
        print("错误: 未找到Cookie文件")
        return
    
    with open(cookie_file, 'r', encoding='utf-8') as f:
        saved_cookies = json.load(f)
    print(f"加载 {len(saved_cookies)} 条Cookie")
    
    browser = None
    try:
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
            
            await context.add_cookies(saved_cookies)
            page = await context.new_page()
            
            # 访问搜索页
            search_url = f"https://search.jd.com/Search?keyword={quote(QUERY)}"
            print(f"\n访问: {search_url}")
            
            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(5)
            
            # 检查
            title = await page.title()
            current_url = page.url
            print(f"标题: {title}")
            print(f"URL: {current_url[:60]}...")
            
            if "login" in current_url.lower():
                print("\nCookie已失效，需要重新登录")
                return
            
            # 滚动
            for i in range(5):
                try:
                    await page.evaluate(f"window.scrollTo(0, {1000 * (i+1)})")
                    await asyncio.sleep(0.5)
                except:
                    pass
            
            # 获取商品
            items = await page.query_selector_all("[data-sku], .gl-item")
            print(f"\n找到 {len(items)} 个商品元素")
            
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
            
            if products:
                products.sort(key=lambda x: x['price'])
                with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                
                print(f"\n京东找到 {len(products)} 个商品:")
                print("-" * 60)
                for i, p in enumerate(products[:10], 1):
                    print(f"[{i:2d}] ¥{p['price']:>8.2f}  {p['title'][:40]}...")
            else:
                print("\n未找到商品")
            
            # 保持浏览器打开一段时间
            print("\n浏览器将在5秒后关闭...")
            await asyncio.sleep(5)
            
    except PlaywrightError as e:
        print(f"浏览器错误: {e}")
    except Exception as e:
        print(f"错误: {e}")
    finally:
        if browser:
            try:
                await browser.close()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())
