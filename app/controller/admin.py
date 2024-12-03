import os

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, current_app, abort
from flask_login import login_required, current_user
from functools import wraps
import json
import numpy as np
import io
from app.services.admin_service import AdminService
from app.models.custom_page import CustomPage
from app import db
from app.services.custom_page_service import CustomPageService
from app.utils.custom_pages import custom_page_manager

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('需要管理员权限')
            return redirect(url_for('blog.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
@login_required
@admin_required
def dashboard():
    """管理后台首页"""
    try:
        data = AdminService.get_dashboard_data()
        if not data:
            abort(500)
        return render_template('admin/dashboard.html', **data)
    except Exception as e:
        current_app.logger.error(f"Dashboard error: {str(e)}")
        abort(500)

@bp.route('/users')
@login_required
@admin_required
def users():
    """用户管理"""
    try:
        pagination, error = AdminService.get_users(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.users'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/users.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Users error: {str(e)}")
        abort(500)

@bp.route('/articles')
@login_required
@admin_required
def articles():
    """文章管理"""
    try:
        pagination, error = AdminService.get_articles(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.articles'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/articles.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Articles error: {str(e)}")
        abort(500)

@bp.route('/comments')
@login_required
@admin_required
def comments():
    """评论管理"""
    try:
        pagination, error = AdminService.get_comments(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.comments'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/comments.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Comments error: {str(e)}")
        abort(500)

@bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_comment(comment_id):
    """删除评论"""
    success, error = AdminService.delete_comment(comment_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
@login_required
@admin_required
def toggle_user_role(user_id):
    """切换用户角色"""
    success, error = AdminService.toggle_user_role(user_id, current_user.id)
    if not success:
        flash(error)
        return redirect(url_for('admin.users'))
    return '', 204

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户"""
    success, error = AdminService.delete_user(user_id, current_user.id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/articles/<int:article_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_article(article_id):
    """删除文章"""
    success, error = AdminService.delete_article(article_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/site-config', methods=['GET', 'POST'])
@login_required
@admin_required
def site_config():
    """网站配置管理"""
    try:
        if request.method == 'POST':
            success, message = AdminService.update_site_config(request.form)
            flash(message)
            if success:
                return redirect(url_for('admin.site_config'))
        
        configs, error = AdminService.get_site_configs()
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        if configs is None:
            abort(500)
            
        return render_template('admin/site_config.html', configs=configs)
        
    except Exception as e:
        current_app.logger.error(f"Site config error: {str(e)}")
        abort(500)

@bp.route('/categories')
@login_required
@admin_required
def categories():
    """分类管理"""
    try:
        pagination, error = AdminService.get_categories(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.categories'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/categories.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Categories error: {str(e)}")
        abort(500)

@bp.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    """添加分类"""
    success, error, data = AdminService.add_category(
        request.form.get('name'),
        request.form.get('description')
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/categories/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_category(id):
    """删除分类"""
    success, error = AdminService.delete_category(id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/categories/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_category(id):
    """编辑分类"""
    success, error, data = AdminService.edit_category(
        id,
        request.form.get('name'),
        request.form.get('description')
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/tags')
@login_required
@admin_required
def tags():
    """标签管理"""
    try:
        pagination, error = AdminService.get_tags(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.tags'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/tags.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Tags error: {str(e)}")
        abort(500)

@bp.route('/tags/add', methods=['POST'])
@login_required
@admin_required
def add_tag():
    """添加标签"""
    success, error, data = AdminService.add_tag(request.form.get('name'))
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/tags/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_tag(id):
    """删除标签"""
    success, error = AdminService.delete_tag(id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/tags/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_tag(id):
    """编辑标签"""
    success, error, data = AdminService.edit_tag(
        id,
        request.form.get('name')
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    """添加用户"""
    success, error, data = AdminService.add_user(
        request.form.get('username'),
        request.form.get('email'),
        request.form.get('password'),
        request.form.get('role', 'user')
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    """编辑用户"""
    success, error, data = AdminService.edit_user(
        user_id,
        request.form,
        current_user.id
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/histories')
@login_required
@admin_required
def histories():
    """浏览历史管理"""
    try:
        pagination, error = AdminService.get_histories(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.histories'))
            
        if not pagination:
            abort(500)
            
        return render_template('admin/histories.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''))
                             
    except Exception as e:
        current_app.logger.error(f"Histories error: {str(e)}")
        abort(500)

@bp.route('/histories/<int:history_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_history(history_id):
    """删除浏览历史"""
    success, error = AdminService.delete_history(history_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/histories/clear/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def clear_user_history(user_id):
    """清除用户的所有浏览历史"""
    success, error = AdminService.clear_user_history(user_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/themes')
@login_required
@admin_required
def themes():
    """主题管理"""
    try:
        data, error = AdminService.get_themes()
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        if not data:
            abort(500)
            
        return render_template('admin/themes.html', **data)
        
    except Exception as e:
        current_app.logger.error(f"Themes error: {str(e)}")
        abort(500)

@bp.route('/change-theme', methods=['POST'])
@login_required
@admin_required
def change_theme():
    """更改主题"""
    success, message = AdminService.change_theme(request.form.get('theme'))
    flash(message)
    if not success:
        return redirect(url_for('admin.themes'))
    return redirect(url_for('admin.themes'))

@bp.route('/theme-preview/<theme>')
@login_required
@admin_required
def theme_preview(theme):
    """主题预览"""
    preview_path = os.path.join(current_app.root_path, 'templates', theme, 'preview.png')
    return send_file(preview_path, mimetype='image/png')

@bp.route('/plugins')
@login_required
@admin_required
def plugins():
    """插件管理页面"""
    try:
        data, error = AdminService.get_plugins(
            page=request.args.get('page', 1, type=int),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        if not data:
            abort(500)
            
        return render_template('admin/plugins.html', **data)
        
    except Exception as e:
        flash(f'加载插件列表失败: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/plugins/<plugin_name>/uninstall', methods=['POST'])
@login_required
@admin_required
def uninstall_plugin(plugin_name):
    """卸载插件"""
    success, message = AdminService.uninstall_plugin(plugin_name)
    if not success:
        return jsonify({'status': 'error', 'message': message})
    return jsonify({'status': 'success', 'message': message})

@bp.route('/plugins/<path:plugin_name>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_plugin(plugin_name):
    """启用/禁用插件"""
    success, message = AdminService.toggle_plugin(plugin_name)
    if not success:
        return jsonify({'status': 'error', 'message': message})
    return jsonify({
        'status': 'success',
        'message': message,
        'reload_required': False
    })

@bp.route('/plugins/<plugin_name>/export')
@login_required
@admin_required
def export_plugin(plugin_name):
    """导出插件"""
    success, error, content, filename = AdminService.export_plugin(plugin_name)
    
    if not success:
        flash(error, 'error')
        return redirect(url_for('admin.plugins'))
        
    # 设置响应头
    response = send_file(
        io.BytesIO(content),
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Pragma"] = "no-cache"
    return response

@bp.route('/plugins/<path:plugin_name>/reload', methods=['POST'])
@login_required
@admin_required
def reload_plugin(plugin_name):
    """重新加载插件"""
    success, message = AdminService.reload_plugin(plugin_name)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message,
        'reload_required': True
    })

@bp.route('/files')
@login_required
@admin_required
def manage_files():
    """文件管理"""
    try:
        data, error = AdminService.get_files(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('type', 'filename'),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        if not data:
            abort(500)
            
        return render_template('admin/files.html', **data)
        
    except Exception as e:
        current_app.logger.error(f"Files error: {str(e)}")
        abort(500)

@bp.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_file(file_id):
    """删除文件"""
    success, error = AdminService.delete_file(file_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

# 添加一个模板上下文处理器
@bp.context_processor
def utility_processor():
    def is_active_group(menu_items):
        menu_endpoints = [item[0] for item in menu_items]
        current_endpoint = request.endpoint
        # 检查当前页面的endpoint是否在这个菜单组的任何子菜单中
        return current_endpoint in menu_endpoints
    
    def is_current_menu(menu_items):
        # 检查当前页面是否属于这个菜单组
        current_endpoint = request.endpoint
        return current_endpoint and any(current_endpoint == item[0] for item in menu_items)
    
    return dict(
        is_active_group=is_active_group,
        is_current_menu=is_current_menu
    ) 

@bp.route('/cache')
@login_required
@admin_required
def cache_stats():
    """缓存统计"""
    try:
        page = request.args.get('page', 1, type=int)
        data, error = AdminService.get_cache_stats(page=page)
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        if not data:
            abort(500)
            
        return render_template('admin/cache.html', **data)
        
    except Exception as e:
        current_app.logger.error(f"Cache stats error: {str(e)}")
        abort(500)

@bp.route('/cache/clear/category/<category>', methods=['POST'])
@login_required
@admin_required
def clear_cache_by_category(category):
    """按类别清除缓存"""
    try:
        success, result = AdminService.clear_cache_by_category(category)
        if not success:
            return jsonify({'error': f'清除缓存失败：{result}'}), 500
            
        return jsonify({
            'message': f'已清除 {result} 个缓存',
            'category': category
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'清除缓存失败：{str(e)}'}), 500

@bp.route('/plugins/<path:plugin_name>/settings')
@login_required
@admin_required
def plugin_settings(plugin_name):
    """插件设置页面"""
    success, error, plugin_record, settings_html = AdminService.get_plugin_settings(plugin_name)
    
    if not success:
        flash(error, 'error')
        return redirect(url_for('admin.plugins'))
        
    return render_template('admin/plugin_settings.html',
                         plugin=plugin_record,
                         settings_html=settings_html)

@bp.route('/plugins/<path:plugin_name>/settings/check')
@login_required
@admin_required
def check_plugin_settings(plugin_name):
    """检查插件是否有设置页面"""
    success, message = AdminService.check_plugin_settings(plugin_name)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/plugins/upload', methods=['POST'])
@login_required
@admin_required
def upload_plugin():
    """上传插件"""
    success, message = AdminService.upload_plugin(request.files.get('plugin'))
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/plugins/<path:plugin_name>/settings/save', methods=['POST'])
@login_required
@admin_required
def save_plugin_settings(plugin_name):
    """保存插件设置"""
    success, message = AdminService.save_plugin_settings(plugin_name, request.form)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/cache/clear/<path:key>', methods=['POST'])
@login_required
@admin_required
def clear_cache(key):
    """清除指定的缓存"""
    success, message = AdminService.clear_single_cache(key)
    if not success:
        return jsonify({'error': f'清除缓存失败：{message}'}), 500
    return jsonify({'message': message}), 200 

@bp.route('/routes')
@login_required
@admin_required
def routes():
    """路由管理"""
    try:
        pagination, error = AdminService.get_routes(
            page=request.args.get('page', 1, type=int),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.dashboard'))
            
        # 获取可用端点
        available_endpoints = AdminService.get_available_endpoints()
            
        return render_template('admin/routes.html',
                             pagination=pagination,
                             search_query=request.args.get('q', ''),
                             available_endpoints=available_endpoints)
                             
    except Exception as e:
        current_app.logger.error(f"Routes error: {str(e)}")
        flash('路由管理加载失败')
        return redirect(url_for('admin.dashboard'))

@bp.route('/routes/add', methods=['POST'])
@login_required
@admin_required
def add_route():
    """添加路由"""
    success, message = AdminService.add_route(request.form)
    flash(message)
    return redirect(url_for('admin.routes'))

@bp.route('/routes/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_route(id):
    """编辑路由"""
    success, message = AdminService.update_route(id, request.form)
    flash(message)
    return redirect(url_for('admin.routes'))

@bp.route('/routes/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_route(id):
    """删除路由"""
    success, message = AdminService.delete_route(id)
    flash(message)
    return redirect(url_for('admin.routes')) 

@bp.route('/custom_pages')
@login_required
@admin_required
def custom_pages():
    """自定义页面管理"""
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        # 分页查询
        pagination = CustomPage.query.order_by(CustomPage.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('admin/custom_pages.html', 
                             pagination=pagination)
    except Exception as e:
        current_app.logger.error(f"Custom pages error: {str(e)}")
        flash('获取自定义页面列表失败')
        return redirect(url_for('admin.dashboard'))

@bp.route('/custom_pages/add', methods=['POST'])
@login_required
@admin_required
def add_custom_page():
    """添加自定义页面"""
    try:
        data = {
            'key': request.form.get('key'),
            'title': request.form.get('title'),
            'template': request.form.get('template'),
            'route': request.form.get('route'),
            'content': request.form.get('content', ''),  # 直接获取内容，不需要 JSON 解析
            'fields': json.loads(request.form.get('fields', '{}')),  # 解析字段 JSON
            'require_login': request.form.get('require_login') == 'true'
        }
        
        success, message, page = CustomPageService.add_page(data)
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({
            'message': message,
            'page': page
        })
    except Exception as e:
        current_app.logger.error(f"Add custom page error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/custom_pages/<int:id>', methods=['GET'])
@login_required
@admin_required
def get_custom_page(id):
    """获取自定义页面"""
    success, error, page = CustomPageService.get_page(id)
    if not success:
        return jsonify({'error': error}), 404
        
    return jsonify({
        'id': page.id,
        'key': page.key,
        'title': page.title,
        'template': page.template,
        'route': page.route,
        'content': page.content,
        'require_login': page.require_login
    })

@bp.route('/custom_pages/<int:id>/edit', methods=['GET'])
@login_required
@admin_required
def edit_custom_page(id):
    """编辑自定义页面表单"""
    success, error, page = CustomPageService.get_page(id)
    if not success:
        flash(error)
        return redirect(url_for('admin.custom_pages'))
        
    templates = custom_page_manager.get_custom_templates()
    return render_template('admin/custom_page_form.html',
                         page=page,
                         templates=templates,
                         title='编辑页面')

@bp.route('/custom_pages/<int:id>/update', methods=['POST'])
@login_required
@admin_required 
def update_custom_page(id):
    """更新自定义页面"""
    try:
        data = {
            'key': request.form.get('key'),  # 添加key字段
            'title': request.form.get('title'),
            'template': request.form.get('template'),
            'route': request.form.get('route'),
            'content': request.form.get('content', ''),
            'fields': json.loads(request.form.get('fields', '{}')),
            'require_login': request.form.get('require_login') == 'true'
        }
        
        success, message, _ = CustomPageService.edit_page(id, data)
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': message})
    except Exception as e:
        current_app.logger.error(f"Edit custom page error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/custom_pages/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_custom_page(id):
    """删除自定义页面"""
    success, message = CustomPageService.delete_page(id)
    if not success:
        return jsonify({'error': message}), 400
        
    return jsonify({'message': message}) 

@bp.route('/custom_pages/create')
@login_required
@admin_required
def create_custom_page():
    """创建自定义页面"""
    templates = custom_page_manager.get_custom_templates()
    return render_template('admin/custom_page_form.html',
                         title='创建页面',
                         page=None,
                         templates=templates)