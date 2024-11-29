from ..extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    avatar = db.Column(db.String(255), default='/static/default_avatar.png')
    role = db.Column(db.Enum('user', 'admin'), default='user')
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    articles = db.relationship('Article', 
                             backref=db.backref('author', lazy=True),
                             lazy=True)
    comments = db.relationship('Comment',
                             backref=db.backref('user', lazy=True),
                             lazy=True)
    view_history = db.relationship('ViewHistory',
                                 backref=db.backref('user', lazy=True),
                                 cascade='all, delete-orphan',
                                 lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password) 