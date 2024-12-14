import os

from flask import Blueprint, render_template, render_template_string, request, flash, redirect, url_for, jsonify, send_file, current_app, abort, session
from flask_login import current_user
from functools import wraps
import json
import io
from app.services.admin_service import AdminService
from app.models.custom_page import CustomPage
from app.services.custom_page_service import CustomPageService
from app.utils.custom_pages import custom_page_manager
from app.models import CommentConfig
from app.models.site_config import SiteConfig
from app.utils.theme_manager import ThemeManager
from app.models.theme_settings import ThemeSettings
from app.models.category import Category

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # 未登录时重定向到管理员登录页面
            return redirect(url_for('admin.login'))

        if current_user.role != 'admin':
            flash('需要管理员权限')
            return redirect(url_for('blog.index'))  # 或者 abort(404) 如果你想对普通用户隐藏该页面存在

        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
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
            
        # 获取评论配置
        comment_config = CommentConfig.get_config()
        
        return render_template('admin/comments.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''),
                             comment_config=comment_config,
                             active_tab=request.args.get('tab', 'comments'))
                             
    except Exception as e:
        current_app.logger.error(f"Comments error: {str(e)}")
        abort(500)

@bp.route('/comments/<int:comment_id>', methods=['DELETE'])

@admin_required
def delete_comment(comment_id):
    """删除评论"""
    success, error = AdminService.delete_comment(comment_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/comments/<int:comment_id>/status', methods=['POST'])

@admin_required
def update_comment_status(comment_id):
    """更新评论状态"""
    data = request.get_json()
    status = data.get('status')
    if status not in ['approved', 'pending', 'rejected']:
        return jsonify({'error': '无效的状态值'}), 400

    success, message = AdminService.update_comment_status(comment_id, status)
    if not success:
        return jsonify({'error': message}), 400
    return '', 204

@bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])

@admin_required
def toggle_user_role(user_id):
    """切换用户角色"""
    success, error = AdminService.toggle_user_role(user_id, current_user.id)
    if not success:
        flash(error)
        return redirect(url_for('admin.users'))
    return '', 204

@bp.route('/users/<int:user_id>', methods=['DELETE'])

