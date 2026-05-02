"""
简单的内存缓存层，用于减少数据库查询压力
"""
import time
from typing import Any, Optional, Dict
from threading import Lock

class SimpleCache:
    """线程安全的简单缓存"""
    
    def __init__(self, default_ttl: int = 300):
        """
        Args:
            default_ttl: 默认过期时间（秒），默认 5 分钟
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，过期返回 None"""
        with self._lock:
            if key not in self._cache:
                return None
            value, expire_at = self._cache[key]
            if time.time() > expire_at:
                del self._cache[key]
                return None
            return value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存值"""
        if ttl is None:
            ttl = self.default_ttl
        with self._lock:
            self._cache[key] = (value, time.time() + ttl)
    
    def delete(self, key: str):
        """删除缓存"""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
    
    def invalidate_pattern(self, pattern: str):
        """删除匹配前缀的所有缓存"""
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for k in keys_to_delete:
                del self._cache[k]


# 全局缓存实例
cache = SimpleCache(default_ttl=300)  # 5 分钟默认过期
