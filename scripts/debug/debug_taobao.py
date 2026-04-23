#!/usr/bin/env python3
"""
淘宝爬虫调试脚本 - 查看页面实际结构

用法:
    python debug_taobao.py "iPhone 15"
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright


async def debug_taobao_search(query: str):
    """调试淘宝搜索，保存页面截图和HTML"""
    
    print(f"Python 版本: {sys.version}")
    print(f"搜索关键词: {query}")
    print("=" * 50)
    
    # Cookie 路径
    cookie_dir = Path(__file__).parent / "cookies"
    cookie_file = cookie_dir / "taobao_cookies.json"
    
    async with async_playwright() as p:
        # 启动浏览器（非无头模式，方便观察）
        print("\n1. 启动浏览器...")
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器窗口
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        # 加载 Cookie
        if cookie_file.exists():
            print(f"2. 加载 Cookie: {cookie_file}")
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"   已加载 {len(cookies)} 条 Cookie")
        else:
            print(f"2. 未找到 Cookie 文件: {cookie_file}")
            print("   请先运行: python scripts/login/login.py taobao qr")
        
        # 先访问首页
        print("\n3. 访问淘宝首页...")
        try:
            await page.goto("https://www.taobao.com", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"   访问首页超时，继续尝试搜索页...")
        
        # 检查登录状态
        print("\n4. 检查登录状态...")
        try:
            # 尝试多种方式检测登录状态
            login_btn = await page.query_selector("text=登录")
            if login_btn:
                print("   ⚠ 未登录或登录已过期！")
                print("   请运行: python scripts/login/login.py taobao qr")
            else:
                # 尝试获取用户名
                user_selectors = [
                    ".site-nav-user a",
                    ".member-nick",
                    "[class*='member']",
                ]
                for sel in user_selectors:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.inner_text()
                        if text and "登录" not in text:
                            print(f"   ✓ 已登录: {text}")
                            break
        except Exception as e:
            print(f"   检查登录状态失败: {e}")
        
        # 访问搜索页
        from urllib.parse import quote
        url = f"https://s.taobao.com/search?q={quote(query)}"
        print(f"\n5. 访问搜索页: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"   页面加载超时: {e}")
            print("   尝试继续...")
        
        # 等待页面加载
        print("   等待页面加载...")
        await asyncio.sleep(5)
        
        # 滚动页面
        print("   滚动页面加载更多...")
        for i in range(3):
            await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {(i+1)/3})")
            await asyncio.sleep(1)
        
        # 保存截图
        screenshot_path = cookie_dir / f"debug_taobao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"\n6. 截图已保存: {screenshot_path}")
        
        # 保存 HTML
        html_path = cookie_dir / f"debug_taobao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_content = await page.content()
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"   HTML已保存: {html_path}")
        
        # 尝试查找商品
        print("\n7. 尝试查找商品元素...")
        
        # 常见选择器
        selectors = [
            "[class*='Card--']",
            "[class*='Item--']",
            "[class*='item']",
            "[data-spm-anchor-id]",
            "a[href*='item.taobao.com']",
            "a[href*='item.htm']",
            ".Content--contentInner--QFC1q4J",
            "#mainsrp-itemlist",
        ]
        
        found_any = False
        for sel in selectors:
            elements = await page.query_selector_all(sel)
            if elements:
                print(f"   ✓ 选择器 '{sel}' 找到 {len(elements)} 个元素")
                found_any = True
                if len(elements) <= 10:
                    # 打印前几个元素的部分内容
                    for i, el in enumerate(elements[:3]):
                        text = await el.inner_text()
                        text = text[:100] + "..." if len(text) > 100 else text
                        print(f"      [{i}] {text}")
        
        if not found_any:
            print("   ✗ 未找到任何商品元素")
            
            # 检查是否有验证码
            print("\n   检查是否有验证码...")
            captcha_selectors = [
                "#nc_1_wrapper",
                ".nc_wrapper", 
                "[class*='captcha']",
                "text=验证码",
                "text=滑块",
            ]
            for sel in captcha_selectors:
                el = await page.query_selector(sel)
                if el:
                    print(f"   ⚠ 检测到验证码: {sel}")
        
        # 等待用户查看
        print("\n" + "=" * 50)
        print("调试完成！浏览器将保持打开，按 Enter 关闭...")
        print("请查看截图和 HTML 文件来分析页面结构")
        input()
        
        await browser.close()


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "iPhone 15"
    asyncio.run(debug_taobao_search(query))
