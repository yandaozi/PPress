from functools import lru_cache
from collections import OrderedDict
import threading

class CacheManager:
    """通用双层缓存管理器"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        self._cache = OrderedDict()
        self._capacity = 10000
    
    @lru_cache(maxsize=1000)
    def get(self, key, query_func):
        """通用一级缓存"""
        return self._get_or_set(key, query_func)
    
    def _get_or_set(self, key, query_func):
        """二级缓存:LRU"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            
            value = query_func()
            
            if len(self._cache) >= self._capacity:
                self._cache.popitem(last=False)
            
            self._cache[key] = value
            return value
    
    def delete(self, key):
        """删除缓存，支持通配符"""
        with self._lock:
            if '*' in key:
                # 通配符匹配删除
                pattern = key.replace('*', '')
                keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                for k in keys_to_delete:
                    self._cache.pop(k, None)
            else:
                # 精确匹配删除
                self._cache.pop(key, None)
            # 清除lru_cache
            self.get.cache_clear()

cache_manager = CacheManager() 