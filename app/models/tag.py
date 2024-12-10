from app import db
from slugify import slugify

class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True)
    article_count = db.Column(db.Integer, default=0)
    use_slug = db.Column(db.Boolean, default=False)
    
    def __init__(self, *args, **kwargs):
        """初始化时自动生成 slug"""
        super().__init__(*args, **kwargs)
        if self.name and not self.slug:
            self.slug = slugify(self.name)
    
    def update_article_count(self):
        """更新文章数量"""
        self.article_count = self.articles.count()
        db.session.commit() 