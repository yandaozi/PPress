from ..extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from flask import url_for
from app.utils.gravatar import Gravatar

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('idx_user_username_role', 'username', 'role'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    nickname = db.Column(db.String(50))
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    avatar = db.Column(db.String(255), default='/static/image/default_avatar.png')
    role = db.Column(db.Enum('user', 'admin'), default='user')
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, default=datetime.now)
    
    articles = db.relationship('Article', 
                             backref=db.backref('author', lazy='select'),
                             lazy='select')
    comments = db.relationship('Comment', 
                             back_populates='user',
                             lazy='dynamic')
    view_history = db.relationship('ViewHistory',
                                 backref=db.backref('user', lazy='select'),
                                 cascade='all, delete-orphan',
                                 lazy='select')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password) 
    
    @classmethod
    def get_by_username(cls, username):
        """使用缓存管理器查询用户"""
        from app.utils.cache_manager import cache_manager
        return cache_manager.get(
            f'user:username:{username}',
            lambda: cls.query.filter_by(username=username).first()
        )
    
    @classmethod
    def get_by_email(cls, email):
        """使用缓存管理器查询邮箱"""
        from app.utils.cache_manager import cache_manager
        return cache_manager.get(
            f'user:email:{email}',
            lambda: cls.query.filter_by(email=email).first()
        )


