import base64
import os

from slugify import slugify

from app import create_app, db
from app.models import User, Article, Tag, Category, SiteConfig
from datetime import datetime
import pymysql
from config.database import MYSQL_CONFIG

LOCK_FILE = 'ppress_db.lock'
COPYRIGHT_INFO = base64.b64decode(
    'UFByZXNzIC0gRmxhc2sgQ29udGVudCBNYW5hZ2VtZW50IFN5c3RlbQrniYjmnYPmiYDmnIkgKGMpIDIwMjQg6KiA6YGT5a2QCuS9nOiAhVFR77yaNTc1NzMyNTYzCumhueebruWcsOWdgO+8mmh0dHBzOi8vZ2l0ZWUuY29tL2ZvamllL1BQcmVzcw=='
).decode('utf-8')

def check_db_lock():
    """检查数据库锁"""
    if os.path.exists(LOCK_FILE):
        print("\n检测到数据库锁文件！这是为了防止意外重置数据库的安全机制！")
        print(f"如果确定要重新初始化数据库，请先删除以下文件：{os.path.abspath(LOCK_FILE)}")
        return True
    return False

def create_db_lock():
    """创建数据库锁文件"""
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(COPYRIGHT_INFO)
    print(f"\n已创建数据库锁文件：{os.path.abspath(LOCK_FILE)}")

def update_db_config(db_type):
    """更新数据库配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'database.py')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式替换 DB_TYPE
        import re
        new_content = re.sub(
            r'DB_TYPE\s*=\s*["\'].*["\']',
            f'DB_TYPE = "{db_type}"',
            content
        )
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        print(f"\n数据库配置已更新：DB_TYPE = {db_type}")
        
    except Exception as e:
        print(f"\n更新数据库配置失败：{str(e)}")

def init_db(db_type='mysql'):
    """初始化数据库"""
    # 检查数据库锁
    if check_db_lock():
        return

    if db_type == 'mysql':
        # 使用配置文件中的连接信息
        conn = pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password']
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute('DROP DATABASE IF EXISTS ' + MYSQL_CONFIG['database'])
                cursor.execute(
                    f"CREATE DATABASE {MYSQL_CONFIG['database']} "
                    'CHARACTER SET utf8mb4 '
                    'COLLATE utf8mb4_unicode_ci'
                )
        finally:
            conn.close()

    # 创建应用实例
    app = create_app(db_type=db_type,init_components=False)

    with app.app_context():
        print(f"\n开始初始化纯净数据到 {db_type} 数据库...")
        db.drop_all()
        db.create_all()
        
        # 初始化网站配置
        default_configs = [
            {'key': 'site_name', 'value': 'PPress', 'description': '网站名称'},
            {'key': 'site_keywords', 'value': 'PPress,技术,博客,Python,Web开发', 'description': '网站关键词'},
            {'key': 'site_description', 'value': '分享技术知识和经验', 'description': '网站描述'},
            {'key': 'contact_email', 'value': 'ponyj@qq.com', 'description': '联系邮箱'},
            {'key': 'icp_number', 'value': '', 'description': 'ICP备案号'},
            {'key': 'footer_text', 'value': '© 2024 PPress 版权所有', 'description': '页脚文本'},
            {'key': 'site_theme', 'value': 'default', 'description': '网站主题'},
        ]
        for config in default_configs:
            db.session.add(SiteConfig(**config))
        
        # 创建管理员用户
        admin = User(
            username='admin',
            nickname=f'昵称_admin',
            email='ponyj@qq.com',
            role='admin'
        )
        admin.set_password('123456')
        db.session.add(admin)
        
        # 创建一个标签
        tag = Tag(name='PPress')
        db.session.add(tag)
        
        # 创建一个分类
        category = Category(
            name='示例分类',
            description='PPress 示例分类'
        )
        category = Category(
            name='示例分类',
            slug=slugify('示例分类'),  # 添加 slug
            description='PPress 示例分类',
            sort_order=1  # 添加排序
        )

        db.session.add(category)
        
        # 提交以获取ID
        db.session.commit()
        
        # 创建一篇示例文章
        article = Article(
            title='欢迎使用 PPress',
            content='''<p>欢迎使用 PPress 博客系统！&nbsp;PPress 是一个基于 Flask 的轻量级博客系统，由言道子(QQ:575732563)开发。</p>
<p>主要特点： 简洁优雅的界面设计、支持插件扩展、支持主题切换、完善的后台管理&nbsp;</p>
<p>项目地址：<a href="https://gitee.com/fojie/PPress">https://gitee.com/fojie/PPress </a></p>
<p>开始使用：</p>
<p>1. 使用管理员账号登录(admin/123456)</p>
<p>2. 在后台进行相关配置</p>
<p>3. 开始创作你的第一篇文章 如有问题或建议，欢迎联系作者！</p>''',
            author_id=admin.id,
            category_id=category.id,
            created_at=datetime.now(),
            view_count=0,
        )
        article.tags.append(tag)
        db.session.add(article)
        
        # 最终提交
        db.session.commit()
        
        print("纯净数据库初始化完成！作者QQ：575732563")
        print("管理员账号：")
        print("用户名：admin")
        print("密码：123456")

        # 创建数据库锁文件
        create_db_lock()
        
        # 更新数据库配置
        update_db_config(db_type)

def get_db_type():
    """交互式获取数据库类型"""
    while True:
        choice = input("\n如果选mysql请提前在config/database.py中，把MYSQL_CONFIG配置好\n请选择数据库类型 [1/2]:\n1. SQLite (默认)\n2. MySQL\n请输入(直接回车使用SQLite，请输入1或者2): ").strip()

        if choice == '':
            print("\n已选择: SQLite")
            return 'sqlite'
        elif choice == '1':
            print("\n已选择: SQLite")
            return 'sqlite'
        elif choice == '2':
            print("\n已选择: MySQL")
            return 'mysql'
        else:
            print("\n输入无效,请重新选择")

if __name__ == '__main__':
    db_type = get_db_type()
    init_db(db_type)