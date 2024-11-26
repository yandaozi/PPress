import random

from app import create_app, db
from app.models.user import User
from app.models.article import Article
from app.models.comment import Comment
from app.models.category import Category
from app.models.tag import Tag
from datetime import datetime

def init_db():
    app = create_app()
    with app.app_context():
        # 删除所有现有数据
        db.drop_all()
        # 创建表
        db.create_all()
        
        # 创建一个管理员用户
        admin = User(
            username='admin',
            email='575732022@qq.com',
            role='admin'
        )
        admin.set_password('123456')
        db.session.add(admin)
        
        # 创建一个测试分类
        category = Category(
            name='测试分类',
            description='这是一个测试分类'
        )
        db.session.add(category)
        
        # 创建一个测试标签
        tag = Tag(name='测试标签')
        db.session.add(tag)
        
        # 提交以获取ID
        db.session.commit()
        
        # 创建一篇测试文章
        article = Article(
            title='Pios-blog测试文章',
            content='这是一篇测试文章的内容。\n\n包含一些测试段落。',
            author_id=admin.id,
            sentiment_score=random.uniform(-1, 1),
            category_id=category.id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            view_count=0
        )
        article.tags.append(tag)
        db.session.add(article)
        
        # 创建一条测试评论
        comment = Comment(
            content='这是一条测试评论',
            article_id=1,
            user_id=admin.id,
            created_at=datetime.now()
        )
        db.session.add(comment)
        
        # 提交所有更改
        db.session.commit()
        
        print('纯净数据库初始化完成!作者QQ：575732022')
        print('管理员账号: admin')
        print('管理员密码: 123456')

if __name__ == '__main__':
    init_db()