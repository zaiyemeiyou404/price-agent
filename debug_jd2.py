import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://search.jd.com/Search?keyword=iPhone%2015', wait_until='networkidle')
        # 获取页面文本内容
        text = await page.text_content('body')
        print('Page text length:', len(text))
        # 查找包含“商品”的文本
        if '商品' in text:
            print('Found "商品" in text')
        # 查找商品列表容器
        html = await page.content()
        # 检查常见商品容器
        selectors = ['#J_goodsList', '.gl-item', '.goods-list', '.item', '.product']
        for sel in selectors:
            count = len(await page.query_selector_all(sel))
            print(f'Selector {sel}: {count} elements')
        # 输出部分HTML
        lines = html.split('\n')
        for line in lines:
            if 'gl-item' in line or 'J_goodsList' in line:
                print(line[:200])
                break
        await browser.close()

asyncio.run(main())