from ..extensions import db
from datetime import datetime
from flask import current_app
from sqlalchemy.orm.attributes import NO_VALUE
from sqlalchemy import event
from sqlalchemy.orm import reconstructor

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
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), index=True)
    
    tags = db.relationship('Tag', secondary=article_tags, backref=db.backref('articles', lazy=True))
    
    # 静态定义表参数
    __table_args__ = (
        db.Index('idx_article_sort', 'created_at', 'view_count'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._category_id = self.category_id
    
    @reconstructor
    def init_on_load(self):
        self._category_id = self.category_id

# 将事件监听器移到文件末尾，并使用延迟导入
def init_article_events():
    from .category import Category
    from .tag import Tag
    
    @event.listens_for(Article, 'after_insert')
    def article_after_insert(mapper, connection, target):
        """文章添加后更新分类和标签计数"""
        try:
            # 更新分类文章数
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
        except Exception as e:
            current_app.logger.error(f"Error in article_after_insert: {str(e)}")

    @event.listens_for(Article, 'after_delete')
    def article_after_delete(mapper, connection, target):
        """文章删除后更新分类和标签计数"""
        try:
            # 更新分类文章数
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
        except Exception as e:
            current_app.logger.error(f"Error in article_after_delete: {str(e)}")

    @event.listens_for(Article.category_id, 'set')
    def article_category_changed(target, value, oldvalue, initiator):
        """文章分类变更时更新计数"""
        if oldvalue == value:
            return
        
        try:
            session = db.session
            
            # 使用 select 查询而不是直接访问关系
            if oldvalue not in (None, NO_VALUE):
                old_count = session.query(db.func.count(Article.id))\
                                  .filter(Article.category_id == oldvalue)\
                                  .scalar()
                session.execute(
                    Category.__table__.update()
                    .values(article_count=old_count)
                    .where(Category.id == oldvalue)
                )
            
            if value is not None:
                new_count = session.query(db.func.count(Article.id))\
                                  .filter(Article.category_id == value)\
                                  .scalar()
                session.execute(
                    Category.__table__.update()
                    .values(article_count=new_count)
                    .where(Category.id == value)
                )
            
        except Exception as e:
            current_app.logger.error(f"Error in article_category_changed: {str(e)}")

    @event.listens_for(Article.tags, 'append')
    def article_tag_append(target, value, initiator):
        """添加标签时更新计数"""
        try:
            # 确保对象在会话中
            session = db.session
            if target not in session:
                session.add(target)
            if value not in session:
                session.add(value)
                
            if value.article_count is None:
                value.article_count = 0
            value.article_count += 1
            
            session.flush()  # 使用 flush 而不是 commit
        except Exception as e:
            current_app.logger.error(f"Error in article_tag_append: {str(e)}")

    @event.listens_for(Article.tags, 'remove')
    def article_tag_remove(target, value, initiator):
        """移除标签时更新计数"""
        try:
            session = db.session
            if target not in session:
                session.add(target)
            if value not in session:
                session.add(value)
                
            if value.article_count is None:
                value.article_count = 0
            value.article_count -= 1
            
            session.flush()  # 使用 flush 而不是 commit
        except Exception as e:
            current_app.logger.error(f"Error in article_tag_remove: {str(e)}")

    @event.listens_for(Article.tags, 'set')
    def article_tags_set(target, value, oldvalue, initiator):
        """文章标签变更时更新计数"""
        try:
            session = db.session
            
            # 如果有旧值，减少旧标签的计数
            if oldvalue is not NO_VALUE:
                for tag in oldvalue:
                    if tag in session and tag.article_count > 0:
                        tag.article_count -= 1
            
            # 增加新标签的计数
            if value is not None:
                for tag in value:
                    if tag in session:
                        if tag.article_count is None:
                            tag.article_count = 0
                        tag.article_count += 1
            
            # 使用 flush 而不是 commit
            session.flush()
            
        except Exception as e:
            current_app.logger.error(f"Error in article_tags_set: {str(e)}")
            session.rollback()

    # 添加删除事件监听器
    @event.listens_for(Article, 'before_delete')
    def article_before_delete(mapper, connection, target):
        """文章删除前清理标签关联"""
        try:
            # 手动删除标签关联
            connection.execute(
                Article.__table__.metadata.tables['article_tags'].delete().where(
                    Article.__table__.metadata.tables['article_tags'].c.article_id == target.id
                )
            )
        except Exception as e:
            current_app.logger.error(f"Error in article_before_delete: {str(e)}")

# 初始化事件监听器
init_article_events()