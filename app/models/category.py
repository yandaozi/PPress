from ..extensions import db
from datetime import datetime
from sqlalchemy import text
from flask import current_app
from .article import Article, article_categories

class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    article_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    use_slug = db.Column(db.Boolean, default=False)
    
    parent = db.relationship('Category', remote_side=[id], backref=db.backref('children', lazy='dynamic'))
    
    # 主分类关系
    primary_articles = db.relationship('Article', 
                                    foreign_keys='Article.category_id',
                                    back_populates='category')
    
    # 多分类关系
    related_articles = db.relationship('Article',
                                    secondary='article_categories',
                                    primaryjoin="Category.id == article_categories.c.category_id",
                                    secondaryjoin="article_categories.c.article_id == Article.id",
                                    back_populates='categories',
                                    cascade="all, delete",
                                    lazy='dynamic')
    
    def update_article_count(self):
        """更新文章计数"""
        try:
            # 使用 UNION 去重计算文章总数
            sql = text("""
                SELECT COUNT(DISTINCT article_id) as total
                FROM (
                    SELECT id as article_id 
                    FROM articles 
                    WHERE category_id = :category_id
                    UNION
                    SELECT article_id
                    FROM article_categories
                    WHERE category_id = :category_id
                ) as combined_articles
            """)
            
            result = db.session.execute(sql, {'category_id': self.id})
            self.article_count = result.scalar() or 0
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating article count for category {self.id}: {str(e)}")
    
    @staticmethod
    def update_all_counts():
        """更新所有分类的文章计数"""
        try:
            # 使用单条 SQL 更新所有分类的计数
            sql = text("""
                UPDATE categories c
                SET article_count = (
                    SELECT COUNT(DISTINCT article_id) 
                    FROM (
                        SELECT id as article_id 
                        FROM articles 
                        WHERE category_id = c.id
                        UNION
                        SELECT article_id
                        FROM article_categories
                        WHERE category_id = c.id
                    ) as combined_articles
                )
            """)
            
            db.session.execute(sql)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating all category counts: {str(e)}")
    
    def get_total_article_count(self):
        """获取包含子分类的总文章数"""
        total = self.primary_articles.count() + self.related_articles.count()
        for child in self.children:
            total += child.get_total_article_count()
        return total
        
    def get_ancestors(self):
        """获取所有祖先分类"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors[::-1]
    
    def get_descendants(self):
        """获取所有子孙分类"""
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
        
    def get_level(self):
        """获取当前分类的层级"""
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level
        
    @staticmethod
    def get_category_tree():
        """获取分类树"""
        def build_tree(parent_id=None):
            categories = Category.query.filter_by(parent_id=parent_id)\
                                    .order_by(Category.sort_order)\
                                    .all()
            tree = []
            for category in categories:
                node = {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'level': category.get_level(),
                    'article_count': category.article_count,
                    'children': build_tree(category.id)
                }
                tree.append(node)
            return tree
            
        return build_tree()