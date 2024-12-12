import os
from flask import render_template, current_app, request, abort
from flask_login import login_required, current_user

from app import db
from app.models import CustomPage, Comment
from app.models.site_config import SiteConfig
from app.utils.cache_manager import cache_manager
from app.models.comment_config import CommentConfig
from app.utils.pagination import Pagination

class CustomPageMiddleware:
    def __init__(self, wsgi_app, flask_app):
        self.wsgi_app = wsgi_app
        self.flask_app = flask_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '').split('?')[0]  # 移除查询参数
        
        # 检查是否匹配自定义页面路由
        custom_pages = self.flask_app.config.get('CUSTOM_PAGES', {})
        if path in custom_pages:
            # 找到匹配的页面,重定向到内部处理函数
            environ['PATH_INFO'] = f'/custom_page/{custom_pages[path]}'
            environ['HTTP_X_CUSTOM_PAGE'] = 'true'
            # 保留原始路径用于分页
            environ['HTTP_X_ORIGINAL_PATH'] = path
                
        return self.wsgi_app(environ, start_response)

def render_custom_page(page):
    """渲染自定义页面"""
    try:
        # 获取当前主题
        current_theme = SiteConfig.get_config('site_theme', 'default')
        
        # 使用 os.path.join 构建完整路径
        template_file = os.path.abspath(os.path.join(
            current_app.root_path,
            'templates',
            current_theme,
            'custom',
            page.template
        ))
        
        # 用于 render_template 的相对路径
        template_path = f'{current_theme}/custom/{page.template}'

        
        # 如果当前主题下没有该模板，直接报错
        if not os.path.exists(template_file):
            current_app.logger.error(f"Template not found: {template_path}")
            current_app.logger.error(f"Checked path: {template_file}")
            abort(404)
            
        # 获取评论配置
        comment_config = CommentConfig.get_config()
        
        # 获取当前页码
        current_page = request.args.get('page', 1, type=int)
        
        # 获取原始路径（用于分页）
        original_path = request.environ.get('HTTP_X_ORIGINAL_PATH', page.route)
        
        # 如果是管理后台的请求，不使用缓存
        if request.endpoint and request.endpoint.startswith('admin.'):
            return _render_template(page, comment_config=comment_config)
            
        # 获取用户状态
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                user_state = 'admin'
            else:
                user_state = 'user'
        else:
            user_state = 'guest'
            
        # 使用缓存获取页面数据
        cache_key = f'custom_page_data:{page.key}:{user_state}:{current_page}'
        page_data = cache_manager.get(cache_key)
        
        if page_data is None:
            # 获取评论数据并分页
            comments_query = Comment.query.filter_by(
                custom_page_id=page.id
            ).order_by(Comment.created_at.desc())
            
            # 非管理员只能看到已审核的评论
            if not (current_user.is_authenticated and current_user.role == 'admin'):
                comments_query = comments_query.filter_by(status='approved')
            
            # 获取评论及其回复
            comments = comments_query.options(
                db.joinedload(Comment.user),
                db.joinedload(Comment.parent),
                db.joinedload(Comment.reply_to)
            ).paginate(
                page=current_page,
                per_page=comment_config.comments_per_page,
                error_out=False
            )
            
            # 准备页面数据
            page_data = dict(
                title=page.title,
                content=page.content,
                created_at=page.created_at,
                updated_at=page.updated_at,
                fields=page.fields,
                template=page.template,
                allow_comment=page.allow_comment,
                key=page.key,
                route=page.route,
                id=page.id
            )
            
            # 缓存页面数据
            cache_manager.set(cache_key, page_data)
            
        # 重新获取评论分页数据（因为分页对象不能被缓存）
        # 1. 获取所有评论
        comments = Comment.query.filter(
            Comment.custom_page_id == page.id
        ).order_by(Comment.created_at.asc()).all()
        
        # 2. 先收集所有评论的ID和状态
        comment_map = {}
        parent_comments = []
        
        # 3. 第一次遍历：收集所有评论
        for comment in comments:
            # 跳过未审核的评论（非管理员）
            if not (current_user.is_authenticated and current_user.role == 'admin'):
                if comment.status != 'approved':
                    continue
            
            # 将评论添加到映射中
            comment_map[comment.id] = comment
            comment.replies = []
            
            # 如果是父评论
            if not comment.parent_id:
                parent_comments.append(comment)
        
        # 4. 第二次遍历：处理回复
        for comment in comments:
            if comment.parent_id and comment.id in comment_map:
                parent = comment_map.get(comment.parent_id)
                if parent:
                    parent.replies.append(comment)
        
        # 5. 对父评论按时间倒序排序
        parent_comments.sort(key=lambda x: x.created_at, reverse=True)
        
        # 6. 对每个父评论的回复按时间正序排序
        for parent in parent_comments:
            parent.replies.sort(key=lambda x: x.created_at)
        
        # 7. 创建分页对象
        per_page = comment_config.comments_per_page
        total = len(parent_comments)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        start = (current_page - 1) * per_page
        end = start + per_page
        
        comments = Pagination(
            items=parent_comments[start:end],
            total=total,
            page=current_page,
            per_page=per_page,
            total_pages=total_pages
        )
        
        # 在渲染模板时传入当前主题信息
        return render_template(template_path,
                             page=page_data if page_data else page,
                             comment_config=comment_config,
                             comment_data=comments,
                             original_path=original_path,
                             current_theme=current_theme)
            
    except Exception as e:
        current_app.logger.error(f"Render custom page error: {str(e)}")
        abort(404)  # 出错时直接返回404，不再尝试使用默认模板

