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
        
        try:
            # 在应用上下文中获取当前主题
            with app.app_context():
                current_theme = SiteConfig.get_config('site_theme', 'default')
        except RuntimeError:
            # 如果没有应用上下文，使用默认主题
            current_theme = 'default'
        
        # 添加当前主题目录
        current_theme_dir = os.path.join(templates_dir, current_theme)
        if os.path.isdir(current_theme_dir):
            theme_loaders.append(FileSystemLoader(current_theme_dir))
        
        # 如果当前主题不是default，且default主题存在，则作为后备添加
        if current_theme != 'default':
            default_theme_dir = os.path.join(templates_dir, 'default')
            if os.path.isdir(default_theme_dir):
                theme_loaders.append(FileSystemLoader(default_theme_dir))
        
        # 最后添加原始模板目录作为后备
        theme_loaders.append(app.jinja_loader)
        
        return ChoiceLoader(theme_loaders)

    @staticmethod
    def update_theme_loader(app):
        """动态更新主题加载器"""
        # 获取新的加载器
        new_loader = ThemeManager.get_theme_loader(app)
        
        # 更新应用的加载器
        app.jinja_loader = new_loader
        
        # 清除模板缓存
        app.jinja_env.cache.clear()

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
            
            # 读取主题配置
            config_file = os.path.join(theme_dir, 'theme.json')
            theme_info = {
                'id': theme_id,
                'name': theme_id.title(),
                'preview': url_for('admin.theme_preview_image', theme=theme_id),
                'has_settings': False,
                'settings_enabled': False
            }
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        theme_info.update(config)
                        # 如果主题配置中有 settings 字段，则认为有设置
                        theme_info['has_settings'] = isinstance(config.get('settings'), dict)
                        
                        # 检查数据库中是否存在设置
                        db_settings = ThemeSettings.get_settings(theme_id)
                        if not db_settings and theme_info['has_settings']:
                            # 如果数据库中没有设置但theme.json中有默认设置，则初始化
                            ThemeSettings.save_settings(theme_id, config['settings'])
                            db_settings = config['settings']
                        
                        if db_settings:
                            theme_info['settings'] = db_settings
                except Exception as e:
                    current_app.logger.error(f'Failed to load theme config: {str(e)}')
            
            # 检查是否有设置文件
            settings_file = os.path.join(theme_dir, 'theme_settings', 'settings.html')
            if os.path.exists(settings_file):
                theme_info['settings_enabled'] = True
            
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
        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp()
            
            # 解压文件
            with zipfile.ZipFile(zip_file, 'r') as z:
                z.extractall(temp_dir)
            
            # 检查主题目录结构
            templates_dir = os.path.join(temp_dir, 'templates')
            static_dir = os.path.join(temp_dir, 'static')
            
            if not os.path.exists(templates_dir):
                return False, '无效的主题包：缺少templates目录'
            
            # 获取主题ID（templates目录下的第一个目录）
            theme_dirs = [d for d in os.listdir(templates_dir) 
                         if os.path.isdir(os.path.join(templates_dir, d))]
            if not theme_dirs:
                return False, '无效的主题包：未找到主题目录'
            
            theme_id = theme_dirs[0]
            theme_dir = os.path.join(templates_dir, theme_id)
            
            # 验证必需文件
            if not os.path.exists(os.path.join(theme_dir, 'theme.json')):
                return False, '缺少必需文件: theme.json'
            if not os.path.exists(os.path.join(theme_dir, 'preview.png')):
                return False, '缺少必需文件: preview.png'
            
            # 检查主题是否已存在
            target_theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
            if os.path.exists(target_theme_dir):
                # 读取已安装主题的版本
                installed_version = None
                installed_json = os.path.join(target_theme_dir, 'theme.json')
                if os.path.exists(installed_json):
                    try:
                        with open(installed_json, 'r', encoding='utf-8') as f:
                            installed_info = json.load(f)
                            installed_version = installed_info.get('version')
                    except:
                        pass
                    
                # 读取要安装的主题版本
                new_version = None
                with open(os.path.join(theme_dir, 'theme.json'), 'r', encoding='utf-8') as f:
                    new_info = json.load(f)
                    new_version = new_info.get('version')
                    
                # 如果版本相同，提示已存在
                if installed_version == new_version:
                    return False, f"主题 {theme_id} - {installed_info.get('name')} (v{installed_version}) 已存在，无需重复安装"
                
                # 版本不同，删除旧版本
                shutil.rmtree(target_theme_dir)
                # 删除旧的静态资源
                target_static_dir = os.path.join(current_app.root_path, 'static', theme_id)
                if os.path.exists(target_static_dir):
                    shutil.rmtree(target_static_dir)
            
            # 复制主题模板目录
            shutil.copytree(theme_dir, target_theme_dir)
            
            # 如果存在静态资源，也复制过去
            theme_static_dir = os.path.join(static_dir, theme_id)
            if os.path.exists(theme_static_dir):
                target_static_dir = os.path.join(current_app.root_path, 'static', theme_id)
                if os.path.exists(target_static_dir):
                    shutil.rmtree(target_static_dir)
                shutil.copytree(theme_static_dir, target_static_dir)
            
            return True, '主题安装成功'
            
        except Exception as e:
            return False, f'安装失败: {str(e)}'
            
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @staticmethod
    def export_theme(theme_id):
        """导出主题"""
        temp_file = None
        try:
            # 检查主题目录
            theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
            if not os.path.exists(theme_dir):
                return False, '主题不存在', None, None
            
            # 检查静态资源目录
            static_dir = os.path.join(current_app.root_path, 'static', theme_id)
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
            temp_file.close()
            
            # 创建zip文件
            with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 打包主题模板目录
                for root, dirs, files in os.walk(theme_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对路径，保持目录结构
                        arc_name = os.path.join('templates', theme_id, 
                                              os.path.relpath(file_path, theme_dir))
                        zf.write(file_path, arc_name)
                
                # 如果存在静态资源目录，也打包进去
                if os.path.exists(static_dir):
                    for root, dirs, files in os.walk(static_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_name = os.path.join('static', theme_id,
                                                  os.path.relpath(file_path, static_dir))
                            zf.write(file_path, arc_name)
            
            # 读取zip文件内容
            with open(temp_file.name, 'rb') as f:
                content = f.read()
            
            return True, None, content, f'{theme_id}.zip'
            
        except Exception as e:
            current_app.logger.error(f"Error exporting theme: {str(e)}")
            return False, str(e), None, None
            
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    current_app.logger.error(f"Error deleting temp file: {str(e)}")

    @staticmethod
    def uninstall_theme(theme_id):
        """卸载主题"""
        try:
            # 不允许卸载 default 主题
            if theme_id == 'default':
                return False, '默认主题不能卸载'
            
            # 检查主题是否是当前使用的主题
            current_theme = SiteConfig.get_config('site_theme', 'default')
            if theme_id == current_theme:
                return False, '不能卸载正在使用的主题'
            
            # 删除主题目录
            theme_dir = os.path.join(current_app.root_path, 'templates', theme_id)
            if os.path.exists(theme_dir):
                shutil.rmtree(theme_dir)
            
            # 删除静态资源目录
            static_dir = os.path.join(current_app.root_path, 'static', theme_id)
            if os.path.exists(static_dir):
                shutil.rmtree(static_dir)
            
            # 删除数据库中的主题设置
            try:
                theme_settings = ThemeSettings.query.filter_by(theme=theme_id).first()
                if theme_settings:
                    from app.extensions import db
                    db.session.delete(theme_settings)
                    db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Error deleting theme settings from database: {str(e)}")
            
            return True, '主题卸载成功'
            
        except Exception as e:
            current_app.logger.error(f"Error uninstalling theme: {str(e)}")
            return False, f'卸载失败: {str(e)}'
