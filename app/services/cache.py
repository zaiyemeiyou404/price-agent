"""
缓存服务

TODO: 实现 Redis 缓存
1. 缓存搜索结果（短期，如5分钟）
2. 缓存商品详情
3. 缓存失效机制
"""
import json
import pickle
from typing import Optional, Any
from datetime import timedelta
from loguru import logger

from app.config import settings


class CacheService:
    """缓存服务"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self.redis_client = None
        self.memory_cache = {}  # 内存缓存作为后备
        self.use_redis = False
        
        # 尝试初始化 Redis
        self._init_redis()
    
    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import redis.asyncio as redis
            
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,  # 不自动解码，我们自己序列化
                socket_connect_timeout=2,
                socket_timeout=2
            )
            self.use_redis = True
            logger.info(f"Redis 缓存已启用: {self.redis_url}")
        except Exception as e:
            logger.warning(f"Redis 初始化失败，使用内存缓存: {e}")
            self.use_redis = False
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存
        """
        try:
            if self.use_redis and self.redis_client:
                # 从 Redis 获取
                data = await self.redis_client.get(key)
                if data:
                    try:
                        return pickle.loads(data)
                    except (pickle.PickleError, TypeError):
                        # 尝试 JSON 解码
                        try:
                            return json.loads(data.decode('utf-8'))
                        except:
                            return None
            else:
                # 从内存缓存获取
                if key in self.memory_cache:
                    data, expiry = self.memory_cache[key]
                    if expiry is None or expiry > self._current_timestamp():
                        return data
                    else:
                        # 缓存过期
                        del self.memory_cache[key]
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: timedelta = None):
        """
        设置缓存
        """
        try:
            # 默认 TTL：5分钟
            if ttl is None:
                ttl = timedelta(minutes=5)
            
            seconds = int(ttl.total_seconds())
            
            if self.use_redis and self.redis_client:
                # 存储到 Redis
                try:
                    data = pickle.dumps(value)
                    await self.redis_client.setex(key, seconds, data)
                except (pickle.PickleError, TypeError):
                    # 如果 pickle 失败，尝试 JSON
                    try:
                        data = json.dumps(value).encode('utf-8')
                        await self.redis_client.setex(key, seconds, data)
                    except:
                        pass
            else:
                # 存储到内存缓存
                expiry = None
                if seconds > 0:
                    expiry = self._current_timestamp() + seconds
                self.memory_cache[key] = (value, expiry)
                
                # 简单的内存清理（如果缓存太大）
                if len(self.memory_cache) > 1000:
                    self._clean_memory_cache()
        except Exception as e:
            logger.warning(f"设置缓存失败: {e}")
    
    async def delete(self, key: str):
        """删除缓存"""
        try:
            if self.use_redis and self.redis_client:
                await self.redis_client.delete(key)
            elif key in self.memory_cache:
                del self.memory_cache[key]
        except Exception as e:
            logger.warning(f"删除缓存失败: {e}")
    
    def _current_timestamp(self) -> int:
        """当前时间戳（秒）"""
        import time
        return int(time.time())
    
    def _clean_memory_cache(self):
        """清理过期的内存缓存"""
        current = self._current_timestamp()
        expired_keys = []
        
        for key, (_, expiry) in self.memory_cache.items():
            if expiry is not None and expiry <= current:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        # 如果仍然太大，删除最旧的一半
        if len(self.memory_cache) > 1000:
            # 简单实现：删除前500个
            keys = list(self.memory_cache.keys())[:500]
            for key in keys:
                del self.memory_cache[key]
    
    def make_key(self, query: str, platforms: list[str]) -> str:
        """生成缓存key"""
        platform_str = ':'.join(sorted([p.value if hasattr(p, 'value') else str(p) for p in platforms]))
        # 简化查询字符串（移除特殊字符，限制长度）
        query_simple = ''.join(c for c in query if c.isalnum() or c in ' _-')[:50]
        return f"compare:{query_simple}:{platform_str}"
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if self.use_redis and self.redis_client:
                await self.redis_client.ping()
                return True
            else:
                # 内存缓存总是健康的
                return True
        except Exception as e:
            logger.warning(f"缓存健康检查失败: {e}")
            return False
    
    async def close(self):
        """关闭连接"""
        if self.use_redis and self.redis_client:
            await self.redis_client.close()
