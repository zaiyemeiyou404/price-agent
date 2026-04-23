#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多平台比价 - 京东+淘宝一体化"""
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
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def search_jd(context: BrowserContext, query: str) -> list:
    """京东搜索"""
    print("\n[京东] 开始搜索...")
    
    page = await context.new_page()
    
    # 先访问首页
    await page.goto("https://www.jd.com", timeout=20000)
    await asyncio.sleep(2)
    
    # 检查登录状态
    user_el = await page.query_selector(".nickname, .user_name")
    if user_el:
        name = await user_el.inner_text()
        print(f"[京东] 已登录: {name}")
    else:
        print("[京东] 请在浏览器窗口中扫码登录...")
    
    # 搜索
    url = f"https://search.jd.com/Search?keyword={quote(query)}"
    await page.goto(url, timeout=20000)
    await asyncio.sleep(2)
    
    # 检查是否被重定向到登录页
    if "passport.jd.com" in page.url or "login" in page.url:
        print("[京东] 被重定向到登录页，请扫码登录（等待最多90秒）...")
        await asyncio.sleep(5)
        
        # 等待登录成功
        logged_in = False
        for i in range(90):
            await asyncio.sleep(1)
            # 检查是否跳转回搜索页
            if "search.jd.com" in page.url:
                print("[京东] 登录成功！")
                logged_in = True
                await asyncio.sleep(3)
                break
            if i == 30:
                print("[京东] 还在等待登录...（剩余60秒）")
            if i == 60:
                print("[京东] 还在等待登录...（剩余30秒）")
        
        # 如果还在登录页，手动导航
        if not logged_in:
            print("[京东] 登录超时，尝试直接访问搜索页...")
            await page.goto(f"https://search.jd.com/Search?keyword={quote(query)}", timeout=20000)
            await asyncio.sleep(3)
    
    # 等待商品列表加载
    print("[京东] 等待商品列表加载...")
    try:
        await page.wait_for_selector("[data-sku]", timeout=10000)
        print("[京东] 商品列表已加载")
    except:
        print("[京东] 未检测到商品列表，尝试继续...")
    
    # 滚动加载
    for i in range(3):
        await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
        await asyncio.sleep(1)  # 增加等待时间
    
    # 截图
    await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"))
    
    # 保存HTML用于调试
    html = await page.content()
    with open(COOKIE_DIR / "jd_debug.html", 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[京东] 当前URL: {page.url}")
    
    # 获取商品 - 尝试多种选择器
    selectors = [
        "[data-sku]",
        ".gl-item",
        ".J-goods-list .gl-item",
        "#J_goodsList .gl-item"
    ]
    
    items = []
    for sel in selectors:
        items = await page.query_selector_all(sel)
        if items:
            print(f"[京东] 使用选择器 '{sel}' 找到 {len(items)} 个商品元素")
            break
    
    if not items:
        # 尝试直接获取所有商品链接
        items = await page.query_selector_all("a[href*='item.jd.com']")
        if items:
            print(f"[京东] 通过商品链接找到 {len(items)} 个元素")
    
    products = []
    for item in items[:30]:
        try:
            sku = await item.get_attribute("data-sku")
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
                    "url": f"https://item.jd.com/{sku}.html"
                })
        except:
            continue
    
    # 保存Cookie
    cookies = await context.cookies()
    with open(COOKIE_DIR / "jd_cookies.json", 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    
    await page.close()
    
    if products:
        print(f"[京东] 成功获取 {len(products)} 个商品")
    else:
        print("[京东] 未获取到商品，请检查登录状态")
    
    return products


async def search_taobao(context: BrowserContext, query: str) -> list:
    """淘宝搜索"""
    print("\n[淘宝] 开始搜索...")
    
    page = await context.new_page()
    url = f"https://s.taobao.com/search?q={quote(query)}"
    
    await page.goto(url, timeout=30000)
    await asyncio.sleep(3)
    
    # 滚动加载
    for i in range(3):
        await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
        await asyncio.sleep(0.8)
    
    # 截图
    await page.screenshot(path=str(COOKIE_DIR / "taobao_result.png"))
    
    # 获取商品
    items = await page.query_selector_all(".doubleCard--gO3Bz6bu, [class*='doubleCard']")
    print(f"[淘宝] 找到 {len(items)} 个商品卡片")
    
    products = []
    for item in items[:30]:
        try:
            # 标题
            title_el = await item.query_selector("[class*='title--']")
            title = await title_el.inner_text() if title_el else ""
            
            # 价格
            price_int_el = await item.query_selector("[class*='priceInt']")
            price_int = await price_int_el.inner_text() if price_int_el else "0"
            
            price_float_el = await item.query_selector("[class*='priceFloat']")
            price_float = await price_float_el.inner_text() if price_float_el else ""
            
            price_str = price_int + price_float
            price = float(re.search(r'(\d+\.?\d*)', price_str).group(1)) if price_str else 0
            
            # 链接
            link_el = await item.query_selector("a")
            href = await link_el.get_attribute("href") if link_el else ""
            
            if title and price > 0:
                products.append({
                    "platform": "淘宝",
                    "title": title.strip()[:80],
                    "price": price,
                    "url": href
                })
        except:
            continue
    
    await page.close()
    
    if products:
        print(f"[淘宝] 成功获取 {len(products)} 个商品")
    
    return products


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    
    print("=" * 60)
    print(f"多平台比价 - {query}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        # 加载淘宝Cookie
        tb_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        tb_cookie_file = COOKIE_DIR / "taobao_cookies.json"
        if tb_cookie_file.exists():
            with open(tb_cookie_file, 'r', encoding='utf-8') as f:
                await tb_context.add_cookies(json.load(f))
        
        # 加载京东Cookie
        jd_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800}
        )
        jd_cookie_file = COOKIE_DIR / "jd_cookies.json"
        if jd_cookie_file.exists():
            with open(jd_cookie_file, 'r', encoding='utf-8') as f:
                await jd_context.add_cookies(json.load(f))
        
        # 并行搜索
        jd_task = asyncio.create_task(search_jd(jd_context, query))
        tb_task = asyncio.create_task(search_taobao(tb_context, query))
        
        jd_products, tb_products = await asyncio.gather(jd_task, tb_task)
        
        await browser.close()
    
    # 合并结果
    all_products = jd_products + tb_products
    all_products.sort(key=lambda x: x['price'])
    
    # 保存结果
    if all_products:
        result_file = COOKIE_DIR / "price_comparison.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "query": query,
                "time": datetime.now().isoformat(),
                "total": len(all_products),
                "jd_count": len(jd_products),
                "tb_count": len(tb_products),
                "products": all_products
            }, f, ensure_ascii=False, indent=2)
        
        print("\n" + "=" * 60)
        print(f"比价结果（共 {len(all_products)} 个商品，按价格排序）")
        print("=" * 60)
        
        for i, p in enumerate(all_products[:15], 1):
            print(f"[{i:2d}] [{p['platform']}] ¥{p['price']:>8.2f}  {p['title'][:35]}...")
        
        print(f"\n结果已保存: {result_file}")
    else:
        print("\n未获取到任何商品数据")


if __name__ == "__main__":
    asyncio.run(main())
