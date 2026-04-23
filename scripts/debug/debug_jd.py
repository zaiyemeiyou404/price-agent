import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://search.jd.com/Search?keyword=iPhone%2015', wait_until='networkidle')
        await page.screenshot(path='jd_page.png')
        content = await page.content()
        with open('jd_page.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print('Screenshot and HTML saved.')
        # 尝试查找商品列表
        items = await page.query_selector_all('#J_goodsList .gl-item')
        print(f'Found {len(items)} items with selector #J_goodsList .gl-item')
        # 尝试其他选择器
        all_items = await page.query_selector_all('.gl-item')
        print(f'Found {len(all_items)} items with .gl-item')
        # 输出一些HTML片段
        if all_items:
            html = await all_items[0].inner_html()
            print('First item HTML:', html[:500])
        await browser.close()

asyncio.run(main())