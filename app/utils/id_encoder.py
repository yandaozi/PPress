import base64
import hashlib
from app.models import SiteConfig
from app.utils.cache_manager import cache_manager
from flask import current_app

class IdEncoder:
    # 添加缓存
    _encoded_cache = {}  # {article_id: encoded_id}
    _decoded_cache = {}  # {encoded_id: article_id}
    
    @classmethod
    def _get_salt_hash(cls):
        """获取缓存的盐值hash"""
        def query_salt_hash():
            salt = SiteConfig.get_config('article_id_salt', 'default_salt')
            return hashlib.sha256(salt.encode()).digest()[:8]
            
        return cache_manager.get(
            'article_id_salt_hash',
            query_salt_hash,
            ttl=3600
        )

    @classmethod
    def encode(cls, id, salt=None, length=None):
        """加密文章ID"""
        try:
            # 先查缓存
            cache_key = f"{id}:{salt}:{length}"
            if cache_key in cls._encoded_cache:
                return cls._encoded_cache[cache_key]
            
            if not length:
                length = int(SiteConfig.get_config('article_id_length', '6'))
            
            # 确保长度在合理范围内
            length = max(6, min(32, length))  # 改为最小6位
            
            # 将ID转换为字节序列
            id_bytes = str(id).encode()
            
            # 获取盐值
            if not salt:
                salt = SiteConfig.get_config('article_id_salt', 'default_salt')
            
            # 组合ID和盐值
            value = f"{id}:{salt}".encode()
            
            # 计算hash
            hash_obj = hashlib.sha256(value)
            hash_bytes = hash_obj.digest()[:6]  # 只取前6字节以提高性能
            
            # Base64编码
            encoded = base64.urlsafe_b64encode(hash_bytes).decode().rstrip('=')
            
            # 如果需要更长的编码，添加ID的编码
            if len(encoded) < length:
                id_encoded = base64.urlsafe_b64encode(id_bytes).decode().rstrip('=')
                encoded = encoded + id_encoded
            
            result = encoded[:length]
            
            # 缓存结果
            cls._encoded_cache[cache_key] = result
            cls._decoded_cache[result] = id
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error encoding article ID: {str(e)}")
            return None

    @classmethod
    def decode(cls, encoded_id):
        """解密文章ID"""
        try:
            # 先查缓存
            if encoded_id in cls._decoded_cache:
                article_id = cls._decoded_cache[encoded_id]
                # 验证文章是否存在
                from app.models import Article
                if Article.query.get(article_id):
                    return article_id
                # 如果文章不存在，清除缓存
                del cls._decoded_cache[encoded_id]
            
            # 从编码中提取ID部分
            id_part = encoded_id[8:] if len(encoded_id) > 8 else ''  # 减少前缀长度
            
            if id_part:
                try:
                    # 尝试从ID部分解码
                    while len(id_part) % 4 != 0:
                        id_part += '='
                    decoded = base64.urlsafe_b64decode(id_part).decode()
                    article_id = int(decoded)
                    
                    # 验证
                    if cls.verify(article_id, encoded_id):
                        cls._decoded_cache[encoded_id] = article_id
                        return article_id
                except:
                    pass
            
            # 使用缓存优化遍历查找
            from app.models import Article
            if not hasattr(cls, '_article_ids'):
                cls._article_ids = set(aid for (aid,) in Article.query.with_entities(Article.id).all())
            
            # 只遍历缓存的文章ID
            for aid in cls._article_ids:
                if cls.verify(aid, encoded_id):
                    cls._decoded_cache[encoded_id] = aid
                    return aid
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error decoding article ID: {str(e)}")
            return None

    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        cls._encoded_cache.clear()
        cls._decoded_cache.clear()
        if hasattr(cls, '_article_ids'):
            delattr(cls, '_article_ids')

    @classmethod
    def verify(cls, id, encoded_id):
        """验证ID与加密ID是否匹配"""
        try:
            encoded = cls.encode(id)
            return encoded[:len(encoded_id)] == encoded_id
        except Exception as e:
            current_app.logger.error(f"Error verifying article ID: {str(e)}")
            return False