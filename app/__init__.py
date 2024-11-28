from flask import Flask, url_for, render_template
import os
from .extensions import db, login_manager, csrf
from .utils.theme_manager import ThemeManager
from app.plugins import get_plugin_manager
from flask_caching import Cache

cache = Cache()

def init_plugins(app):
    """初始化插件"""
    plugin_manager = get_plugin_manager()
    plugin_manager.init_app(app)

def create_app(config_name='default'):
    app = Flask(__name__)

    # 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://flaskiosblog:flaskiosblog@localhost/flaskiosblog?charset=utf8mb4'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

    # 添加数据库连接选项
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

    # 初始化缓存
    cache.init_app(app)

    # 注册一个请求钩子来延迟初始化插件
    @app.before_request
    def lazy_init_plugins():
        if not hasattr(app, '_plugins_initialized'):
            with app.app_context():
                init_plugins(app)
            app._plugins_initialized = True

    # 注册蓝图
    from .views import auth, blog, admin, user
    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(user.bp)

    # 注册404错误处理器
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template(ThemeManager.get_template_path('errors/404.html')), 404

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
        from .models import Category
        return {'categories': Category.query.all()}

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

    # 添加用户信息处理函
    @app.context_processor
    def user_info_processor():
        def get_user_info(user):
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
        return dict(get_user_info=get_user_info)

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