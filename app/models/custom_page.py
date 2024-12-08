from app import db
from datetime import datetime

class CustomPage(db.Model):
    __tablename__ = 'custom_pages'
    
    # 状态常量定义
    STATUS_PUBLIC = 1    # 公开
    STATUS_PRIVATE = 2   # 隐藏
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, comment='页面标识')
    title = db.Column(db.String(200), nullable=False, comment='页面标题')
    template = db.Column(db.String(200), nullable=False, comment='模板文件路径')
    route = db.Column(db.String(200), nullable=False, comment='路由规则')
    content = db.Column(db.Text, nullable=True, comment='页面内容')
    fields = db.Column(db.JSON, nullable=True, comment='自定义字段')
    require_login = db.Column(db.Boolean, default=False, comment='是否需要登录')
    enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    # 修改状态字段为整数类型
    status = db.Column(db.Integer, default=STATUS_PUBLIC, comment='状态:1=公开,2=隐藏')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 新增评论相关字段
    allow_comment = db.Column(db.Boolean, default=True, comment='是否允许评论')
    
    @property
    def status_text(self):
        """获取状态文本"""
        return {
            self.STATUS_PUBLIC: '公开',
            self.STATUS_PRIVATE: '隐藏'
        }.get(self.status, '未知')
    
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