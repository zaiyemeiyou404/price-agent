#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东搜索 - 增强版"""
import asyncio
import json
import re
import sys
import os
from datetime import datetime

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
    print(f"时间: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)
    
    async with async_playwright() as p:
        # 启动浏览器 - 不加载旧Cookie，避免污染
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="zh-CN"
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 第一步：访问京东首页
        print("\n[1/4] 访问京东首页...")
        await page.goto("https://www.jd.com", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查是否已登录
        try:
            user_el = await page.query_selector(".nickname")
            if user_el:
                name = await user_el.inner_text()
                print(f"      已登录: {name}")
            else:
                print("      未登录")
        except:
            pass
        
        # 第二步：访问搜索页
        search_url = f"https://search.jd.com/Search?keyword={quote(query)}"
        print(f"\n[2/4] 访问搜索页...")
        await page.goto(search_url, timeout=30000)
        await asyncio.sleep(2)
        
        # 检查是否被重定向到登录页
        current_url = page.url
        print(f"      当前URL: {current_url[:60]}...")
        
        if "passport.jd.com" in current_url or "login" in current_url:
            print("\n" + "=" * 60)
            print("请在浏览器窗口中扫码登录京东！")
            print("扫码后请点击'确认登录'按钮")
            print("=" * 60 + "\n")
            
            # 等待登录完成
            logged_in = False
            for i in range(120):
                await asyncio.sleep(1)
                current_url = page.url
                
                # 检查是否跳转到搜索页或首页
                if "search.jd.com" in current_url or ("jd.com" in current_url and "passport" not in current_url and "login" not in current_url):
                    print(f"\n      检测到跳转: {current_url[:50]}...")
                    logged_in = True
                    break
                
                if i % 20 == 0 and i > 0:
                    print(f"      等待登录... ({i}秒)")
            
            if not logged_in:
                print("\n      登录超时，尝试继续...")
            
            # 无论是否登录成功，都重新访问搜索页
            await asyncio.sleep(2)
            print(f"\n[3/4] 重新访问搜索页...")
            await page.goto(search_url, timeout=30000)
            await asyncio.sleep(3)
        else:
            print("      直接进入搜索页")
        
        # 第三步：滚动加载商品
        print("\n[4/4] 加载商品列表...")
        
        # 先等待页面加载
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        # 滚动多次触发懒加载
        for i in range(5):
            await page.evaluate(f"window.scrollTo(0, {1000 * (i+1)})")
            await asyncio.sleep(0.5)
        
        # 滚回顶部
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(1)
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"), full_page=False)
        print("      截图已保存")
        
        # 保存HTML
        html = await page.content()
        with open(COOKIE_DIR / "jd_debug.html", 'w', encoding='utf-8') as f:
            f.write(html)
        
        # 检查页面标题
        title = await page.title()
        print(f"      页面标题: {title}")
        print(f"      当前URL: {page.url[:60]}...")
        
        # 获取商品 - 尝试多种选择器
        selectors = [
            "[data-sku]",
            ".gl-item",
            "#J_goodsList .gl-item",
            ".goods-list-v2 li",
        ]
        
        items = []
        for sel in selectors:
            items = await page.query_selector_all(sel)
            if items:
                print(f"      使用 '{sel}' 找到 {len(items)} 个商品")
                break
        
        products = []
        if items:
            for item in items[:30]:
                try:
                    # SKU
                    sku = await item.get_attribute("data-sku")
                    
                    # 标题
                    title_el = await item.query_selector(".p-name em, .p-name a em")
                    title = await title_el.inner_text() if title_el else ""
                    
                    # 价格
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
        
        # 保存Cookie
        cookies = await context.cookies()
        with open(COOKIE_DIR / "jd_cookies.json", 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"\n      已保存 {len(cookies)} 条Cookie")
        
        await browser.close()
        
        # 输出结果
        if products:
            products.sort(key=lambda x: x['price'])
            with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*60}")
            print(f"找到 {len(products)} 个商品:")
            print("=" * 60)
            for i, p in enumerate(products[:10], 1):
                print(f"[{i:2d}] ¥{p['price']:>8.2f}  {p['title'][:40]}...")
            print(f"\n结果已保存: {COOKIE_DIR}/jd_products.json")
        else:
            print(f"\n未找到商品。请检查:")
            print("1. 截图: jd_result.png")
            print("2. HTML: jd_debug.html")
            print("3. 是否成功登录京东")


if __name__ == "__main__":
    asyncio.run(main())