def _render_template(page, page_data=None, comment_config=None):
    """渲染模板"""
    try:
        # 获取当前主题
        current_theme = SiteConfig.get_config('site_theme', 'default')
        template_path = f'{current_theme}/custom/{page.template}'
        template_file = os.path.join(current_app.template_folder, current_theme, 'custom', page.template)
        
        # 如果当前主题下没有该模板，直接报错
        if not os.path.exists(template_file):
            current_app.logger.error(f"Template not found: {template_path}")
            abort(404)
        
        # 准备模板上下文
        context = {
            'page': page_data if page_data else page,
            'comment_config': comment_config or CommentConfig.get_config(),
            'current_theme': current_theme  # 添加当前主题信息
        }
        
        return render_template(template_path, **context)
        
    except Exception as e:
        current_app.logger.error(f"Render template error: {str(e)}")
        abort(404)  # 出错时直接返回404

class CustomPageManager:
    @staticmethod
    def get_custom_templates():
        """获取自定义页面模板列表"""
        templates = []
        theme_path = os.path.join(current_app.root_path, 'templates')
        current_theme = SiteConfig.get_config('site_theme', 'default')

        # 获取当前主题模板
        theme_custom_path = os.path.join(theme_path, f'{current_theme}/custom')

        if os.path.exists(theme_custom_path):
            for file in os.listdir(theme_custom_path):
                print(f"- {file}")
                if file.endswith('.html'):
                    templates.append({
                        'name': file.replace('.html', '').title(),
                        'path': file
                    })
        else:
            print("目录不存在!")

        return templates

    @staticmethod
    def init_custom_pages(app):
        """初始化所有自定义页面路由"""
        print("\n开始初始化自定义页面路由...")
        
        try:
            # 注册中间件
            app.wsgi_app = CustomPageMiddleware(app.wsgi_app, app)
            
            # 初始化路由映射
            with app.app_context():
                pages = CustomPage.query.filter_by(enabled=True).all()
                app.config['CUSTOM_PAGES'] = {p.route: p.key for p in pages}
                print(f"ok 已加载 {len(pages)} 个自定义页面路由")
            
            # 注册内部处理路由
            @app.route('/custom_page/<path:page_key>')
            def handle_custom_page(page_key):
                # 检查是否是通过中间件重定向的请求
                if not request.environ.get('HTTP_X_CUSTOM_PAGE'):
                    return abort(404)
                    
                page = CustomPage.query.filter_by(key=page_key, enabled=True).first_or_404()
                if page.require_login:
                    return login_required(lambda: render_custom_page(page))()
                return render_custom_page(page)
                
            print("ok 自定义页面路由初始化完成\n")
            
        except Exception as e:
            try:
                print(f"X 初始化自定义页面路由失败: {str(e)}\n")
            except UnicodeEncodeError as ex:
                # 这里可以选择将特殊字符替换掉等操作，比如简单替换为空字符串
                print(f" 初始化自定义页面路由失败: {str(e).encode('gbk', 'replace').decode('gbk')}\n")
            app.logger.error(f"Error initializing custom pages: {str(e)}")

    @staticmethod
    def add_page_route(app, page):
        """添加单个页面路由"""
        try:
            # 更新路由映射
            with app.app_context():
                pages = CustomPage.query.filter_by(enabled=True).all()
                app.config['CUSTOM_PAGES'] = {p.route: p.key for p in pages}
            print(f"ok 已更新路由映射: {page.route} -> {page.key}")
        except Exception as e:
            print(f"x 添加路由失败: {str(e)}")
            app.logger.error(f"Error adding page route: {str(e)}")

    @staticmethod
    def update_page_route(app, page):
        """更新页面路由"""
        try:
            # 更新路由映射
            with app.app_context():
                pages = CustomPage.query.filter_by(enabled=True).all()
                app.config['CUSTOM_PAGES'] = {p.route: p.key for p in pages}
            print(f"ok 已更新路由映射: {page.route} -> {page.key}")
        except Exception as e:
            print(f"x 更新路由失败: {str(e)}")
            app.logger.error(f"Error updating page route: {str(e)}")

# 创建全局实例
custom_page_manager = CustomPageManager()