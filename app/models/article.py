from ..extensions import db
from datetime import datetime
from flask import current_app
from sqlalchemy.orm.attributes import NO_VALUE

# 创建文章-标签关联表
article_tags = db.Table('article_tags',
    db.Column('article_id', db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

class Article(db.Model):
    __tablename__ = 'articles'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    sentiment_score = db.Column(db.Float)
    view_count = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    
    tags = db.relationship('Tag', secondary=article_tags, backref=db.backref('articles', lazy=True))
    
    # 静态定义表参数
    __table_args__ = (
        db.Index('idx_article_sort', 'created_at', 'view_count'),
    )

# 将事件监听器移到文件末尾，并使用延迟导入
def init_article_events():
    from .category import Category
    from .tag import Tag
    
    @db.event.listens_for(Article, 'after_insert')
    def article_after_insert(mapper, connection, target):
        """文章创建后更新计数"""
        if target.category_id:
            connection.execute(
                Category.__table__.update().
                values(article_count=Category.__table__.c.article_count + 1).
                where(Category.__table__.c.id == target.category_id)
            )
        
        # 更新标签计数
        for tag in target.tags:
            connection.execute(
                Tag.__table__.update().
                values(article_count=Tag.__table__.c.article_count + 1).
                where(Tag.__table__.c.id == tag.id)
            )

    @db.event.listens_for(Article, 'after_delete')
    def article_after_delete(mapper, connection, target):
        """文章删除后更新计数"""
        if target.category_id:
            connection.execute(
                Category.__table__.update().
                values(article_count=Category.__table__.c.article_count - 1).
                where(Category.__table__.c.id == target.category_id)
            )
        
        # 更新标签计数
        for tag in target.tags:
            connection.execute(
                Tag.__table__.update().
                values(article_count=Tag.__table__.c.article_count - 1).
                where(Tag.__table__.c.id == tag.id)
            )

    @db.event.listens_for(Article.category_id, 'set')
    def article_category_changed(target, value, oldvalue, initiator):
        """文章分类变更时更新计数"""
        # 如果新旧值相同，不需要更新
        if oldvalue == value:
            return
        
        try:
            # 处理旧分类
            if oldvalue not in (None, NO_VALUE):  # 添加 NO_VALUE 检查
                old_category = Category.query.get(oldvalue)
                if old_category:
                    old_category.article_count = Category.query.filter_by(id=oldvalue).first().articles.count()
            
            # 处理新分类
            if value is not None:  # 只在有新分类时更新
                new_category = Category.query.get(value)
                if new_category:
                    new_category.article_count = Category.query.filter_by(id=value).first().articles.count()
            
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating category counts: {str(e)}")

# 初始化事件监听器
init_article_events()