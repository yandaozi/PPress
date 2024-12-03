from flask import current_app, abort
from werkzeug.routing import Rule
from threading import Lock
from app.models import Route
from app.utils.cache_manager import cache_manager
import time

class RouteManager:
    """路由管理器 - 只负责路由规则的管理"""
    _instance = None
    _lock = Lock()
    _original_views = {}  # 存储原始视图函数的引用

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._route_lock = Lock()

    def refresh_routes(self):
        """刷新自定义路由"""
        # 使用缓存检查是否需要刷新
        cache_key = 'routes_last_refresh'
        last_refresh = cache_manager.get(cache_key)
        current_time = time.time()
        
        if last_refresh and current_time - last_refresh < 1:
            return True
        
        with self._route_lock:
            try:
                print("\n[Route System] 开始刷新路由...")
                
                # 更新刷新时间
                cache_manager.set(cache_key, current_time)
                
                # 清除路由状态缓存
                route_keys = [k for k in cache_manager._cache.keys() if k.startswith('route_status:')]
                for key in route_keys:
                    cache_manager.delete(key)
                
                # 1. 清理所有自定义路由
                self._clear_custom_routes()
                
                # 2. 注册活动路由
                self._register_active_routes()
                
                print("[Route System] 路由刷新完成!\n")
                return True
                
            except Exception as e:
                current_app.logger.error(f"Error refreshing routes: {str(e)}")
                print(f"[Route System] 路由刷新失败: {str(e)}\n")
                return False

    def _clear_custom_routes(self):
        """清理所有自定义路由规则"""
        rules_to_remove = []
        for rule in current_app.url_map.iter_rules():
            if hasattr(rule, 'is_custom_route'):
                rules_to_remove.append(rule)
        
        for rule in rules_to_remove:
            try:
                # 从 url_map 中移除规则
                current_app.url_map._rules.remove(rule)
                if rule.endpoint in current_app.url_map._rules_by_endpoint:
                    current_app.url_map._rules_by_endpoint[rule.endpoint].remove(rule)
                    if not current_app.url_map._rules_by_endpoint[rule.endpoint]:
                        del current_app.url_map._rules_by_endpoint[rule.endpoint]
                
                # 恢复原始视图函数
                if rule.endpoint.startswith('custom_'):
                    route_id = int(rule.endpoint.replace('custom_', ''))
                    route = Route.query.get(route_id)
                    if route:
                        original_endpoint = route.original_endpoint
                        # 如果有保存的原始视图函数，恢复它
                        if original_endpoint in self._original_views:
                            current_app.view_functions[original_endpoint] = self._original_views[original_endpoint]
                            del self._original_views[original_endpoint]
                
                # 清理自定义视图函数
                if rule.endpoint in current_app.view_functions:
                    del current_app.view_functions[rule.endpoint]
                
                print(f"[Route System] 已清理路由: {rule.rule} -> {rule.endpoint}")
            except Exception as e:
                print(f"[Route System] 清理路由时出错: {rule.rule} -> {str(e)}")

    def _register_active_routes(self):
        """注册活动的自定义路由规则"""
        active_routes = Route.query.filter_by(is_active=True).all()
        for route in active_routes:
            try:
                self._register_route(route)
            except Exception as e:
                print(f"[Route System] 注册路由时出错: {route.path} -> {str(e)}")

    def _register_route(self, route):
        """注册单个路由规则"""
        # 查找原始路由规则
        original_rule = None
        original_view = None
        for rule in current_app.url_map.iter_rules():
            if rule.endpoint == route.original_endpoint:
                original_rule = rule
                original_view = current_app.view_functions.get(route.original_endpoint)
                break
        
        if not original_rule or not original_view:
            print(f"[Route System] 跳过无效路由: {route.original_endpoint}")
            return
        
        # 创建新的路由规则
        new_path = route.path if route.path.startswith('/') else '/' + route.path
        custom_endpoint = f'custom_{route.id}'
        
        # 保存原始视图函数
        self._original_views[route.original_endpoint] = original_view
        
        # 注册新的视图函数
        current_app.view_functions[custom_endpoint] = original_view
        current_app.view_functions[route.original_endpoint] = lambda *args, **kwargs: abort(404)
        
        # 添加新路由规则
        new_rule = Rule(
            new_path,
            endpoint=custom_endpoint,
            methods=original_rule.methods,
            defaults=original_rule.defaults,
            subdomain=original_rule.subdomain,
            strict_slashes=original_rule.strict_slashes,
            build_only=original_rule.build_only,
            redirect_to=original_rule.redirect_to
        )
        new_rule.is_custom_route = True
        current_app.url_map.add(new_rule)
        
        print(f"[Route System] 已注册路由: {new_path} -> {custom_endpoint}")

# 创建全局实例
route_manager = RouteManager() 