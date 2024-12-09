from flask import render_template, request, redirect, url_for, current_app, jsonify

from app import create_app
from app.installer import bp
from app.installer.utils import Installer
from app.models import (
    User, Tag, Category, Article, SiteConfig, CommentConfig,
    Plugin, File, Route, CustomPage, ViewHistory, Comment
)
from app.extensions import db
from datetime import datetime
import os
import pymysql
import base64
from slugify import slugify
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
                # 获取表单中的 MySQL 配置并更新 MYSQL_CONFIG
                MYSQL_CONFIG.update({
                    'host': request.form.get('mysql_host'),
                    'port': int(request.form.get('mysql_port', 3306)),
                    'database': request.form.get('mysql_database').strip().replace(' ', '_'),
                    'user': request.form.get('mysql_user'),
                    'password': request.form.get('mysql_password')
                })
                
                try:
                    # 更新数据库配置
                    mysql_config = MYSQL_CONFIG.copy()
                    mysql_config['db_type'] = db_type
                    success, error = Installer.update_db_config(mysql_config)
                    if not success:
                        return jsonify({
                            'success': False,
                            'message': error
                        })
                        
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'message': f'MySQL初始化失败: {str(e)}'
                    })

            # 创建应用实例
            app = create_app(db_type=db_type, init_components=False)

            with app.app_context():
                print(f"\n开始初始化数据到 {db_type} 数据库...")
                # 删除所有表并重新创建
                db.drop_all()
                db.create_all()
                
                # 初始化网站配置
                default_configs = [
                    {'key': 'site_name', 'value': site_name, 'description': '网站名称'},
                    {'key': 'site_keywords', 'value': 'PPress,技术,博客,Python', 'description': '网站关键词'},
                    {'key': 'site_description', 'value': '分享技术知识和经验', 'description': '网站描述'},
                    {'key': 'contact_email', 'value': 'ponyj@qq.com', 'description': '联系邮箱'},
                    {'key': 'icp_number', 'value': '', 'description': 'ICP备案号'},
                    {'key': 'footer_text', 'value': '© 2024 PPress 版权所有', 'description': '页脚文本'},
                    {'key': 'site_theme', 'value': 'default', 'description': '网站主题'},
                ]
                for config in default_configs:
                    db.session.add(SiteConfig(**config))

                # 创建管理员账号
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
                    slug=slugify('示例分类'),
                    description='PPress 示例分类',
                    sort_order=1
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
                    status='public'
                )
                article.tags.append(tag)
                article.categories = [category]
                db.session.add(article)

                # 最终提交
                db.session.commit()

                # 创建安装锁文件
                with open(os.path.join(current_app.root_path, '..', 'ppress_db.lock'), 'w', encoding='utf-8') as f:
                    f.write(base64.b64decode(
                        'UFByZXNzIC0gRmxhc2sgQ29udGVudCBNYW5hZ2VtZW50IFN5c3RlbQrniYjmnYPmiYDmnIkgKGMpIDIwMjQg6KiA6YGT5a2QCuS9nOiAhVFR77yaNTc1NzMyNTYzCumhueebruWcsOWdgO+8mmh0dHBzOi8vZ2l0ZWUuY29tL2ZvamllL1BQcmVzcw=='
                    ).decode('utf-8'))

                # 清理安装文件
                success, error = Installer.cleanup_installer()
                if not success:
                    return jsonify({
                        'success': False,
                        'message': error
                    })

                return jsonify({
                    'success': True,
                    'message': '安装成功！记得重启应用！',
                    'redirect_url': '/'
                })

        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            })

    return render_template('install.html', tailwind_content=tailwind_content)