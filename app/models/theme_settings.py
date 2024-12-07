from ..extensions import db
from ..utils.cache_manager import cache_manager

class ThemeSettings(db.Model):
    """主题设置模型"""
    __tablename__ = 'theme_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    theme = db.Column(db.String(50), nullable=False)  # 主题标识
    settings = db.Column(db.JSON)  # 主题设置JSON
    
    @staticmethod
    def get_settings(theme_id):
        """获取主题设置(带缓存)"""
        cache_key = f'theme_settings:{theme_id}'
        settings = cache_manager.get(cache_key)
        
        if settings is None:
            settings = ThemeSettings.query.filter_by(theme=theme_id).first()
            settings = settings.settings if settings else {}
            cache_manager.set(cache_key, settings)
            
        return settings
        
    @staticmethod
    def save_settings(theme_id, settings_data):
        """保存主题设置"""
        settings = ThemeSettings.query.filter_by(theme=theme_id).first()
        if not settings:
            settings = ThemeSettings(theme=theme_id)
        settings.settings = settings_data
        db.session.add(settings)
        db.session.commit()
        
        # 清除缓存
        cache_manager.delete(f'theme_settings:{theme_id}') 