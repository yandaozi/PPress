from ..extensions import db
from datetime import datetime
from flask import current_app
from sqlalchemy.orm.attributes import NO_VALUE
from sqlalchemy import event
from sqlalchemy.orm import reconstructor
from sqlalchemy.orm import object_session
from slugify import slugify

# 创建文章-标签关联表
article_tags = db.Table('article_tags',
    db.Column('article_id', db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)

# 创建文章-分类关联表
article_categories = db.Table('article_categories',
    db.Column('article_id', db.Integer, db.ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True)
)

class Article(db.Model):
    __tablename__ = 'articles'
    
    # 文章状态枚举
    STATUS_PUBLIC = 'public'      # 公开
    STATUS_HIDDEN = 'hidden'      # 隐藏
    STATUS_PASSWORD = 'password'  # 密码保护
    STATUS_PRIVATE = 'private'    # 私密
    STATUS_PENDING = 'pending'    # 待审核
    STATUS_DRAFT = 'draft'        # 草稿
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    view_count = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # 新增字段
    status = db.Column(db.Enum(STATUS_PUBLIC, STATUS_HIDDEN, STATUS_PASSWORD, 
                              STATUS_PRIVATE, STATUS_PENDING, STATUS_DRAFT),
                      default=STATUS_PUBLIC, index=True)
    password = db.Column(db.String(128))  # 文章密码
    allow_comment = db.Column(db.Boolean, default=True)  # 是否允许评论
    
    # 主分类关系
    category = db.relationship('Category', 
                             foreign_keys=[category_id],
                             back_populates='primary_articles')
    
    # 多分类关系 - 使用 back_populates
    categories = db.relationship('Category', 
                               secondary='article_categories',
                               primaryjoin="Article.id == article_categories.c.article_id",
                               secondaryjoin="article_categories.c.category_id == Category.id",
                               back_populates='related_articles',  # 对应 Category 的关系名
                               lazy='joined')
    
    tags = db.relationship('Tag', secondary=article_tags, backref=db.backref('articles', lazy=True))
    
    # 添加自定义字段
    fields = db.Column(db.JSON, nullable=True, comment='自定义字段')
    
    # 静态定义表参数
    __table_args__ = (
        db.Index('idx_article_sort', 'created_at', 'view_count'),
    )

    slug = db.Column(db.String(200), nullable=True, unique=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._category_id = self.category_id
    
    @reconstructor
    def init_on_load(self):
        self._category_id = self.category_id

    def is_accessible_by(self, user):
        """检查用户是否有权限访问文章"""
        # 管理员可以访问任何文章
        if hasattr(user, 'role') and user.role == 'admin':
            return True
        
        # 作者可以访问自己的文章
        if hasattr(user, 'id') and self.author_id == user.id:
            return True
        
        # 待审核文章只有作者和管理员可以访问
        if self.status == self.STATUS_PENDING:
            return False
        
        # 公开文章何人可访问
        if self.status == self.STATUS_PUBLIC:
            return True
        
        # 隐藏文章需要知道链接
        if self.status == self.STATUS_HIDDEN:
            return True
        
        # 密码保护的文章需输入密码
        if self.status == self.STATUS_PASSWORD:
            return True
        
        # 私密文章只有作者和管理员可以访问
        if self.status == self.STATUS_PRIVATE:
            return False
        
        # 草稿只有作者和管理员可以访问
        if self.status == self.STATUS_DRAFT:
            return False
        
        return False
    
    def can_comment(self, user):
        """检查用户是否可以评论"""
        if not self.allow_comment:
            return False
            
        if not user:
            return False
            
        if self.status not in [self.STATUS_PUBLIC, self.STATUS_PASSWORD]:
            return False
            
        return True

    @property
    def main_category(self):
        """获取主分类，如果没有则返回第一个多分类"""
        if self.category:
            return self.category
        elif self.categories:
            return self.categories[0] if self.categories else None
        return None

    def get_field(self, key, default=None):
        """获取自定义字段值"""
        if not self.fields:
            return default
        return self.fields.get(key) or default

    def generate_slug(self):
        """生成 slug"""
        if not self.slug and self.title:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            # 检查是否存在相同的 slug
            while Article.query.filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
                
            self.slug = slug

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
            
            # 更新标签数
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
            session = object_session(target)
            if session is None or not session.is_active:
                return
            
            # 更新计数
            if value.article_count is None:
                value.article_count = 0
            value.article_count += 1
            
            session.flush()
            
        except Exception as e:
            current_app.logger.error(f"Error in article_tag_append: {str(e)}")

    @event.listens_for(Article.tags, 'remove')
    def article_tag_remove(target, value, initiator):
        """移除标签时更新计数"""
        try:
            session = object_session(target)
            if session is None or not session.is_active:
                return
            
            # 更新计数
            if value.article_count is not None and value.article_count > 0:
                value.article_count -= 1
            
            session.flush()
            
        except Exception as e:
            current_app.logger.error(f"Error in article_tag_remove: {str(e)}")

    @event.listens_for(Article.tags, 'set')
    def article_tags_set(target, value, oldvalue, initiator):
        """标签集合被替换时更新计数"""
        try:
            session = object_session(target)
            if session is None or not session.is_active:
                return
            
            # 确保目标对象在会话中
            if target not in session:
                session.add(target)
            
            # 减少旧标签的计数
            if oldvalue is not NO_VALUE:
                for tag in oldvalue:
                    if tag not in value:  # 只处理被移除的标签
                        if tag not in session:
                            session.add(tag)
                        if tag.article_count is not None and tag.article_count > 0:
                            tag.article_count -= 1
            
            # 增加新标签的计数
            if value is not None:
                for tag in value:
                    if oldvalue is NO_VALUE or tag not in oldvalue:  # 只处理新增的标签
                        if tag not in session:
                            session.add(tag)
                        if tag.article_count is None:
                            tag.article_count = 0
                        tag.article_count += 1
            
            session.flush()
            
        except Exception as e:
            current_app.logger.error(f"Error in article_tags_set: {str(e)}")

    @event.listens_for(Article, 'before_delete')
    def article_before_delete(mapper, connection, target):
        """文章删除前更新分类和标签计数"""
        try:
            # 使用 connection 而不是 session 执行更新
            if target.category_id:
                connection.execute(
                    Category.__table__.update()
                    .values(article_count=Category.__table__.c.article_count - 1)
                    .where(Category.__table__.c.id == target.category_id)
                )
            
            # 更新标签计数
            for tag in target.tags:
                connection.execute(
                    Tag.__table__.update()
                    .values(article_count=Tag.__table__.c.article_count - 1)
                    .where(Tag.__table__.c.id == tag.id)
                )
            
        except Exception as e:
            current_app.logger.error(f"Error in article_before_delete: {str(e)}")

# 初始化事件监听器
init_article_events()