#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""京东搜索 - 登录+搜索一体化"""
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


async def login_and_search(query: str):
    """登录并搜索京东"""
    print(f"\n京东搜索: {query}")
    print("=" * 50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # 先访问京东首页
        print("访问京东首页...")
        await page.goto("https://www.jd.com", timeout=20000)
        await asyncio.sleep(2)
        
        # 检查是否已登录
        try:
            user_name = await page.query_selector(".nickname")
            if user_name:
                name = await user_name.inner_text()
                print(f"已登录: {name}")
            else:
                print("未登录，请扫码登录...")
                # 点击登录按钮
                login_btn = await page.query_selector(".link-login, a[href*='login']")
                if login_btn:
                    await login_btn.click()
                    await asyncio.sleep(2)
                
                # 等待用户扫码登录
                print("请在弹出的窗口中扫码登录（等待最多60秒）...")
                await asyncio.sleep(5)
                
                # 等待登录成功（检测用户名出现）
                try:
                    await page.wait_for_selector(".nickname", timeout=60000)
                    print("登录成功！")
                except:
                    print("登录超时，继续尝试搜索...")
        except Exception as e:
            print(f"检测登录状态失败: {e}")
        
        # 执行搜索
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        print(f"\n搜索: {url}")
        
        await page.goto(url, timeout=20000)
        await asyncio.sleep(3)
        
        # 滚动加载
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
            await asyncio.sleep(1)
        
        # 检查是否在登录页
        current_url = page.url
        if "passport.jd.com" in current_url or "login" in current_url:
            print("仍在登录页，请手动登录...")
            print("等待登录成功（最多60秒）...")
            
            # 等待URL变化
            for _ in range(60):
                await asyncio.sleep(1)
                current_url = page.url
                if "search.jd.com" in current_url:
                    print("登录成功，正在加载商品...")
                    break
        
        # 截图
        await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"))
        
        # 获取商品
        items = await page.query_selector_all("[data-sku]")
        print(f"找到 {len(items)} 个商品元素")
        
        products = []
        for item in items[:30]:
            try:
                sku = await item.get_attribute("data-sku")
                
                # 标题
                title_el = await item.query_selector(".p-name em, .p-name a em, em")
                title = await title_el.inner_text() if title_el else ""
                
                # 价格
                price_el = await item.query_selector(".p-price i, .p-price")
                price_text = await price_el.inner_text() if price_el else "0"
                price = float(re.search(r'(\d+\.?\d*)', price_text).group(1)) if price_text else 0
                
                if title and price > 0:
                    products.append({
                        "platform": "jd",
                        "title": title.strip()[:80],
                        "price": price,
                        "url": f"https://item.jd.com/{sku}.html"
                    })
            except:
                continue
        
        # 保存Cookie
        if products:
            cookies = await context.cookies()
            with open(COOKIE_DIR / "jd_cookies.json", 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"保存 {len(cookies)} 条Cookie")
        
        await browser.close()
        
        # 保存结果
        if products:
            products.sort(key=lambda x: x['price'])
            
            with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            
            print(f"\n找到 {len(products)} 个商品（已保存）")
            print("-" * 50)
            for i, p in enumerate(products[:10], 1):
                print(f"[{i}] 价格: {p['price']:.2f} 元")
                print(f"    {p['title'][:50]}")
            
            return products
        else:
            print("未找到商品，请检查截图 jd_result.png")
            return []


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    asyncio.run(login_and_search(query))
