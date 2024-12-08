import os
from flask import Blueprint

# 使用绝对路径
template_dir = os.path.abspath(os.path.dirname(__file__))
static_dir = os.path.join(template_dir, 'static')

bp = Blueprint('installer', __name__, 
              template_folder=template_dir)

def is_installed(app=None):
    """检查是否已安装"""
    if app is None:
        from flask import current_app
        app = current_app
    lock_file = os.path.join(app.root_path, '..', 'ppress_db.lock')
    return os.path.exists(lock_file)

def init_installer(app):
    """初始化安装模块"""
    # 在应用上下文中检查是否已安装
    with app.app_context():
        if not is_installed(app):
            # 确保 CSRF 保护已启用
            from app.extensions import csrf
            csrf.init_app(app)
            
            from .routes import bp as installer_bp
            app.register_blueprint(installer_bp)
            
            @app.before_request
            def check_installed():
                from flask import request, redirect, url_for
                if not is_installed(app) and request.endpoint != 'installer.install':
                    return redirect(url_for('installer.install')) 