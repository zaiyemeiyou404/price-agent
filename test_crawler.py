#!/usr/bin/env python
"""
简单测试脚本 - 测试爬虫是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_import():
    """测试导入"""
    print("📦 测试模块导入...")
    
    try:
        from app.models import Platform, Product, CompareRequest
        print("  ✅ models 导入成功")
    except Exception as e:
        print(f"  ❌ models 导入失败: {e}")
        return False
    
    try:
        from app.tools.base_crawler import BaseCrawler, BrowserManager
        print("  ✅ base_crawler 导入成功")
    except Exception as e:
        print(f"  ❌ base_crawler 导入失败: {e}")
        return False
    
    try:
        from app.tools import TaobaoCrawler, JDCrawler, MeituanCrawler, ElemeCrawler, PDDCrawler
        print("  ✅ 所有爬虫工具导入成功")
    except Exception as e:
        print(f"  ❌ 爬虫工具导入失败: {e}")
        return False
    
    try:
        from app.tools import get_tool
        print("  ✅ get_tool 导入成功")
    except Exception as e:
        print(f"  ❌ get_tool 导入失败: {e}")
        return False
    
    return True


async def test_crawler(platform_name: str, query: str):
    """测试单个爬虫"""
    from app.models import Platform
    from app.tools import get_tool
    from app.tools.pdd import PDDTool
    
    print(f"\n🔍 测试 {platform_name} 爬虫: {query}")
    
    if platform_name == "pdd":
        tool = PDDTool()
    else:
        platform_map = {
            "taobao": Platform.TAOBAO,
            "jd": Platform.JD,
            "meituan": Platform.MEITUAN,
            "eleme": Platform.ELEME,
        }
        tool = get_tool(platform_map[platform_name])
    
    try:
        products = await tool.search(query)
        
        if products:
            print(f"  ✅ 成功获取 {len(products)} 个商品")
            # 显示前3个
            for i, p in enumerate(products[:3]):
                print(f"     [{i+1}] {p.title[:30]}... - ¥{p.price:.2f}")
        else:
            print(f"  ⚠️ 未获取到商品（可能是反爬或网络问题）")
        
        return len(products) > 0
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False
    finally:
        await tool.close()


async def test_api():
    """测试API接口"""
    print("\n🌐 测试 API 接口...")
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # 测试健康检查
            try:
                response = await client.get("http://127.0.0.1:8000/health", timeout=5)
                if response.status_code == 200:
                    print("  ✅ 服务正在运行")
                    return True
            except:
                pass
            
            print("  ⚠️ 服务未启动，请运行: uvicorn app.main:app --reload")
            return False
            
    except ImportError:
        print("  ⚠️ httpx 未安装，跳过 API 测试")
        return None


async def main():
    print("=" * 50)
    print("  智能价格比价系统 - 测试脚本")
    print("=" * 50)
    
    # 1. 测试导入
    if not await test_import():
        print("\n❌ 导入测试失败，请检查依赖安装")
        return
    
    # 2. 测试API
    await test_api()
    
    # 3. 询问是否测试爬虫
    print("\n" + "=" * 50)
    print("是否测试爬虫功能？（需要安装 Playwright 浏览器）")
    print("1. 测试淘宝")
    print("2. 测试京东")
    print("3. 测试拼多多")
    print("4. 测试所有购物平台")
    print("0. 跳过")
    print("=" * 50)
    
    try:
        choice = input("请选择 (0-4): ").strip()
    except:
        choice = "0"
    
    if choice == "1":
        await test_crawler("taobao", "iPhone")
    elif choice == "2":
        await test_crawler("jd", "iPhone")
    elif choice == "3":
        await test_crawler("pdd", "iPhone")
    elif choice == "4":
        for platform in ["taobao", "jd", "pdd"]:
            await test_crawler(platform, "iPhone")
    else:
        print("\n⏭️ 跳过爬虫测试")
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n📖 使用说明:")
    print("  1. 启动服务: uvicorn app.main:app --reload")
    print("  2. 打开前端: simple-ui.html")
    print("  3. API文档: http://127.0.0.1:8000/docs")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
