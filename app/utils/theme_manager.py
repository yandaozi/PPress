import os
import json
import shutil
import tempfile
import zipfile
from flask import current_app, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
from app.models.site_config import SiteConfig
from app.models.theme_settings import ThemeSettings

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

    @staticmethod
    def get_theme_info(theme_id):
        """获取主题信息"""
        try:
            theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
            current_app.logger.debug(f"Checking theme directory: {theme_dir}")
            
            settings_file = os.path.join(theme_dir, 'theme_settings', 'settings.html')
            current_app.logger.debug(f"Settings file exists: {os.path.exists(settings_file)}")
            
            # 读取主题配置
            config_file = os.path.join(theme_dir, 'theme.json')
            theme_info = {
                'id': theme_id,
                'name': theme_id.title(),
                'preview': url_for('admin.theme_preview_image', theme=theme_id),
                'has_settings': False  # 默认设置为 False
            }
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        theme_info.update(config)
                        # 如果主题配置中有 settings 字段，则认为有设置
                        theme_info['has_settings'] = bool(config.get('settings'))
                except Exception as e:
                    current_app.logger.error(f'Failed to load theme config: {str(e)}')
            
            # 检查是否有设置文件
            settings_file = os.path.join(theme_dir, 'theme_settings', 'settings.html')
            if os.path.exists(settings_file):
                theme_info['has_settings'] = True
            
            # 获取设置值
            if theme_info['has_settings']:
                theme_info['settings'] = ThemeSettings.get_settings(theme_id)
            
            current_app.logger.debug(f"Theme info: {theme_info}")
            return theme_info
        except Exception as e:
            current_app.logger.error(f"Error in get_theme_info: {str(e)}")
            return None

    @staticmethod
    def get_theme_settings_template(theme_id):
        """获取主题设置模板内容"""
        settings_file = os.path.join(
            current_app.root_path, 
            'templates', 
            theme_id,
            'theme_settings',
            'settings.html'
        )
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    @staticmethod
    def save_theme_settings(theme_id, settings_data):
        """保存主题设置"""
        try:
            ThemeSettings.save_settings(theme_id, settings_data)
            return True, '设置保存成功'
        except Exception as e:
            current_app.logger.error(f"Error saving theme settings: {str(e)}")
            return False, str(e)

    @staticmethod
    def validate_theme_structure(theme_dir):
        """验证主题目录结构"""
        required_files = [
            'theme.json',
            'preview.png',
            'templates/base.html'
        ]
        
        for file in required_files:
            if not os.path.exists(os.path.join(theme_dir, file)):
                return False, f'缺少必需文件: {file}'
            
        # 检查主题信息文件格式
        try:
            with open(os.path.join(theme_dir, 'theme.json'), 'r', encoding='utf-8') as f:
                theme_info = json.load(f)
                required_fields = ['name', 'version', 'author']
                for field in required_fields:
                    if field not in theme_info:
                        return False, f'theme.json 缺少必需字段: {field}'
        except Exception as e:
            return False, f'theme.json 格式错误: {str(e)}'
            
        return True, None

    @staticmethod
    def install_theme(zip_file):
        """安装主题"""
        try:
            temp_dir = tempfile.mkdtemp()
            try:
                # 解压文件
                with zipfile.ZipFile(zip_file, 'r') as z:
                    z.extractall(temp_dir)
                
                # 验证主题结构
                valid, error = ThemeManager.validate_theme_structure(temp_dir)
                if not valid:
                    return False, error
                
                # 读取主题信息
                with open(os.path.join(temp_dir, 'theme.json'), 'r', encoding='utf-8') as f:
                    theme_info = json.load(f)
                
                theme_id = theme_info.get('id', '').lower()
                if not theme_id:
                    return False, '主题ID不能为空'
                
                # 复制到主题目录
                theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
                if os.path.exists(theme_dir):
                    shutil.rmtree(theme_dir)
                shutil.copytree(temp_dir, theme_dir)
                
                return True, '主题安装成功'
                
            finally:
                shutil.rmtree(temp_dir)
                
        except Exception as e:
            return False, f'安装失败: {str(e)}'

    @staticmethod
    def export_theme(theme_id):
        """导出主题"""
        temp_file = None
        try:
            theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
            if not os.path.exists(theme_dir):
                return False, '主题不存在', None, None
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_file.close()  # 立即关闭文件
            
            # 创建zip文件
            with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(theme_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, theme_dir)
                        zf.write(file_path, arc_name)
            
            # 读取zip文件内容
            with open(temp_file.name, 'rb') as f:
                content = f.read()
            
            return True, None, content, f'{theme_id}.zip'
            
        except Exception as e:
            current_app.logger.error(f"Error exporting theme: {str(e)}")
            return False, str(e), None, None
            
        finally:
            # 确保临时文件被删除
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    current_app.logger.error(f"Error deleting temp file: {str(e)}")