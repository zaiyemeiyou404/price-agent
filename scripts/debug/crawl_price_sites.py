#!/usr/bin/env python3
"""
比价网站爬虫 - 慢慢买

慢慢买是一个聚合比价网站，反爬宽松，容易成功
网址: https://home.manmanbuy.com/
"""
import asyncio
import re
from urllib.parse import quote
from playwright.async_api import async_playwright
from loguru import logger
import sys
import json

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")


async def search_manmanbuy(query: str):
    """
    从慢慢买搜索商品比价信息
    
    Args:
        query: 搜索关键词
    
    Returns:
        商品列表
    """
    logger.info(f"[慢慢买] 搜索: {query}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        try:
            # 搜索URL
            url = f"https://home.manmanbuy.com/search.aspx?keyword={quote(query)}"
            logger.info(f"访问: {url}")
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 等待商品列表
            await page.wait_for_selector(".shop-list, .goods-list, table", timeout=10000)
            
            # 获取页面内容
            content = await page.content()
            
            # 尝试解析商品
            products = []
            
            # 方法1: 查找表格行
            rows = await page.query_selector_all("table tr, .list-item, .goods-item")
            
            if not rows:
                # 方法2: 查找列表项
                rows = await page.query_selector_all("li[class*='item'], div[class*='goods']")
            
            logger.info(f"找到 {len(rows)} 个元素")
            
            for i, row in enumerate(rows[:15]):
                try:
                    text = await row.inner_text()
                    if not text or len(text) < 10:
                        continue
                    
                    # 尝试提取商品信息
                    # 格式通常是: 商品名 价格 来源平台
                    
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    if len(lines) >= 2:
                        title = lines[0]
                        
                        # 提取价格
                        price_match = re.search(r'¥?(\d+\.?\d*)', text)
                        price = float(price_match.group(1)) if price_match else 0
                        
                        # 提取平台名
                        platforms = ['京东', '淘宝', '天猫', '拼多多', '苏宁']
                        platform = '未知'
                        for p in platforms:
                            if p in text:
                                platform = p
                                break
                        
                        if price > 0:
                            products.append({
                                "title": title[:50],
                                "price": price,
                                "platform": platform,
                                "raw_text": text[:100]
                            })
                            
                except Exception as e:
                    logger.debug(f"解析行失败: {e}")
                    continue
            
            # 如果表格方式没找到，尝试直接提取价格信息
            if not products:
                logger.info("尝试提取页面价格信息...")
                
                # 查找所有价格
                price_elements = await page.query_selector_all("span, td, div")
                for el in price_elements[:50]:
                    try:
                        text = await el.inner_text()
                        if '¥' in text or '￥' in text:
                            price_match = re.search(r'[¥￥](\d+\.?\d*)', text)
                            if price_match:
                                products.append({
                                    "price": float(price_match.group(1)),
                                    "raw_text": text[:50]
                                })
                    except:
                        pass
            
            logger.info(f"解析到 {len(products)} 个商品")
            
            # 显示结果
            if products:
                print("\n" + "="*60)
                for i, p in enumerate(products[:10], 1):
                    if 'title' in p:
                        print(f"[{i}] {p['title']}")
                        print(f"    价格: ¥{p['price']} | 平台: {p['platform']}")
                    else:
                        print(f"[{i}] ¥{p['price']}")
                print("="*60)
            
            # 保存截图
            await page.screenshot(path=r"G:\.openclaw\workspace\price-agent\manmanbuy.png")
            logger.info("截图已保存")
            
            return products
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
        finally:
            await browser.close()


async def search_smzdm(query: str):
    """
    从什么值得买搜索商品
    
    Args:
        query: 搜索关键词
    
    Returns:
        商品列表
    """
    logger.info(f"[什么值得买] 搜索: {query}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        try:
            url = f"https://search.smzdm.com/?c=post&s={quote(query)}"
            logger.info(f"访问: {url}")
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # 查找商品项
            items = await page.query_selector_all(".feed-row-wide, .item, article")
            logger.info(f"找到 {len(items)} 个元素")
            
            products = []
            for item in items[:15]:
                try:
                    text = await item.inner_text()
                    if not text or len(text) < 10:
                        continue
                    
                    # 提取标题
                    title_el = await item.query_selector("h1, h2, .title, a[title]")
                    title = ""
                    if title_el:
                        title = await title_el.inner_text()
                    
                    # 提取价格
                    price_match = re.search(r'[¥￥](\d+\.?\d*)', text)
                    price = float(price_match.group(1)) if price_match else 0
                    
                    if title or price > 0:
                        products.append({
                            "title": title[:50] or text[:30],
                            "price": price,
                            "raw_text": text[:100]
                        })
                        
                except Exception as e:
                    logger.debug(f"解析失败: {e}")
                    continue
            
            logger.info(f"解析到 {len(products)} 个商品")
            
            if products:
                print("\n" + "="*60)
                for i, p in enumerate(products[:10], 1):
                    print(f"[{i}] {p['title'][:40]}")
                    if p['price'] > 0:
                        print(f"    价格: ¥{p['price']}")
                print("="*60)
            
            await page.screenshot(path=r"G:\.openclaw\workspace\price-agent\smzdm.png")
            logger.info("截图已保存")
            
            return products
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
        finally:
            await browser.close()


async def main():
    print("\n" + "="*60)
    print("比价网站爬虫测试")
    print("="*60)
    
    query = "iPhone 15"
    
    # 测试慢慢买
    print("\n>>> 测试慢慢买")
    await search_manmanbuy(query)
    
    # 测试什么值得买
    print("\n>>> 测试什么值得买")
    await search_smzdm(query)
    
    print("\n完成！")


if __name__ == "__main__":
    asyncio.run(main())
