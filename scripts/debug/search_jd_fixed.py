#!/usr/bin/env python3
"""
京东搜索修复版 - 更强大的解析器
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


async def search_with_cookie(query: str = "iPhone 15"):
    """使用保存的Cookie搜索京东"""
    print("\n" + "="*60)
    print(f"京东搜索: {query}")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器便于调试
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        # 加载Cookie
        cookie_file = COOKIE_DIR / "jd_cookies.json"
        if not cookie_file.exists():
            logger.error("未找到Cookie，请先运行登录脚本")
            return []
        
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        await context.add_cookies(cookies)
        logger.info(f"已加载 {len(cookies)} 条Cookie")
        
        page = await context.new_page()
        
        # 先访问首页验证登录状态
        logger.info("Step 1: 验证登录状态...")
        await page.goto("https://www.jd.com", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查用户名
        try:
            user_el = await page.query_selector(".nickname, [class*='username']")
            if user_el:
                username = await user_el.inner_text()
                logger.info(f"登录用户: {username}")
        except:
            logger.warning("未能获取用户名，但Cookie可能有效")
        
        # Step 2: 搜索
        logger.info(f"Step 2: 搜索 {query}...")
        search_url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"URL: {search_url}")
        
        await page.goto(search_url, timeout=60000, wait_until="networkidle")
        await asyncio.sleep(3)
        
        # 滚动加载更多
        logger.info("Step 3: 滚动加载...")
        for i in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            logger.info(f"滚动 {i+1}/5")
        
        # 截图
        screenshot_path = COOKIE_DIR / "jd_search_debug.png"
        await page.screenshot(path=str(screenshot_path))
        logger.info(f"截图已保存: {screenshot_path}")
        
        # 获取页面HTML以分析结构
        page_html = await page.content()
        html_path = COOKIE_DIR / "jd_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page_html)
        logger.info(f"HTML已保存: {html_path}")
        
        # 多种方式查找商品
        logger.info("Step 4: 解析商品...")
        
        # 方法1: 尝试多种选择器
        selectors = [
            ".gl-item", 
            "[data-sku]", 
            ".gl-i-wrap", 
            ".item",
            ".good-item",
            ".product-item",
            ".goods-item"
        ]
        
        all_items = []
        for selector in selectors:
            items = await page.query_selector_all(selector)
            if items:
                logger.info(f"使用选择器 '{selector}' 找到 {len(items)} 个元素")
                all_items.extend(items)
        
        if not all_items:
            logger.warning("未找到商品元素，尝试XPath...")
            # 使用XPath
            items = await page.query_selector_all('xpath=//div[contains(@class, "item")]')
            all_items = items
            logger.info(f"XPath找到 {len(items)} 个元素")
        
        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            try:
                item_id = await item.get_attribute("data-sku") or str(id(item))
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
            except:
                unique_items.append(item)
        
        logger.info(f"去重后得到 {len(unique_items)} 个商品")
        
        # 解析商品信息
        products = []
        for item in unique_items[:30]:
            try:
                # 提取信息
                title = ""
                price = 0
                shop = "京东"
                
                # 标题
                title_selectors = [
                    ".p-name em", 
                    ".p-name a", 
                    "[class*='title']",
                    ".title",
                    "a[title]"
                ]
                for sel in title_selectors:
                    title_el = await item.query_selector(sel)
                    if title_el:
                        title = await title_el.inner_text()
                        if not title:
                            title = await title_el.get_attribute("title") or ""
                        if title:
                            break
                
                # 价格
                price_selectors = [
                    ".p-price i", 
                    ".price i", 
                    "[class*='price']",
                    ".price"
                ]
                for sel in price_selectors:
                    price_el = await item.query_selector(sel)
                    if price_el:
                        price_text = await price_el.inner_text()
                        price_match = re.search(r'(\d+\.?\d*)', price_text)
                        if price_match:
                            price = float(price_match.group(1))
                            break
                
                # 店铺
                shop_selectors = [
                    ".p-shop a", 
                    ".shop a", 
                    "[class*='shop']",
                    ".shop"
                ]
                for sel in shop_selectors:
                    shop_el = await item.query_selector(sel)
                    if shop_el:
                        shop_text = await shop_el.inner_text()
                        if shop_text:
                            shop = shop_text.strip()
                            break
                
                # 商品ID
                sku_id = await item.get_attribute("data-sku") or ""
                
                # 链接
                url = f"https://item.jd.com/{sku_id}.html" if sku_id else ""
                
                # 保存有效商品
                if title and len(title) > 2 and price > 0:
                    product = {
                        "title": title.strip()[:80],
                        "price": price,
                        "shop": shop[:30],
                        "url": url,
                        "sku_id": sku_id
                    }
                    products.append(product)
                    
            except Exception as e:
                logger.debug(f"解析单个商品失败: {e}")
                continue
        
        # 显示结果
        logger.info(f"Step 5: 解析到 {len(products)} 个有效商品")
        
        if products:
            print("\n" + "="*60)
            print(f"✅ 搜索成功！找到 {len(products)} 个商品:")
            print("="*60)
            
            for i, p in enumerate(products[:15], 1):
                print(f"\n[{i:2d}] {p['title']}")
                print(f"    价格: ¥{p['price']} | 店铺: {p['shop']}")
            
            print("\n" + "="*60)
            
            # 保存结果
            output = COOKIE_DIR / f"jd_results_{query}.json"
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            logger.info(f"结果已保存: {output}")
            
            # 简化版本给前端用
            simple_products = [{
                "platform": "jd",
                "title": p["title"],
                "price": p["price"],
                "shop": p["shop"],
                "url": p["url"]
            } for p in products[:20]]
            
            simple_output = COOKIE_DIR / f"jd_simple.json"
            with open(simple_output, 'w', encoding='utf-8') as f:
                json.dump(simple_products, f, ensure_ascii=False, indent=2)
            logger.info(f"简化结果已保存: {simple_output}")
        else:
            logger.error("未找到商品，查看截图和HTML分析页面结构")
            print("\n⚠️ 未找到商品，可能需要手动分析页面结构:")
            print(f"   截图: {screenshot_path}")
            print(f"   HTML: {html_path}")
        
        # 保持浏览器打开查看
        print("\n浏览器保持打开，按 Ctrl+C 关闭...")
        try:
            await asyncio.sleep(30)
        except KeyboardInterrupt:
            print("\n用户中断")
        
        await browser.close()
        return products


if __name__ == "__main__":
    # 支持命令行参数
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    asyncio.run(search_with_cookie(query))
