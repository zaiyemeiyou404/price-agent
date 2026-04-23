#!/usr/bin/env python3
"""
分析当前爬虫问题并提供解决方案
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright

async def test_jd_search():
    """测试京东搜索实际效果"""
    print("测试京东搜索...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 375, "height": 667},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        
        # 访问搜索页面
        url = "https://search.jd.com/Search?keyword=iPhone%2015"
        print(f"访问: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # 检查页面标题
        title = await page.title()
        print(f"页面标题: {title}")
        
        # 检查URL是否被重定向
        current_url = page.url
        print(f"当前URL: {current_url}")
        
        # 检查页面内容
        content = await page.content()
        print(f"页面长度: {len(content)} 字符")
        
        # 检查是否有搜索相关文本
        text = await page.text_content("body")
        if "iPhone" in text or "15" in text:
            print("✓ 页面包含搜索关键词")
        else:
            print("✗ 页面不包含搜索关键词 - 可能被重定向或反爬")
        
        # 检查常见的京东元素
        selectors = [
            "#J_goodsList",  # 商品列表
            ".gl-item",      # 商品项
            ".search-page",  # 搜索页
            ".search-2014",  # 搜索页标识
            ".w", ".main"    # 主内容区
        ]
        
        for selector in selectors:
            elements = await page.query_selector_all(selector)
            print(f"选择器 '{selector}': {len(elements)} 个元素")
        
        # 截图保存
        await page.screenshot(path="jd_search_debug.png")
        print("截图已保存到 jd_search_debug.png")
        
        # 保存HTML用于分析
        with open("jd_search_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("HTML已保存到 jd_search_page.html")
        
        await browser.close()

async def test_taobao_search():
    """测试淘宝搜索实际效果"""
    print("\n测试淘宝搜索...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 375, "height": 667},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()
        
        # 访问搜索页面
        url = "https://s.taobao.com/search?q=iPhone%2015"
        print(f"访问: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # 检查页面标题
        title = await page.title()
        print(f"页面标题: {title}")
        
        # 检查URL是否被重定向
        current_url = page.url
        print(f"当前URL: {current_url}")
        
        # 检查是否跳转到登录页
        if "login" in current_url or "login.taobao.com" in current_url:
            print("✗ 被重定向到登录页 - 需要Cookie")
        
        # 检查页面内容
        content = await page.content()
        print(f"页面长度: {len(content)} 字符")
        
        # 截图保存
        await page.screenshot(path="taobao_search_debug.png")
        print("截图已保存到 taobao_search_debug.png")
        
        await browser.close()

async def main():
    print("=" * 60)
    print("价格Agent爬虫问题诊断")
    print("=" * 60)
    
    try:
        await test_jd_search()
        await test_taobao_search()
        
        print("\n" + "=" * 60)
        print("问题诊断:")
        print("=" * 60)
        print("""
1. 京东搜索问题:
   - 京东可能对自动化工具检测严格
   - 可能需要切换移动端页面策略并增强指纹伪装
   - 推荐方案: 优先完善有头调试 + Cookie 会话续期

2. 淘宝搜索问题:
   - 淘宝需要登录Cookie才能看到商品列表
   - 无Cookie时会重定向到登录页或返回空白列表
   - 推荐方案: 获取有效Cookie并增加验证码处理兜底

3. 整体建议:
   a) 短期方案: 修复爬虫
     - 更新选择器，使用更真实的浏览器指纹
     - 配置代理IP轮换
     - 添加淘宝Cookie
   
   b) 中期方案: 强化爬虫稳定性
     - 平台级失败熔断与重试
     - 自动截图留证并记录错误上下文
     - 差异化页面策略（有头/无头）
   
   c) 长期方案: 纯爬虫工程化
     - 平台插件化接入
     - 价格监控和通知功能
     - 自动回归测试与可观测性完善
        """)
        
    except Exception as e:
        print(f"诊断过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
