import base64
import hashlib
from app.models import SiteConfig

class IdEncoder:
    @staticmethod
    def encode(id, salt=None, length=None):
        """加密文章ID
        :param id: 文章ID
        :param salt: 加密盐值
        :param length: 生成的加密ID长度
        """
        if not salt:
            salt = SiteConfig.get_config('article_id_salt', 'default_salt')
            
        if not length:
            length = int(SiteConfig.get_config('article_id_length', '8'))
            
        # 将ID和盐值组合
        value = f"{id}:{salt}"
        # 使用 SHA256 生成 hash
        hash_obj = hashlib.sha256(value.encode())
        # 取前 length*2 个字符（因为每个字节需要2个字符表示）
        hash_str = hash_obj.hexdigest()[:length*2]
        # Base64 编码并移除填充字符
        encoded = base64.urlsafe_b64encode(bytes.fromhex(hash_str)).decode().rstrip('=')
        # 确保长度符合要求
        return encoded[:length]
    
    @staticmethod
    def decode(encoded_id):
        """解密文章ID
        :param encoded_id: 加密后的ID
        :return: 原始ID或None
        """
        # 从数据库中获取所有文章ID
        from app.models import Article
        from app import db
        
        # 获取盐值
        salt = SiteConfig.get_config('article_id_salt', 'default_salt')
        
        # 获取所有文章ID
        article_ids = db.session.query(Article.id).all()
        
        # 尝试匹配
        for (id,) in article_ids:
            if IdEncoder.encode(id, salt) == encoded_id:
                return id
        return None 