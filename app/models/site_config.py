from ..extensions import db
from app.utils.cache_manager import cache_manager

class SiteConfig(db.Model):
    __tablename__ = 'site_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    
    # 文章URL模式
    ARTICLE_URL_PATTERNS = {
        'default': 'article/{id}',
        'date': '{year}/{month}/{day}/{id}',
        'category': '{category}/{id}',
        'custom': None  # 自定义模式
    }
    
    DEFAULT_ARTICLE_URL_PATTERN = 'article/{id}'  # 修改默认模式
    
    @staticmethod
    def get_config(key, default=None):
        config = SiteConfig.query.filter_by(key=key).first()
        return config.value if config else default 
    
    @staticmethod
    def get_article_url_pattern():
        """获取文章URL模式，使用缓存"""
        def query_pattern():
            config = SiteConfig.query.filter_by(key='article_url_pattern').first()
            return config.value if config else SiteConfig.DEFAULT_ARTICLE_URL_PATTERN
            
        return cache_manager.get(
            'article_url_pattern',
            query_pattern,
            ttl=3600
        )