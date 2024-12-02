from flask import render_template_string, current_app
from flask_login import login_required
from app.plugins import PluginBase
from app.controller.admin import admin_required
from app.utils.cache_manager import cache_manager
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
            # 尝试从缓存获取仪表盘内容
            cache_key = 'plugin_custom_dashboard:content'
            content = cache_manager.get(
                cache_key,
                default_factory=lambda: self._get_dashboard_content(),
                ttl=300  # 缓存5分钟
            )
            return content

        # 直接替换视图函数
        app.view_functions['admin.dashboard'] = custom_dashboard
        print(f"Dashboard view function replaced: {id(custom_dashboard)}")

    def _get_dashboard_content(self):
        """获取仪表盘内容"""
        try:
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'dashboard.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            return render_template_string(template)
        except Exception as e:
            current_app.logger.error(f"Error getting dashboard content: {str(e)}")
            return "Error loading dashboard"

    def teardown(self):
        """清理插件"""
        try:
            # 恢复原始视图函数
            if self.app and hasattr(self, '_original_dashboard'):
                self.app.view_functions['admin.dashboard'] = self._original_dashboard
                print("Restored original dashboard view")
            
            # 清除仪表盘缓存
            cache_manager.delete('plugin_custom_dashboard:*')
        except Exception as e:
            current_app.logger.error(f"Error in teardown: {str(e)}")