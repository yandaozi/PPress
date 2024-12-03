from app import db
from datetime import datetime
import json

class CustomPage(db.Model):
    __tablename__ = 'custom_pages'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, comment='页面标识')
    title = db.Column(db.String(200), nullable=False, comment='页面标题')
    template = db.Column(db.String(200), nullable=False, comment='模板文件路径')
    route = db.Column(db.String(200), nullable=False, comment='路由规则')
    content = db.Column(db.Text, nullable=True, comment='页面内容')
    fields = db.Column(db.JSON, nullable=True, comment='自定义字段')
    require_login = db.Column(db.Boolean, default=False, comment='是否需要登录')
    enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_content(self, content_dict):
        """设置页面内容"""
        self.content = content_dict
        
    def get_content(self, key=None, default=None):
        """获取页面内容"""
        if not self.content:
            return default if key else {}
        return self.content.get(key, default) if key else self.content
    
    def get_field(self, key, default=None):
        """获取自定义字段值"""
        if not self.fields:
            return default
        return self.fields.get(key, default)
    
    def __repr__(self):
        return f'<CustomPage {self.key}>' 