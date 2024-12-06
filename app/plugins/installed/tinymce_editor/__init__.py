from flask import render_template_string, current_app, url_for, send_from_directory
from app import db
from app.plugins import PluginBase
from markupsafe import Markup
from app.utils.cache_manager import cache_manager
import os

class Plugin(PluginBase):
    # 默认设置
    default_settings = {
        'language': 'zh_CN',
        'plugins': [
            'advlist', 'anchor', 'autolink', 'autoresize', 'autosave',
            'charmap', 'code', 'codesample', 'directionality', 'emoticons',
            'fullscreen', 'help', 'image', 'importcss', 'insertdatetime',
            'link', 'lists', 'media', 'nonbreaking', 'pagebreak', 'preview',
            'quickbars', 'save', 'searchreplace', 'visualblocks', 'visualchars',
            'wordcount'
        ],
        'image_dimensions': False,
        'image_class_list': [
            { 'title': '响应式', 'value': 'img-fluid' }
        ]
    }
    
    def __init__(self):
        super().__init__()
        
        # 注册静态文件路由
        @self.route('/plugin/tinymce_editor/static/<path:filename>', 
                   endpoint='tinymce_editor_static',
                   methods=['GET'])
        def serve_static(filename):
            """提供静态文件访问"""
            static_folder = os.path.join(os.path.dirname(__file__), 'static')
            return send_from_directory(static_folder, filename)
    
    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 注册模板函数
        def render_editor(selector='#content', **kwargs):
            """渲染编辑器"""
            try:
                # 生成缓存键
                cache_key = f'plugin_tinymce_editor:render:{selector}:{hash(frozenset(kwargs.items()))}'
                
                # 尝试从缓存获取渲染结果
                rendered = cache_manager.get(
                    cache_key,
                    default_factory=lambda: self._render_editor(selector, **kwargs),
                    ttl=3600  # 缓存1小时
                )
                return rendered
                
            except Exception as e:
                current_app.logger.error(f"Error rendering editor: {str(e)}")
                return ''
        
        app.jinja_env.globals['render_tinymce'] = render_editor
    
    def _render_editor(self, selector='#content', height=450, **kwargs):
        """渲染编辑器的具体实现"""
        try:
            # 合并配置
            config = self.default_settings.copy()
            settings = self.get_settings()  # 获取最新配置
            config.update(settings)
            config.update(kwargs)
            config['selector'] = selector
            config['height'] = height
            
            # 获取静态文件URL
            static_url = url_for('tinymce_editor_static', filename='').rstrip('/')
            
            # 构建自动保存前缀
            from flask import request
            autosave_prefix = f'tinymce-autosave-{request.path}-{kwargs.get("article_id", 0)}'
            
            # 渲染模板
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'editor.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                    
                rendered = render_template_string(
                    template, 
                    config=config,
                    static_url=static_url,
                    autosave_prefix=autosave_prefix
                )
                return Markup(rendered)
            return ''
            
        except Exception as e:
            current_app.logger.error(f"Error in _render_editor: {str(e)}")
            return ''
    
    def get_settings_template(self):
        """获取设置页面模板"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'settings.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
                
            # 获取当前配置
            settings = self.settings if hasattr(self, 'settings') else self.default_settings
            
            return render_template_string(
                template,
                settings=settings
            )
        return ''
    
    def save_settings(self, form_data):
        """保存插件设置"""
        try:
            settings = {
                'language': 'zh_CN',
                'branding': False,
                'plugins': form_data.getlist('plugins[]'),
                'image_dimensions': False,
                'image_class_list': [
                    { 'title': '响应式', 'value': 'img-fluid' }
                ]
            }
            
            # 保存到数据库
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            if plugin:
                plugin.config = settings
                db.session.commit()
                self.settings = settings
                # 清除编辑器渲染缓存
                cache_manager.delete('plugin_tinymce_editor:render:*')
                return True, '设置已保存'
            return False, '插件不存在'
            
        except Exception as e:
            return False, f'保存设置失败: {str(e)}' 