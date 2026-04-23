#!/usr/bin/env python3
"""
测试 Playwright 是否正常工作
"""
import sys
print(f"Python 版本: {sys.version}")
print(f"平台: {sys.platform}")

print("\n测试 1: 同步 API...")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.baidu.com")
        title = page.title()
        print(f"✓ 页面标题: {title}")
        browser.close()
    print("✓ 同步 API 测试通过!")
except Exception as e:
    print(f"✗ 同步 API 测试失败: {e}")

print("\n测试 2: 异步 API...")
try:
    import asyncio
    
    async def test_async():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://www.baidu.com")
            title = await page.title()
            print(f"✓ 页面标题: {title}")
            await browser.close()
    
    # Windows 上需要特殊处理
    if sys.platform == 'win32':
        if sys.version_info >= (3, 14):
            # Python 3.14+ 
            asyncio.run(test_async())
        else:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            asyncio.run(test_async())
    else:
        asyncio.run(test_async())
    
    print("✓ 异步 API 测试通过!")
except Exception as e:
    print(f"✗ 异步 API 测试失败: {e}")

print("\n测试完成!")
