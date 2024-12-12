from datetime import datetime

from flask import current_app
from flask_login import current_user, login_user
from slugify import slugify
from werkzeug.security import check_password_hash

from app.models import User, Article, Comment, ViewHistory, Category, Tag, Plugin, File, SiteConfig, Route, \
    CommentConfig
from app.models.article import article_categories, article_tags
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
from threading import Lock

from app.utils.route_manager import route_manager
from sqlalchemy import text, update, func, distinct, case
from app.utils.article_url import ArticleUrlGenerator
from app.utils.id_encoder import IdEncoder

def format_size(size):
    """格式化文件大小显示"""
    if size >= 1024 * 1024:  # MB
        return f"{size / (1024 * 1024):.2f} MB"
    elif size >= 1024:  # KB
        return f"{size / 1024:.2f} KB"
    else:  # B
        return f"{size} B"

class AdminService:
    _route_lock = Lock()
    
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
                'app_version': current_app.config.get('VERSION', '0.0.9'),
                'operating_system': f"{platform.system()} {platform.release()}"
            }
            
            # 获取分类数据
            categories = [{
                'id': cat.id,
                'name': cat.name,
                'article_count': cat.article_count
            } for cat in Category.query.all()]
            
            # 标签
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
                        'avatar': comment.user.avatar if comment.user else '/static/image/default_avatar.png'
                    },
                    'article': comment.article,
                    'article_url': ArticleUrlGenerator.generate(comment.article),
                    'action': '发表了评论',
                    'created_at': comment.created_at
                })
            
            for article in recent_articles:
                recent_activities.append({
                    'type': 'article',
                    'user': {
                        'id': article.author.id if article.author else None,
                        'username': article.author.username if article.author else '已注销用户',
                        'avatar': article.author.avatar if article.author else '/static/image/default_avatar.png'
                    },
                    'article': article,
                    'article_url': ArticleUrlGenerator.generate(article),
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
                        return None, 'ID必须是数'
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
        """获取章列表"""
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
    def get_comments(page=1, search_type='content', search_query=''):
        """获取评论列表"""
        try:
            query = Comment.query.options(
                db.joinedload(Comment.user),
                db.joinedload(Comment.article),
                db.joinedload(Comment.custom_page),
                db.joinedload(Comment.parent)
            )
            
            # 搜索过滤
            if search_query:
                if search_type == 'content':
                    query = query.filter(Comment.content.ilike(f'%{search_query}%'))
                elif search_type == 'id':  # 添加回ID搜索
                    try:
                        comment_id = int(search_query)
                        query = query.filter(Comment.id == comment_id)
                    except ValueError:
                        return None, 'ID必须是数字'
                elif search_type == 'author':  # 修改回author搜索
                    query = query.join(User).filter(User.username.ilike(f'%{search_query}%'))
                elif search_type == 'article':
                    query = query.join(Article).filter(Article.title.ilike(f'%{search_query}%'))
                elif search_type == 'status':
                    query = query.filter(Comment.status == search_query)
            
            # 按时间倒序排序
            query = query.order_by(Comment.id.desc())
            
            # 分页
            pagination = query.paginate(
                page=page,
                per_page=20,
                error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Comments error: {str(e)}")
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
            cache_manager.delete(f'article:{article_id}')  # 章详情缓存
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
            
            # 除置缓存
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
                        # ID搜索时直接返回匹配的分类
                        categories = [Category.query.get_or_404(category_id)]
                    except ValueError:
                        return None, 'ID必须是数字'
                else:
                    # 名称搜索 - 先精确后模
                    exact_matches = query.filter(Category.name == search_query)
                    fuzzy_matches = query.filter(
                        Category.name.like(f'%{search_query}%'),
                        Category.name != search_query
                    )
                    query = exact_matches.union(fuzzy_matches)
                    categories = query.order_by(Category.sort_order).all()
                    
                    # 对于名称搜索，添加父分类链
                    result_categories = []
                    added_ids = set()
                    
                    for category in categories:
                        # 添加父分类
                        ancestors = category.get_ancestors()
                        for ancestor in ancestors:
                            if ancestor.id not in added_ids:
                                result_categories.append(ancestor)
                                added_ids.add(ancestor.id)
                        
                        # 添加当前分类
                        if category.id not in added_ids:
                            result_categories.append(category)
                            added_ids.add(category.id)
                    
                    # 按层级排序重排序
                    result_categories.sort(key=lambda x: (x.get_level(), x.sort_order))
                    categories = result_categories
            else:
                # 非搜索时只显示顶级分类
                categories = query.filter(Category.parent_id == None)\
                               .order_by(Category.sort_order).all()
            
            # 手动分页
            per_page = 50
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
    def add_category(data):
        """添加分类"""
        try:
            # 检查同级分类名称是否重复
            if Category.query.filter_by(
                name=data['name'],
                parent_id=data.get('parent_id')
            ).first():
                return False, '同级分类下已存在相同名称', None
            
            # 生成分类别名(slug)
            from slugify import slugify
            slug = slugify(data['name'])
            
            # 创建分类
            category = Category(
                name=data['name'],
                slug=slug,
                description=data.get('description'),
                parent_id=data.get('parent_id', type=int),
                sort_order=data.get('sort_order', type=int, default=0),
                use_slug=data.get('use_slug') == 'on',
                template=data.get('template', '')
            )
            
            db.session.add(category)
            db.session.commit()
            
            # 清除分类缓存
            cache_manager.delete('admin:categories:*')
            cache_manager.delete('categories_*')
            
            return True, '分类添加成功', {
                'id': category.id,
                'name': category.name
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Add category error: {str(e)}")
            return False, str(e), None

    @staticmethod
    def update_category(category_id, data):
        """更新分类"""
        try:
            category = Category.query.get_or_404(category_id)
            
            # 检查同级分类名称是否重复
            if data['name'] != category.name:
                if Category.query.filter_by(
                    name=data['name'],
                    parent_id=data.get('parent_id', category.parent_id)
                ).first():
                    return False, '同级分类下已存在相同名称', None
            
            # 检查 slug 是否重复
            new_slug = data.get('slug')
            if new_slug:  # 如果提供了新的 slug
                if new_slug != category.slug and Category.query.filter_by(slug=new_slug).first():
                    return False, '别名已被使用', None
                category.slug = new_slug
            else:  # 如果没提供 slug，根据名称生成
                from slugify import slugify
                category.slug = slugify(data['name'])
            
            # 更新其他字段
            category.name = data['name']
            category.description = data.get('description')
            category.use_slug = data.get('use_slug') == 'on'
            category.template = data.get('template', '')  # 更新模板字段
            # 只在明确提供 parent_id 时更新
            if 'parent_id' in data:
                category.parent_id = data.get('parent_id', type=int)
            category.sort_order = data.get('sort_order', type=int, default=category.sort_order)
            
            # 处理每页文章数
            per_page = data.get('per_page')
            if per_page:
                try:
                    category.per_page = max(1, min(100, int(per_page)))  # 限制在1-100之间
                except (TypeError, ValueError):
                    category.per_page = None  # 如果转换失败则使用默认值
            else:
                category.per_page = None  # 未填写则使用默认值
            
            db.session.commit()
            
            # 清除分类缓存
            cache_manager.delete('admin:categories:*')
            cache_manager.delete('categories_*')
            
            # 如果修改了 use_slug 设置，清除 URL 映射缓存
            if 'use_slug' in data and data['use_slug'] != category.use_slug:
                ArticleUrlGenerator.clear_cache()
            
            return True, '分类更新成功', {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'parent_id': category.parent_id,
                'sort_order': category.sort_order,
                'template': category.template  # 返回模板信息
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update category error: {str(e)}")
            return False, str(e), None

    @staticmethod
    def delete_category(category_id):
        """删除分类"""
        try:
            # 不能删除默认分类
            if category_id == 1:
                return False, '不能删除默认分类'
            
            category = Category.query.get_or_404(category_id)
            default_category = Category.query.get(1)
            
            if not default_category:
                return False, '默认分类不存在'

            # 1. 获取所需更新的分类ID
            affected_categories = set()
            affected_categories.add(default_category.id)  # 默认分类会接收文章
            if category.parent_id:
                affected_categories.add(category.parent_id)  # 父分类需要更新
            
            # 2. 更新主分类
            Article.query.filter_by(category_id=category_id).update({
                'category_id': default_category.id
            })
            
            # 3. 删除多分类关系
            db.session.execute(
                article_categories.delete().where(
                    article_categories.c.category_id == category_id
                )
            )
            
            # 4. 删除分类
            db.session.delete(category)
            db.session.commit()
            
            # 5. 更新受影响分类的文章计数
            for cat_id in affected_categories:
                cat = Category.query.get(cat_id)
                if cat:
                    cat.update_article_count()
            
            # 6. 清除缓存
            cache_manager.delete('categories_data')
            cache_manager.delete('category:*')
            cache_manager.delete('index:articles:*')
            
            return True, '分类删除成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Delete category error: {str(e)}")
            return False, f'删除失败: {str(e)}'

    @staticmethod
    def move_category(category_id, new_parent_id):
        """移动分类"""
        try:
            category = Category.query.get_or_404(category_id)
            
            # 检查是否形成循环
            if new_parent_id:
                parent = Category.query.get_or_404(new_parent_id)
                if category.id == new_parent_id or parent.id in [c.id for c in category.get_descendants()]:
                    return False, '不能将分类移动到自己或其子分类下'
            
            category.parent_id = new_parent_id
            db.session.commit()
            
            # 清除分类缓存
            cache_manager.delete('admin:categories:*')
            cache_manager.delete('categories_*')
            
            return True, '分类移动成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Move category error: {str(e)}")
            return False, str(e)

    @staticmethod
    def sort_categories(category_ids):
        """批量排序分类"""
        try:
            for index, category_id in enumerate(category_ids):
                category = Category.query.get(category_id)
                if category:
                    category.sort_order = index
            
            db.session.commit()
            
            # 清除分缓存
            cache_manager.delete('admin:categories:*')
            cache_manager.delete('categories_*')
            
            return True, '排序更新成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Sort categories error: {str(e)}")
            return False, str(e)

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
            
            # 分
            pagination = query.order_by(Tag.id.desc()).paginate(
                page=page, per_page=20, error_out=False
            )
            
            return pagination, None
            
        except Exception as e:
            current_app.logger.error(f"Get tags error: {str(e)}")
            return None, str(e)

    @staticmethod
    def add_tag(data):
        """添加标签"""
        try:
            name = data.get('name', '').strip()
            slug = data.get('slug', '').strip()
            use_slug = data.get('use_slug') == 'true'

            if not name:
                return False, '标签名不能为空', None

            if Tag.query.filter_by(name=name).first():
                return False, '标签名已存在', None

            # 检查 slug 是否已存在
            if slug and Tag.query.filter_by(slug=slug).first():
                return False, '缩略名已存在', None

            tag = Tag(name=name)
            if slug:
                tag.slug = slug
            tag.use_slug = use_slug

            db.session.add(tag)
            db.session.commit()
            
            # 清除标签缓存
            cache_manager.delete('tag_*')

            return True, '标签添加成功', {
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'use_slug': tag.use_slug,
                'article_count': 0
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
    def edit_tag(tag_id, data):
        """编辑标签"""
        try:
            tag = Tag.query.get_or_404(tag_id)

            name = data.get('name', '').strip()
            slug = data.get('slug', '').strip()
            use_slug = data.get('use_slug') == 'true'

            if not name:
                return False, '标签名不能为空', None

            # 检查名称是否已存在(排除自身)
            existing = Tag.query.filter(Tag.name == name, Tag.id != tag_id).first()
            if existing:
                return False, '标签名已存在', None

            # 检查 slug 是否已存在(排除自身)
            if slug:
                existing = Tag.query.filter(Tag.slug == slug, Tag.id != tag_id).first()
                if existing:
                    return False, '缩略名已存在', None
            if slug == '':
                slug = slugify(name)

            tag.name = name
            tag.slug = slug if slug else None
            tag.use_slug = use_slug

            db.session.commit()
            
            # 清除标签缓存
            #cache_manager.delete('tag_*')
            cache_manager.delete(f'tag:{tag_id}:*')  # 清除标签相关缓存
            cache_manager.delete(f'tag:{tag.slug}:*')  # 清除 slug 相关缓存


            return True, '标签更新成功', {
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'use_slug': tag.use_slug,
                'article_count': tag.article_count
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
            nickname = data.get('nickname', '').strip() or None
            
            # 检查用户名和箱是否已存在
            if username != user.username and User.query.filter_by(username=username).first():
                return False, '用户名已存在', None
            if email != user.email and User.query.filter_by(email=email).first():
                return False, '邮箱已存在', None
            
            user.username = username
            user.email = email
            user.nickname = nickname
            if password:
                user.set_password(password)
            # 只编辑其他用户时才允许修改角色
            if user.id != current_user_id and role:
                user.role = role
            
            db.session.commit()
            
            return True, None, {
                'id': user.id,
                'username': user.username,
                'nickname': user.nickname,
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

            # 处理插件信息并添加到 pagination.items
            for item in pagination.items:
                # 添加额外属性
                item.is_loaded = item.directory in loaded_plugins
                item.logo = f'/plugin/{item.directory}/static/logo.png'  # 添加 logo 属性

            return {
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
            # 从数库中获取插件记录
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

            # 从据库中删除插件记
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
                # 启用插件 - 新加
                if plugin_manager.reload_plugin(plugin_name):
                    status = '启用'
                else:
                    # 加载失败时回滚
                    plugin.enabled = False
                    db.session.commit()
                    return False, '插件加载失败'
            else:
                # 禁插件
                plugin_manager.unload_plugin(plugin_name)
                status = '禁用'

            return True, f'插件已{status}'

        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def save_plugin_settings(plugin_name, form_data):
        """保存插设"""
        try:
            # 除开头和结尾的斜杠
            plugin_name = plugin_name.strip('/')

            # 获插件实
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
        """上传插件"""
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
                    # 获取zip中的第一级目录名作为插件目录名
                    plugin_dir = None
                    for name in zip_ref.namelist():
                        if name.endswith('/'):  # 是目录
                            if '/' not in name[:-1]:  # 只取第一级目录
                                plugin_dir = name[:-1]
                                break
                    
                    if not plugin_dir:
                        return False, '无效的插件格式:缺少插件目录'

                    # 检查插件格式是否正确
                    if not f'{plugin_dir}/plugin.json' in zip_ref.namelist():
                        return False, '无效的插件格式:缺少plugin.json'

                    # 解压到临时目录
                    zip_ref.extractall(temp_dir)

                # 读取插件信息
                plugin_info_path = os.path.join(temp_dir, plugin_dir, 'plugin.json')
                with open(plugin_info_path, 'r', encoding='utf-8') as f:
                    plugin_info = json.load(f)

                # 检查插件是否已存在
                if Plugin.query.filter_by(name=plugin_info['name']).first():
                    return False, '插件已存在'

                # 复制插件目录到安装目录
                plugin_install_dir = os.path.join(current_app.root_path, 'plugins', 'installed')
                target_dir = os.path.join(plugin_install_dir, plugin_dir)

                if os.path.exists(target_dir):
                    return False, '插件目录已存在'

                # 复制整个插件目录
                shutil.copytree(os.path.join(temp_dir, plugin_dir), target_dir)

                # 导入插件模块获取默认配置
                module = import_module(f'app.plugins.installed.{plugin_dir}')
                plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
                plugin = plugin_class()
                default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}

                # 获取启用状态
                enabled = plugin_info.get('enabled', True)

                # 添加到数据库
                Plugin.add_plugin(plugin_info, plugin_dir, enabled=enabled, config=default_config)

                # 如果插件默认启用，则立即加载它
                if enabled:
                    plugin_manager.load_plugin(plugin_dir)

                return True, f'插件 {plugin_info["name"]} 安装成功！(默认状态：{"启用" if enabled else "禁用"})'

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

            # 获取件的物理路径
            file_path = os.path.join(current_app.root_path, file.file_path.lstrip('/'))

            # 删除物理文件
            if os.path.exists(file_path):
                os.remove(file_path)

                # 如果文件所目录为空，除目录
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

            # 获取插件的实际目录路径
            installed_dir = os.path.join(current_app.root_path, 'plugins', 'installed')
            plugin_path = os.path.join(installed_dir, plugin_dir)

            # 创建临时zip文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_file.close()

            try:
                # 创建zip文件,直接压缩整个插件目录
                with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # 将整个插件目录添加到zip中
                    zf.write(plugin_path, plugin_dir)
                    # 递归添加目录下的所有文件
                    for root, dirs, files in os.walk(plugin_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(plugin_dir, os.path.relpath(file_path, plugin_path))
                            zf.write(file_path, arcname)

                # 读取zip文件内容
                with open(temp_file.name, 'rb') as f:
                    content = f.read()

                return True, None, content, f'{plugin_dir}.zip'

            finally:
                # 清理临时文件
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)

        except Exception as e:
            current_app.logger.error(f'Export plugin error: {str(e)}')
            return False, str(e), None, None

    @staticmethod
    def get_plugin_settings(plugin_name):
        """获取插件设置页面"""
        try:
            # 移除开头和结尾的斜杠
            plugin_name = plugin_name.strip('/')

            # 取插件实
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return False, '插件未加载或不存在', None, None

            # 获取插件的设模板
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

            # 获取插件实
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                return False, '插件未加载或不存在'

            # 检查是否有设置模板
            settings_html = plugin.get_settings_template()
            if not settings_html:
                return False, '插没有设页面'

            return True, '插件有设置页面'

        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_cache_stats(page=1, search_query=None):
        """获取缓存统计信"""
        try:
            from app.utils.cache_manager import cache_manager

            # 获取所有缓存键
            cache_keys = list(cache_manager._cache.keys())
            
            # 如果有搜索关键词，过滤缓存键
            if search_query:
                cache_keys = [key for key in cache_keys if search_query.lower() in key.lower()]
            
            total_cache_count = len(cache_keys)

            # 计总内存占用
            total_size = sum(len(str(cache_manager._cache.get(key))) for key in cache_keys)
            memory_usage = format_size(total_size)

            # 计算命中率
            hits = getattr(cache_manager, '_hits', 0)
            misses = getattr(cache_manager, '_misses', 0)
            hit_rate = f"{(hits / (hits + misses) * 100):.1f}%" if hits + misses > 0 else "0%"

            # 按别统计缓存
            cache_categories = {
                'index': len([k for k in cache_keys if 'index' in k]),
                'article': len([k for k in cache_keys if 'article' in k]),
                'category': len([k for k in cache_keys if 'category' in k or 'categories' in k]),
                'tag': len([k for k in cache_keys if 'tag' in k or 'tags' in k]),
                'search': len([k for k in cache_keys if 'search' in k]),
                'user': len([k for k in cache_keys if 'user' in k]),
                'plugin': len([k for k in cache_keys if 'plugin_' in k]),
                'custom_page': len([k for k in cache_keys if 'custom_page' in k]),
                'route': len([k for k in cache_keys if 'route' in k or 'routes' in k]),
                'other': len([k for k in cache_keys if not any(x in k for x in ['index', 'article', 'category', 'tag', 'search', 'user', 'plugin', 'route'])])
            }

            # 获取缓存键的详细信息
            cache_keys_info = []
            for key in sorted(cache_keys):
                value = cache_manager._cache.get(key)
                size = len(str(value)) if value else 0
                cache_keys_info.append({
                    'key': key,
                    'type': type(value).__name__,
                    'size': format_size(size)
                })

            # 分页
            per_page = 15
            total = len(cache_keys_info)
            total_pages = (total + per_page - 1) // per_page
            page = min(max(page, 1), total_pages if total_pages > 0 else 1)
            start = (page - 1) * per_page
            end = start + per_page

            pagination = Pagination(
                items=cache_keys_info[start:end],
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
                'pagination': pagination,
                'cache_categories': cache_categories,
                'total_cache_count': total_cache_count,
                'memory_usage': memory_usage,
                'hit_rate': hit_rate,
                'search_query': search_query
            }, None

        except Exception as e:
            current_app.logger.error(f"Get cache stats error: {str(e)}")
            return None, str(e)

    @staticmethod
    def clear_cache_by_category(category):
        """按类别清除存"""
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
                elif category == 'plugin' and 'plugin_' in key:
                    should_delete = True
                elif category == 'custom_page' and 'custom_page' in key:
                    should_delete = True
                elif category == 'route' and ('route' in key or 'routes' in key):  # 添加路由缓处理
                    should_delete = True
                    # 如果清除路由缓存，需要刷新路由
                    if key == 'routes_last_refresh':
                        AdminService.refresh_custom_routes()

                if should_delete:
                    cache_manager.delete(key)
                    deleted_count += 1

            return True, deleted_count

        except Exception as e:
            current_app.logger.error(f"Clear cache error: {str(e)}")
            return False, str(e)

    @staticmethod
    def reload_plugin(plugin_name):
        """新加载插件"""
        try:
            # 读取插件信息
            plugin_dir = os.path.join(current_app.root_path, 'plugins', 'installed', plugin_name)
            with open(os.path.join(plugin_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
                plugin_info = json.load(f)

            # 获插件实例
            module = import_module(f'app.plugins.installed.{plugin_name}')
            plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
            plugin = plugin_class()
            default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}

            # 获取启用状态
            enabled = plugin_info.get('enabled', True)

            # 更新数库记录
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

            return True, f'插件重载成！(默认状态：{"启用" if enabled else "禁用"})'

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

    @staticmethod
    def add_route(data):
        """添加路由映"""
        return route_manager.add_route(data)

    @staticmethod
    def update_route(route_id, data):
        """更新路由"""
        return route_manager.update_route(route_id, data)

    @staticmethod
    def delete_route(route_id):
        """删除由"""
        return route_manager.delete_route(route_id)

    @staticmethod
    def toggle_route(route_id):
        """启用/禁用路由"""
        return route_manager.toggle_route(route_id)

    @staticmethod
    def refresh_custom_routes():
        """刷新自定义路由"""
        return route_manager.refresh_routes()

    @staticmethod
    def get_available_endpoints():
        """获取可用端点"""
        return route_manager.get_available_endpoints()

    @staticmethod
    def get_routes(page=1, search_query=''):
        """获路由列表"""
        try:
            # 检查表是否存在
            inspector = db.inspect(db.engine)
            if 'routes' not in inspector.get_table_names():
                db.create_all()

            query = Route.query

            if search_query:
                query = query.filter(
                    db.or_(
                        Route.path.like(f'%{search_query}%'),
                        Route.original_endpoint.like(f'%{search_query}%'),
                        Route.description.like(f'%{search_query}%')
                    )
                )

            # 使用通用分页类
            items = query.order_by(Route.id.desc()).all()
            if items is None:
                items = []

            per_page = 10
            total = len(items)
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1
            page = min(max(page, 1), total_pages)
            start = (page - 1) * per_page
            end = start + per_page

            pagination = Pagination(
                items=items[start:end],
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )

            return pagination, None

        except Exception as e:
            current_app.logger.error(f"Get routes error: {str(e)}")
            return Pagination(
                items=[],
                total=0,
                page=1,
                per_page=10,
                total_pages=1
            ), str(e)

    @staticmethod
    def add_route(data):
        """添加路由映射"""
        try:
            # 检查路径是否已存在
            if Route.query.filter_by(path=data['path']).first():
                return False, '路由路径已存在'

            # 创建新路由
            route = Route(
                path=data['path'],
                original_endpoint=data['endpoint'],
                description=data.get('description', ''),
                is_active=True
            )

            db.session.add(route)
            db.session.commit()

            # 刷新路由
            route_manager.refresh_routes()
            return True, '路由添加成功'

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Add route error: {str(e)}")
            return False, str(e)

    @staticmethod
    def update_route(route_id, data):
        """更新路由"""
        try:
            route = Route.query.get_or_404(route_id)
            if data['path'] != route.path and Route.query.filter_by(path=data['path']).first():
                return False, '路由路径已存在'

            route.path = data['path']
            route.description = data.get('description', '')
            route.is_active = data.get('is_active', '').lower() in ('true', 'on', '1', 'yes')
            db.session.commit()

            # 刷新路由
            route_manager.refresh_routes()
            return True, '路由更新成功'
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def delete_route(route_id):
        """删除路由"""
        try:
            route = Route.query.get_or_404(route_id)
            db.session.delete(route)
            db.session.commit()
            
            # 刷新路由
            route_manager.refresh_routes()
            return True, '路由删除成功'
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def toggle_route(route_id):
        """启用/禁用路由"""
        try:
            route = Route.query.get_or_404(route_id)
            route.is_active = not route.is_active
            db.session.commit()
            
            # 刷新路由
            route_manager.refresh_routes()
            return True, f'路由已{"启用" if route.is_active else "禁用"}'
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def get_available_endpoints():
        """获取所有可用的端点"""
        endpoints = []
        for rule in current_app.url_map.iter_rules():
            if not rule.endpoint.startswith('static') and not hasattr(rule, 'is_custom_route'):
                route = Route.query.filter_by(
                    original_endpoint=rule.endpoint, 
                    is_active=True
                ).first()
                if not route:
                    endpoints.append({
                        'endpoint': rule.endpoint,
                        'path': rule.rule,
                        'methods': list(rule.methods)
                    })
        return endpoints

    @staticmethod
    def refresh_custom_routes():
        """刷新自定义路由"""
        return route_manager.refresh_routes()

    @staticmethod
    def get_category(category_id):
        """获取单个分类信息"""
        try:
            category = Category.query.get_or_404(category_id)
            return True, None, {
                'id': category.id,
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'parent_id': category.parent_id,
                'sort_order': category.sort_order,
                'use_slug': category.use_slug,
                'template': category.template,
                'per_page': category.per_page  # 添加 per_page
            }
        except Exception as e:
            current_app.logger.error(f"Get category error: {str(e)}")
            return False, str(e), None

    @staticmethod
    def get_all_categories():
        """获取所有分类(用于移动类选择)"""
        try:
            # 获所有分类并按层级排序
            categories = Category.query.order_by(Category.sort_order).all()
            
            # 将分类对象转换为字典
            def category_to_dict(category):
                return {
                    'id': category.id,
                    'name': category.name,
                    'parent_id': category.parent_id,
                    'sort_order': category.sort_order
                }
            
            # 构建树形结构
            tree = []
            category_map = {category.id: category_to_dict(category) for category in categories}
            
            for category in categories:
                category_dict = category_map[category.id]
                if category.parent_id is None:
                    tree.append(category_dict)
                else:
                    parent = category_map.get(category.parent_id)
                    if parent:
                        if '_children' not in parent:
                            parent['_children'] = []
                        parent['_children'].append(category_dict)
            
            return tree, None
        except Exception as e:
            current_app.logger.error(f"Get all categories error: {str(e)}")
            return None, str(e)

    @staticmethod
    def update_comment_config(data):
        """更新评论配置"""
        try:
            config = CommentConfig.get_config()
            
            config.require_audit = data.get('require_audit') == 'true'
            config.require_email = data.get('require_email') == 'true'
            config.require_contact = data.get('require_contact') == 'true'
            config.allow_guest = data.get('allow_guest') == 'true'
             # 添加分页设置
            try:
                comments_per_page = int(data.get('comments_per_page', 10))
                config.comments_per_page = max(1, min(100, comments_per_page))  # 限制范围在1-100
            except (TypeError, ValueError):
                config.comments_per_page = 10  # 如果转换失败，使用默认值
            
            db.session.commit()
            # 清除相关缓存
            cache_manager.delete('comment_config')
            return True, '评论设置已更新'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update comment config error: {str(e)}")
            return False, f'更新失败: {str(e)}'

    @staticmethod
    def update_comment_status(comment_id, status):
        """更新评论状态"""
        try:
            comment = Comment.query.get_or_404(comment_id)
            comment.status = status
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete(f'article:{comment.article_id}:*')
            
            return True, '评论状态已更新'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update comment status error: {str(e)}")
            return False, f'更新失败: {str(e)}'

    @staticmethod
    def update_article_url_pattern(pattern_type, custom_pattern=None, encode_settings=None):
        """更新文章URL模式"""
        try:
            if pattern_type == 'custom':
                if not custom_pattern:
                    return False, '自定义模式需要提供模式字符串'
                pattern = custom_pattern
            else:
                pattern = SiteConfig.ARTICLE_URL_PATTERNS.get(pattern_type)
                if not pattern:
                    return False, '不支持的URL模式类型'
            
            # 更新配置
            config = SiteConfig.query.filter_by(key='article_url_pattern').first()
            if not config:
                config = SiteConfig(key='article_url_pattern')
                db.session.add(config)
            
            config.value = pattern
            
            # 如果有加密设置，更新加密配置
            if encode_settings:
                salt = encode_settings.get('salt')
                length = encode_settings.get('length')
                
                if salt:
                    salt_config = SiteConfig.query.filter_by(key='article_id_salt').first()
                    if not salt_config:
                        salt_config = SiteConfig(key='article_id_salt')
                        db.session.add(salt_config)
                    salt_config.value = salt
                
                if length:
                    length_config = SiteConfig.query.filter_by(key='article_id_length').first()
                    if not length_config:
                        length_config = SiteConfig(key='article_id_length')
                        db.session.add(length_config)
                    length_config.value = length
            
            db.session.commit()
            
            # 清除缓存
            cache_manager.delete('article_url_pattern')
            cache_manager.delete('article_id_salt')
            cache_manager.delete('article_id_length')
            cache_manager.delete('article_id_salt_hash')
            ArticleUrlGenerator.clear_cache()
            IdEncoder.clear_cache()
            
            return True, '文章URL模式更新成功'
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)

    @staticmethod
    def reload_plugin_list():
        """重新加载插件列表"""
        try:
            # 获取已安装插件目录
            installed_dir = os.path.join(current_app.root_path, 'plugins', 'installed')
            if not os.path.exists(installed_dir):
                return True, '没有发现新插件'
            
            # 获取已安装的插件目录列表
            installed_plugins = {p.directory for p in Plugin.query.all()}
            new_plugins = 0
            
            # 遍历插件目录
            for plugin_dir in os.listdir(installed_dir):
                # 跳过已安装的插件
                if plugin_dir in installed_plugins:
                    continue
                
                plugin_path = os.path.join(installed_dir, plugin_dir)
                if not os.path.isdir(plugin_path):
                    continue
                
                # 检查插件信息文件
                info_file = os.path.join(plugin_path, 'plugin.json')
                if not os.path.exists(info_file):
                    continue
                
                try:
                    # 读取插件信息
                    with open(info_file, 'r', encoding='utf-8') as f:
                        plugin_info = json.load(f)
                    
                    # 导入插件模块获取默认配置
                    module = import_module(f'app.plugins.installed.{plugin_dir}')
                    plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
                    plugin = plugin_class()
                    default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}
                    
                    # 添加到数据库
                    Plugin.add_plugin(
                        plugin_info, 
                        plugin_dir,
                        enabled=plugin_info.get('enabled', True),
                        config=default_config
                    )
                    
                    # 如果插件默认启用,立即加载它
                    if plugin_info.get('enabled', True):
                        plugin_manager.load_plugin(plugin_dir)
                    
                    new_plugins += 1
                    
                except Exception as e:
                    current_app.logger.error(f"Error loading plugin {plugin_dir}: {str(e)}")
                    continue
                
            db.session.commit()
            
            if new_plugins > 0:
                return True, f'发现并安装了 {new_plugins} 个新插件'
            return True, '没有发现新插件'
            
        except Exception as e:
            db.session.rollback()
            return False, f'重载插件列表失败: {str(e)}'

    @staticmethod
    def get_available_category_templates():
        """获取当前主题下可用的分类模板"""
        try:
            from app.models.site_config import SiteConfig
            current_theme = SiteConfig.get_config('site_theme', 'default')
            
            # 获取主题目录下的 category 文件夹
            category_dir = os.path.join(
                current_app.root_path,
                'templates',
                current_theme,
                'category'
            )
            
            templates = []
            if os.path.exists(category_dir):
                for file in os.listdir(category_dir):
                    if file.endswith('.html'):
                        # 只返回文件名，不包含路径
                        templates.append(file)
                    
            return templates
        except Exception as e:
            current_app.logger.error(f"Error getting category templates: {str(e)}")
            return []

    @staticmethod
    def batch_update_per_page(per_page):
        """批量更新分类的每页文章数"""
        try:
            # 验证输入
            per_page = max(1, min(100, int(per_page)))
            
            # 批量更新所有分类
            Category.query.update({Category.per_page: per_page})
            db.session.commit()
            
            # 清除缓存
            cache_manager.delete('admin:categories:*')
            cache_manager.delete('categories_*')
            
            return True, f'已将所有分类的每页文章数设置为 {per_page}'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch update per_page error: {str(e)}")
            return False, str(e)

    @staticmethod
    def save_article(article_id, form_data):
        """保存文章"""
        try:
            # 先回滚之前的事务
            db.session.rollback()
            
            with db.session.no_autoflush:
                # 获取表单数据
                title = form_data.get('title')
                content = form_data.get('content')
                status = form_data.get('status', Article.STATUS_PUBLIC)
                password = form_data.get('password', '')
                
                # 获取分类ID列表
                category_ids = form_data.getlist('categories')
                if not category_ids:
                    return False, '请至少选择一个分类', None
                
                # 获取标签
                tags = form_data.get('tag_names', '').strip()
                tag_names = [name.strip() for name in tags.split() if name.strip()]
                new_tags = []

                
                # 创建或更新文章
                if article_id:
                    article = Article.query.get_or_404(article_id)
                else:
                    article = Article(author_id=current_user.id)
                
                # 更新文章属性
                article.title = title
                article.content = content
                article.status = status
                article.password = password if status == Article.STATUS_PASSWORD else None
                article.allow_comment = form_data.get('allow_comment') == 'on'
                
                # 更新发布时间
                created_at = form_data.get('created_at')
                if created_at:
                    try:
                        article.created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        return False, '发布时间格式不正确', None
                elif not article_id:  # 新文章且未设置时间则使用当前时间
                    article.created_at = datetime.now()
                
                # 更新分类
                categories = Category.query.filter(Category.id.in_(category_ids)).all()
                if not categories:
                    return False, '无效的分类ID', None
                
                article.category_id = categories[0].id  # 第一个作为主分类
                article.categories = categories
                
                # 手动处理标签关联
                if article_id:
                    # 先清除所有现有的标签关联
                    db.session.execute(
                        article_tags.delete().where(
                            article_tags.c.article_id == article_id
                        )
                    )
                    db.session.flush()

                # 获取或创建标签
                for name in tag_names:
                    # 先查找是否已存在同名标签
                    tag = Tag.query.filter_by(name=name).first()
                    if tag:
                        # 如果标签已存在,直接使用
                        if tag not in new_tags:  # 避免同一标签添加多次
                            new_tags.append(tag)
                    else:
                        # 如果标签不存在,创建新标签
                        tag = Tag(name=name)
                        tag.slug = slugify(name)  # 设置 slug
                        db.session.add(tag)
                        db.session.flush()  # 立即执行以获取 id
                        new_tags.append(tag)

                # 设置新的标签
                article.tags = new_tags
                
                # 处理自定义字段
                try:
                    fields = json.loads(form_data.get('fields', '{}'))
                except:
                    fields = {}
                article.fields = fields
                
                # 处理 slug - 移到事务提交前
                slug = form_data.get('slug', '').strip()

                # 如果提供了自定义 slug
                if slug:
                    # 检查自定义 slug 唯一性
                    existing = Article.query.filter(
                        Article.slug == slug,
                        Article.id != article_id
                    ).first()
                    if existing:
                        return False, '你的自定义URL别名已被使用', None
                    article.slug = slug
                else:
                    # 自动生成 slug
                    base_slug = slugify(article.title)
                    slug = base_slug
                    counter = 1
                    
                    # 检查是否存在相同的 slug,如果存在则添加数字后缀
                    while Article.query.filter(
                        Article.slug == slug,
                        Article.id != article_id
                    ).first():
                        slug = f"{base_slug}-{counter}"
                        counter += 1
                    
                    article.slug = slug

                # 处理密码保护
                if article.status == Article.STATUS_PASSWORD:
                    article.password = form_data.get('password') or '123456'
                else:
                    article.password = None

                
                # 保存到数据库
                if not article_id:
                    db.session.add(article)
                
                # 提交事务
                db.session.commit()
                
                # 清除缓存
                from app.services.blog_service import BlogService
                BlogService.clear_article_related_cache(article.id)
                
                return True, '保存成功', article
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Save article error: {str(e)}")
            return False, str(e), None

    @staticmethod
    def get_article_for_edit(article_id):
        """获取要编辑的文章"""
        try:
            article = Article.query.options(
                db.joinedload(Article.author),
                db.joinedload(Article.tags),
                db.joinedload(Article.categories)
            ).get_or_404(article_id)
            
            # 返回文章和文件列表
            return article
        except Exception as e:
            current_app.logger.error(f"Get article for edit error: {str(e)}")
            return None

    @staticmethod
    def update_category_counts(category_ids=None):
        """更新分类文章数"""
        try:
            if not category_ids:
                return True, []
            
            # 使用 SQLAlchemy 查询分类文章数
            category_counts = db.session.query(
                Category.id,
                func.count(distinct(
                    func.coalesce(Article.id, article_categories.c.article_id)
                )).label('count')
            ).outerjoin(
                Article,
                Category.id == Article.category_id
            ).outerjoin(
                article_categories,
                Category.id == article_categories.c.category_id
            ).filter(
                Category.id.in_(category_ids)
            ).group_by(
                Category.id
            ).all()
            
            # 记录更新的分类
            updated = []
            
            # 更新每个分类的文章数
            for category_id, count in category_counts:
                category = Category.query.get(category_id)
                if category and (category.article_count is None or category.article_count != count):
                    category.article_count = count
                    updated.append({
                        'id': category.id,
                        'name': category.name,
                        'new_count': count
                    })
            
            db.session.commit()
            return True, updated
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update category counts error: {str(e)}")
            return False, str(e)

    @staticmethod
    def update_tag_counts(tag_ids=None):
        """更新标签文章数"""
        try:
            if not tag_ids:
                return True, []
            
            # 使用 SQLAlchemy 的方式查询标签文章数
            tag_counts = db.session.query(
                Tag.id,
                func.count(distinct(article_tags.c.article_id)).label('count')
            ).outerjoin(
                article_tags, 
                Tag.id == article_tags.c.tag_id
            ).filter(
                Tag.id.in_(tag_ids)
            ).group_by(
                Tag.id
            ).all()
            
            # 记录更新的标签
            updated = []
            
            # 更新每个标签的文章数
            for tag_id, count in tag_counts:
                tag = Tag.query.get(tag_id)
                if tag and (tag.article_count is None or tag.article_count != count):
                    tag.article_count = count
                    updated.append({
                        'id': tag.id,
                        'name': tag.name,
                        'new_count': count
                    })
            
            db.session.commit()
            return True, updated
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update tag counts error: {str(e)}")
            return False, str(e)

    @staticmethod
    def update_all_category_counts():
        """更新所有分类的文章计数"""
        try:
            # 获取所有分类
            categories = Category.query.all()
            updated = []
            
            for category in categories:
                # 计算文章数 - 修复 join 语句
                count = db.session.query(
                    func.count(distinct(
                        func.coalesce(Article.id, article_categories.c.article_id)
                    ))
                ).select_from(Category).filter(
                    Category.id == category.id
                ).outerjoin(
                    Article,
                    Category.id == Article.category_id
                ).outerjoin(
                    article_categories,
                    Category.id == article_categories.c.category_id
                ).scalar()
                
                # 如果计数有变化,更新并记录
                if category.article_count != count:
                    category.article_count = count
                    updated.append({
                        'id': category.id,
                        'name': category.name,
                        'new_count': count
                    })
            
            db.session.commit()
            return True, updated
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating all category counts: {str(e)}")
            return False, str(e)

    @staticmethod
    def update_all_tag_counts():
        """高性能更新所有标签的文章计数"""
        try:
            # 1. 创建子查询获取标签计数
            tag_counts = db.session.query(
                article_tags.c.tag_id.label('tag_id'),
                func.count(distinct(article_tags.c.article_id)).label('count')
            ).group_by(
                article_tags.c.tag_id
            ).subquery()

            # 2. 获取需要更新的标签
            updated_tags = db.session.query(Tag).outerjoin(
                tag_counts,
                Tag.id == tag_counts.c.tag_id
            ).filter(
                Tag.article_count != func.coalesce(tag_counts.c.count, 0)
            ).with_entities(
                Tag.id,
                Tag.name,
                func.coalesce(tag_counts.c.count, 0).label('new_count')
            ).all()

            if updated_tags:
                # 3. 使用正确的 case() 语法执行批量更新
                # 使用 coalesce 确保空值为 0
                stmt = update(Tag).values(
                    article_count=func.coalesce(
                        db.session.query(
                            func.count(distinct(article_tags.c.article_id))
                        ).filter(
                            article_tags.c.tag_id == Tag.id
                        ).as_scalar(),
                        0
                    )
                )
                db.session.execute(stmt)

                # 4. 提交事务
                db.session.commit()

                # 5. 返回更新的标签信息
                return True, [
                    {
                        'id': tag.id,
                        'name': tag.name,
                        'new_count': tag.new_count
                    } for tag in updated_tags
                ]

            return True, []
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating all tag counts: {str(e)}")
            return False, str(e)

    @staticmethod
    def batch_delete_articles(article_ids, user_id, is_admin=False):
        """批量删除文章"""
        try:
            # 查询要删除的文章
            query = Article.query.filter(Article.id.in_(article_ids))
            
            # 非管理员只能删除自己的文章
            if not is_admin:
                query = query.filter_by(author_id=user_id)
            
            articles = query.all()
            
            if not articles:
                return False, '没有找到可删除的文章'
                
            # 删除文章
            for article in articles:
                db.session.delete(article)
                
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch delete articles error: {str(e)}")
            return False, str(e)

    @staticmethod
    def batch_delete_comments(comment_ids):
        """批量删除评论"""
        try:
            # 查询要删除的评论
            comments = Comment.query.filter(Comment.id.in_(comment_ids)).all()
            
            if not comments:
                return False, '没有找到可删除的评论'
                
            # 删除评论
            for comment in comments:
                db.session.delete(comment)
                
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch delete comments error: {str(e)}")
            return False, str(e)

    @staticmethod
    def batch_set_tags_access_mode(mode):
        """批量设置标签访问方式
        Args:
            mode: 'slug' 或 'id'
        """
        try:
            if mode not in ['slug', 'id']:
                return False, '无效的访问方式'
                
            tags = Tag.query.all()
            for tag in tags:
                if mode == 'slug':
                    # 如果没有slug，使用名称生成
                    if not tag.slug:
                        tag.slug = slugify(tag.name)
                    tag.use_slug = True
                else:
                    tag.use_slug = False
                    
            db.session.commit()
            
            # 清除所有标签相关缓存
            cache_manager.delete('tag:*')
            
            return True, f'已将所有标签设置为使用{"缩略名" if mode == "slug" else "ID"}访问'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Batch set tags access mode error: {str(e)}")
            return False, str(e)

    @staticmethod
    def save_upload_settings(allowed_types, max_size):
        """保存上传设置
        Args:
            allowed_types (str): 允许的文件类型，如 '.jpg,.png'
            max_size (int): 最大上传大小(MB)
        Returns:
            tuple: (success, message)
        """
        try:
            # 更新允许的文件类型
            type_config = SiteConfig.query.filter_by(key='upload_allowed_types').first()
            if type_config:
                type_config.value = allowed_types
                
            # 更新最大上传大小
            size_config = SiteConfig.query.filter_by(key='upload_max_size').first()
            if size_config:
                size_config.value = str(max_size)
                
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete('site_config:*')
            
            return True, '上传设置已更新'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Save upload settings error: {str(e)}")
            return False, str(e)

    @staticmethod
    def rename_file(file_id, new_name):
        """重命名文件"""
        try:
            file = File.query.get_or_404(file_id)
            file.original_filename = new_name
            db.session.commit()
            return True, '文件名已更新'
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Rename file error: {str(e)}")
            return False, str(e)

    @staticmethod
    def admin_login(username, password, remember=False):
        """
        管理员登录
        :param username: 用户名
        :param password: 密码
        :param remember: 是否记住登录
        :return: (success, message, user)
        """
        try:
            user = User.query.filter_by(username=username).first()
            
            if not user:
                return False, "用户名或密码错误", None
                
            if user.role != 'admin':
                return False, "该账号没有管理权限", None
                
            if not check_password_hash(user.password_hash, password):
                return False, "用户名或密码错误", None
                
            # 登录用户
            login_user(user, remember=remember)
            return True, "登录成功", user
            
        except Exception as e:
            current_app.logger.error(f"Admin login error: {str(e)}")
            return False, "登录过程发生错误", None