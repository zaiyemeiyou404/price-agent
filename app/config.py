"""
配置管理
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 大模型配置
    llm_provider: str = "glm5"
    glm5_api_key: Optional[str] = None
    glm5_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # 爬虫配置
    crawler_timeout: int = 30
    crawler_delay: int = 2
    crawler_proxy: Optional[str] = None
    crawler_headless: bool = True  # 无头模式
    crawler_max_retries: int = 3  # 最大重试次数
    crawler_cookies_dir: str = str(BASE_DIR / "cookies")  # Cookie存储目录
    
    # 平台Cookie
    taobao_cookie: Optional[str] = None
    
    # 美团定位
    meituan_lat: float = 39.9042
    meituan_lng: float = 116.4074
    
    # 运行模式配置（固定为纯爬虫）
    api_mode: bool = False  # 固定禁用API，仅使用爬虫
    taobao_only_mode: bool = True  # True: 仅启用淘宝平台（稳定模式）
    
settings = Settings()
# 强制纯爬虫模式，忽略任何环境变量中的 api_mode 配置
settings.api_mode = False
