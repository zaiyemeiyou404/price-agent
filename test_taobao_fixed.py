import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.tools.taobao import TaobaoTool

async def test():
    tool = TaobaoTool()
    try:
        products = await tool.search("iPhone 15")
        print(f"Success! Got {len(products)} products")
        for p in products[:5]:
            print(f"  - {p.title[:50]}... ¥{p.price}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tool.close()

asyncio.run(test())