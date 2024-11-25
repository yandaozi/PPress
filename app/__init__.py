from flask import Flask
import os
from .extensions import db, login_manager, csrf

def create_app():
    app = Flask(__name__)
    
    # 配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://flask_han_blog:flask_han_blog@localhost/flask_han_blog'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    
    # 初始化插件
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # 注册蓝图
    from .views import auth, blog, admin, user
    app.register_blueprint(auth.bp)
    app.register_blueprint(blog.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(user.bp)
    
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
    
    return app 