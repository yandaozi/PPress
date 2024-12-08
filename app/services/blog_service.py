from app.models import Article, Category, Tag, Comment, ViewHistory, File, User, CommentConfig, SiteConfig
from app.models.article import article_tags, article_categories
from sqlalchemy import func
from datetime import datetime, timedelta

from app.models.article import article_categories
from app.utils.cache_manager import cache_manager
from app import db
import os
import hashlib
from flask import current_app, abort
import random
from app.utils.pagination import Pagination
import json


class BlogService:
    # 定义缓存过期时间常量
    CACHE_TIMES = {
        'INDEX': 3600,        # 首页缓存1小时
        'ARTICLE': 43200,     # 文章详情缓存12小时
        'HOT_TODAY': 600,     # 今日热门缓存10分钟
        'HOT_WEEK': 1800,     # 本周热门缓存30分钟
        'RANDOM': 300,        # 随机推荐缓存5分钟
        'TAGS': 3600,         # 标签缓存1小时
        'COMMENTS': 300,      # 评论缓存5分钟
        'SEARCH': 1800,       # 搜索结果缓存30分钟
        'CATEGORY': 3600      # 分类缓存1小时
    }

    @staticmethod
    def get_index_articles(page=1, category_id=None, user=None):
        """获取首页文章列表"""
        def query_articles():
            with db.session.no_autoflush:
                query = Article.query.options(
                    db.joinedload(Article.author),
                    db.joinedload(Article.category),
                    db.joinedload(Article.tags)
                )
                
                # 检查是否是管理员
                is_admin = user and hasattr(user, 'role') and user.role == 'admin'
                
                if is_admin:
                    # 管理员可以看到所有文章
                    pass
                elif user and hasattr(user, 'id'):
                    # 登录用户可以看到:
                    # 1. 所有公开文章
                    # 2. 自己的所有文章
                    query = query.filter(
                        db.or_(
                            Article.status == Article.STATUS_PUBLIC,  # 只显示公开文章
                            Article.author_id == user.id  # 显示自己的所有文章
                        )
                    )
                else:
                    # 未登录用户只能看到公开文章
                    query = query.filter(Article.status == Article.STATUS_PUBLIC)

                # 分类过滤
                if category_id:
                    query = query.filter(Article.category_id == category_id)
                    
                return query.order_by(Article.id.desc(), Article.created_at.desc())\
                           .paginate(page=page, per_page=10, error_out=False)
                       
        return cache_manager.get(f'index:articles:{page}:{category_id}', 
                               query_articles, 
                               ttl=BlogService.CACHE_TIMES['INDEX'])

    @staticmethod
    def get_category_articles(category_id, page=1, user=None):
        """获取分类文章列表"""
        def query_articles():
            # 尝试通过 id 或 slug 获取分类
            try:
                # 尝试将 id 转换为整数
                id_num = int(category_id)
                category = Category.query.get_or_404(id_num)
                # 如果设置为使用 slug 访问但使用 ID 访问，返回 404
                if category.use_slug:
                    abort(404)
            except ValueError:
                # 如果转换失败，则通过 slug 查找
                category = Category.query.filter_by(slug=category_id).first_or_404()
                # 如果设置为使用 ID 访问但使用 slug 访问，返回 404
                if not category.use_slug:
                    abort(404)
            
            # 构建查询
            query = Article.query.options(
                db.joinedload(Article.author),
                db.joinedload(Article.tags)
            )
            
            # 检查是否是管理员
            is_admin = user and hasattr(user, 'role') and user.role == 'admin'
            
            if is_admin:
                # 管理员可以看到所有文章
                pass
            elif user and hasattr(user, 'id'):
                # 登录用户可以看到:
                # 1. 所有公开文章
                # 2. 自己的所有文章
                query = query.filter(
                    db.or_(
                        Article.status == Article.STATUS_PUBLIC,  # 只显示公开文章
                        Article.author_id == user.id  # 显示自己的所有文章
                    )
                )
            else:
                # 未登录用户只能看到公开文章
                query = query.filter(Article.status == Article.STATUS_PUBLIC)
            
            # 使用 union 合并主分类和多分类的文章
            main_category_articles = query.filter(Article.category_id == category.id)
            multi_category_articles = query.join(article_categories).filter(article_categories.c.category_id == category.id)
            
            # 合并查询结果
            combined_query = main_category_articles.union(multi_category_articles)
            
            # 获取分页数量 - 优先使用分类设置的值
            per_page = category.per_page or 10  # 如果未设置则使用默认值10
            
            # 排序和分页
            paginated = combined_query\
                .order_by(Article.created_at.desc())\
                .paginate(page=page, per_page=per_page, error_out=False)
            
            # 获取分类的自定义模板
            template = None
            if category.template:
                # 构建完整的模板路径
                template = f'category/{category.template}'
                # 检查模板是否存在
                template_path = os.path.join(
                    current_app.root_path,
                    'templates',
                    SiteConfig.get_config('site_theme', 'default'),
                    template
                )
                if not os.path.exists(template_path):
                    template = None
            
            # 如果没有自定义模板或模板不存在，使用默认模板
            if not template:
                template = 'blog/index.html'
            
            return {
                'pagination': paginated,
                'current_category': category,
                'template': template  # 返回模板信息
            }
        
        return cache_manager.get(
            f'category:{category_id}:page:{page}', 
            query_articles,
            ttl=BlogService.CACHE_TIMES['CATEGORY']
        )

    @staticmethod
    def get_article_detail(article_id, password=None, user=None):
        """获取文章详"""
        try:
            article = Article.query.options(
                db.joinedload(Article.author),
                db.joinedload(Article.tags),
                db.joinedload(Article.categories)
            ).get_or_404(article_id)
            
            # 如果文章没有任何分类，添加到默认分类
            if not article.category and not article.categories:
                default_category = Category.query.get(1)
                if default_category:
                    article.category = default_category
                    article.categories.append(default_category)
                    db.session.commit()
            
            # 检查是否是管理员或作者
            is_admin = user and hasattr(user, 'role') and user.role == 'admin'
            is_author = user and hasattr(user, 'id') and article.author_id == user.id
            
            # 如果是管理员或作者，直接返回文章
            if is_admin or is_author:
                # 获取评论数据
                article.comment_data = BlogService.get_article_comments(article_id, user)
                return article
            
            # 如果是待审核、私密或草稿文章，返回错误
            if article.status in [Article.STATUS_PENDING, Article.STATUS_PRIVATE, Article.STATUS_DRAFT]:
                return {'error': '您没有权限访问此文章'}
            
            # 如果是密码保护的文章
            if article.status == Article.STATUS_PASSWORD:
                if not password:
                    return {'need_password': True, 'article': article}
                if password != article.password:
                    return {'error': '密码错误', 'need_password': True, 'article': article}
                # 密码正确，获取评论数据并返回章
                article.comment_data = BlogService.get_article_comments(article_id, user)
                return article
            
            # 如果是公开或隐藏文章允许访问
            if article.status in [Article.STATUS_PUBLIC, Article.STATUS_HIDDEN]:
                # 获取评论数据
                article.comment_data = BlogService.get_article_comments(article_id, user)
                return article
            
            # 其他情况返回错误
            return {'error': '您没有权限访问此文章'}
            
        except Exception as e:
            current_app.logger.error(f"Get article detail error: {str(e)}")
            abort(404)

    @staticmethod
    def get_hot_articles_today():
        """获取今日热门文章"""
        def query_hot():
            today = datetime.now().date()
            views_subquery = db.session.query(
                ViewHistory.article_id,
                func.count(ViewHistory.id).label('views')
            ).filter(
                func.date(ViewHistory.viewed_at) == today
            ).group_by(ViewHistory.article_id)\
             .subquery()
            
            # 只获取存在的公开文章
            return db.session.query(Article, views_subquery.c.views)\
                .join(views_subquery, Article.id == views_subquery.c.article_id)\
                .filter(Article.status == Article.STATUS_PUBLIC)\
                .options(db.joinedload(Article.author))\
                .order_by(views_subquery.c.views.desc())\
                .limit(5)\
                .all()
                
        return cache_manager.get('hot_articles:today', 
                               query_hot,
                               ttl=BlogService.CACHE_TIMES['HOT_TODAY'])

    @staticmethod
    def get_hot_articles_week():
        """获取本周热门文章"""
        def query_hot():
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            views_subquery = db.session.query(
                ViewHistory.article_id,
                func.count(ViewHistory.id).label('views')
            ).filter(
                func.date(ViewHistory.viewed_at) >= week_start
            ).group_by(ViewHistory.article_id)\
             .subquery()
            
            # 只获取存在的公开文章
            return db.session.query(Article, views_subquery.c.views)\
                .join(views_subquery, Article.id == views_subquery.c.article_id)\
                .filter(Article.status == Article.STATUS_PUBLIC)\
                .options(db.joinedload(Article.author))\
                .order_by(views_subquery.c.views.desc())\
                .limit(5)\
                .all()
                
        return cache_manager.get('hot_articles:week', 
                               query_hot,
                               ttl=BlogService.CACHE_TIMES['HOT_WEEK'])

    @staticmethod
    def get_random_articles():
        """获取随机推荐文章"""
        def query_random():
            count = Article.query.count()
            if count < 5:
                return Article.query.all()
            ids = random.sample(range(1, count + 1), min(5, count))
            return Article.query\
                .options(db.joinedload(Article.author))\
                .filter(Article.id.in_(ids))\
                .all()
                
        return cache_manager.get('random_articles', 
                               query_random,
                               ttl=BlogService.CACHE_TIMES['RANDOM'])

    @staticmethod
    def get_random_tags():
        """获取随机标签"""
        def query_tags():
            count = Tag.query.count()
            if count < 10:
                return Tag.query.all()
            ids = random.sample(range(1, count + 1), min(10, count))
            return Tag.query.filter(Tag.id.in_(ids)).all()
                
        return cache_manager.get('random_tags', 
                               query_tags,
                               ttl=BlogService.CACHE_TIMES['TAGS'])

    @staticmethod
    def get_latest_comments():
        """获取最新评论"""
        def query_comments():
            return db.session.query(Comment, User, Article)\
                .join(User, Comment.user_id == User.id)\
                .join(Article, Comment.article_id == Article.id)\
                .order_by(Comment.created_at.desc())\
                .limit(10)\
                .all()
                
        return cache_manager.get('latest_comments', 
                               query_comments,
                               ttl=BlogService.CACHE_TIMES['COMMENTS'])
    
    @staticmethod
    def record_view(user_id, article_id):
        """记录文章浏览"""
        view = ViewHistory(user_id=user_id, article_id=article_id)
        db.session.add(view)
        
        # 更新浏览次数
        article = Article.query.get(article_id)
        article.view_count += 1
        db.session.commit()
    
    @staticmethod
    def search_articles(query, page=1, selected_tags=None, sort='recent'):
        """搜索文章"""
        def do_search():
            # 构建基础查询
            base_query = Article.query.options(
                db.joinedload(Article.author),
                db.joinedload(Article.category)
            )
            
            # 搜索标题
            base_query = base_query.filter(Article.title.ilike(f'%{query}%'))
            
            # 标签过滤
            if selected_tags:
                tag_subquery = db.session.query(Article.id)\
                    .join(Article.tags)\
                    .filter(Tag.name.in_(selected_tags))\
                    .group_by(Article.id)\
                    .having(db.func.count(Tag.id) == len(selected_tags))\
                    .subquery()
                base_query = base_query.filter(Article.id.in_(tag_subquery))
            
            # 排序处理
            if sort == 'views':
                base_query = base_query.order_by(Article.view_count.desc())
            elif sort == 'comments':
                comment_counts = db.session.query(
                    Article.id,
                    db.func.count(Comment.id).label('comment_count')
                ).outerjoin(Comment)\
                 .group_by(Article.id)\
                 .subquery()
                
                base_query = base_query.outerjoin(
                    comment_counts,
                    Article.id == comment_counts.c.id
                ).order_by(db.desc(comment_counts.c.comment_count))
            else:  # recent
                base_query = base_query.order_by(Article.created_at.desc())
            
            return base_query.paginate(page=page, per_page=10, error_out=False)
            
        # 生成缓存键，包含所有搜索参数
        cache_key = f'search:{query}:tags:{"-".join(sorted(selected_tags or []))}:sort:{sort}:page:{page}'
        return cache_manager.get(cache_key, do_search, ttl=BlogService.CACHE_TIMES['SEARCH'])

    @staticmethod
    def get_tag_articles(tag_id, page=1):
        """获取标签下的文章"""
        def query_tag_articles():
            return Article.query.options(
                db.joinedload(Article.author),
                db.joinedload(Article.category)
            ).filter(Article.tags.any(Tag.id == tag_id))\
             .order_by(Article.created_at.desc())\
             .paginate(page=page, per_page=10, error_out=False)
            
        return cache_manager.get(f'tag:{tag_id}:articles:{page}', query_tag_articles)
    
    @staticmethod
    def get_tag_info(tag_id):
        """获取标签信息"""
        return cache_manager.get(
            f'tag:{tag_id}',
            lambda: Tag.query.get_or_404(tag_id)
        )
    
    @staticmethod
    def get_article_comments(article_id, user=None, page=1):
        """获取文章评论"""
        try:
            config = CommentConfig.get_config()
            is_admin = user and hasattr(user, 'role') and user.role == 'admin'
            
            # 1. 获取所有评论
            comments = Comment.query.filter(
                Comment.article_id == article_id
            ).order_by(Comment.created_at.asc()).all()
            
            # 2. 先收集所有评论的ID和状态
            comment_map = {}
            parent_comments = []
            
            # 3. 第一次遍历：收集所有评论
            for comment in comments:
                # 跳过未审核的评论（非管理员）
                if not is_admin and comment.status != 'approved':
                    continue
                
                # 将评论添加到映射中
                comment_map[comment.id] = comment
                comment.replies = []
                
                # 如果是父评论（parent_id 为 None 或空字符串）
                if not comment.parent_id:
                    parent_comments.append(comment)
            
            # 4. 第二次遍历：处理回复
            for comment in comments:
                if not is_admin and comment.status != 'approved':
                    continue
                    
                if comment.parent_id and comment.parent_id in comment_map:
                    parent = comment_map[comment.parent_id]
                    parent.replies.append(comment)
            
            # 5. 对父评论按时间倒序排序
            parent_comments.sort(key=lambda x: x.created_at, reverse=True)
            
            # 6. 对每个父评论的回复进行排序
            for parent in parent_comments:
                parent.replies.sort(key=lambda x: x.created_at)
            
            # 7. 进行分页
            per_page = config.comments_per_page
            total = len(parent_comments)
            total_pages = (total + per_page - 1) // per_page
            start = (page - 1) * per_page
            end = start + per_page
            paginated_comments = parent_comments[start:end]
            
            # 创建分页对象
            return Pagination(
                items=paginated_comments,
                total=total,
                page=page,
                per_page=per_page,
                total_pages=total_pages
            )
            
        except Exception as e:
            current_app.logger.error(f"Get article comments error: {str(e)}")
            return None
    
    @staticmethod
    def add_comment(article_id, user_id, data):
        """添加评论"""
        try:
            # 获取文章
            article = Article.query.get_or_404(article_id)
            if not article.allow_comment:
                return False, '该文章已关闭评论功能'
            
            # 获取评论配置
            config = CommentConfig.get_config()
            
            # 添加调试日志
            current_app.logger.info(f"Adding comment for article {article_id}, user {user_id}")
            current_app.logger.info(f"Comment config - require_audit: {config.require_audit}")
            
            # 创建评论
            status = 'pending' if config.require_audit else 'approved'
            current_app.logger.info(f"New comment status will be: {status}")
            
            comment = Comment(
                content=data['content'].strip(),
                article_id=article_id,
                user_id=user_id,
                guest_name=data.get('guest_name'),
                guest_email=data.get('guest_email'),
                guest_contact=data.get('guest_contact'),
                parent_id=data.get('parent_id'),
                reply_to_id=data.get('reply_to_id'),
                status=status
            )
            
            db.session.add(comment)
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete(f'article:{article_id}:*')
            cache_manager.delete('latest_comments')
            
            return True, '评论发表成功' + ('，等待审核' if config.require_audit else '')
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Add comment error: {str(e)}")
            return False, f'评论失败: {str(e)}'
    
    @staticmethod
    def delete_comment(comment_id, user_id, is_admin=False):
        """删除评论"""
        try:
            comment = Comment.query.get_or_404(comment_id)
            
            # 检查权限
            if not is_admin and comment.user_id != user_id:
                return False, '没有权限删除此评论'
            
            # 删除评论及其所有回复
            Comment.query.filter(
                db.or_(
                    Comment.id == comment_id,
                    Comment.parent_id == comment_id
                )
            ).delete()
            
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete(f'article:{comment.article_id}:*')
            
            return True, '评论删除成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Delete comment error: {str(e)}")
            return False, f'删除失败: {str(e)}'
    
    @staticmethod
    def edit_article(article_id, data, user_id, is_admin=False):
        """编辑文章"""
        try:
            # 验证必填字段
            required_fields = ['title', 'content']
            for field in required_fields:
                if not data.get(field):
                    return False, f'请填写{field}字段', None

            # 验分类
            category_ids = data.getlist('categories')  # 获取多个分类ID
            if not category_ids:
                return False, '请至少选择一个分类', None
            
            # 验证分类ID的有效性
            try:
                category_ids = [int(cid) for cid in category_ids]
                categories = Category.query.filter(Category.id.in_(category_ids)).all()
                if len(categories) != len(category_ids):
                    return False, '无效的分类ID', None
            except (ValueError, TypeError):
                return False, '分类ID必须是数字', None

            # 获取或创建文章
            if article_id:
                article = Article.query.get_or_404(article_id)
                if not is_admin and article.author_id != user_id:
                    return False, '没有权限编辑此文章', None
            else:
                article = Article(author_id=user_id)
                db.session.add(article)

            # 记录原始状态
            old_status = article.status if article_id else None

            # 更新文章状态
            new_status = data.get('status', Article.STATUS_PUBLIC)
            article.status = new_status

            # 更新本信息
            article.title = data['title'].strip()
            article.content = data['content']
            
            # 更新发布时间
            created_at = data.get('created_at')
            if created_at:
                try:
                    article.created_at = datetime.strptime(created_at, '%Y-%m-%dT%H:%M')
                except ValueError:
                    return False, '发布时间格式不正确', None
            elif not article_id:  # 新文章且未设置时间则使用当前时间
                article.created_at = datetime.now()
            
            # 更新分类关联
            article.categories = categories
            # 设置主分类（使用第一个选的类作为主分类）
            article.category_id = categories[0].id if categories else None
            
            # 新文章状态
            article.status = data.get('status', Article.STATUS_PUBLIC)
            if article.status == Article.STATUS_PASSWORD:
                # 如果密码为空，使用默认密码
                article.password = data.get('password') or '123456'
            else:
                article.password = None
            
            # 更新评论设置
            article.allow_comment = data.get('allow_comment') == 'on'
            
            # 处理标签
            tag_names = [name.strip() for name in data.get('tag_names', '').split() if name.strip()]
            new_tags = []
            
            # 获取或创建标签
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                new_tags.append(tag)
            
            try:
                # 手动处理标签关联
                if article_id:
                    # 先清除所有现有的标签关联
                    db.session.execute(
                        article_tags.delete().where(
                            article_tags.c.article_id == article_id
                        )
                    )
                    db.session.flush()
                
                # 设置新的标签
                article.tags = new_tags
                db.session.flush()
                
            except Exception as e:
                current_app.logger.error(f"Error updating article tags: {str(e)}")
                db.session.rollback()
                return False, f'更新标签失败: {str(e)}', None
            
            # 处理自定义字段
            try:
                fields = json.loads(data.get('fields', '{}'))
                if isinstance(fields, dict):  # 确保是字典类型
                    article.fields = fields
                else:
                    article.fields = {}
            except (json.JSONDecodeError, TypeError):
                article.fields = {}  # 如果解析失败,使用空字典
            
            db.session.commit()
            
            # 清除相关缓存
            BlogService.clear_article_related_cache(article.id)
            cache_manager.delete(f'user:{user_id}:articles:*')
            cache_manager.delete('routes_last_refresh')
            
            # 生成URL并返回
            from app.utils.article_url import ArticleUrlGenerator
            return True, '文章保存成功', {
                'id': article.id,
                'url': ArticleUrlGenerator.generate(
                    article.id,  # 直接传递参数,不使用关键字参数
                    article.category_id,
                    article.created_at
                ),
                'message': '文章保存成功'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Save article error: {str(e)}")
            return False, f'保存失败: {str(e)}', None
    
    @staticmethod
    def get_tag_suggestions(query):
        """获取标签建议"""
        def query_tags():
            return Tag.query.filter(
                Tag.name.ilike(f'%{query}%')
            ).order_by(Tag.article_count.desc()).limit(10).all()
            
        return cache_manager.get(f'tag_suggestions:{query}', query_tags)
    
    @staticmethod
    def upload_image(file, user_id):
        """上传图片"""
        try:
            # 生成文件内容的 MD5 哈希值
            file_content = file.read()
            file_hash = hashlib.md5(file_content).hexdigest()
            file.seek(0)  # 重置文件指针
            
            # 检查是否存在相同的文件
            existing_file = File.query.filter_by(md5=file_hash).first()
            if existing_file:
                return True, existing_file.file_path
            
            # 生成期路径和文件名
            date_path = datetime.now().strftime('%Y%m%d')
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{file_hash}.{file_ext}"
            
            # 创建目录
            upload_folder = os.path.join(current_app.static_folder, 'uploads', 'images', date_path)
            os.makedirs(upload_folder, exist_ok=True)
            
            # 保存文件
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # 使用相对路径
            relative_path = f'/static/uploads/images/{date_path}/{filename}'
            
            # 保存文件信息到数据库
            db_file = File(
                filename=filename,
                original_filename=file.filename,
                file_path=relative_path,
                file_type='images/'+file_ext,
                file_size=os.path.getsize(file_path),
                md5=file_hash,
                uploader_id=user_id
            )
            db.session.add(db_file)
            db.session.commit()
            
            return True, relative_path
            
        except Exception as e:
            db.session.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            return False, str(e)
    
    @staticmethod
    def delete_article(article_id, user_id, is_admin=False):
        """删除文章"""
        try:
            article = Article.query.get_or_404(article_id)
            
            # 权限检查
            if article.author_id != user_id and not is_admin:
                return False, '没有权限删除此文章'
            
            # 删除文章
            db.session.delete(article)
            db.session.commit()
            
            # 清除相关缓存
            BlogService.clear_article_related_cache(article_id)
            # 清除用户章列表缓存
            cache_manager.delete(f'user:{user_id}:articles:*')
            
            return True, '文章已删除'
            
        except Exception as e:
            db.session.rollback()
            return False, f'删除失败: {str(e)}'
    
    @staticmethod
    def clear_article_related_cache(article_id):
        """清除文章相关的所有缓存"""
        try:
            # 获取文章信息以清除相关类缓存
            article = Article.query.options(
                db.joinedload(Article.categories)
            ).get(article_id)
            
            # 基础缓存式
            cache_patterns = [
                f'article:{article_id}*',     # 所有用户的文章详情缓存（注意*前不加:）
                'index:articles:*',           # 首页文章列表缓存
                'hot_articles:*',             # 热门文章缓存
                'random_articles',            # 随机文章缓存
                'search:*',                   # 搜索结果缓存
                'tag:*',                      # 标签相关缓存
                'search_suggestions:*',       # 搜索建议缓存
                'search_tags:*'               # 搜索标签缓存
            ]
            
            # 添加分类相关缓存
            if article:
                for category in article.categories:
                    cache_patterns.append(f'category:{category.id}:*')
                    # 清除父分类缓存
                    parent = category.parent
                    while parent:
                        cache_patterns.append(f'category:{parent.id}:*')
                        parent = parent.parent
            
            # 批量清除缓存
            for pattern in cache_patterns:
                current_app.logger.info(f"Clearing cache pattern: {pattern}")  # 添加日志
                cache_manager.delete(pattern)
            
        except Exception as e:
            current_app.logger.error(f"Error clearing article cache: {str(e)}")
    
    @staticmethod
    def get_search_suggestions(query):
        """获取搜索建议"""
        def query_suggestions():
            return Article.query.with_entities(Article.title)\
                .filter(Article.title.ilike(f'%{query}%'))\
                .order_by(Article.view_count.desc())\
                .limit(5)\
                .all()
            
        return cache_manager.get(f'search_suggestions:{query}', 
                               query_suggestions,
                               ttl=BlogService.CACHE_TIMES['SEARCH'])
    
    @staticmethod
    def get_search_tags(query):
        """获取搜索相关标签"""
        def query_tags():
            return Tag.query.join(Article.tags)\
                .filter(Article.title.ilike(f'%{query}%'))\
                .distinct()\
                .order_by(Tag.article_count.desc())\
                .all()
                
        return cache_manager.get(f'search_tags:{query}', 
                               query_tags,
                               ttl=BlogService.CACHE_TIMES['SEARCH'])
    
    @staticmethod
    def warmup_cache():
        """预热常用缓存"""
        warmup_keys = {
            'index:articles:1': lambda: BlogService.get_index_articles(1),
            'hot_articles:today': lambda: BlogService.get_hot_articles_today(),
            'hot_articles:week': lambda: BlogService.get_hot_articles_week(),
            'random_articles': lambda: BlogService.get_random_articles(),
            'random_tags': lambda: BlogService.get_random_tags(),
            'latest_comments': lambda: BlogService.get_latest_comments()
        }
        cache_manager.warmup(warmup_keys)

    @staticmethod
    def get_article_for_edit(article_id, user):
        """获取用于编辑的文章"""
        article = Article.query.options(
            db.joinedload(Article.author),
            db.joinedload(Article.tags),
            db.joinedload(Article.categories),
            db.joinedload(Article.comments).joinedload(Comment.user)
        ).get_or_404(article_id)
        
        # 检查编辑权限
        if not user or (user.role != 'admin' and article.author_id != user.id):
            abort(403, '您没有权限编辑此文章')
        
        return article

    @staticmethod
    def get_sidebar_data(widgets=None):
        """获取侧边栏数据
        Args:
            widgets: 需要获取的组件列表,如 ['hot_today', 'hot_week']
        """
        if not widgets:
            return {}
        
        # 定义组件与获取方法的映射
        widget_map = {
            'hot_today': ('hot_articles_today', BlogService.get_hot_articles_today),
            'hot_week': ('hot_articles_week', BlogService.get_hot_articles_week),
            'random_articles': ('random_articles', BlogService.get_random_articles),
            'random_tags': ('random_tags', BlogService.get_random_tags),
            'latest_comments': ('latest_comments', BlogService.get_latest_comments)
        }
        
        # 使用字典推导式获取数据
        return {
            widget_map[widget][0]: widget_map[widget][1]()
            for widget in widgets
            if widget in widget_map
        }
