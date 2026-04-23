# 开发指南 - 给 DeepSeek 的完整任务规格

> 本文档包含所有需要实现的功能模块，提供完整的接口定义、实现逻辑、错误处理和测试示例。
> 
> **请严格按照本文档实现，保持代码风格一致。**

---

## 📋 项目概述

### 项目目标
多平台智能比价系统，支持：
- **购物比价**：淘宝、京东
- **外卖比价**：饿了么、美团

### 核心架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户请求                                        │
│                    POST /api/v1/compare                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API层 (compare.py)                                 │
│                    接收 CompareRequest，返回 CompareResult                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CompareService (服务层)                              │
│              1. 检查缓存 → 2. 调用 Agent → 3. 缓存结果                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Agent (ReAct引擎)                                 │
│     ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐               │
│     │  Plan   │ →  │   Act   │ →  │ Observe │ →  │ Reflect │               │
│     │ 规划器   │    │ 工具调用 │    │ 收集结果 │    │ 反思推荐 │               │
│     └─────────┘    └─────────┘    └─────────┘    └─────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Tools (平台爬虫)                                   │
│     ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│     │ TaobaoTool│  │  JDTool   │  │ ElemeTool │  │MeituanTool│            │
│     │  淘宝爬虫  │  │  京东爬虫  │  │ 饿了么爬虫 │  │ 美团爬虫  │            │
│     └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
│                           ↓                                                  │
│                    Playwright 浏览器自动化                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 数据流详解

```
用户输入: "帮我比价 iPhone 15"
    │
    ▼
CompareRequest(query="iPhone 15", type="shopping", platforms=["taobao", "jd"])
    │
    ▼
CompareService.compare()
    │
    ├── 1. CacheService.get("compare:iPhone 15:taobao:jd") → 缓存未命中
    │
    ├── 2. Agent.run(request)
    │       │
    │       ├── Planner.plan("iPhone 15") → ["taobao", "jd"]
    │       │
    │       ├── 并发调用工具:
    │       │   ├── TaobaoTool.search("iPhone 15") → [Product, Product, ...]
    │       │   └── JDTool.search("iPhone 15") → [Product, Product, ...]
    │       │
    │       └── Reflector.reflect(products) → {best_deal, summary}
    │
    ├── 3. CacheService.set("compare:iPhone 15:taobao:jd", result, ttl=5min)
    │
    ▼
CompareResult(
    query="iPhone 15",
    type="shopping",
    products=[Product, Product, ...],
    best_deal=Product(...),
    summary="京东价格最低，5999元，比淘宝便宜200元..."
)
```

### 技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| Web框架 | FastAPI + Uvicorn | 异步API框架 |
| 爬虫引擎 | Playwright | 无头浏览器自动化 |
| 数据模型 | Pydantic v2 | 数据验证和序列化 |
| 大模型 | GLM-5 / DeepSeek | 意图识别和推荐生成 |
| 缓存 | Redis + aiocache | 搜索结果缓存 |

---

## 🎯 优先级说明

| 优先级 | 含义 | 说明 |
|--------|------|------|
| 🔴 P0 | 核心功能 | 必须先实现，系统才能运行 |
| 🟡 P1 | 重要功能 | 完善用户体验 |
| 🟢 P2 | 优化功能 | 可后续迭代 |

---

## 📁 已有代码结构

```
price-agent/
├── app/
│   ├── __init__.py
│   ├── main.py              # ✅ FastAPI 入口 (已完成)
│   ├── config.py            # ✅ 配置管理 (已完成)
│   │
│   ├── models/
│   │   ├── __init__.py      # ✅ 导出所有模型
│   │   └── product.py       # ✅ 数据模型定义 (已完成)
│   │
│   ├── tools/
│   │   ├── __init__.py      # ✅ 工具注册中心
│   │   ├── base.py          # ✅ 工具基类 (需要继承)
│   │   ├── taobao.py        # ⏳ TODO: 淘宝爬虫
│   │   ├── jd.py            # ⏳ TODO: 京东爬虫
│   │   ├── eleme.py         # ⏳ TODO: 饿了么爬虫
│   │   └── meituan.py       # ⏳ TODO: 美团爬虫
│   │
│   ├── agent/
│   │   ├── __init__.py      # ✅ 导出 Agent, Planner, Reflector
│   │   ├── engine.py        # ⏳ TODO: Agent 引擎
│   │   ├── planner.py       # ⏳ TODO: 规划器
│   │   └── reflector.py     # ⏳ TODO: 反思器
│   │
│   ├── services/
│   │   ├── __init__.py      # ✅ 导出服务
│   │   ├── compare.py       # ⏳ TODO: 比价服务
│   │   └── cache.py         # ⏳ TODO: 缓存服务
│   │
│   └── api/
│       ├── __init__.py
│       ├── compare.py       # ✅ API 路由 (已完成，调用 service)
│       └── websocket.py     # ⏳ TODO: WebSocket 推送
│
├── DEV_GUIDE.md             # 📋 本文档
└── requirements.txt         # ✅ 依赖列表
```

