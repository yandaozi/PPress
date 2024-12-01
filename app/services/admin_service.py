from flask import current_app

from app.models import User, Article, Comment, ViewHistory, Category, Tag, Plugin, File, SiteConfig
from app.utils.cache_manager import cache_manager
from app.plugins import plugin_manager

import json
from app import db
import os
import tempfile
import zipfile
from importlib import import_module
import shutil
import platform
import flask
import sqlalchemy

from app.utils.pagination import Pagination


def format_size(size):
    """格式化文件大小显示"""
    if size >= 1024 * 1024:  # MB
        return f"{size / (1024 * 1024):.2f} MB"
    elif size >= 1024:  # KB
        return f"{size / 1024:.2f} KB"
    else:  # B
        return f"{size} B"

class AdminService:
    @staticmethod
    def get_dashboard_data():
        """获取仪表盘数据"""
        try:
            # 基础统计
            total_users = User.query.count()
            total_articles = Article.query.count()
            total_comments = Comment.query.count()
            total_views = ViewHistory.query.count()
            
            # 获取系统信息
            system_info = {
                'python_version': platform.python_version(),
                'flask_version': flask.__version__,
                'sqlalchemy_version': sqlalchemy.__version__,
                'database': current_app.config['SQLALCHEMY_DATABASE_URI'].split('://')[0],
                'cache_type': current_app.config.get('CACHE_TYPE', 'simple'),
                'upload_folder': current_app.config.get('UPLOAD_FOLDER', 'uploads'),
                'static_folder': os.path.basename(current_app.static_folder),
                'template_folder': os.path.basename(current_app.template_folder),
                'debug_mode': current_app.debug,
                'environment': 'Development' if current_app.debug else 'Production',
                'app_version': current_app.config.get('VERSION', '0.0.1'),
                'operating_system': f"{platform.system()} {platform.release()}"
            }
            
            # 获取分类数据
            categories = [{
                'id': cat.id,
                'name': cat.name,
                'article_count': cat.article_count
            } for cat in Category.query.all()]
            
            # 获取随机标签
            selected_tags = [{
                'id': tag.id,
                'name': tag.name,
                'article_count': tag.article_count
            } for tag in Tag.query.order_by(db.func.random()).limit(15)]
            
            # 获取最近活动
            recent_activities = []
            
            # 最近评论
            recent_comments = Comment.query.options(
                db.joinedload(Comment.user),
                db.joinedload(Comment.article)
            ).order_by(Comment.created_at.desc()).limit(5).all()
            
            # 最近文章
            recent_articles = Article.query.options(
                db.joinedload(Article.author)
            ).order_by(Article.created_at.desc()).limit(5).all()
            
            # 组装活动数据
            for comment in recent_comments:
                recent_activities.append({
                    'type': 'comment',
                    'user': {
                        'id': comment.user.id if comment.user else None,
                        'username': comment.user.username if comment.user else '已注销用户',
                        'avatar': comment.user.avatar if comment.user else '/static/default_avatar.png'
                    },
                    'article': comment.article,
                    'action': '发表了评论',
                    'created_at': comment.created_at
                })
            
            for article in recent_articles:
                recent_activities.append({
                    'type': 'article',
                    'user': {
                        'id': article.author.id if article.author else None,
                        'username': article.author.username if article.author else '已注销用户',
                        'avatar': article.author.avatar if article.author else '/static/default_avatar.png'
                    },
                    'article': article,
                    'action': '发布了文章',
                    'created_at': article.created_at
                })
            
            # 按时间排序
            recent_activities.sort(key=lambda x: x['created_at'], reverse=True)
            
            return {
                'total_users': total_users,
                'total_articles': total_articles, 
                'total_comments': total_comments,
                'total_views': total_views,
                'categories': categories,
                'tags': selected_tags,
                'recent_activities': recent_activities,
                'system_info': system_info
            }
            
        except Exception as e:
            current_app.logger.error(f"Dashboard error: {str(e)}")
            return None 

    @staticmethod
    def get_users(page=1, search_type='', search_query=''):
        """获取用户列表"""
        try:
            # 构建基础查询
            query = User.query
            
            if search_query:
                if search_type == 'id':
                    try:
                        user_id = int(search_query)
                        query = query.filter(User.id == user_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                else:
                    # 用名搜索 - 先精确后模糊
                    exact_matches = query.filter(User.username == search_query)
                    fuzzy_matches = query.filter(
                        User.username.like(f'%{search_query}%'),
                        User.username != search_query
                    )
                    query = exact_matches.union(fuzzy_matches)
            
            # 分页
            pagination = query.order_by(User.id.desc()).paginate(
                page=page, per_page=10, error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get users error: {str(e)}")
            return None, str(e)

    @staticmethod
    def toggle_user_role(user_id, current_user_id):
        """切换用户角色"""
        try:
            if user_id == current_user_id:
                return False, '不能修改自己的角色'
            
            user = User.query.get_or_404(user_id)
            user.role = 'user' if user.role == 'admin' else 'admin'
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def delete_user(user_id, current_user_id):
        """删用户"""
        try:
            if user_id == current_user_id:
                return False, '不能删除自己'
            
            user = User.query.get_or_404(user_id)
            db.session.delete(user)
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_articles(page=1, search_type='', search_query=''):
        """获取文章列表"""
        try:
            # 构建基础查询
            query = Article.query
            
            if search_query:
                if search_type == 'id':
                    try:
                        article_id = int(search_query)
                        query = query.filter(Article.id == article_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                elif search_type == 'author':
                    query = query.join(User).filter(User.username.like(f'%{search_query}%'))
                elif search_type == 'category':
                    query = query.join(Category).filter(Category.name == search_query)
                elif search_type == 'tag':
                    query = query.join(Article.tags).filter(
                        db.or_(
                            Tag.name == search_query,
                            Tag.name.like(f'%{search_query}%')
                        )
                    ).distinct()
                else:
                    # 标题搜索 - 先精确后模糊
                    exact_matches = query.filter(Article.title == search_query)
                    fuzzy_matches = query.filter(
                        Article.title.like(f'%{search_query}%'),
                        Article.title != search_query
                    )
                    query = exact_matches.union(fuzzy_matches)
            
            # 分页
            pagination = query.order_by(Article.id.desc()).paginate(
                page=page, per_page=10, error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get articles error: {str(e)}")
            return None, str(e)

    @staticmethod
    def delete_article(article_id):
        """删除文章"""
        try:
            article = Article.query.get_or_404(article_id)
            db.session.delete(article)
            db.session.commit()
            
            # 清除相关缓存
            from app.services.blog_service import BlogService
            BlogService.clear_article_related_cache(article_id)
            
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_comments(page=1, search_type='', search_query=''):
        """获取评论列表"""
        try:
            # 构建基础查询
            query = Comment.query.options(
                db.joinedload(Comment.user),
                db.joinedload(Comment.article)
            )
            
            if search_query:
                if search_type == 'id':
                    try:
                        comment_id = int(search_query)
                        query = query.filter(Comment.id == comment_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                elif search_type == 'author':
                    query = query.join(User).filter(User.username.like(f'%{search_query}%'))
                else:
                    # 内容搜索
                    query = query.filter(Comment.content.like(f'%{search_query}%'))
            
            # 分页
            pagination = query.order_by(Comment.id.desc()).paginate(
                page=page, per_page=10, error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get comments error: {str(e)}")
            return None, str(e)

    @staticmethod
    def delete_comment(comment_id):
        """删除评论"""
        try:
            comment = Comment.query.get_or_404(comment_id)
            article_id = comment.article_id
            db.session.delete(comment)
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete(f'article:{article_id}')  # 文章详情缓存
            cache_manager.delete('latest_comments')        # 最新评论缓存
            
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e) 

    @staticmethod
    def update_site_config(form_data):
        """更新网站配置"""
        try:
            for key in form_data:
                if key.startswith('config_'):
                    config_key = key[7:]  # 去掉'config_'前缀
                    config = SiteConfig.query.filter_by(key=config_key).first()
                    if config:
                        config.value = form_data[key]
                    else:
                        config = SiteConfig(key=config_key, value=form_data[key])
                        db.session.add(config)
            
            db.session.commit()
            
            # 清除配置缓存
            cache_manager.delete('site_config:*')
            
            return True, '配置已更新'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update site config error: {str(e)}")
            return False, f'更新失败: {str(e)}'

    @staticmethod
    def get_site_configs():
        """获所有网站配置"""
        try:
            configs = SiteConfig.query.all()
            return configs, None
            
        except Exception as e:
            current_app.logger.error(f"Get site configs error: {str(e)}")
            return None, str(e) 

    @staticmethod
    def get_categories(page=1, search_type='', search_query=''):
        """获取分类列表"""
        try:
            # 构建基础查询
            query = Category.query
            
            if search_query:
                if search_type == 'id':
                    try:
                        category_id = int(search_query)
                        query = query.filter(Category.id == category_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                else:
                    # 名称搜索 - 先精确后模糊
                    exact_matches = query.filter(Category.name == search_query)
                    fuzzy_matches = query.filter(
                        Category.name.like(f'%{search_query}%'),
                        Category.name != search_query
                    )
                    query = exact_matches.union(fuzzy_matches)
            
            # 获取分类数据
            categories = [{
                'id': cat.id,
                'name': cat.name,
                'description': cat.description,
                'article_count': cat.article_count
            } for cat in query.all()]
            
            # 手动分页
            per_page = 10
            total = len(categories)
            total_pages = (total + per_page - 1) // per_page
            page = min(max(page, 1), total_pages if total_pages > 0 else 1)
            start = (page - 1) * per_page
            end = start + per_page

            # 使用通用分页类
            pagination = Pagination(
                items=categories[start:end],
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get categories error: {str(e)}")
            return None, str(e)

    @staticmethod
    def add_category(name, description):
        """添加分类"""
        try:
            if Category.query.filter_by(name=name).first():
                return False, '分类已存在', None
            
            category = Category(name=name, description=description)
            db.session.add(category)
            db.session.commit()
            
            # 清除分类缓存
            cache_manager.delete('categories_*')
            
            return True, None, {
                'id': category.id,
                'name': category.name
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def delete_category(category_id):
        """删除分类"""
        try:
            category = Category.query.get_or_404(category_id)
            
            # 不能删除默认分类
            if category.id == 1:
                return False, '不能删除默认分类'
            
            # 将该分类下的文章移动到默认分类
            default_category = Category.query.get(1)
            if not default_category:
                default_category = Category(id=1, name='默认分类')
                db.session.add(default_category)
                db.session.flush()
            
            # 更新文章分类
            articles_count = category.article_count
            Article.query.filter_by(category_id=category.id).update({
                'category_id': default_category.id
            })
            
            # 更新默认分类文章计数
            default_category.article_count += articles_count
            
            # 删除分类
            db.session.delete(category)
            
            # 清除缓存
            cache_manager.delete('categories_*')
            
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def edit_category(category_id, name, description):
        """编辑分类"""
        try:
            category = Category.query.get_or_404(category_id)
            
            # 检查名称是否已存在
            if name != category.name and Category.query.filter_by(name=name).first():
                return False, '分类名称已存在', None
            
            category.name = name
            category.description = description
            db.session.commit()
            
            # 清除缓存
            cache_manager.delete('categories_*')
            
            return True, None, {
                'id': category.id,
                'name': category.name,
                'description': category.description
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def get_tags(page=1, search_type='', search_query=''):
        """获取标签列表"""
        try:
            # 构建基础查询
            query = Tag.query
            
            if search_query:
                if search_type == 'id':
                    try:
                        tag_id = int(search_query)
                        query = query.filter(Tag.id == tag_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                else:
                    query = query.filter(Tag.name.ilike(f'%{search_query}%'))
            
            # 分页
            pagination = query.order_by(Tag.id.desc()).paginate(
                page=page, per_page=20, error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get tags error: {str(e)}")
            return None, str(e)

    @staticmethod
    def add_tag(name):
        """添加标签"""
        try:
            if Tag.query.filter_by(name=name).first():
                return False, '标签已存在', None
            
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.commit()
            
            # 清除标签缓存
            cache_manager.delete('tag_*')
            
            return True, None, {
                'id': tag.id,
                'name': tag.name
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def delete_tag(tag_id):
        """删除标签"""
        try:
            tag = Tag.query.get_or_404(tag_id)
            db.session.delete(tag)
            db.session.commit()
            
            # 清除标签缓存
            cache_manager.delete('tag_*')
            
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def edit_tag(tag_id, name):
        """编辑标签"""
        try:
            tag = Tag.query.get_or_404(tag_id)
            
            # 检查名称是否已存在
            if name != tag.name and Tag.query.filter_by(name=name).first():
                return False, '标签称已存在', None
            
            tag.name = name
            db.session.commit()
            
            # 清除标签缓存
            cache_manager.delete('tag_*')
            
            return True, None, {
                'id': tag.id,
                'name': tag.name
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def add_user(username, email, password, role='user'):
        """添加用户"""
        try:
            # 检查用户名和邮箱是否已存在
            if User.query.filter_by(username=username).first():
                return False, '用户名已存在', None
            if User.query.filter_by(email=email).first():
                return False, '邮箱已存在', None
            
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            return True, None, {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def edit_user(user_id, data, current_user_id):
        """编辑用户"""
        try:
            user = User.query.get_or_404(user_id)
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            role = data.get('role')
            
            # 检查用户名和邮箱是否已存在
            if username != user.username and User.query.filter_by(username=username).first():
                return False, '用户名已存在', None
            if email != user.email and User.query.filter_by(email=email).first():
                return False, '邮箱已存在', None
            
            user.username = username
            user.email = email
            if password:
                user.set_password(password)
            # 只有编辑其他用户时才允许修改角色
            if user.id != current_user_id and role:
                user.role = role
            
            db.session.commit()
            
            return True, None, {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
            }
            
        except Exception as e:
            db.session.rollback()
            return False, str(e), None

    @staticmethod
    def get_histories(page=1, search_type='', search_query=''):
        """取浏览历史列表"""
        try:
            # 构建基础查询
            query = ViewHistory.query.join(ViewHistory.article).join(ViewHistory.user)
            
            if search_query:
                if search_type == 'id':
                    try:
                        history_id = int(search_query)
                        query = query.filter(ViewHistory.id == history_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                elif search_type == 'user':
                    query = query.filter(User.username.like(f'%{search_query}%'))
                elif search_type == 'article':
                    query = query.filter(Article.title.like(f'%{search_query}%'))
            
            # 分页
            pagination = query.order_by(
                ViewHistory.id.desc(),
                ViewHistory.viewed_at.desc()
            ).paginate(page=page, per_page=10, error_out=False)
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get histories error: {str(e)}")
            return None, str(e)

    @staticmethod
    def delete_history(history_id):
        """删除浏览历史"""
        try:
            history = ViewHistory.query.get_or_404(history_id)
            db.session.delete(history)
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def clear_user_history(user_id):
        """清除用户的所有浏览历史"""
        try:
            ViewHistory.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_themes():
        """获取主题列表"""
        try:
            from app.models.site_config import SiteConfig
            from app.utils.theme_manager import ThemeManager
            
            themes = ThemeManager.get_available_themes()
            current_theme = SiteConfig.get_config('site_theme', 'default')
            
            return {
                'themes': themes,
                'current_theme': current_theme
            }, None
            
        except Exception as e:
            current_app.logger.error(f"Get themes error: {str(e)}")
            return None, str(e)

    @staticmethod
    def change_theme(theme_name):
        """更改主题"""
        try:
            from app.models.site_config import SiteConfig
            
            if not theme_name:
                return False, '主题名称不能为空'
            
            config = SiteConfig.query.filter_by(key='site_theme').first()
            if config:
                config.value = theme_name
            else:
                config = SiteConfig(key='site_theme', value=theme_name)
                db.session.add(config)
            
            db.session.commit()
            
            # 清除主题相关缓存
            cache_manager.delete('site_config:*')
            
            return True, '主题更新成功'
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_plugins(page=1, search_query=''):
        """获取插件列表"""
        try:
            # 构建查询
            query = Plugin.query
            
            # 搜索
            if search_query:
                query = query.filter(
                    db.or_(
                        Plugin.name.ilike(f'%{search_query}%'),
                        Plugin.description.ilike(f'%{search_query}%'),
                        Plugin.author.ilike(f'%{search_query}%')
                    )
                )
            
            # 分页
            pagination = query.order_by(Plugin.installed_at.desc()).paginate(
                page=page, per_page=9, error_out=False
            )
            
            # 获取已加载的插件实例
            loaded_plugins = plugin_manager.plugins
            
            # 处理插件信息
            plugin_info = []
            for plugin in pagination.items:
                info = {
                    'name': plugin.name,
                    'directory': plugin.directory,
                    'description': plugin.description,
                    'version': plugin.version,
                    'author': plugin.author,
                    'author_url': plugin.author_url,
                    'enabled': plugin.enabled,
                    'installed_at': plugin.installed_at,
                    'is_loaded': plugin.directory in loaded_plugins,
                    'config': plugin.config
                }
                plugin_info.append(info)
            
            return {
                'plugins': plugin_info,
                'pagination': pagination,
                'search_query': search_query
            }, None
            
        except Exception as e:
            current_app.logger.error(f"Get plugins error: {str(e)}")
            return None, str(e)

    @staticmethod
    def uninstall_plugin(plugin_name):
        """卸载插件"""
        try:
            # 从数据库中获取插件记录
            plugin_record = Plugin.query.filter_by(name=plugin_name).first_or_404()
            plugin_dir = plugin_record.directory
            
            # 获取插件的实际目录路径
            installed_dir = os.path.join(current_app.root_path, 'plugins', 'installed')
            plugin_path = os.path.join(installed_dir, plugin_dir)
            
            # 如果插件已加载，先卸载它
            if plugin_dir in plugin_manager.plugins:
                plugin_manager.unload_plugin(plugin_dir)
            
            # 删除插件目录
            if os.path.exists(plugin_path):
                import shutil
                shutil.rmtree(plugin_path)
            
            # 从数据库中删除插件记录
            db.session.delete(plugin_record)
            db.session.commit()
            
            return True, f'插件 {plugin_name} 卸载成功'
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def toggle_plugin(plugin_name):
        """启用/禁用插件"""
        try:
            plugin = Plugin.query.filter_by(directory=plugin_name).first_or_404()
            plugin.enabled = not plugin.enabled
            db.session.commit()
            
            if plugin.enabled:
                # 启用插件 - 重新加载
                if plugin_manager.reload_plugin(plugin_name):
                    status = '启用'
                else:
                    # 加载失败时回滚状态
                    plugin.enabled = False
                    db.session.commit()
                    return False, '插件加载失败'
            else:
                # 禁用插件
                plugin_manager.unload_plugin(plugin_name)
                status = '禁用'
            
            return True, f'插件已{status}'
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def save_plugin_settings(plugin_name, form_data):
        """保存插件设置"""
        try:
            # 移除开头和结尾的斜杠
            plugin_name = plugin_name.strip('/')
            
            # 获取插件实例
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return False, '插件未加载或不存在'
            
            # 调用插件的保存设置方法
            success, message = plugin.save_settings(form_data)
            
            return success, message
            
        except Exception as e:
            current_app.logger.error(f"Save plugin settings error: {str(e)}")
            return False, str(e)

    @staticmethod
    def upload_plugin(file):
        """上传件"""
        try:
            if not file:
                return False, '没有上传文件'
            
            if file.filename == '':
                return False, '没有选择文件'
            
            if not file.filename.endswith('.zip'):
                return False, '只支持 zip 格式的插件包'
            
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, file.filename)
            
            try:
                # 保存上传的文件
                file.save(zip_path)
                
                # 解压文件
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # 检查插件格式是否正确
                if not os.path.exists(os.path.join(temp_dir, 'plugin.json')):
                    return False, '无效的插件格式'
                
                # 读取插件信息
                with open(os.path.join(temp_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
                    plugin_info = json.load(f)
                
                plugin_name = plugin_info.get('name')
                if not plugin_name:
                    return False, '插件信息不完整'
                
                # 检查插件是否已存在
                if Plugin.query.filter_by(name=plugin_name).first():
                    return False, '插件已存在'
                
                # 生成目录名
                directory = plugin_info.get('directory', plugin_name.lower().replace(' ', '_'))
                plugin_dir = os.path.join(current_app.root_path, 'plugins', 'installed', directory)
                
                if os.path.exists(plugin_dir):
                    return False, '插件目录已存在'
                
                # 复制文件到插件目录
                shutil.copytree(temp_dir, plugin_dir)
                
                # 删除插件目录下的zip文件
                plugin_zip = os.path.join(plugin_dir, file.filename)
                if os.path.exists(plugin_zip):
                    os.remove(plugin_zip)
                
                # 导入插件模块获取默认配置
                module = import_module(f'app.plugins.installed.{directory}')
                plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
                plugin = plugin_class()
                default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}
                
                # 获取启用状态
                enabled = plugin_info.get('enabled', True)  # 如果未指定，默认为启用
                
                # 添加到数据库
                Plugin.add_plugin(plugin_info, directory, enabled=enabled, config=default_config)
                
                # 如果插件默认启用，则立即加载它
                if enabled:
                    plugin_manager.load_plugin(directory)
                
                return True, f'插件 {plugin_name} 安装成功！(默认状态：{"启用" if enabled else "禁用"})'
                
            finally:
                # 清理临时目录
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_files(page=1, search_type='', search_query=''):
        """获取文件列表"""
        try:
            # 构建查询
            query = File.query
            
            # 搜索
            if search_query:
                if search_type == 'filename':
                    query = query.filter(File.original_filename.ilike(f'%{search_query}%'))
                elif search_type == 'type':
                    query = query.filter(File.file_type.ilike(f'%{search_query}%'))
                elif search_type == 'uploader':
                    query = query.join(File.uploader).filter(User.username.ilike(f'%{search_query}%'))
            
            # 分页
            pagination = query.order_by(File.upload_time.desc()).paginate(
                page=page, per_page=20, error_out=False
            )
            
            return {
                'files': pagination,
                'search_query': search_query,
                'search_type': search_type
            }, None
            
        except Exception as e:
            current_app.logger.error(f"Get files error: {str(e)}")
            return None, str(e)

    @staticmethod
    def delete_file(file_id):
        """删除文件"""
        try:
            file = File.query.get_or_404(file_id)
            
            # 获取文件的物理路径
            file_path = os.path.join(current_app.root_path, file.file_path.lstrip('/'))
            
            # 删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)
                
                # 如果文件所在目录为空，删除目录
                directory = os.path.dirname(file_path)
                if not os.listdir(directory):
                    os.rmdir(directory)
            
            # 从数据库中删除记录
            db.session.delete(file)
            db.session.commit()
            
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def export_plugin(plugin_name):
        """导出插件"""
        try:
            # 从数据库获取插件记录
            plugin_record = Plugin.query.filter_by(name=plugin_name).first_or_404()
            plugin_dir = plugin_record.directory
            
            # 获取插件实例
            plugin = plugin_manager.get_plugin(plugin_dir)
            if not plugin:
                return False, '插件未加载', None, None
            
            content, filename = plugin.export_plugin()
            
            return True, None, content, filename
            
        except Exception as e:
            current_app.logger.error(f'Export plugin error: {str(e)}')
            return False, str(e), None, None

    @staticmethod
    def get_plugin_settings(plugin_name):
        """获取插件设置页面"""
        try:
            # 移除开头和结尾的斜杠
            plugin_name = plugin_name.strip('/')
            
            # 获取插件实例
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return False, '插件未加载或不存在', None, None
            
            # 获取插件的设置模板
            settings_html = plugin.get_settings_template()
            if not settings_html:
                return False, '该插件没有设置页面', None, None
            
            # 从数据库获取插件记录
            plugin_record = Plugin.query.filter_by(directory=plugin_name).first_or_404()
            
            return True, None, plugin_record, settings_html
            
        except Exception as e:
            current_app.logger.error(f"Get plugin settings error: {str(e)}")
            return False, str(e), None, None

    @staticmethod
    def check_plugin_settings(plugin_name):
        """检查插件是否有设置页面"""
        try:
            # 移除开头和结尾的斜杠
            plugin_name = plugin_name.strip('/')
            
            # 获取插件实例
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return False, '插件未加载或不存在'
            
            # 检查是否有设置模板
            settings_html = plugin.get_settings_template()
            if not settings_html:
                return False, '该插件没有设置页面'
            
            return True, '插件有设置页面'
            
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_cache_stats(page=1):
        """获取缓存统计信息"""
        try:
            from app.utils.cache_manager import cache_manager
            
            # 获取所有缓存键
            cache_keys = list(cache_manager._cache.keys())
            total_cache_count = len(cache_keys)
            
            # 计算总内存占用
            total_size = sum(len(str(cache_manager._cache.get(key))) for key in cache_keys)
            memory_usage = format_size(total_size)
            
            # 计算命中率 (这里需要从 cache_manager 获取命中和未命中的次数)
            hits = getattr(cache_manager, '_hits', 0)
            misses = getattr(cache_manager, '_misses', 0)
            hit_rate = f"{(hits / (hits + misses) * 100):.1f}%" if hits + misses > 0 else "0%"
            
            # 按类别统计缓存
            cache_categories = {
                'index': len([k for k in cache_keys if 'index' in k]),
                'article': len([k for k in cache_keys if 'article' in k]),
                'category': len([k for k in cache_keys if 'category' in k or 'categories' in k]),
                'tag': len([k for k in cache_keys if 'tag' in k or 'tags' in k]),
                'search': len([k for k in cache_keys if 'search' in k]),
                'user': len([k for k in cache_keys if 'user' in k]),
                'other': len([k for k in cache_keys if not any(x in k for x in ['index', 'article', 'category', 'tag', 'search', 'user'])])
            }
            
            # 获取缓存键的详细信息
            cache_keys_info = []  # 改为列表
            for key in sorted(cache_keys):
                value = cache_manager._cache.get(key)
                size = len(str(value)) if value else 0
                cache_keys_info.append({
                    'key': key,
                    'type': type(value).__name__,
                    'size': format_size(size)
                })
            
            # 使用传入的页码
            per_page = 15
            total = len(cache_keys_info)
            total_pages = (total + per_page - 1) // per_page
            page = min(max(page, 1), total_pages if total_pages > 0 else 1)
            start = (page - 1) * per_page
            end = start + per_page

            # 创建分页对象
            pagination = Pagination(
                items=cache_keys_info[start:end],  # 直接使用切片的列表
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )
            
            return {
                'cache_stats': {
                    'total_keys': total_cache_count,
                    'memory_usage': memory_usage,
                    'hit_rate': hit_rate,
                    'by_category': cache_categories
                },
                'cache_keys': cache_keys_info[start:end],  # 只返回当前页的数据
                'cache_categories': cache_categories,
                'total_cache_count': total_cache_count,
                'pagination': pagination
            }, None
            
        except Exception as e:
            current_app.logger.error(f"Get cache stats error: {str(e)}")
            return None, str(e)

    @staticmethod
    def clear_cache_by_category(category):
        """按类别清除缓存"""
        try:
            from app.utils.cache_manager import cache_manager
            deleted_count = 0
            
            # 获取所有缓存键
            cache_keys = list(cache_manager._cache.keys())
            
            for key in cache_keys:
                should_delete = False
                
                if category == 'all':
                    should_delete = True
                elif category == 'index' and 'index' in key:
                    should_delete = True
                elif category == 'article' and 'article' in key:
                    should_delete = True
                elif category == 'category' and ('category' in key or 'categories' in key):
                    should_delete = True
                elif category == 'tag' and ('tag' in key or 'tags' in key):
                    should_delete = True
                elif category == 'search' and 'search' in key:
                    should_delete = True
                elif category == 'user' and 'user' in key:
                    should_delete = True
                
                if should_delete:
                    cache_manager.delete(key)
                    deleted_count += 1
            
            return True, deleted_count
            
        except Exception as e:
            current_app.logger.error(f"Clear cache error: {str(e)}")
            return False, str(e)

    @staticmethod
    def reload_plugin(plugin_name):
        """重新加载插件"""
        try:
            # 读取插件信息
            plugin_dir = os.path.join(current_app.root_path, 'plugins', 'installed', plugin_name)
            with open(os.path.join(plugin_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
                plugin_info = json.load(f)
            
            # 获取插件实例
            module = import_module(f'app.plugins.installed.{plugin_name}')
            plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
            plugin = plugin_class()
            default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}
            
            # 获取启用状态
            enabled = plugin_info.get('enabled', True)
            
            # 更新数据库记录
            db_plugin = Plugin.query.filter_by(directory=plugin_name).first()
            if db_plugin:
                db_plugin.name = plugin_info['name']
                db_plugin.description = plugin_info.get('description', '')
                db_plugin.version = plugin_info.get('version', '1.0.0')
                db_plugin.author = plugin_info.get('author', '')
                db_plugin.author_url = plugin_info.get('author_url', '')
                db_plugin.enabled = enabled
                db_plugin.config = default_config
                db.session.commit()
            
            # 重新加载插件
            plugin_manager.reload_plugin(plugin_name)
            
            return True, f'插件重载成功！(默认状态：{"启用" if enabled else "禁用"})'
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def clear_single_cache(key):
        """清除指定的缓存"""
        try:
            cache_manager.delete(key)
            return True, f'缓存 {key} 已删除'
        except Exception as e:
            current_app.logger.error(f"Clear single cache error: {str(e)}")
            return False, str(e)