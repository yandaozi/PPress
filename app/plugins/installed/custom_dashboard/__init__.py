from flask import render_template_string, current_app
from flask_login import login_required
from app.plugins import PluginBase
from app.views.admin import admin_required
import os

class Plugin(PluginBase):
    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 确保模板目录存在
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(template_path, exist_ok=True)
        
        # 保存原始视图函数
        self._original_dashboard = app.view_functions.get('admin.dashboard')
        
        # 注册新的仪表盘视图
        @login_required
        @admin_required
        def custom_dashboard():
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            return render_template_string(template)
        
        # 直接替换视图函数
        app.view_functions['admin.dashboard'] = custom_dashboard
        print(f"Dashboard view function replaced: {id(custom_dashboard)}")

    def teardown(self):
        """清理插件"""
        # 恢复原始视图函数
        if self.app and hasattr(self, '_original_dashboard'):
            self.app.view_functions['admin.dashboard'] = self._original_dashboard
            print("Restored original dashboard view")