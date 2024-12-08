from flask import render_template, request, redirect, url_for, current_app
from app.installer import bp
from app.installer.utils import Installer
from app.models import User, Tag, Category, Article, SiteConfig, CommentConfig
from app.extensions import db
from datetime import datetime
import os
import pymysql
import base64
from config.database import MYSQL_CONFIG

@bp.route('/install', methods=['GET', 'POST'])
def install():
    """安装路由"""
    # 读取 Tailwind CSS 内容
    tailwind_path = os.path.join(current_app.static_folder, 'default/vendor/3.4.5')
    try:
        with open(tailwind_path, 'r', encoding='utf-8') as f:
            tailwind_content = f.read()
    except:
        tailwind_content = ''

    if request.method == 'POST':
        try:
            site_name = request.form.get('site_name')
            db_type = request.form.get('db_type')

            # MySQL 配置
            if db_type == 'mysql':
                # 获取表单中的 MySQL 配置
                mysql_config = {
                    'db_type': db_type,
                    'host': request.form.get('mysql_host'),
                    'port': int(request.form.get('mysql_port', 3306)),
                    'database': request.form.get('mysql_database').strip().replace(' ', '_'),
                    'user': request.form.get('mysql_user'),
                    'password': request.form.get('mysql_password'),
                    'charset': 'utf8mb4'
                }
                
                # 验证数据库名称
                if not mysql_config['database'].isalnum() and not '_' in mysql_config['database']:
                    return render_template('install.html', 
                                         error='数据库名称只能包含字母、数字和下划线', 
                                         tailwind_content=tailwind_content)
                
                try:
                    # 连接MySQL并创建数据库
                    conn = pymysql.connect(
                        host=mysql_config['host'],
                        port=mysql_config['port'],
                        user=mysql_config['user'],
                        password=mysql_config['password']
                    )
                    
                    with conn.cursor() as cursor:
                        # 删除数据库如果存在
                        cursor.execute(f"DROP DATABASE IF EXISTS `{mysql_config['database']}`")
                        # 创建新数据库
                        cursor.execute(
                            f"CREATE DATABASE `{mysql_config['database']}` "
                            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                        )
                    conn.close()
                    
                    # 更新数据库配置
                    success, error = Installer.update_db_config(mysql_config)
                    if not success:
                        return render_template('install.html', error=error, tailwind_content=tailwind_content)
                        
                except Exception as e:
                    return render_template('install.html', error=f'MySQL初始化失败: {str(e)}', tailwind_content=tailwind_content)

            # 删除所有表并重新创建
            db.drop_all()
            db.create_all()

            # 开始一个新的事务
            db.session.begin()
            try:
                # 创建管理员账号
                admin = User(
                    username='admin',
                    nickname=f'昵称_admin',
                    email='ponyj@qq.com',
                    role='admin'
                )
                admin.set_password('123456')
                db.session.add(admin)
                db.session.flush()

                # 创建一个标签
                tag = Tag(name='PPress')
                db.session.add(tag)
                db.session.flush()

                # 创建一个分类
                category = Category(
                    name='示例分类',
                    slug='example',
                    description='PPress 示例分类',
                    sort_order=1
                )
                db.session.add(category)
                db.session.flush()

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
                    status='public'
                )
                article.tags.append(tag)
                db.session.add(article)

                # 初始化网站配置
                site_configs = [
                    SiteConfig(key='site_name', value=site_name, description='网站名称'),
                    SiteConfig(key='site_keywords', value='PPress,技术,博客', description='网站关键词'),
                    SiteConfig(key='site_description', value='基于 Flask 的博客系统', description='网站描述'),
                    SiteConfig(key='contact_email', value='ponyj@qq.com', description='联系邮箱'),
                    SiteConfig(key='footer_text', value='© 2024 PPress 版权所有', description='页脚文本'),
                    SiteConfig(key='site_theme', value='default', description='网站主题'),
                    SiteConfig(key='article_url_pattern', value='article/{id}'),
                ]
                db.session.bulk_save_objects(site_configs)

                # 初始化评论配置
                comment_config = CommentConfig(
                    require_audit=True,
                    require_email=True,
                    require_contact=False,
                    allow_guest=True,
                    comments_per_page=10
                )
                db.session.add(comment_config)

                # 提交事务
                db.session.commit()

                # 创建安装锁文件
                with open(os.path.join(current_app.root_path, '..', 'ppress_db.lock'), 'w', encoding='utf-8') as f:
                    f.write(base64.b64decode(
                        'UFByZXNzIC0gRmxhc2sgQ29udGVudCBNYW5hZ2VtZW50IFN5c3RlbQrniYjmnYPmiYDmnIkgKGMpIDIwMjQg6KiA6YGT5a2QCuS9nOiAhVFR77yaNTc1NzMyNTYzCumhueebruWcsOWdgO+8mmh0dHBzOi8vZ2l0ZWUuY29tL2ZvamllL1BQcmVzcw=='
                    ).decode('utf-8'))

                # 清理安装文件
                success, error = Installer.cleanup_installer()
                if not success:
                    return render_template('install.html', error=error, tailwind_content=tailwind_content)

                return redirect(url_for('blog.index'))

            except Exception as e:
                db.session.rollback()
                return render_template('install.html', error=str(e), tailwind_content=tailwind_content)

        except Exception as e:
            return render_template('install.html', error=str(e), tailwind_content=tailwind_content)

    return render_template('install.html', tailwind_content=tailwind_content)