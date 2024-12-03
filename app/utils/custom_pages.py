import os
from flask import render_template, current_app, request, abort
from flask_login import login_required
from app.models import CustomPage
from app.models.site_config import SiteConfig
from app.utils.cache_manager import cache_manager

class CustomPageMiddleware:
    def __init__(self, wsgi_app, flask_app):
        self.wsgi_app = wsgi_app
        self.flask_app = flask_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        
        # 检查是否匹配自定义页面路由
        custom_pages = self.flask_app.config.get('CUSTOM_PAGES', {})
        if path in custom_pages:
            # 找到匹配的页面,重定向到内部处理函数
            environ['PATH_INFO'] = f'/custom_page/{custom_pages[path]}'
            environ['HTTP_X_CUSTOM_PAGE'] = 'true'
                
        return self.wsgi_app(environ, start_response)

def render_custom_page(page):
    """渲染自定义页面"""
    try:
        # 如果是管理后台的请求，不使用缓存
        if request.endpoint and request.endpoint.startswith('admin.'):
            current_theme = SiteConfig.get_config('site_theme', 'default')
            template = f'{current_theme}/custom/{page.template}'
            if not os.path.exists(os.path.join(current_app.template_folder, template)):
                template = f'default/custom/{page.template}'
            return render_template(template, page=page)
            
        # 前台页面使用缓存
        cache_key = f'custom_page_html:{page.key}'
        html = cache_manager.get(cache_key)
        
        if html is None:
            current_theme = SiteConfig.get_config('site_theme', 'default')
            template = f'{current_theme}/custom/{page.template}'
            if not os.path.exists(os.path.join(current_app.template_folder, template)):
                template = f'default/custom/{page.template}'
            html = render_template(template, page=page)
            cache_manager.set(cache_key, html)
            
        return html
    except Exception as e:
        current_app.logger.error(f"Render custom page error: {str(e)}")
        return render_template('default/custom/example.html', page=page)

class CustomPageManager:
    @staticmethod
    def get_custom_templates():
        """获取自定义页面模板列表"""
        templates = []
        theme_path = os.path.join(current_app.root_path, 'templates')
        
        # 获取默认主题模板
        default_path = os.path.join(theme_path, 'default/custom')
        if os.path.exists(default_path):
            for file in os.listdir(default_path):
                if file.endswith('.html'):
                    templates.append({
                        'name': file.replace('.html', '').title(),
                        'path': file  # 只保留文件名
                    })
        
        # 获取当前主题模板
        current_theme = SiteConfig.get_config('site_theme', 'default')
        if current_theme != 'default':
            theme_custom_path = os.path.join(theme_path, f'{current_theme}/custom')
            if os.path.exists(theme_custom_path):
                for file in os.listdir(theme_custom_path):
                    if file.endswith('.html'):
                        templates.append({
                            'name': file.replace('.html', '').title(),
                            'path': file  # 只保留文件名
                        })
        
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
                print(f"✓ 已加载 {len(pages)} 个自定义页面路由")
            
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
                
            print("✓ 自定义页面路由初始化完成\n")
            
        except Exception as e:
            print(f"✗ 初始化自定义页面路由失败: {str(e)}\n")
            app.logger.error(f"Error initializing custom pages: {str(e)}")

    @staticmethod
    def add_page_route(app, page):
        """添加单个页面路由"""
        try:
            # 更新路由映射
            with app.app_context():
                pages = CustomPage.query.filter_by(enabled=True).all()
                app.config['CUSTOM_PAGES'] = {p.route: p.key for p in pages}
            print(f"✓ 已更新路由映射: {page.route} -> {page.key}")
        except Exception as e:
            print(f"✗ 添加路由失败: {str(e)}")
            app.logger.error(f"Error adding page route: {str(e)}")

    @staticmethod
    def update_page_route(app, page):
        """更新页面路由"""
        try:
            # 更新路由映射
            with app.app_context():
                pages = CustomPage.query.filter_by(enabled=True).all()
                app.config['CUSTOM_PAGES'] = {p.route: p.key for p in pages}
            print(f"✓ 已更新路由映射: {page.route} -> {page.key}")
        except Exception as e:
            print(f"✗ 更新路由失败: {str(e)}")
            app.logger.error(f"Error updating page route: {str(e)}")

# 创建全局实例
custom_page_manager = CustomPageManager()