@admin_required
def delete_user(user_id):
    """删除用户"""
    success, error = AdminService.delete_user(user_id, current_user.id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/article/<int:article_id>', methods=['DELETE'])

@admin_required
def delete_article(article_id):
    """删除文章"""
    success, error = AdminService.delete_article(article_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/site-config', methods=['GET', 'POST'])
@admin_required
def site_config():
    """网站配置管理"""
    try:
        if request.method == 'POST':
            success, message = AdminService.update_site_config(request.form)
            return jsonify({
                'success': success,
                'message': message
            })
        
        configs, error = AdminService.get_site_configs()
        if error:
            return jsonify({
                'success': False,
                'message': error
            })
            
        if configs is None:
            abort(500)
            
        return render_template('admin/site_config.html', configs=configs)
        
    except Exception as e:
        current_app.logger.error(f"Site config error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        })
        abort(500)

@bp.route('/categories')

@admin_required
def categories():
    """分类管理"""
    try:
        pagination, error = AdminService.get_categories(
            page=request.args.get('page', 1, type=int),
            search_type=request.args.get('search_type', ''),
            search_query=request.args.get('q', '').strip()
        )
        
        # 获取可用的分类模板
        available_templates = AdminService.get_available_category_templates()
        
        return render_template('admin/categories.html',
                             pagination=pagination,
                             search_type=request.args.get('search_type', ''),
                             search_query=request.args.get('q', ''),
                             available_templates=available_templates)
                             
    except Exception as e:
        current_app.logger.error(f"Categories error: {str(e)}")
        abort(500)

@bp.route('/categories/add', methods=['POST'])

@admin_required
def add_category():
    """添加分类"""
    success, error, data = AdminService.add_category(request.form)
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/categories/<int:id>/edit', methods=['POST'])

@admin_required
def edit_category(id):
    """编辑分类"""
    success, error, data = AdminService.update_category(id, request.form)
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/categories/<int:id>/move', methods=['POST'])

@admin_required
def move_category(id):
    """移动分类"""
    success, message = AdminService.move_category(id, request.form.get('new_parent_id', type=int))
    if not success:
        return jsonify({'error': message}), 400
    return jsonify({'message': message})

@bp.route('/categories/<int:id>', methods=['DELETE'])

@admin_required
def delete_category(id):
    """删除分类"""
    success, message = AdminService.delete_category(id)
    if not success:
        return jsonify({'error': message}), 400
    return jsonify({'message': message})

@bp.route('/categories/sort', methods=['POST'])

@admin_required
def sort_categories():
    """排序分类"""
    data = request.get_json()
    if not data or 'category_ids' not in data:
        return jsonify({'error': '无效的请求数据'}), 400
        
    success, message = AdminService.sort_categories(data['category_ids'])
    if not success:
        return jsonify({'error': message}), 400
    return jsonify({'message': message})

@bp.route('/categories/<int:id>')

@admin_required
def get_category(id):
    """获取单个分类信息"""
    success, error, data = AdminService.get_category(id)
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/tags')

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

@admin_required
def add_tag():
    """添加标签"""
    success, error, data = AdminService.add_tag(request.form)
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/tags/<int:id>', methods=['DELETE'])

@admin_required
def delete_tag(id):
    """删除标签"""
    success, error = AdminService.delete_tag(id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/tags/<int:id>/edit', methods=['POST'])

@admin_required
def edit_tag(id):
    """编辑标签"""
    success, error, data = AdminService.edit_tag(
        id,
        request.form
    )
    if not success:
        return jsonify({'error': error}), 400
    return jsonify(data)

@bp.route('/users/add', methods=['POST'])

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

@admin_required
def delete_history(history_id):
    """删除浏览历史"""
    success, error = AdminService.delete_history(history_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/histories/clear/<int:user_id>', methods=['DELETE'])

@admin_required
def clear_user_history(user_id):
    """清除用户的所有浏览历史"""
    success, error = AdminService.clear_user_history(user_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/themes')

@admin_required
def themes():
    """主题管理"""
    try:
        # 直接获取完整的主题信息
        themes_dir = os.path.join(current_app.root_path, 'templates')
        themes = []
        
        # 定义需要排除的目录
        exclude_dirs = {'admin', 'errors', 'components', 'email'}
        
        for theme_id in os.listdir(themes_dir):
            # 排除特殊目录和非主题目录
            if (theme_id not in exclude_dirs and 
                os.path.isdir(os.path.join(themes_dir, theme_id)) and
                os.path.exists(os.path.join(themes_dir, theme_id, 'theme.json'))):
                
                theme_info = ThemeManager.get_theme_info(theme_id)
                if theme_info:
                    themes.append(theme_info)
        
        current_theme = SiteConfig.get_config('site_theme', 'default')
        
        return render_template('admin/themes.html',
                             themes=themes,
                             current_theme=current_theme)
    except Exception as e:
        current_app.logger.error(f"Themes error: {str(e)}")
        flash('获取主题列表失败')
        return redirect(url_for('admin.dashboard'))

@bp.route('/change-theme', methods=['POST'])

@admin_required
def change_theme():
    """更改主题"""
    success, message = AdminService.change_theme(request.form.get('theme'))
    ThemeManager.update_theme_loader(current_app)   #jinja2更新主题
    flash(message)
    if not success:
        return redirect(url_for('admin.themes'))
    return redirect(url_for('admin.themes'))

@bp.route('/theme-preview/<theme>')

@admin_required
def theme_preview(theme):
    """主题预览"""
    preview_path = os.path.join(current_app.root_path, 'templates', theme, 'preview.png')
    return send_file(preview_path, mimetype='image/png')

@bp.route('/plugins')

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

@admin_required
def uninstall_plugin(plugin_name):
    """卸载插件"""
    success, message = AdminService.uninstall_plugin(plugin_name)
    if not success:
        return jsonify({'status': 'error', 'message': message})
    return jsonify({'status': 'success', 'message': message})

@bp.route('/plugins/<path:plugin_name>/toggle', methods=['POST'])

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

@admin_required
def export_plugin(plugin_name):
    """导出插件"""
    success, error, content, filename = AdminService.export_plugin(plugin_name)
    
    if not success:
        flash(error, 'error')
        return redirect(url_for('admin.plugins'))
        
    # 置响应头
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

@admin_required
def delete_file(file_id):
    """删除文件"""
    success, error = AdminService.delete_file(file_id)
    if not success:
        return jsonify({'error': error}), 400
    return '', 204

@bp.route('/files/<int:file_id>/rename', methods=['POST'])

@admin_required
def rename_file(file_id):
    """重命名文件"""
    try:
        data = request.get_json()
        new_name = data.get('name', '').strip()
        
        if not new_name:
            return jsonify({'error': '文件名不能为空'}), 400
            
        success, message = AdminService.rename_file(file_id, new_name)
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': '文件名已更新'})
        
    except Exception as e:
        current_app.logger.error(f"Rename file error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 添加一个模板上下文处器
@bp.context_processor
def utility_processor():
    def is_active_group(menu_items):
        menu_endpoints = [item[0] for item in menu_items]
        current_endpoint = request.endpoint
        # 检查当前页面的endpoint是否在这个菜单组的任何子菜单中
        return current_endpoint in menu_endpoints
    
    def is_current_menu(menu_items):
        # 检查当页面是否属于这个菜单组
        current_endpoint = request.endpoint
        return current_endpoint and any(current_endpoint == item[0] for item in menu_items)
    
    return dict(
        is_active_group=is_active_group,
        is_current_menu=is_current_menu
    ) 

@bp.route('/cache')

@admin_required
def cache_stats():
    """缓存统计"""
    try:
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('q', '').strip()
        
        data, error = AdminService.get_cache_stats(page=page, search_query=search_query)
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

@admin_required
def check_plugin_settings(plugin_name):
    """检查插件是否有设置页面"""
    success, message = AdminService.check_plugin_settings(plugin_name)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/plugins/upload', methods=['POST'])

@admin_required
def upload_plugin():
    """上传插件"""
    success, message = AdminService.upload_plugin(request.files.get('plugin'))
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/plugins/<path:plugin_name>/settings/save', methods=['POST'])

@admin_required
def save_plugin_settings(plugin_name):
    """保存插件设置"""
    success, message = AdminService.save_plugin_settings(plugin_name, request.form)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/cache/clear/<path:key>', methods=['POST'])

@admin_required
def clear_cache(key):
    """清除指定的缓存"""
    success, message = AdminService.clear_single_cache(key)
    if not success:
        return jsonify({'error': f'清除缓存失败：{message}'}), 500
    return jsonify({'message': message}), 200 

@bp.route('/routes')

@admin_required
def routes():
    """路由管理"""
    try:
        # 如果是文章URL配置tab，使用单独的模板
        if request.args.get('tab') == 'article_url':
            # 获取当前文章 URL 模式
            current_pattern = SiteConfig.get_article_url_pattern()
            # 断是否是预定义模式
            is_custom_pattern = True
            for pattern in SiteConfig.ARTICLE_URL_PATTERNS.values():
                if pattern and pattern == current_pattern:
                    is_custom_pattern = False
                    break
                    
            return render_template('admin/article_url_settings.html',  # 使用新模板
                                 current_pattern=current_pattern,
                                 is_custom_pattern=is_custom_pattern)
        
        # 原有的路由管理代码
        pagination, error = AdminService.get_routes(
            page=request.args.get('page', 1, type=int),
            search_query=request.args.get('q', '').strip()
        )
        
        if error:
            flash(error)
            return redirect(url_for('admin.routes'))
            
        return render_template('admin/routes.html',
                             pagination=pagination,
                             search_query=request.args.get('q', ''),
                             available_endpoints=AdminService.get_available_endpoints())
                             
    except Exception as e:
        current_app.logger.error(f"Routes error: {str(e)}")
        abort(500)

@bp.route('/routes/add', methods=['POST'])

@admin_required
def add_route():
    """添加路由"""
    success, message = AdminService.add_route(request.form)
    flash(message)
    return redirect(url_for('admin.routes'))

@bp.route('/routes/<int:id>/edit', methods=['POST'])

@admin_required
def edit_route(id):
    """编辑路由"""
    success, message = AdminService.update_route(id, request.form)
    flash(message)
    return redirect(url_for('admin.routes'))

@bp.route('/routes/<int:id>/delete', methods=['POST'])

@admin_required
def delete_route(id):
    """删除路由"""
    success, message = AdminService.delete_route(id)
    flash(message)
    return redirect(url_for('admin.routes')) 

@bp.route('/custom_pages')

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
                             pagination=pagination,
                             CustomPage=CustomPage
                               )
    except Exception as e:
        current_app.logger.error(f"Custom pages error: {str(e)}")
        flash('获取自定义页面列表失败')
        return redirect(url_for('admin.dashboard'))

@bp.route('/custom_pages/add', methods=['POST'])

@admin_required
def add_custom_page():
    """添加自定义页面"""
    try:
        data = {
            'key': request.form.get('key'),
            'title': request.form.get('title'),
            'template': request.form.get('template'),
            'route': request.form.get('route'),
            'content': request.form.get('content', ''),
            'fields': json.loads(request.form.get('fields', '{}')),
            'require_login': request.form.get('require_login') == 'true',
            'status': int(request.form.get('status', CustomPage.STATUS_PUBLIC)),
            'allow_comment': request.form.get('allow_comment') == 'true'
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
                         title='编辑页面',
                          CustomPage=CustomPage
                           )

@bp.route('/custom_pages/<int:id>/update', methods=['POST'])

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
            'require_login': request.form.get('require_login') == 'true',
            'status': int(request.form.get('status', CustomPage.STATUS_PUBLIC)),
            'allow_comment': request.form.get('allow_comment') == 'true'
        }
        
        success, message, _ = CustomPageService.edit_page(id, data)
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': message})
    except Exception as e:
        current_app.logger.error(f"Edit custom page error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/custom_pages/<int:id>', methods=['DELETE'])

@admin_required
def delete_custom_page(id):
    """删除自定义页面"""
    success, message = CustomPageService.delete_page(id)
    if not success:
        return jsonify({'error': message}), 400
        
    return jsonify({'message': message}) 

@bp.route('/custom_pages/create')

@admin_required
def create_custom_page():
    """创建自定义页面"""
    templates = custom_page_manager.get_custom_templates()
    return render_template('admin/custom_page_form.html',
                         title='创建页面',
                         page=None,
                         templates=templates,
                         CustomPage=CustomPage)

@bp.route('/categories/all')

@admin_required
def get_all_categories():
    """获取所有分类(用于移动分类选择)"""
    categories, error = AdminService.get_all_categories()
    if error:
        return jsonify({'error': error}), 400
    return jsonify(categories)

@bp.route('/comments/config', methods=['POST'])

@admin_required
def update_comment_config():
    """更新评论配置"""
    success, message = AdminService.update_comment_config(request.form)
    if not success:
        return jsonify({'error': message}), 400
    return jsonify({'message': message})

@bp.route('/comments/<int:comment_id>/approve', methods=['POST'])

@admin_required
def approve_comment(comment_id):
    """通过评论"""
    success, message = AdminService.update_comment_status(comment_id, 'approved')
    if not success:
        return jsonify({'error': message}), 400
    return '', 204

@bp.route('/comments/<int:comment_id>/reject', methods=['POST'])

@admin_required
def reject_comment(comment_id):
    """拒绝评论"""
    success, message = AdminService.update_comment_status(comment_id, 'rejected')
    if not success:
        return jsonify({'error': message}), 400
    return '', 204

@bp.route('/article-url-config', methods=['GET', 'POST'])

@admin_required
def article_url_config():
    """文章URL配置"""
    if request.method == 'POST':
        data = request.get_json()
        success, message = AdminService.update_article_url_pattern(
            data.get('pattern_type'),
            data.get('custom_pattern'),
            data.get('encode_settings')
        )
        if not success:
            return jsonify({'error': message}), 400
        return jsonify({'message': message})
        
    # 获取当前配置
    pattern = SiteConfig.get_article_url_pattern()
    
    # 判断当前模式类型
    pattern_type = 'custom'
    for key, value in SiteConfig.ARTICLE_URL_PATTERNS.items():
        if value == pattern:
            pattern_type = key
            break
            
    return render_template('admin/article_url_settings.html',
                         pattern=pattern,
                         pattern_type=pattern_type,
                         site_config=SiteConfig)

@bp.route('/plugins/reload-list', methods=['POST'])

@admin_required
def reload_plugin_list():
    """重新加载插件列表"""
    success, message = AdminService.reload_plugin_list()
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/themes/<theme_id>/settings/page')

@admin_required
def theme_settings_page(theme_id):
    """主题设置页面"""
    # 获取主题信息
    theme_info = ThemeManager.get_theme_info(theme_id)
    if not theme_info:
        flash('主题不存在')
        return redirect(url_for('admin.themes'))
        
    # 获取主题设置
    settings = ThemeSettings.get_settings(theme_id)
    
    # 获取设置模板
    settings_html = ThemeManager.get_theme_settings_template(theme_id)
    if not settings_html:
        flash('此主题没有设置页面')
        return redirect(url_for('admin.themes'))
        
    # 先渲染设置模板
    rendered_settings = render_template_string(
        settings_html,
        settings=settings
    )
        
    # 再渲染整个页面
    return render_template('admin/theme_settings_page.html',
                         theme=theme_info,
                         settings_html=rendered_settings)

@bp.route('/themes/<theme_id>/settings/save', methods=['POST'])

@admin_required
def save_theme_settings(theme_id):
    """保存主题设置"""
    success, message = ThemeManager.save_theme_settings(theme_id, request.form.to_dict())
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/themes/upload', methods=['POST'])

@admin_required
def upload_theme():
    """上传主题"""
    if 'theme' not in request.files:
        return jsonify({'status': 'error', 'message': '没有上传文件'})
        
    file = request.files['theme']
    if not file.filename:
        return jsonify({'status': 'error', 'message': '没有选择文件'})
        
    if not file.filename.endswith('.zip'):
        return jsonify({'status': 'error', 'message': '只支持zip格式的主题'})
        
    success, message = ThemeManager.install_theme(file)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/themes/<theme_id>/export')

@admin_required
def export_theme(theme_id):
    """导出主题"""
    success, error, content, filename = ThemeManager.export_theme(theme_id)
    
    if not success:
        flash(error, 'error')
        return redirect(url_for('admin.themes'))
        
    response = send_file(
        io.BytesIO(content),
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Pragma"] = "no-cache"
    return response

@bp.route('/themes/<theme>/preview_image')

@admin_required
def theme_preview_image(theme):
    """主题预览图"""
    preview_path = os.path.join(
        current_app.root_path, 
        'templates', 
        theme, 
        'preview.png'
    )
    if os.path.exists(preview_path):
        return send_file(preview_path, mimetype='image/png')
    return send_file('static/default_theme_preview.png', mimetype='image/png')

@bp.route('/themes/<theme_id>/uninstall', methods=['POST'])

@admin_required
def uninstall_theme(theme_id):
    """卸载主题"""
    success, message = ThemeManager.uninstall_theme(theme_id)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': message
    })

@bp.route('/categories/batch-per-page', methods=['POST'])

@admin_required
def batch_update_category_per_page():
    """批量更新分类每页文章数"""
    try:
        data = request.get_json()
        per_page = data.get('per_page')
        if not per_page:
            return jsonify({'error': '请提供每页文章数'}), 400
            
        success, message = AdminService.batch_update_per_page(per_page)
        if success:
            return jsonify({'message': message})
        return jsonify({'error': message}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/article/edit', methods=['GET', 'POST'])
@bp.route('/article/<int:id>/edit', methods=['GET', 'POST'])

@admin_required
def edit_article(id=None):
    """编辑/创建文章"""
    try:
        if request.method == 'POST':
            success, message, data = AdminService.save_article(id, request.form)
            return jsonify({
                'error': message if not success else None,
                'message': message if success else None,
                'url': url_for('admin.articles') if success else None
            })
            
        # GET 请求
        if id:
            article = AdminService.get_article_for_edit(id)
            if not article:
                abort(404)
        else:
            article = None
            
        # 获取分类列表
        categories = Category.query.order_by(Category.sort_order).all()
        
        return render_template('admin/articles_edit.html',
                             article=article,
                             categories=categories)
                             
    except Exception as e:
        current_app.logger.error(f"Edit article error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/categories/update-counts', methods=['POST'])

@admin_required
def update_category_counts():
    """更新分类文章数"""
    try:
        category_ids = request.json.get('category_ids', [])
        success, result = AdminService.update_category_counts(category_ids)
        
        if not success:
            return jsonify({'error': result}), 400
            
        return jsonify({
            'success': True,
            'updated': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/tags/update-counts', methods=['POST'])

@admin_required
def update_tag_counts():
    """更新标签文章数"""
    try:
        tag_ids = request.json.get('tag_ids', [])
        success, result = AdminService.update_tag_counts(tag_ids)
        
        if not success:
            return jsonify({'error': result}), 400
            
        return jsonify({
            'success': True,
            'updated': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/categories/update-all-counts', methods=['POST'])

@admin_required
def update_all_category_counts():
    """更新所有分类文章数"""
    try:
        success, result = AdminService.update_all_category_counts()
        
        if not success:
            return jsonify({'error': result}), 400
            
        return jsonify({
            'success': True,
            'message': '所有分类计数已更新',
            'updated': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/tags/update-all-counts', methods=['POST'])

@admin_required
def update_all_tag_counts():
    """更新所有标签文章数"""
    try:
        success, result = AdminService.update_all_tag_counts()
        
        if not success:
            return jsonify({'error': result}), 400
            
        return jsonify({
            'success': True,
            'message': '所有标签计数已更新',
            'updated': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/articles/batch-delete', methods=['POST'])

@admin_required
def batch_delete_articles():
    """批量删除文章"""
    try:
        article_ids = request.json.get('article_ids', [])
        if not article_ids:
            return jsonify({'error': '未选择文章'}), 400
            
        success, message = AdminService.batch_delete_articles(
            article_ids,
            current_user.id,
            current_user.role == 'admin'
        )
        
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': '删除成功'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/comments/batch-delete', methods=['POST'])

@admin_required
def batch_delete_comments():
    """批量删除评论"""
    try:
        comment_ids = request.json.get('comment_ids', [])
        if not comment_ids:
            return jsonify({'error': '未选择评论'}), 400
            
        success, message = AdminService.batch_delete_comments(comment_ids)
        
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': '删除成功'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/tags/batch-set-access-mode', methods=['POST'])

@admin_required
def batch_set_tags_access_mode():
    """批量设置标签访问方式"""
    try:
        data = request.get_json()
        mode = data.get('mode')
        
        success, message = AdminService.batch_set_tags_access_mode(mode)
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': message})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/upload-settings', methods=['POST'])

@admin_required
def save_upload_settings():
    """保存上传设置"""
    try:
        data = request.get_json()

        # 验证和清理数据
        allowed_types = data.get('upload_allowed_types', '').strip()
        max_size = int(data.get('upload_max_size', 10))
        
        if max_size < 1 or max_size > 100:
            return jsonify({'error': '上传大小必须在1-100MB之间'}), 400
            
        # 使用专门的上传设置服务方法
        success, message = AdminService.save_upload_settings(allowed_types, max_size)
        
        if not success:
            return jsonify({'error': message}), 400
            
        return jsonify({'message': message})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """管理员登录"""
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        success, message, user = AdminService.admin_login(
            username=request.form.get('username'),
            password=request.form.get('password'),
            remember=request.form.get('remember', False)
        )
        
        if success:
            # 获取next参数
            next_page = request.args.get('next')
            admin_url = url_for('admin.dashboard')  # 获取后台URL前缀
            if not next_page or not next_page.startswith(admin_url):
                next_page = url_for('admin.dashboard')
            return redirect(next_page)
        else:
            flash(message, 'error')
            
    return render_template('admin/login.html')

@bp.context_processor
def admin_context():
    """添加后台相关的上下文变量"""
    # 在函数开始时就计算好 admin_url，避免重复计算
    admin_url = url_for('admin.dashboard')
    
    return {
        'admin_url': admin_url,
        'is_admin_url': lambda path: path.startswith(admin_url)
    }