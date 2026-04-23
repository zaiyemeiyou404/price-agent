#!/usr/bin/env python3
"""京东爬虫 - 可视化模式"""
import asyncio
from playwright.async_api import async_playwright
import json

async def crawl_jd():
    async with async_playwright() as p:
        # 非headless模式，更难被检测
        browser = await p.chromium.launch(
            headless=False,  # 可视化模式
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        
        # 加载Cookie
        try:
            with open(r"G:\.openclaw\workspace\price-agent\cookies\jd_cookies.json", 'r') as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                print(f"已加载 {len(cookies)} 条Cookie")
        except Exception as e:
            print(f"加载Cookie失败: {e}")
        
        page = await context.new_page()
        
        # 先访问首页
        print("访问京东首页...")
        await page.goto("https://www.jd.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # 检查登录状态
        try:
            user_info = await page.query_selector(".nickname")
            if user_info:
                nick = await user_info.inner_text()
                print(f"登录用户: {nick}")
            else:
                print("未检测到登录用户")
        except:
            pass
        
        # 访问搜索页
        url = "https://search.jd.com/Search?keyword=iPhone%2015"
        print(f"搜索: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # 等待页面加载
        await asyncio.sleep(3)
        
        # 滚动加载商品
        for i in range(5):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            print(f"滚动 {i+1}/5")
        
        # 尝试多种选择器
        selectors = [
            "li.gl-item",
            ".gl-item",
            "[data-sku]",
            "#J_goodsList .gl-item",
            ".goods-list-v2 li",
        ]
        
        items = []
        for sel in selectors:
            found = await page.query_selector_all(sel)
            if found:
                items = found
                print(f"选择器 '{sel}' 找到 {len(items)} 个商品")
                break
        
        if not items:
            print("未找到商品，页面可能需要登录")
            # 保存截图和HTML
            await page.screenshot(path=r"G:\.openclaw\workspace\price-agent\jd_debug.png")
            html = await page.content()
            with open(r"G:\.openclaw\workspace\price-agent\jd_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("已保存截图和HTML用于调试")
        else:
            # 解析商品
            print(f"\n找到 {len(items)} 个商品，解析中...")
            products = []
            for i, item in enumerate(items[:10]):
                try:
                    # 标题
                    title_el = await item.query_selector(".p-name em, .p-name a, [class*='p-name']")
                    title = await title_el.inner_text() if title_el else ""
                    
                    # 价格
                    price_el = await item.query_selector(".p-price i, [class*='p-price'] i")
                    price = await price_el.inner_text() if price_el else "0"
                    
                    # 店铺
                    shop_el = await item.query_selector(".p-shop a")
                    shop = await shop_el.inner_text() if shop_el else "京东"
                    
                    # 链接
                    link_el = await item.query_selector(".p-img a")
                    href = await link_el.get_attribute("href") if link_el else ""
                    
                    print(f"\n[{i+1}] {title[:40]}...")
                    print(f"    价格: {price} | 店铺: {shop}")
                    
                    products.append({
                        "title": title,
                        "price": price,
                        "shop": shop,
                        "url": href
                    })
                except Exception as e:
                    print(f"解析商品 {i} 失败: {e}")
            
            # 保存结果
            with open(r"G:\.openclaw\workspace\price-agent\jd_products.json", "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到 jd_products.json")
        
        print("\n按回车关闭浏览器...")
        # 不自动关闭，让用户观察
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(crawl_jd())
