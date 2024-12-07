from flask import Flask, url_for, render_template, g, current_app
import os

from werkzeug.routing import BuildError

from .extensions import db, login_manager, csrf
from app.utils.cache_manager import cache_manager
from .utils.theme_manager import ThemeManager
from app.plugins import get_plugin_manager
from flask_caching import Cache
from config.database import get_db_url, DB_TYPE
from sqlalchemy import event
from app.utils.custom_pages import custom_page_manager
from app.utils.article_url import ArticleUrlGenerator

cache = Cache()

def init_plugins(app):
    """初始化插件"""
    with app.app_context():
        plugin_manager = get_plugin_manager()
        plugin_manager.init_app(app)

def init_cache(app):
    """初始化缓存"""
    with app.app_context():
        from app.services.blog_service import BlogService
        from app.services.user_service import UserService
        
        BlogService.warmup_cache()
        UserService.warmup_cache()
        
        app.logger.info("Cache warmed up successfully")

def init_app_components(app):
    """初始化应用组件"""
    if not hasattr(app, '_components_initialized'):
        with app.app_context():
            init_plugins(app)
            init_cache(app)
            # 初始化自定义页面
            custom_page_manager.init_custom_pages(app)
        app._components_initialized = True

def init_routes(app):
    """初始化自定义路由"""
    from app.services.admin_service import AdminService
    from app.models import Route
    
    def refresh_routes():
        """刷新路由"""
        with app.app_context():
            AdminService.refresh_custom_routes()

    # 初始化路由
    with app.app_context():
        AdminService.refresh_custom_routes()

    # 监听会话事件
    @event.listens_for(db.session, 'after_commit')
    def after_commit(session):
        for obj in session.new | session.dirty | session.deleted:
            if isinstance(obj, Route):
                refresh_routes()
                break
    
    # 自定义 url_for 函数
    def custom_url_for(endpoint, **values):
        # 如果是自定义路由端点，直接使用
        if endpoint.startswith('custom_'):
            try:
                return url_for(endpoint, **values)
            except BuildError:
                # 如果构建失败，尝试使用原始端点
                route_id = endpoint.replace('custom_', '')
                try:
                    route = Route.query.get(int(route_id))
                    if route:
                        return url_for(route.original_endpoint, **values)
                except:
                    pass
        
        # 检查是否有活动的重写规则
        try:
            # 使用缓存检查路由状态
            route_key = f'route_status:{endpoint}'
            route_status = cache_manager.get(route_key)
            
            if route_status is None:
                route = Route.query.filter_by(
                    original_endpoint=endpoint, 
                    is_active=True
                ).first()
                
                if route:
                    route_status = {'id': route.id, 'active': True}
                else:
                    route_status = {'active': False}
                    
                # 缓存路由状态，使用 cache_manager 的 set 方法
                cache_manager.set(route_key, route_status)  # 移除 timeout 参数
            
            if route_status.get('active'):
                custom_endpoint = f'custom_{route_status["id"]}'
                try:
                    return url_for(custom_endpoint, **values)
                except BuildError:
                    # 如果构建失败，刷新路由并重试
                    AdminService.refresh_custom_routes()
                    return url_for(custom_endpoint, **values)
                    
        except Exception as e:
            current_app.logger.error(f"Error in custom_url_for: {str(e)}")
            
        # 如果没有匹配的重写规则，使用原始端点
        return url_for(endpoint, **values)
    
    # 替换全局 url_for
    app.jinja_env.globals['url_for'] = custom_url_for

def create_app(db_type=DB_TYPE, init_components=True):
    app = Flask(__name__)

    # 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'PPress')
    app.config['SQLALCHEMY_DATABASE_URI'] = get_db_url(db_type)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

    # 添加数据库连接选项
    if db_type == 'mysql':
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {
                'charset': 'utf8mb4'
            }
        }
    
    # 添加这行配置，自动处理 URL 结尾的斜杠
    app.url_map.strict_slashes = False

    # 初始化基础扩展
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'

    # 使用内存缓存
    app.config['CACHE_TYPE'] = 'simple'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300
    cache.init_app(app)

    # 注册蓝图
    from .controller import auth, blog, admin, user
    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(user.bp)

    # 初始化路由（确保在注册蓝图之后）
    if init_components:
        init_app_components(app)
        init_routes(app)

    # 注册错误处理器
    @app.errorhandler(404)
    def page_not_found(e):
        from app.utils.common import get_categories_data
        return render_template('errors/404.html', **get_categories_data()), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        from app.utils.common import get_categories_data
        return render_template('errors/500.html', **get_categories_data()), 500

    # 添加user_loader回调
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 添加网站配置上下文处理器
    from .models.site_config import SiteConfig
    @app.context_processor
    def inject_site_config():
        return {'site_config': SiteConfig}

    @app.context_processor
    def inject_categories():
        from app.utils.common import get_categories_data
        return get_categories_data()

    # 添加全局函数到模板
    @app.context_processor
    def utility_processor():
        return {
            'max': max,
            'min': min,
            'dict': dict,
            'hasattr': hasattr,
            'dict_items': lambda d: d.items() if d else [],
            'reject': lambda items, key: {k: v for k, v in items if k != key}
        }

    # 修改用户信息处理函数
    @app.context_processor
    def user_info_processor():
        def get_user_info(user):
            """获取用户信息"""
            if user:
                nickname = user.nickname if user.nickname else user.username
                return {
                    'id': user.id,
                    'nickname': nickname,
                    'username': user.username,
                    'avatar': user.avatar
                }
            return {
                'id': None,
                'nickname': '已注销用户',
                'username': '已注销用户',
                'avatar': url_for('static', filename='default_avatar.png')
            }
        
        def get_author_info(article_or_author):
            """获取作者信息，支持从文章或作者对象获取"""
            # 如果传入的是文章对象，获取其作
            if hasattr(article_or_author, 'author'):
                author = article_or_author.author
            else:
                author = article_or_author
            
            return get_user_info(author)
        
        return dict(
            get_user_info=get_user_info,
            get_author_info=get_author_info
        )

    # 添加模板全局函数
    @app.context_processor
    def inject_template_utils():
        return {
            'theme_path': ThemeManager.get_template_path
        }

    # 修改 Jinja2 模板加载器配置
    app.jinja_loader = ThemeManager.get_theme_loader(app)

    # 添加全局上下文处理器
    @app.context_processor
    def inject_categories_data():
        from app.utils.common import get_categories_data
        data = get_categories_data()
        return dict(
            categories=data['categories'],
            article_counts=data['article_counts'],
            all_categories=data['all_categories']
        )

    # 注册加密版权信息函数
    @app.template_global()
    def get_encrypted_copyright():
        from .utils.encrypt import CopyrightEncryptor
        return CopyrightEncryptor.get_copyright()

    # 添加全局模板变量
    app.jinja_env.globals['ArticleUrlGenerator'] = ArticleUrlGenerator

    # 添加主题设置上下文处理器
    @app.context_processor
    def inject_theme_settings():
        from app.utils.theme_manager import ThemeManager
        from app.models.site_config import SiteConfig
        
        def get_theme_settings():
            current_theme = SiteConfig.get_config('site_theme', 'default')
            theme_info = ThemeManager.get_theme_info(current_theme)
            return theme_info
            
        return {'theme': get_theme_settings()}

    return app 