---

## 📦 核心数据模型 (已定义，请勿修改)

### models/product.py

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    TAOBAO = "taobao"
    JD = "jd"
    ELEME = "eleme"
    MEITUAN = "meituan"


class ProductType(str, Enum):
    SHOPPING = "shopping"
    FOOD = "food"


class Product(BaseModel):
    """商品信息 - 所有爬虫返回此格式"""
    platform: Platform
    product_id: str
    title: str
    price: float
    original_price: Optional[float] = None
    coupon: Optional[str] = None
    coupon_amount: Optional[float] = None
    image_url: Optional[str] = None
    shop_name: Optional[str] = None
    sales: Optional[int] = None
    rating: Optional[float] = None
    jump_url: str
    location: Optional[str] = None      # 外卖需要
    delivery_fee: Optional[float] = None  # 外卖配送费
    delivery_time: Optional[str] = None   # 预计送达时间
    fetched_at: datetime = datetime.now()

    @property
    def final_price(self) -> float:
        """最终价格 (扣除优惠)"""
        if self.coupon_amount:
            return max(0, self.price - self.coupon_amount)
        return self.price


class CompareRequest(BaseModel):
    """比价请求"""
    query: str
    type: ProductType = ProductType.SHOPPING
    platforms: Optional[list[Platform]] = None  # 不指定则全部平台
    location: Optional[str] = None  # 外卖需要定位


class CompareResult(BaseModel):
    """比价结果"""
    query: str
    type: ProductType
    products: list[Product]
    best_deal: Optional[Product] = None
    summary: Optional[str] = None
    generated_at: datetime = datetime.now()
```

---

## 🔧 工具基类 (已定义，需要继承)

### tools/base.py

```python
from abc import ABC, abstractmethod
from typing import Optional
from app.models import Product, Platform


class BaseTool(ABC):
    """工具基类 - 所有平台爬虫必须继承此类"""
    
    platform: Platform  # 子类必须指定平台
    name: str           # 子类必须指定名称
    description: str    # 子类必须指定描述
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[Product]:
        """搜索商品 - 子类必须实现"""
        pass
    
    @abstractmethod
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """获取商品详情 - 子类必须实现"""
        pass
    
    async def close(self):
        """关闭资源（如浏览器）- 子类可选覆盖"""
        pass
```

---

## 模块 1: 京东爬虫 `app/tools/jd.py` 🔴 P0

### 📍 文件位置
`price-agent/app/tools/jd.py`

### 🎯 任务目标
实现 `JDTool` 类，继承 `BaseTool`，能够搜索京东商品并返回标准化商品列表。

### 📐 完整代码模板

```python
"""
京东商品搜索工具

实现要点：
1. 使用 Playwright 无头浏览器访问京东
2. 搜索页面: https://search.jd.com/Search?keyword={query}
3. 解析商品列表，返回 Product 对象列表
4. 处理反爬策略：随机UA、延迟、代理

依赖：
- playwright (已在 requirements.txt)
- fake-useragent (已在 requirements.txt)
"""
import asyncio
import re
from typing import Optional
from urllib.parse import quote
from datetime import datetime
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser

from app.tools.base import BaseTool
from app.models import Product, Platform
from app.config import settings


class CrawlerException(Exception):
    """爬虫异常"""
    pass


