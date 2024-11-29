import os
from flask import current_app, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from app.models.site_config import SiteConfig

class ThemeManager:
    @staticmethod
    def get_theme_loader(app):
        """获取主题模板加载器"""
        templates_dir = os.path.join(app.root_path, 'templates')
        theme_loaders = []
        
        # 添加管理后台模板目录
        admin_dir = os.path.join(templates_dir, 'admin')
        if os.path.isdir(admin_dir):
            theme_loaders.append(FileSystemLoader(admin_dir))
        
        # 添加默认主题目录
        default_theme_dir = os.path.join(templates_dir, 'default')
        if os.path.isdir(default_theme_dir):
            theme_loaders.append(FileSystemLoader(default_theme_dir))
        
        # 添加其他主题目录
        for theme in os.listdir(templates_dir):
            if theme not in ['default', 'admin']:  # 跳过默认主题和管理后台
                theme_dir = os.path.join(templates_dir, theme)
                if os.path.isdir(theme_dir):
                    theme_loaders.append(FileSystemLoader(theme_dir))
        
        # 最后添加原始模板目录作为后备
        theme_loaders.append(app.jinja_loader)
        
        return ChoiceLoader(theme_loaders)

    @staticmethod
    def get_available_themes():
        """获取所有可用的主题"""
        themes_dir = os.path.join(current_app.root_path, 'templates')
        themes = []
        
        for theme in os.listdir(themes_dir):
            theme_dir = os.path.join(themes_dir, theme)
            preview_image = os.path.join(theme_dir, 'preview.png')
            
            if os.path.isdir(theme_dir) and os.path.exists(preview_image):
                # 读取主题配置文件（如果存在）
                config_file = os.path.join(theme_dir, 'theme.json')
                theme_info = {
                    'id': theme,
                    'name': theme.title(),
                    'preview': url_for('admin.theme_preview', theme=theme),
                    'description': ''
                }
                
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            import json
                            config = json.load(f)
                            theme_info.update(config)
                    except:
                        current_app.logger.error(f'Failed to load theme config: {theme}')
                
                themes.append(theme_info)
        
        return themes

    @staticmethod
    def get_template_path(template_name):
        """获取模板的完整路径"""
        # 如果是管理后台模板，直接返回
        if template_name.startswith('admin/'):
            return template_name
            
        # 其他模板使用主题
        theme = SiteConfig.get_config('site_theme', 'default')
        return f'{theme}/{template_name}' 