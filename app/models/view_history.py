from ..extensions import db
from datetime import datetime

class ViewHistory(db.Model):
    __tablename__ = 'view_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'))
    viewed_at = db.Column(db.DateTime, default=datetime.now)
    
    article = db.relationship('Article', backref=db.backref('views', lazy=True, cascade='all, delete'))