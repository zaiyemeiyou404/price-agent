#!/usr/bin/env python
"""
爬虫调试工具

用于测试和调试各个平台的爬虫功能

用法:
    python scripts/debug/debug_crawler.py taobao "iPhone 15"
    python scripts/debug/debug_crawler.py jd "华为手机"
    python scripts/debug/debug_crawler.py meituan "肯德基" --lat 39.9042 --lng 116.4074
    python scripts/debug/debug_crawler.py eleme "麦当劳"
    python scripts/debug/debug_crawler.py pdd "耳机"
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


async def test_crawler(platform: str, query: str, lat: float = None, lng: float = None, headless: bool = True):
    """
    测试爬虫
    
    Args:
        platform: 平台名称 (taobao, jd, meituan, eleme, pdd)
        query: 搜索关键词
        lat: 纬度
        lng: 经度
        headless: 是否无头模式
    """
    from app.tools import get_tool
    from app.models import Platform
    
    # 平台映射
    platform_map = {
        "taobao": Platform.TAOBAO,
        "jd": Platform.JD,
        "meituan": Platform.MEITUAN,
        "eleme": Platform.ELEME,
        # "pdd": Platform.PDD,  # 拼多多暂未加入枚举
    }
    
    if platform not in platform_map:
        # 特殊处理拼多多
        if platform == "pdd":
            from app.tools.pdd import PDDTool
            tool = PDDTool()
        else:
            logger.error(f"不支持的平台: {platform}")
            return []
    else:
        tool = get_tool(platform_map[platform])
    
    logger.info(f"{'='*50}")
    logger.info(f"测试平台: {platform}")
    logger.info(f"搜索关键词: {query}")
    logger.info(f"无头模式: {headless}")
    if lat and lng:
        logger.info(f"定位: ({lat}, {lng})")
    logger.info(f"{'='*50}")
    
    # 执行搜索
    start_time = datetime.now()
    
    try:
        if lat and lng:
            products = await tool.search(query, location=f"{lat},{lng}", lat=lat, lng=lng)
        else:
            products = await tool.search(query)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"\n{'='*50}")
        logger.info(f"搜索完成，耗时: {elapsed:.2f}秒")
        logger.info(f"找到商品: {len(products)} 个")
        logger.info(f"{'='*50}\n")
        
        # 显示结果
        if products:
            for i, p in enumerate(products[:10]):  # 只显示前10个
                logger.info(f"【{i+1}】{p.title[:30]}...")
                logger.info(f"    价格: ¥{p.price:.2f} | 店铺: {p.shop_name}")
                logger.info(f"    链接: {p.jump_url[:50]}...")
                logger.info("")
        else:
            logger.warning("未找到任何商品")
        
        # 保存结果到文件
        output_file = Path(__file__).parent / "debug_output" / f"{platform}_{query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                [p.model_dump() for p in products],
                f,
                ensure_ascii=False,
                indent=2
            )
        
        logger.info(f"结果已保存到: {output_file}")
        
        return products
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await tool.close()


async def test_detail(platform: str, product_id: str):
    """
    测试获取商品详情
    
    Args:
        platform: 平台名称
        product_id: 商品ID
    """
    from app.tools import get_tool
    from app.models import Platform
    
    platform_map = {
        "taobao": Platform.TAOBAO,
        "jd": Platform.JD,
        "meituan": Platform.MEITUAN,
        "eleme": Platform.ELEME,
    }
    
    if platform not in platform_map:
        logger.error(f"不支持的平台: {platform}")
        return None
    
    tool = get_tool(platform_map[platform])
    
    logger.info(f"获取商品详情: {platform} - {product_id}")
    
    try:
        product = await tool.get_detail(product_id)
        
        if product:
            logger.info(f"标题: {product.title}")
            logger.info(f"价格: ¥{product.price:.2f}")
            logger.info(f"店铺: {product.shop_name}")
            logger.info(f"链接: {product.jump_url}")
        else:
            logger.warning("获取详情失败")
        
        return product
        
    except Exception as e:
        logger.error(f"获取详情失败: {e}")
        return None
    finally:
        await tool.close()


async def screenshot_test(platform: str, query: str, output: str = None):
    """
    截图测试 - 用于调试页面结构
    
    Args:
        platform: 平台名称
        query: 搜索关键词
        output: 截图保存路径
    """
    from app.tools.base_crawler import BrowserManager
    
    manager = BrowserManager()
    
    try:
        browser = await manager.get_browser(headless=False)  # 非无头模式方便观察
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = await context.new_page()
        
        # 根据平台访问不同URL
        from urllib.parse import quote
        
        urls = {
            "taobao": f"https://s.taobao.com/search?q={quote(query)}",
            "jd": f"https://search.jd.com/Search?keyword={quote(query)}",
            "meituan": "https://waimai.meituan.com/",
            "eleme": "https://www.ele.me/",
            "pdd": f"https://mobile.yangkeduo.com/search_result.html?search_key={quote(query)}",
        }
        
        if platform not in urls:
            logger.error(f"不支持的平台: {platform}")
            return
        
        url = urls[platform]
        logger.info(f"访问: {url}")
        
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # 滚动加载
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
        
        # 截图
        output_path = output or f"debug_{platform}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=output_path, full_page=True)
        
        logger.info(f"截图已保存: {output_path}")
        
        # 等待用户观察
        input("按回车键关闭浏览器...")
        
    except Exception as e:
        logger.error(f"截图测试失败: {e}")
    finally:
        await manager.close_all()


def main():
    parser = argparse.ArgumentParser(description="爬虫调试工具")
    parser.add_argument("platform", help="平台名称 (taobao, jd, meituan, eleme, pdd)")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--lat", type=float, help="纬度")
    parser.add_argument("--lng", type=float, help="经度")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    parser.add_argument("--no-headless", action="store_true", help="非无头模式")
    parser.add_argument("--detail", type=str, help="获取商品详情，传入商品ID")
    parser.add_argument("--screenshot", action="store_true", help="截图模式")
    parser.add_argument("--output", type=str, help="截图输出路径")
    
    args = parser.parse_args()
    
    headless = not args.no_headless
    
    if args.screenshot:
        asyncio.run(screenshot_test(args.platform, args.query, args.output))
    elif args.detail:
        asyncio.run(test_detail(args.platform, args.detail))
    else:
        asyncio.run(test_crawler(args.platform, args.query, args.lat, args.lng, headless))


if __name__ == "__main__":
    main()
