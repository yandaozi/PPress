from typing import Dict, List, Type
from importlib import import_module
import os
import json
from flask import Blueprint, render_template_string
import inspect
import sys
from werkzeug.routing import Rule
from app import db

class PluginBase:
    """插件基类"""
    name = ''  # 插件名称
    description = ''  # 插件描述
    version = ''  # 插件版本
    author = ''  # 插件作者
    author_url = ''  # 插件作者的URL
    
    # 默认设置
    default_settings = {
        'enabled': True,  # 是否启用
        'position': 'content',  # 显示位置: content(内容区), sidebar(侧边栏)
        'priority': 100,  # 显示优先级
        'cache_time': 3600,  # 缓存时间(秒)
    }
    
    def __init__(self):
        self.app = None
        self._routes = []  # 存储路由信息
        self.settings = {}  # 实际设置
    
    def init_app(self, app):
        """初始化插件"""
        self.app = app
        # 从 plugin.json 加载插件信息
        plugin_dir = os.path.dirname(inspect.getfile(self.__class__))
        with open(os.path.join(plugin_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
            info = json.load(f)
            
        self.name = info.get('name')
        self.description = info.get('description')
        self.version = info.get('version')
        self.author = info.get('author')
        self.author_url = info.get('author_url')
        
        # 加载设置
        self.load_settings()
    
    def load_settings(self):
        """加载插件设置"""
        from app.models import Plugin as PluginModel
        plugin = PluginModel.query.filter_by(name=self.name).first()
        if plugin and plugin.config:
            # 合并默认设置和保存的设置
            self.settings = {**self.default_settings, **plugin.config}
        else:
            self.settings = self.default_settings.copy()
    
    def save_settings(self, settings):
        """保存插件设置"""
        from app.models import Plugin as PluginModel
        plugin = PluginModel.query.filter_by(name=self.name).first()
        if plugin:
            plugin.config = settings
            db.session.commit()
            # 更新实例的设置
            self.settings = {**self.default_settings, **settings}
    
    def export_plugin(self):
        """导出插件"""
        import tempfile
        import zipfile
        import shutil
        
        plugin_dir = os.path.dirname(inspect.getfile(self.__class__))
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"{self.name}.zip")
        
        try:
            # 创建 zip 文件
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 遍历插件目录
                for root, dirs, files in os.walk(plugin_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, plugin_dir)
                        zipf.write(file_path, arcname)
            
            # 读取 zip 文件
            with open(zip_path, 'rb') as f:
                content = f.read()
            
            return content, f"{self.name}.zip"
            
        finally:
            shutil.rmtree(temp_dir)
    
    def route(self, rule, **options):
        """注册路由装饰器"""
        def decorator(f):
            self._routes.append((rule, f, options))
            return f
        return decorator
    
    def register_routes(self):
        """注册所有路由"""
        for rule, view_func, options in self._routes:
            endpoint = f"{self.__class__.__name__.lower()}.{view_func.__name__}"
            self.app.view_functions[endpoint] = view_func
            self.app.url_map.add(Rule(rule, endpoint=endpoint, **options))
    
    def unregister_routes(self):
        """注销所有路由"""
        prefix = f"{self.__class__.__name__.lower()}."
        # 移除路由规则
        rules_to_remove = []
        for rule in self.app.url_map.iter_rules():
            if rule.endpoint.startswith(prefix):
                rules_to_remove.append(rule)
                if rule.endpoint in self.app.view_functions:
                    del self.app.view_functions[rule.endpoint]
        
        for rule in rules_to_remove:
            self.app.url_map._rules.remove(rule)
    
    def teardown(self):
        """卸载插件时的清理工作"""
        if hasattr(self, 'blueprint') and self.blueprint:
            # 从应用中移除蓝图
            if self.blueprint.name in self.app.blueprints:
                del self.app.blueprints[self.blueprint.name]
            
            # 移除蓝图的所有路由
            for rule in list(self.app.url_map.iter_rules()):
                if rule.endpoint.startswith(self.blueprint.name + '.'):
                    self.app.url_map._rules.remove(rule)
                    if rule.endpoint in self.app.view_functions:
                        del self.app.view_functions[rule.endpoint]
            
            self.blueprint = None
    
    def __str__(self):
        return f"{self.name} - {self.description}"
    
    def get_settings_template(self):
        """获取设置页面模板"""
        template_path = os.path.join(os.path.dirname(inspect.getfile(self.__class__)), 'templates/settings.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def render_settings_template(self, settings):
        """渲染设置页面模板"""
        template = self.get_settings_template()
        if template:
            return render_template_string(template, settings=settings, plugin=self)
        return None

class PluginManager:
    """插件管理器"""
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.app = None
    
    def init_app(self, app):
        """初始化插件管理器"""
        self.app = app
        with app.app_context():
            # 先检查并注册所有已存在的插件
            self.register_existing_plugins()
            # 然后加载启用的插件
            self.load_enabled_plugins()
    
    def register_existing_plugins(self):
        """检查并注册已存在的插件"""
        from app.models import Plugin as PluginModel
        
        plugins_dir = os.path.join(os.path.dirname(__file__), 'installed')
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
            return
        
        # 获取所有已注册的插件目录
        registered_dirs = {p.directory for p in PluginModel.query.all()}
        
        # 遍历插件目录
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            if not os.path.isdir(plugin_path):
                continue
                
            plugin_json = os.path.join(plugin_path, 'plugin.json')
            if not os.path.exists(plugin_json):
                continue
                
            # 如果插件目录存在但未注册，则注册它
            if plugin_name not in registered_dirs:
                try:
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        plugin_info = json.load(f)
                    # 添加到数据库
                    PluginModel.add_plugin(plugin_info, plugin_name)
                    print(f"Auto registered plugin: {plugin_name}")
                except Exception as e:
                    print(f"Failed to register plugin {plugin_name}: {str(e)}")
    
    def load_enabled_plugins(self):
        """加载所有已启用的插件"""
        from app.models import Plugin as PluginModel
        
        # 获取所有已启用的插件
        enabled_plugins = PluginModel.query.filter_by(enabled=True).all()
        for plugin in enabled_plugins:
            self.load_plugin(plugin.directory)
    
    def load_plugin(self, plugin_name: str) -> bool:
        """加载单个插件"""
        try:
            # 如果插件已经加载，先卸载它
            if plugin_name in self.plugins:
                self.unload_plugin(plugin_name)
            
            plugin_dir = os.path.join(os.path.dirname(__file__), 'installed', plugin_name)
            
            # 检查插件目录是否存在
            if not os.path.exists(plugin_dir):
                print(f"Plugin directory not found: {plugin_dir}")
                return False
            
            # 读取插件配置
            config_path = os.path.join(plugin_dir, 'plugin.json')
            if not os.path.exists(config_path):
                print(f"Plugin config not found: {config_path}")
                return False
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 导入插件模块
            try:
                # 强制重新加载模块
                import importlib
                module_name = f'app.plugins.installed.{plugin_name}'
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = import_module(module_name)
            except ImportError as e:
                print(f"Failed to import plugin module {plugin_name}: {str(e)}")
                return False
            
            plugin_class = getattr(module, config.get('plugin_class', 'Plugin'))
            
            # 实例化插件并初始化
            plugin = plugin_class()
            plugin.init_app(self.app)
            
            # 确保配置已加载
            plugin.load_settings()
            
            self.plugins[plugin_name] = plugin
            
            print(f"Successfully loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {str(e)}")
            return False
    
    def get_plugin(self, name: str) -> PluginBase:
        """获取插件实例"""
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> List[PluginBase]:
        """获取所有已加载的插件"""
        return list(self.plugins.values())
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            if plugin_name in self.plugins:
                plugin = self.plugins[plugin_name]
                plugin.teardown()  # 调用插件的清理方法
                del self.plugins[plugin_name]
                print(f"Successfully unloaded plugin: {plugin_name}")
                return True
            return False
        except Exception as e:
            print(f"Error unloading plugin {plugin_name}: {str(e)}")
            return False

# 创建全局实例
plugin_manager = PluginManager()

def get_plugin_manager():
    return plugin_manager 