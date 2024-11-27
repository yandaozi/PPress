import random

from app import create_app, db
from app.models import User, Article, Tag, Comment, ViewHistory, Category, SiteConfig
from datetime import datetime

def init_db():
    app = create_app()
    with app.app_context():
        print("开始初始化数据库...")
        # 删除所有现有数据
        db.drop_all()
        # 创建表
        print("创建新表...")
        db.create_all()
        
        # 初始化网站配置
        default_configs = [
            {'key': 'site_name', 'value': 'PPress', 'description': '网站名称'},
            {'key': 'site_keywords', 'value': 'PPress,技术,博客,Python,Web开发', 'description': '网站关键词'},
            {'key': 'site_description', 'value': '分享技术知识和经验', 'description': '网站描述'},
            {'key': 'contact_email', 'value': '575732022@qq.com', 'description': '联系邮箱'},
            {'key': 'icp_number', 'value': '', 'description': 'ICP备案号'},
            {'key': 'footer_text', 'value': '© 2024 PPress 版权所有', 'description': '页脚文本'},
            {'key': 'site_theme', 'value': 'default', 'description': '网站主题'},
        ]
        for config in default_configs:
            db.session.add(SiteConfig(**config))
        db.session.commit()
        
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
            title='PPress测试文章',
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