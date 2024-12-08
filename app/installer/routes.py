from flask import render_template, request, redirect, url_for, current_app
from . import bp
from .utils import Installer
from app import db
from app.models import User, Article, Tag, Category, SiteConfig, CommentConfig
from werkzeug.security import generate_password_hash
import pymysql
import os
from datetime import datetime

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
            # 只获取网站名称和数据库类型
            site_name = request.form.get('site_name')
            db_type = request.form.get('db_type')
            
            # MySQL 配置
            if db_type == 'mysql':
                mysql_config = {
                    'db_type': db_type,
                    'mysql_host': request.form.get('mysql_host'),
                    'mysql_port': int(request.form.get('mysql_port', 3306)),
                    'mysql_database': request.form.get('mysql_database'),
                    'mysql_user': request.form.get('mysql_user'),
                    'mysql_password': request.form.get('mysql_password')
                }
                
                # 测试连接并创建数据库
                try:
                    conn = pymysql.connect(
                        host=mysql_config['mysql_host'],
                        port=mysql_config['mysql_port'],
                        user=mysql_config['mysql_user'],
                        password=mysql_config['mysql_password']
                    )
                    with conn.cursor() as cursor:
                        cursor.execute('DROP DATABASE IF EXISTS ' + mysql_config['mysql_database'])
                        cursor.execute(
                            f"CREATE DATABASE {mysql_config['mysql_database']} "
                            'CHARACTER SET utf8mb4 '
                            'COLLATE utf8mb4_unicode_ci'
                        )
                    conn.close()
                except Exception as e:
                    return render_template('install.html', error=f'MySQL连接失败: {str(e)}', tailwind_content=tailwind_content)
                
                # 更新数据库配置
                success, error = Installer.update_db_config(mysql_config)
                if not success:
                    return render_template('install.html', error=error, tailwind_content=tailwind_content)

            # 删除所有表并重新创建
            db.drop_all()
            db.create_all()
            
            # 创建管理员账号
            admin = User(
                username='admin',
                email='ponyj@qq.com',
                role='admin'
            )
            admin.set_password('123456')
            db.session.add(admin)
            db.session.flush()  # 获取 admin.id
            
            # 创建一个标签
            tag = Tag(name='PPress')
            db.session.add(tag)
            db.session.flush()  # 获取 tag.id
            
            # 创建一个分类
            category = Category(
                name='示例分类',
                slug='example',
                description='PPress 示例分类',
                sort_order=1
            )
            db.session.add(category)
            db.session.flush()  # 获取 category.id
            
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
                SiteConfig(key='site_name', value=site_name),
                SiteConfig(key='site_description', value='基于 Flask 的博客系统'),
                SiteConfig(key='site_keywords', value='PPress,技术,博客'),
                SiteConfig(key='site_theme', value='default'),
                SiteConfig(key='article_url_pattern', value='article/{id}')
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
            
            db.session.commit()
            
            # 创建安装锁文件
            with open(os.path.join(current_app.root_path, '..', 'ppress_db.lock'), 'w', encoding='utf-8') as f:
                f.write('installed')
            
            # 清理安装文件
            success, error = Installer.cleanup_installer()
            if not success:
                return render_template('install.html', error=error, tailwind_content=tailwind_content)
            
            return redirect(url_for('blog.index'))
            
        except Exception as e:
            db.session.rollback()  # 出错时回滚
            return render_template('install.html', error=str(e), tailwind_content=tailwind_content)
    
    return render_template('install.html', tailwind_content=tailwind_content)