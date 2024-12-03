from typing import Dict, List
from importlib import import_module
import os
import json
from flask import render_template_string, current_app
import inspect
from werkzeug.routing import Rule, Map
from app import db
from markupsafe import Markup

class DynamicRoute:
    def __init__(self, rule, endpoint, view_func, methods=None):
        self.rule = rule
        self.endpoint = endpoint
        self.view_func = view_func
        self.methods = methods or ['GET']

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
        self._routes = []
        self.settings = {}
        self._view_functions = {}
        self._endpoints = {}
        self.enabled = True
        self._plugin_name = self.__class__.__name__.lower()  # 添加插件名称
    
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
        
        # 如果插件已启用，注册路由
        if self.enabled:
            self.register_routes()
    
    def route(self, rule, **options):
        """注册路由装饰器"""
        def decorator(f):
            # 使用插件名称作为前缀，确保端点唯一
            endpoint = options.pop('endpoint', f"{self._plugin_name}_{f.__name__}")
            route = DynamicRoute(rule, endpoint, f, options.get('methods', ['GET']))
            self._routes.append(route)
            self._view_functions[endpoint] = f
            return f
        return decorator
    
    def register_routes(self):
        """注册所有路由"""
        if not self.app:
            return
            
        for route in self._routes:
            if route.endpoint not in self.app.view_functions:
                # 注册视图函数
                view_func = route.view_func
                
                # 如果是静态文件路由，包装视图函数以确保独立性
                if 'static' in route.endpoint:
                    original_func = view_func
                    def wrapped_static_func(*args, **kwargs):
                        return original_func(*args, **kwargs)
                    view_func = wrapped_static_func
                
                self.app.view_functions[route.endpoint] = view_func
                
                # 创建路由规则
                rule = Rule(
                    route.rule,
                    endpoint=route.endpoint,
                    methods=route.methods,
                    strict_slashes=False
                )
                
                # 添加到 URL Map
                try:
                    self.app.url_map.add(rule)
                    print(f"[{self._plugin_name}] Registered route: {route.rule} -> {route.endpoint}")
                except Exception as e:
                    print(f"[{self._plugin_name}] Error registering route {route.rule}: {str(e)}")
    
    def unregister_routes(self):
        """注销所有路由"""
        if not self.app:
            return
            
        for route in self._routes:
            # 移除视图函数
            if route.endpoint in self.app.view_functions:
                del self.app.view_functions[route.endpoint]
            
            # 移除路由规则
            rules_to_remove = []
            for rule in self.app.url_map.iter_rules():
                if rule.endpoint == route.endpoint:
                    rules_to_remove.append(rule)
            
            for rule in rules_to_remove:
                self.app.url_map._rules.remove(rule)
                if rule.endpoint in self.app.url_map._rules_by_endpoint:
                    del self.app.url_map._rules_by_endpoint[rule.endpoint]
        
        # 更新 URL Map
        self.app.url_map.update()
        print(f"[{self._plugin_name}] Routes unregistered")
    
    def enable(self):
        """启用插件"""
        self.enabled = True
        self.register_routes()
        print(f"[{self._plugin_name}] Plugin enabled")
    
    def disable(self):
        """禁用插件"""
        self.enabled = False
        self.unregister_routes()
        print(f"[{self._plugin_name}] Plugin disabled")
    
    def load_settings(self):
        """加载插件设置"""
        try:
            # 每次都从数据库获取最新配置
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            if plugin and plugin.config:
                self.settings = plugin.config
            else:
                self.settings = self.default_settings.copy()
        except Exception as e:
            current_app.logger.error(f"Error loading plugin settings: {str(e)}")
            self.settings = self.default_settings.copy()
    
    def get_settings(self):
        """获取最新设置"""
        self.load_settings()  # 每次都重新加载
        return self.settings
    
    def save_settings(self, form_data):
        """保存插件设置的基类方法"""
        try:
            # 子类实现具体的设置保存逻辑
            settings = self._save_settings(form_data)
            
            # 保存到数据库
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            if plugin:
                plugin.config = settings
                db.session.commit()
                self.settings = settings
                return True, '设置已保存'
            return False, '插件不存在'
            
        except Exception as e:
            db.session.rollback()
            return False, f'保存设置失败: {str(e)}'
    
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
    
    def render_template(self, template_string, **context):
        """渲染模板并标记为安全的HTML"""
        rendered = render_template_string(template_string, **context)
        return Markup(rendered)