class JDTool(BaseTool):
    """京东商品搜索工具"""
    
    platform = Platform.JD
    name = "京东"
    description = "京东商品搜索和比价"
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def _init_browser(self):
        """
        初始化 Playwright 浏览器
        
        实现要点：
        1. 使用 async_playwright() 启动 chromium
        2. headless=True (无头模式)
        3. 设置 viewport: 1920x1080
        4. 设置随机 User-Agent
        5. 禁用图片加载以提速
        """
        # TODO: 实现浏览器初始化
        raise NotImplementedError("请实现浏览器初始化逻辑")
    
    async def search(self, query: str, **kwargs) -> list[Product]:
        """
        搜索京东商品
        
        实现步骤：
        1. 初始化浏览器 (如果未初始化)
        2. 访问搜索页面: https://search.jd.com/Search?keyword={query}
        3. 滚动页面加载更多商品 (京东需要滚动触发懒加载)
        4. 解析商品列表
        5. 返回 Product 列表 (最多20个)
        """
        # TODO: 实现搜索逻辑
        raise NotImplementedError("请实现搜索逻辑")
    
    async def get_detail(self, product_id: str) -> Optional[Product]:
        """
        获取商品详情 (可选实现)
        
        URL: https://item.jd.com/{product_id}.html
        """
        # TODO: 可选实现，返回 None 即可
        return None
    
    def _parse_price(self, price_text: str) -> float:
        """
        解析价格字符串
        
        输入示例: "¥5999.00", "5999", "5999.00"
        输出: 5999.0
        """
        # TODO: 实现价格解析
        raise NotImplementedError("请实现价格解析")
    
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None


# 导出
__all__ = ["JDTool", "CrawlerException"]
```

### 🔧 详细实现说明

#### 1. `_init_browser()` 实现细节

```python
async def _init_browser(self):
    """
    初始化 Playwright 浏览器
    
    完整实现示例：
    """
    from fake_useragent import UserAgent
    
    ua = UserAgent()
    random_ua = ua.random
    
    playwright = await async_playwright().start()
    self.browser = await playwright.chromium.launch(
        headless=True,
        proxy={"server": settings.crawler_proxy} if settings.crawler_proxy else None
    )
    
    context = await self.browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=random_ua
    )
    
    self.page = await context.new_page()
    
    # 禁用图片加载以提速
    async def route_images(route):
        if route.request.resource_type in ["image", "media", "font"]:
            await route.abort()
        else:
            await route.continue_()
    
    await self.page.route("**/*", route_images)
    
    logger.info(f"京东浏览器初始化完成，UA: {random_ua[:50]}...")
```

#### 2. `search()` 实现细节

```python
async def search(self, query: str, **kwargs) -> list[Product]:
    """
    搜索京东商品
    
    完整实现步骤：
    """
    try:
        # Step 1: 初始化浏览器
        if not self.browser:
            await self._init_browser()
        
        # Step 2: 访问搜索页面
        url = f"https://search.jd.com/Search?keyword={quote(query)}"
        logger.info(f"京东搜索: {url}")
        
        await self.page.goto(url, wait_until="networkidle", timeout=settings.crawler_timeout * 1000)
        
        # Step 3: 滚动加载更多商品 (京东懒加载)
        for _ in range(3):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
        
        # Step 4: 解析商品列表
        products = []
        items = await self.page.query_selector_all("#J_goodsList .gl-item")
        logger.info(f"京东找到 {len(items)} 个商品")
        
        for item in items[:20]:  # 最多20个
            try:
                product = await self._parse_product(item)
                if product and product.price > 0:
                    products.append(product)
            except Exception as e:
                logger.warning(f"解析商品失败: {e}")
                continue
        
        logger.info(f"京东成功解析 {len(products)} 个商品")
        return products
        
    except TimeoutError:
        logger.error("京东搜索超时")
        raise CrawlerException("京东搜索超时")
    except Exception as e:
        logger.error(f"京东搜索失败: {e}")
        raise CrawlerException(f"京东搜索失败: {e}")


async def _parse_product(self, item) -> Optional[Product]:
    """
    解析单个商品元素
    
    选择器说明：
    - data-sku: 商品SKU ID
    - .p-name em: 商品标题
    - .p-price i: 价格
    - .p-shop a: 店铺名称
    - .p-img img: 商品图片
    - .p-img a: 商品链接
    """
    # 提取商品ID
    product_id = await item.get_attribute("data-sku")
    if not product_id:
        return None
    
    # 提取标题
    title_el = await item.query_selector(".p-name em")
    title = await title_el.inner_text() if title_el else ""
    
    # 提取价格
    price_el = await item.query_selector(".p-price i")
    price_text = await price_el.inner_text() if price_el else "0"
    price = self._parse_price(price_text)
    
    # 提取店铺
    shop_el = await item.query_selector(".p-shop a")
    shop_name = await shop_el.inner_text() if shop_el else ""
    
    # 提取图片
    img_el = await item.query_selector(".p-img img")
    image_url = await img_el.get_attribute("src") if img_el