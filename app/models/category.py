from ..extensions import db

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    article_count = db.Column(db.Integer, default=0)
    articles = db.relationship('Article', backref='category', lazy='dynamic')
    
    def update_article_count(self):
        """手动更新文章数量"""
        self.article_count = self.articles.count()
        db.session.commit() 