class PluginManager:
    """插件管理器"""
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.app = None
        self._original_rules = []
    
    def init_app(self, app):
        """初始化插件管理器"""
        self.app = app
        self._original_rules = list(app.url_map._rules)
        
        with app.app_context():
            self.register_existing_plugins()
            self.load_enabled_plugins()
    
    def load_plugin(self, plugin_name):
        """加载单个插件"""
        try:
            # 获取插件目录
            plugin_dir = os.path.join(os.path.dirname(__file__), 'installed', plugin_name)
            if not os.path.exists(plugin_dir):
                return False
            
            # 导入插件模块
            module = import_module(f'app.plugins.installed.{plugin_name}')
            
            # 加载插件配置
            with open(os.path.join(plugin_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
                plugin_info = json.load(f)
            
            plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
            
            # 如果插件已存在，先卸载它
            if plugin_name in self.plugins:
                old_plugin = self.plugins[plugin_name]
                old_plugin.disable()  # 禁用旧插件
                old_plugin.teardown()  # 清理旧插件
                del self.plugins[plugin_name]  # 移除旧插件
            
            # 创建新的插件实例
            plugin = plugin_class()
            
            # 初始化插件配置
            from app.models import Plugin as PluginModel
            plugin_record = PluginModel.query.filter_by(directory=plugin_name).first()
            if plugin_record:
                # 如果数据库中没有配置，使用插件的默认配置
                if not plugin_record.config and hasattr(plugin, 'default_settings'):
                    plugin_record.config = plugin.default_settings
                    db.session.commit()
            
            # 初始化插件
            plugin.init_app(self.app)
            
            # 保存插件实例
            self.plugins[plugin_name] = plugin
            
            print(f"Successfully loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {str(e)}")
            return False
    
    def unload_plugin(self, plugin_name):
        """卸载插件"""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.disable()  # 禁用插件
            plugin.teardown()  # 清理插件
            del self.plugins[plugin_name]  # 移除插件实例
            return True
        return False
    
    def reload_plugin(self, plugin_name):
        """重新加载插件"""
        self.unload_plugin(plugin_name)  # 先卸载
        return self.load_plugin(plugin_name)  # 再加载
    
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
                    # 导入插件模块以获取默认配置
                    module = import_module(f'app.plugins.installed.{plugin_name}')
                    with open(plugin_json, 'r', encoding='utf-8') as f:
                        plugin_info = json.load(f)
                    
                    # 使用插件的默认配置而不是 plugin.json 中的配置
                    plugin_class = getattr(module, plugin_info.get('plugin_class', 'Plugin'))
                    plugin = plugin_class()
                    
                    # 获取插件默认配置
                    default_config = plugin.default_settings if hasattr(plugin, 'default_settings') else {}
                    
                    # 添加到数据库，使用 plugin.json 中的 enabled 字段决定是否默认启用
                    enabled = plugin_info.get('enabled', True)  # 如果未指定，默认为启用
                    PluginModel.add_plugin(plugin_info, plugin_name, enabled=enabled, config=default_config)
                    print(f"Auto registered plugin: {plugin_name} (enabled: {enabled})")
                    
                except Exception as e:
                    print(f"Failed to register plugin {plugin_name}: {str(e)}")
    
    def load_enabled_plugins(self):
        """加载所有已启用的插件"""
        from app.models import Plugin as PluginModel
        
        # 获取所有已启用的插件
        enabled_plugins = PluginModel.query.filter_by(enabled=True).all()
        for plugin in enabled_plugins:
            self.load_plugin(plugin.directory)
    
    def get_plugin(self, name: str) -> PluginBase:
        """获取插件实例"""
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> List[PluginBase]:
        """获取所有已加载的插件"""
        return list(self.plugins.values())

# 创建局实例
plugin_manager = PluginManager()

def get_plugin_manager():
    return plugin_manager 