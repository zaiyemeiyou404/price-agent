#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复版搜索 - 京东 + 淘宝
"""
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def search_jd(query: str):
    """京东搜索 - 需要登录状态"""
    print(f"\n{'='*50}")
    print(f"京东搜索: {query}")
    print('='*50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        if cookie_file.exists():
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"加载 {len(cookies)} 条Cookie")
        
        page = await context.new_page()
        
        # 先访问首页建立session
        print("访问京东首页...")
        await page.goto("https://www.jd.com", timeout=20000)
        await asyncio.sleep(2)
        
        # 再搜索
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        print(f"搜索: {url}")
        
        try:
            await page.goto(url, timeout=20000)
            await asyncio.sleep(3)
            
            # 滚动加载更多
            for i in range(3):
                await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
                await asyncio.sleep(1)
            
            # 检查是否在登录页
            title = await page.title()
            if "登录" in title:
                print("[X] 仍在登录页，Cookie无效")
                await page.screenshot(path=str(COOKIE_DIR / "jd_login_page.png"))
                return []
            
            # 获取商品
            items = await page.query_selector_all("[data-sku]")
            print(f"找到 {len(items)} 个商品元素")
            
            products = []
            for item in items[:20]:
                try:
                    sku = await item.get_attribute("data-sku")
                    
                    # 标题
                    title_el = await item.query_selector(".p-name em, .p-name a em, em")
                    title = await title_el.inner_text() if title_el else ""
                    
                    # 价格
                    price_el = await item.query_selector(".p-price i, .p-price")
                    price_text = await price_el.inner_text() if price_el else "0"
                    price_match = re.search(r'(\d+\.?\d*)', price_text)
                    price = float(price_match.group(1)) if price_match else 0
                    
                    if title and price > 0:
                        products.append({
                            "platform": "jd",
                            "title": title.strip()[:80],
                            "price": price,
                            "url": f"https://item.jd.com/{sku}.html"
                        })
                except Exception as e:
                    continue
            
            # 截图
            await page.screenshot(path=str(COOKIE_DIR / "jd_result.png"), full_page=False)
            
            if products:
                print(f"\n[OK] 京东找到 {len(products)} 个商品")
                for i, p in enumerate(products[:5], 1):
                    print(f"  [{i}] ¥{p['price']:.2f} - {p['title'][:40]}...")
            
            return products
            
        except Exception as e:
            print(f"错误: {e}")
            return []
        finally:
            await browser.close()


async def search_taobao(query: str):
    """淘宝搜索"""
    print(f"\n{'='*50}")
    print(f"淘宝搜索: {query}")
    print('='*50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
        print(f"搜索: {url}")
        
        try:
            await page.goto(url, timeout=30000)
            await asyncio.sleep(3)
            
            # 滚动加载
            for i in range(3):
                await page.evaluate(f"window.scrollTo(0, {1500 * (i+1)})")
                await asyncio.sleep(1)
            
            # 使用新的选择器
            # 尝试多种卡片选择器
            card_selectors = [
                ".doubleCard--gO3Bz6bu",
                ".card--NIVn65S6",
                "[class*='doubleCard']",
                "[class*='Card--']",
            ]
            
            products = []
            for sel in card_selectors:
                items = await page.query_selector_all(sel)
                if items:
                    print(f"使用选择器 '{sel}' 找到 {len(items)} 个商品")
                    
                    for item in items[:20]:
                        try:
                            # 标题 - 多种选择器
                            title = ""
                            for title_sel in [".title--RoseSo8H", "[class*='title--']", "h3 a", "a[title]"]:
                                title_el = await item.query_selector(title_sel)
                                if title_el:
                                    title = await title_el.inner_text()
                                    if title:
                                        break
                            
                            # 价格
                            price = 0
                            for price_sel in [".priceInt--yqqZMJ5a", "[class*='priceInt']", ".price"]:
                                price_el = await item.query_selector(price_sel)
                                if price_el:
                                    price_text = await price_el.inner_text()
                                    match = re.search(r'(\d+\.?\d*)', price_text)
                                    if match:
                                        price = float(match.group(1))
                                        break
                            
                            # 链接
                            link_el = await item.query_selector("a[href*='item.taobao.com'], a[href*='detail.tmall.com']")
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
                    
                    if products:
                        break
            
            # 截图
            await page.screenshot(path=str(COOKIE_DIR / "taobao_result.png"), full_page=False)
            
            if products:
                print(f"\n[OK] 淘宝找到 {len(products)} 个商品")
                for i, p in enumerate(products[:5], 1):
                    print(f"  [{i}] ¥{p['price']:.2f} - {p['title'][:40]}...")
            else:
                print("[X] 未找到商品，可能需要更新选择器")
                # 保存HTML用于调试
                html = await page.content()
                with open(COOKIE_DIR / "taobao_debug.html", 'w', encoding='utf-8') as f:
                    f.write(html)
                print("HTML已保存到 taobao_debug.html")
            
            return products
            
        except Exception as e:
            print(f"错误: {e}")
            return []
        finally:
            await browser.close()


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    
    print(f"\n开始搜索: {query}")
    
    # 京东
    jd_products = await search_jd(query)
    
    # 淘宝
    tb_products = await search_taobao(query)
    
    # 合并结果
    all_products = jd_products + tb_products
    
    # 按价格排序
    all_products.sort(key=lambda x: x['price'])
    
    # 保存结果
    if all_products:
        try:
            with open(COOKIE_DIR / "all_products.json", 'w', encoding='utf-8') as f:
                json.dump(all_products, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存: {COOKIE_DIR}/all_products.json")
        except Exception as e:
            print(f"保存失败: {e}")
        
        print(f"\n{'='*50}")
        print(f"总计 {len(all_products)} 个商品（按价格排序）")
        print('='*50)
        for i, p in enumerate(all_products[:10], 1):
            try:
                print(f"[{i}] [{p['platform']}] 价格:{p['price']:.2f}")
                print(f"    {p['title'][:40]}...")
            except:
                print(f"[{i}] [{p['platform']}] 价格:{p['price']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
