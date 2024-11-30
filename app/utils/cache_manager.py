from collections import OrderedDict
from time import time
from threading import Lock
import threading
from flask import current_app
from app import db
from sqlalchemy.orm.session import make_transient
from sqlalchemy import inspect

class CacheManager:
    """增强版缓存管理器"""
    def __init__(self, max_size=1000, default_ttl=3600):
        self._cache = OrderedDict()
        self._expires = {}
        self._hits = 0
        self._misses = 0
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = Lock()
    
    def get(self, key, default_factory=None, ttl=None):
        """获取缓存"""
        try:
            # 检查是否过期
            if key in self._cache and self._is_expired(key):
                with self._lock:
                    self._cache.pop(key, None)
                    self._expires.pop(key, None)
                    self._misses += 1

            # 缓存命中
            if key in self._cache:
                self._hits += 1
                return self._cache[key]
            
            # 缓存未命中
            self._misses += 1
            if default_factory is not None:
                with db.session.no_autoflush:
                    value = default_factory()
                    self.set(key, value, ttl)
                    return value
            return None
            
        except Exception as e:
            current_app.logger.error(f"Cache get error: {str(e)}")
            # 出错时直接执行原始查询
            if default_factory is not None:
                with db.session.no_autoflush:
                    return default_factory()
            return None

    def set(self, key, value, ttl=None):
        """设置缓存"""
        try:
            with self._lock:
                # LRU: 如果达到最大大小，删除最早的项
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                
                self._cache[key] = value
                if ttl is not None:
                    self._expires[key] = time() + ttl
                elif self._default_ttl:
                    self._expires[key] = time() + self._default_ttl
                return value
        except Exception as e:
            current_app.logger.error(f"Cache set error: {str(e)}")
            return value

    def delete(self, key):
        """删除缓存"""
        try:
            with self._lock:
                # 支持通配符删除
                if '*' in key:
                    pattern = key.replace('*', '')
                    keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                    for k in keys_to_delete:
                        self._cache.pop(k, None)
                        self._expires.pop(k, None)
                else:
                    self._cache.pop(key, None)
                    self._expires.pop(key, None)
        except Exception as e:
            current_app.logger.error(f"Cache delete error: {str(e)}")

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._expires.clear()
            self._hits = 0
            self._misses = 0

    def _is_expired(self, key):
        """检查是否过期"""
        return key in self._expires and time() > self._expires[key]

    def warmup(self, keys):
        """缓存预热"""
        for key, factory in keys.items():
            try:
                if key not in self._cache:
                    self.set(key, factory())
            except Exception as e:
                current_app.logger.error(f"Cache warmup error for {key}: {str(e)}")

    @property
    def stats(self):
        """获取缓存统计信息"""
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{(self._hits / (self._hits + self._misses) * 100):.1f}%" if self._hits + self._misses > 0 else "0%"
        }

# 单例实例
cache_manager = CacheManager() 