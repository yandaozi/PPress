from flask import Flask, url_for, render_template
import os
from .extensions import db, login_manager, csrf
from .utils.theme_manager import ThemeManager
from app.plugins import get_plugin_manager
from flask_caching import Cache
from config.database import get_db_url, DB_TYPE

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
        app._components_initialized = True

def create_app(db_type=DB_TYPE, init_components=True):
    app = Flask(__name__)

    # 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
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
    from .views import auth, blog, admin, user
    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(user.bp)

    # 只在需要时初始化组件
    if init_components:
        init_app_components(app)

    # 注册错误处理器
    @app.errorhandler(404)
    def page_not_found(e):
        from app.utils.common import get_categories_data
        return render_template('errors/404.html', **get_categories_data()), 404

    # @app.errorhandler(500)
    # def internal_server_error(e):
    #     from app.utils.common import get_categories_data
    #     return render_template('errors/500.html', **get_categories_data()), 500

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
            'dict_items': lambda d: d.items() if d else [],
            'reject': lambda items, key: {k: v for k, v in items if k != key}
        }

    # 修改用户信息处理函数
    @app.context_processor
    def user_info_processor():
        def get_user_info(user):
            """获取用户信息"""
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'avatar': user.avatar
                }
            return {
                'id': None,
                'username': '已注销用户',
                'avatar': url_for('static', filename='default_avatar.png')
            }
        
        def get_author_info(article_or_author):
            """获取作者信息，支持从文章或作者对象获取"""
            # 如果传入的是文章对象，获取其作者
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
        categories, article_counts = get_categories_data()
        return dict(
            categories=categories,
            article_counts=article_counts
        )

    # 注册加密版权信息函数
    @app.template_global()
    def get_encrypted_copyright():
        from .utils.encrypt import CopyrightEncryptor
        return CopyrightEncryptor.get_copyright()

    return app 