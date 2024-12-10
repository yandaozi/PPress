from ..extensions import db
from app.utils.cache_manager import cache_manager
import secrets

class SiteConfig(db.Model):
    __tablename__ = 'site_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    
    DEFAULT_ARTICLE_URL_PATTERN = 'article/{id}'
    
    # 默认网站配置
    DEFAULT_CONFIGS = [
        {'key': 'site_name', 'value': 'PPress', 'description': '网站名称'},
        {'key': 'site_keywords', 'value': 'PPress,技术,博客', 'description': '网站关键词'},
        {'key': 'site_description', 'value': '分享技术知识和经验', 'description': '网站描述'},
        {'key': 'contact_email', 'value': 'ponyj@qq.com', 'description': '联系邮箱'},
        {'key': 'icp_number', 'value': '', 'description': 'ICP备案号'},
        {'key': 'footer_text', 'value': '© 2024 PPress 版权所有', 'description': '页脚文本'},
        {'key': 'site_theme', 'value': 'default', 'description': '网站主题'},
    ]
    
    # API相关的默认配置
    DEFAULT_API_CONFIGS = {
        'enable_api': {
            'value': 'false',
            'description': '是否启用API接口'
        },
        'api_token_required': {
            'value': 'true', 
            'description': '是否需要Token验证'
        },
        'api_token': {
            'value': '',  # 初始为空,会在初始化时生成
            'description': 'API访问令牌'
        },
        'api_rate_limit': {
            'value': '60',
            'description': 'API请求频率限制(次/分钟)'
        }
    }

    @classmethod
    def init_default_configs(cls, custom_configs=None):
        """初始化默认配置
        Args:
            custom_configs (dict): 自定义配置,用于覆盖默认配置
                例如: {'site_name': 'My Blog', 'site_description': 'My blog description'}
        """
        from app import db
        
        # 合并所有默认配置
        all_configs = cls.DEFAULT_CONFIGS.copy()
        
        # 如果有自定义配置,覆盖默认值
        if custom_configs:
            for config in all_configs:
                if config['key'] in custom_configs:
                    config['value'] = custom_configs[config['key']]
        
        # 添加API配置
        for key, config in cls.DEFAULT_API_CONFIGS.items():
            all_configs.append({
                'key': key,
                'value': config['value'],
                'description': config['description']
            })
            
        # 生成API Token
        api_token = secrets.token_urlsafe(32)
        for config in all_configs:
            if config['key'] == 'api_token':
                config['value'] = api_token
                break
        
        # 批量添加配置
        for config in all_configs:
            if not cls.query.filter_by(key=config['key']).first():
                db.session.add(cls(**config))
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

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