import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # stealth
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        page = await context.new_page()
        await page.goto('https://search.jd.com/Search?keyword=iPhone%2015', wait_until='domcontentloaded')
        await page.screenshot(path='jd_debug.png')
        html = await page.content()
        with open('jd_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print('Saved screenshot and HTML')
        # 搜索商品相关文本
        text = await page.text_content('body')
        if 'iPhone' in text:
            print('Found iPhone in text')
        # 查找所有包含价格的元素
        price_elements = await page.query_selector_all('[class*=\"price\"]')
        print(f'Found {len(price_elements)} price-like elements')
        # 查找所有图片
        img_elements = await page.query_selector_all('img')
        print(f'Found {len(img_elements)} images')
        # 输出部分HTML
        lines = html.split('\\n')
        for line in lines:
            if 'gl-item' in line or 'J_goodsList' in line or 'item' in line:
                print(line[:200])
        await browser.close()

asyncio.run(main())