"""
商品数据模型
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    TAOBAO = "taobao"
    JD = "jd"
    ELEME = "eleme"
    MEITUAN = "meituan"
    PDD = "pdd"  # 拼多多


class ProductType(str, Enum):
    SHOPPING = "shopping"
    FOOD = "food"


class Product(BaseModel):
    """商品信息"""
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
    location: Optional[str] = None  # 外卖需要
    delivery_fee: Optional[float] = None  # 外卖配送费
    delivery_time: Optional[str] = None  # 预计送达时间
    fetched_at: datetime = datetime.now()

    @property
    def final_price(self) -> float:
        """最终价格"""
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
