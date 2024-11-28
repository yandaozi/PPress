from app import db

class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    article_count = db.Column(db.Integer, default=0)
    
    def update_article_count(self):
        """更新文章数量"""
        self.article_count = self.articles.count()
        db.session.commit() 