import base64
import os
from app import create_app, db
from app.models import User, Article, Tag, Comment, ViewHistory, Category, SiteConfig, Plugin, File
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random
import pymysql
from config.database import MYSQL_CONFIG
from slugify import slugify

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

def create_db_lock():
    """创建数据库锁文件"""
    with open(LOCK_FILE, 'w', encoding='utf-8') as f:
        f.write(COPYRIGHT_INFO)
    print(f"\n已创建数据库锁文件：{os.path.abspath(LOCK_FILE)}")

def init_db(db_type='mysql', site_name='PPress'):
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
        print(f"\n开始初始化100条测试数据到 {db_type} 数据库...")
        # 清空所有表
        db.drop_all()
        print("创建新表...")
        db.create_all()
        db.session.commit()

        # 初始化网站配置,传入自定义网站名称
        custom_configs = {
            'site_name': site_name,
            'footer_text': f'© 2024 {site_name} 版权所有'
        }
        SiteConfig.init_default_configs(custom_configs)

        # 创建管理员用户
        admin = User(
            username='admin',
            nickname='昵称_admin',
            email='575732022@qq.com',
            role='admin'
        )
        admin.set_password('123456')
        db.session.add(admin)

        # 创建普通用户
        users = []
        for i in range(25):
            user = User(
                username=f'user{i}',
                nickname=f'昵称_user{i}',
                email=f'user{i}@example.com',
                password_hash=generate_password_hash(f'user{i}123'),
                role='user'
            )
            users.append(user)
            db.session.add(user)

        # 创建标签
        tags = []
        tag_names = ['Python','Java','C++','数据结构','算法','人工智能','机器学习','深度学习','数据分析','数据挖掘','大数据','云计算','区块链','网络安全','物联网','移动开发','Android','iOS','游戏开发','图形图像','音视频处理','数据库设计','SQL','NoSQL','MongoDB','Redis','Web框架','Django','Flask','Spring','Hibernate','前端框架','Vue.js','React','Angular','HTML5','CSS3','JavaScript','TypeScript','Node.js','后端开发','服务器','运维','Linux','Unix','Windows开发','软件测试','自动化测试','性能测试','单元测试','集成测试','系统测试','UI设计','UX设计','交互设计','产品设计','项目管理','敏捷开发','瀑布模型','迭代开发','版本控制','Git','SVN','代码规范','编程思想','设计模式','软件工程','计算机网络','TCP/IP','HTTP','HTTPS','网络协议','路由交换','无线网络','云计算平台','AWS','Azure','阿里云','腾讯云','虚拟化技术','Docker','Kubernetes','微服务架构','消息队列','Kafka','RabbitMQ','缓存技术','数据存储','文件系统','分布式系统','一致性算法','分布式数据库','数据仓库','数据湖','数据可视化','Echarts','Tableau','PowerBI','商业智能','人工智能算法','神经网络','卷积神经网络','循环神经网络','自然语言处理','语音识别','图像识别','计算机视觉','机器人技术','智能硬件','传感器技术','嵌入式系统','电子电路','单片机','PLC编程','工业自动化','增材制造','3D打印','虚拟现实','增强现实','混合现实','元宇宙','数字孪生','教育科技','在线教育','教育信息化','智慧教育','金融科技','数字货币','区块链金融','支付系统','风控系统','保险科技','医疗科技','医疗信息化','电子病历','远程医疗','医学影像','生物识别','基因技术','精准医疗','农业科技','智慧农业','农业物联网','农业大数据','无人机植保','智能家居','智能家电','智能照明','智能安防','智能门锁','智能窗帘','智能音箱','智能手表','智能手环','智能交通','自动驾驶','车联网','智能物流','物流信息化','供应链管理','电商平台','电商运营','电商营销','跨境电商','社交网络','社交媒体','短视频','直播','内容创作','数字营销','搜索引擎优化','搜索引擎营销','社交媒体营销','电子邮件营销','内容管理系统','WordPress','Drupal','Joomla']
        for name in tag_names:
            tag = Tag(name=name)
            tags.append(tag)
            db.session.add(tag)

        # 创建分类
        categories = []
        default_categories = [
            {'name': '技术教程', 'description': '各类技术教程和指南'},
            {'name': '经验分享', 'description': '个人经验和心得分享'},
            {'name': '项目实战', 'description': '实际项目开发经验'},
            {'name': '技术资讯', 'description': '行业新闻和技术动态'},
            {'name': '其他', 'description': '其他类型的文章'},
        ]
        for category_data in default_categories:
            # 生成 slug
            slug = slugify(category_data['name'])
            category = Category(
                name=category_data['name'],
                slug=slug,  # 添加 slug
                description=category_data['description'],
                sort_order=len(categories)  # 添加排序
            )
            categories.append(category)
            db.session.add(category)

        # 添加一些子分类作为示例
        child_categories = [
            {'name': 'Python教程', 'parent': '技术教程'},
            {'name': 'Flask教程', 'parent': 'Python教程'},
            {'name': 'Django教程', 'parent': 'Python教程'},
            {'name': '前端开发', 'parent': '技术教程'},
            {'name': 'Vue教程', 'parent': '前端开发'},
            {'name': 'React教程', 'parent': '前端开发'},
        ]

        # 创建子分类
        for child_data in child_categories:
            parent = next((c for c in categories if c.name == child_data['parent']), None)
            if parent:
                child = Category(
                    name=child_data['name'],
                    slug=slugify(child_data['name']),
                    parent_id=parent.id,
                    sort_order=len(categories)
                )
                categories.append(child)
                db.session.add(child)

        # 提交以获取分类ID
        db.session.commit()

        # 初始化插件表
        default_plugins = [

        ]

        for plugin_info in default_plugins:
            plugin = Plugin(
                name=plugin_info['name'],
                directory=plugin_info['directory'],
                description=plugin_info['description'],
                version=plugin_info['version'],
                author=plugin_info['author'],
                author_url=plugin_info['author_url'],
                enabled=plugin_info['enabled'],
                config=plugin_info['config']
            )
            db.session.add(plugin)

        # 提交以获取ID
        db.session.commit()

        # 文章内容模板
        article_contents = [
            '''PPress,FlaksIOS风Blog系统，作者QQ：575732022.Flask是一个轻量级的Python Web框架，它提供了基础的核心功能，同时具有很强的可扩展性。本文将介绍Flask的主要特点和基本使用方法。

Flask的设计理念是"微框架"，这意味着它的核心很简单，但可以通过各种扩展来增加功能。它不会强制你使用特定的项目布局或依赖特定的数据库。

Flask的主要优点包括：
1. 轻量级，易于学习
2. 灵活性强，可以根据需求选择组件
3. 详细的文档和活跃的社区
4. 适合小型到中型项目

如果你正在选择Python Web框架，Flask是一个值得考虑的选择。''',

            '''数据库设计是Web开发中的重要环节，好的数据库设计可以提高系统性能和可维护性。

在设计数据库时，我们需要注意以下几点：
1. 合理的表结构设计
2. 适当的索引使用
3. 关系的正确处理
4. 数据的完整性约束

同时，我们还需要考虑数据库的性能优化，包括查询优化、索引优化等方面。''',

            '''前端开发技术日新月异，作为开发者需要不断学习和更新知识。目前主流的前端技术包括：

1. 现代JavaScript框架（React、Vue、Angular）
2. CSS预处理器（Sass、Less）
3. 构建工具（Webpack、Vite）
4. 响应式设计
5. 性能优化

前端开发不仅要注重功能实现，还要关注用户体验、页面性能和代码质量。'''
        ]

        # 创建文章
        articles = []
        for i in range(300):
            # 随机选择主分类和额外分类
            main_category = random.choice(categories)
            extra_categories = random.sample(
                [c for c in categories if c != main_category],
                k=random.randint(0, 2)  # 随机选择0-2个额外分类
            )
            
            article = Article(
                title=f'技术探讨：{random.choice(["Web开发实践", "数据库优化", "前端技术", "后端架构", "系统设计"])} {i+1}',
                content=random.choice(article_contents),
                author_id=random.choice(users + [admin]).id,
                category_id=main_category.id,  # 设置主分类
                created_at=datetime.now() - timedelta(days=random.randint(0, 30)),
                view_count=random.randint(0, 100),
            )
            
            # 设置多分类关系（包括主分类）
            article.categories = [main_category] + extra_categories
            
            # 随机添加2-4个标签
            article.tags = random.sample(tags, random.randint(2, 4))
            
            articles.append(article)
            db.session.add(article)

        # 提交以获取文章ID
        db.session.commit()

        # 创建评论
        for _ in range(300):
            comment = Comment(
                content=random.choice([
                    '这篇文章讲解得很清楚，对我帮助很大！',
                    '这篇文章太溜了，技术大师！',
                    '文章内容很实用，期待更多类似的分享。',
                    '写得不错，把复杂的概解释得很通俗易懂。',
                    '这个观点很有意思，值得深入探讨。',
                    '感谢分享，学到了很多新知识。'
                ]),
                article_id=random.choice(articles).id,
                user_id=random.choice(users + [admin]).id,
                created_at=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            db.session.add(comment)

        # 创建浏览历史
        for _ in range(500):
            view = ViewHistory(
                user_id=random.choice(users + [admin]).id,
                article_id=random.choice(articles).id,
                viewed_at=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            db.session.add(view)

        # 最终提交
        db.session.commit()

        print("测试数据库初始化完成！作者QQ：575732022")
        print("\n测试账号：")
        print("管理员 - 用户名：admin，密码：123456")
        print("普通用户 - 用户名：user0-4，密码：user0-4123")
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