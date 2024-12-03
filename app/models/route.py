from ..extensions import db
from datetime import datetime

class Route(db.Model):
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(191), unique=True, nullable=False)  # 缩短长度到191
    original_endpoint = db.Column(db.String(255), nullable=False)  # 原始端点
    description = db.Column(db.String(255))  # 描述
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)