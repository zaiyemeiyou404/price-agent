#!/usr/bin/env python3
"""
简单京东搜索 - 最小化版本
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from playwright.async_api import async_playwright
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)


async def simple_search(query: str = "iPhone 15"):
    """简单搜索"""
    print(f"\n搜索: {query}\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        if cookie_file.exists():
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            logger.info(f"加载 {len(cookies)} 条Cookie")
        
        page = await context.new_page()
        
        # 直接搜索
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"访问: {url}")
        
        try:
            await page.goto(url, timeout=20000)
            await asyncio.sleep(2)
            
            # 滚动
            await page.evaluate("window.scrollTo(0, 2000)")
            await asyncio.sleep(1)
            
            # 获取HTML
            html = await page.content()
            with open(COOKIE_DIR / "jd_search.html", 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info("HTML已保存")
            
            # 截图
            await page.screenshot(path=str(COOKIE_DIR / "jd_screenshot.png"))
            logger.info("截图已保存")
            
            # 用正则提取商品（最简单方式）
            # 京东商品通常在 <div class="gl-item" data-sku="...">
            products = []
            
            # 匹配商品块
            pattern = r'<div[^>]*class="gl-item[^"]*"[^>]*data-sku="(\d+)"[^>]*>.*?<em[^>]*>([^<]+)</em>.*?<i[^>]*>(\d+\.?\d*)</i>'
            
            matches = re.findall(pattern, html, re.DOTALL)
            
            for sku_id, title, price in matches[:20]:
                products.append({
                    "title": title.strip()[:60],
                    "price": float(price),
                    "url": f"https://item.jd.com/{sku_id}.html"
                })
            
            if products:
                print(f"\n✅ 找到 {len(products)} 个商品:\n")
                for i, p in enumerate(products[:10], 1):
                    print(f"[{i}] {p['title']}")
                    print(f"    ¥{p['price']}\n")
                
                # 保存
                with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                print(f"结果已保存: {COOKIE_DIR}/jd_products.json\n")
            else:
                logger.warning("正则未匹配，尝试选择器...")
                
                # 尝试选择器
                items = await page.query_selector_all("[data-sku]")
                logger.info(f"找到 {len(items)} 个商品元素")
                
                for item in items[:15]:
                    try:
                        sku = await item.get_attribute("data-sku")
                        title_el = await item.query_selector("em")
                        title = await title_el.inner_text() if title_el else ""
                        price_el = await item.query_selector(".p-price i")
                        price_text = await price_el.inner_text() if price_el else "0"
                        price = float(re.search(r'(\d+\.?\d*)', price_text).group(1))
                        
                        if title and price > 0:
                            products.append({
                                "title": title.strip()[:60],
                                "price": price,
                                "url": f"https://item.jd.com/{sku}.html"
                            })
                    except:
                        continue
                
                if products:
                    print(f"\n✅ 找到 {len(products)} 个商品:\n")
                    for i, p in enumerate(products[:10], 1):
                        print(f"[{i}] {p['title']}")
                        print(f"    ¥{p['price']}\n")
                    
                    with open(COOKIE_DIR / "jd_products.json", 'w', encoding='utf-8') as f:
                        json.dump(products, f, ensure_ascii=False, indent=2)
                    print(f"结果已保存\n")
                else:
                    logger.error("未找到商品")
                    print("查看截图分析问题")
            
        except Exception as e:
            logger.error(f"错误: {e}")
        
        finally:
            await asyncio.sleep(2)
            await browser.close()
        
        return products


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    asyncio.run(simple_search(query))
