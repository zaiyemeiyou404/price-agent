#!/usr/bin/env python3
"""
简单测试脚本 - 测试京东/淘宝搜索
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.tools.jd import JDTool
from app.tools.taobao import TaobaoTool


async def test_jd(query: str):
    """测试京东搜索"""
    print("=" * 50)
    print("测试京东搜索...")
    print("=" * 50)
    
    tool = JDTool()
    tool.headless = True  # 后台运行
    
    try:
        products = await tool.search(query, max_results=10)
        print(f"\n找到 {len(products)} 个商品:\n")
        
        for i, p in enumerate(products[:5], 1):
            print(f"{i}. {p.title[:40]}...")
            print(f"   价格: ¥{p.price:.2f}")
            print(f"   店铺: {p.shop_name}")
            print()
            
        return products
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await tool.close()


async def test_taobao(query: str):
    """测试淘宝搜索"""
    print("=" * 50)
    print("测试淘宝搜索...")
    print("=" * 50)
    
    tool = TaobaoTool()
    tool.headless = True  # 后台运行
    
    try:
        products = await tool.search(query, max_results=10)
        print(f"\n找到 {len(products)} 个商品:\n")
        
        for i, p in enumerate(products[:5], 1):
            print(f"{i}. {p.title[:40]}...")
            print(f"   价格: ¥{p.price:.2f}")
            print(f"   店铺: {p.shop_name}")
            print()
            
        return products
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        await tool.close()


async def main():
    query = input("请输入搜索关键词 (默认: iPhone 15): ").strip()
    if not query:
        query = "iPhone 15"
    
    print(f"\n搜索关键词: {query}")
    print("1. 测试京东")
    print("2. 测试淘宝")
    print("3. 测试两个平台")
    
    choice = input("\n输入选项 (1/2/3, 默认3): ").strip()
    if not choice:
        choice = "3"
    
    all_products = []
    
    if choice in ["1", "3"]:
        products = await test_jd(query)
        all_products.extend(products)
    
    if choice in ["2", "3"]:
        products = await test_taobao(query)
        all_products.extend(products)
    
    # 输出比价摘要
    if all_products:
        print("\n" + "=" * 50)
        print("📊 比价摘要")
        print("=" * 50)
        valid_prices = [p.price for p in all_products if p.price > 0]
        if valid_prices:
            print(f"最低价: ¥{min(valid_prices):.2f}")
            print(f"最高价: ¥{max(valid_prices):.2f}")
            
            # 找出最低价商品
            min_product = min(all_products, key=lambda p: p.price if p.price > 0 else float('inf'))
            print(f"\n最划算: {min_product.title[:30]}...")
            print(f"        ¥{min_product.price:.2f} - {min_product.shop_name}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
