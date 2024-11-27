import random
import os

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, current_app
from flask_login import login_required, current_user
from app.models.user import User
from app.models.article import Article
from app.models.comment import Comment
from app.models.view_history import ViewHistory
from app.models.site_config import SiteConfig
from app.models.category import Category
from app.models.tag import Tag
from app.models import Plugin
from app import db
from functools import wraps
import pandas as pd
import plotly.express as px
import json
import numpy as np
from ..utils.theme_manager import ThemeManager
from app.plugins import plugin_manager, get_plugin_manager
import io

bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('需要管理员权限')
            return redirect(url_for('blog.index'))
        return f(*args, **kwargs)
    return decorated_function

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    # 基础统计数据
    total_users = User.query.count()
    total_articles = Article.query.count()
    total_comments = Comment.query.count()
    total_views = ViewHistory.query.count()
    
    # 获取所有分类
    categories = Category.query.all()
    
    # 获取所有标签并随机选择10个
    all_tags = Tag.query.all()
    tags = random.sample(all_tags, min(15, len(all_tags)))  # 如果标签总数少于15个，就全部显示
    
    # 访问量统计图表
    article_views = db.session.query(
        Article.title,
        db.func.count(ViewHistory.id).label('views')
    ).join(ViewHistory)\
     .group_by(Article.id, Article.title)\
     .order_by(db.func.count(ViewHistory.id).desc())\
     .limit(20)\
     .all()
    
    # 生成图表
    if article_views:
        df = pd.DataFrame(article_views, columns=['title', 'views'])
        df['title'] = df['title'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
        fig = px.bar(df, 
                    x='views', 
                    y='title',
                    orientation='h',
                    title='热门文章访问量统计（Top 20）',
                    labels={'views': '访问量', 'title': ''})
        fig.update_layout(
            height=550,
            showlegend=False,
            plot_bgcolor='white',
            title_x=0.5,
            yaxis={'categoryorder': 'total ascending'}
        )
        views_chart = json.dumps(fig.to_dict(), cls=NumpyEncoder)
    else:
        views_chart = None
    
    # 创建一个辅助函数来处理用户信息
    def get_user_info(user):
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'avatar': user.avatar
            }
        return {
            'id': None,
            'username': '已注销用户',
            'avatar': url_for('static', filename='default_avatar.png')
        }
    
    # 获取最近活动
    recent_activities = []
    
    # 最近评论
    recent_comments = Comment.query.order_by(Comment.created_at.desc()).limit(5).all()
    for comment in recent_comments:
        recent_activities.append({
            'type': 'comment',
            'user': get_user_info(comment.user),
            'article': comment.article,
            'action': '发表了评论',
            'created_at': comment.created_at
        })
    
    # 最近文章
    recent_articles = Article.query.order_by(Article.created_at.desc()).limit(5).all()
    for article in recent_articles:
        recent_activities.append({
            'type': 'article',
            'user': get_user_info(article.author),
            'article': article,
            'action': '发布了文章',
            'created_at': article.created_at
        })
    
    # 按时间排序
    recent_activities.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_articles=total_articles,
                         total_comments=total_comments,
                         total_views=total_views,
                         views_chart=views_chart,
                         recent_activities=recent_activities,
                         categories=categories,
                         tags=tags)

@bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    # 构建基础查询
    query = User.query
    
    if search_query:
        if search_type == 'id':
            # ID搜索
            try:
                user_id = int(search_query)
                query = query.filter(User.id == user_id)
            except ValueError:
                flash('ID必须是数字')
        else:
            # 用户名搜索
            # 先查询精确匹配
            exact_matches = query.filter(User.username == search_query)
            # 再查询模糊匹配
            fuzzy_matches = query.filter(
                User.username.like(f'%{search_query}%'),
                User.username != search_query  # 排除精确匹配的结果
            )
            # 合并结果
            query = exact_matches.union(fuzzy_matches)
    
    # 分页
    pagination = query.order_by(User.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/users.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/articles')
@login_required
@admin_required
def articles():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    # 构建基查询
    query = Article.query
    
    if search_query:
        if search_type == 'id':
            try:
                article_id = int(search_query)
                query = query.filter(Article.id == article_id)
            except ValueError:
                flash('ID必须是数字')
        elif search_type == 'author':
            query = query.join(User).filter(User.username.like(f'%{search_query}%'))
        elif search_type == 'category':
            # 按分类搜索
            query = query.join(Category).filter(Category.name == search_query)
        elif search_type == 'tag':
            # 按标签搜索 - 修改为支持模糊匹配
            query = query.join(Article.tags).filter(
                db.or_(
                    Tag.name == search_query,  # 精确匹配
                    Tag.name.like(f'%{search_query}%')  # 模糊匹配
                )
            ).distinct()  # 添加distinct避免重复结果
        else:
            # 标题搜索
            exact_matches = query.filter(Article.title == search_query)
            fuzzy_matches = query.filter(
                Article.title.like(f'%{search_query}%'),
                Article.title != search_query
            )
            query = exact_matches.union(fuzzy_matches)
    
    # 分页
    pagination = query.order_by(Article.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/articles.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/comments')
@login_required
@admin_required
def comments():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    # 构建基础查询
    query = Comment.query
    
    if search_query:
        if search_type == 'id':
            try:
                comment_id = int(search_query)
                query = query.filter(Comment.id == comment_id)
            except ValueError:
                flash('ID必须是数字')
        elif search_type == 'author':
            query = query.join(User).filter(User.username.like(f'%{search_query}%'))
        else:
            # 内容搜索
            query = query.filter(Comment.content.like(f'%{search_query}%'))
    
    # 分页
    pagination = query.order_by(Comment.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/comments.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/comments/<int:comments_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_comments(comments_id):
    comment = Comment.query.get_or_404(comments_id)
    db.session.delete(comment)
    db.session.commit()
    return '', 204

@bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
@login_required
@admin_required
def toggle_user_role(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('不能修改自己的角色')
        return redirect(url_for('admin.users'))
        
    user.role = 'user' if user.role == 'admin' else 'admin'
    db.session.commit()
    return '', 204

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        return jsonify({'error': '不能删除自己'}), 400
        
    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': '删除失败：' + str(e)}), 500

@bp.route('/articles/<int:article_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return '', 204

@bp.route('/site-config', methods=['GET', 'POST'])
@login_required
@admin_required
def site_config():
    if request.method == 'POST':
        for key in request.form:
            if key.startswith('config_'):
                config_key = key[7:]  # 去掉'config_'前缀
                config = SiteConfig.query.filter_by(key=config_key).first()
                if config:
                    config.value = request.form[key]
                else:
                    config = SiteConfig(key=config_key, value=request.form[key])
                    db.session.add(config)
        db.session.commit()
        flash('配置已更新')
        return redirect(url_for('admin.site_config'))
    
    configs = SiteConfig.query.all()
    return render_template('admin/site_config.html', configs=configs)

@bp.route('/categories')
@login_required
@admin_required
def categories():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    query = Category.query
    
    if search_query:
        if search_type == 'id':
            try:
                category_id = int(search_query)
                query = query.filter(Category.id == category_id)
            except ValueError:
                flash('ID必须是数字')
        else:
            # 名称搜索
            exact_matches = query.filter(Category.name == search_query)
            fuzzy_matches = query.filter(
                Category.name.like(f'%{search_query}%'),
                Category.name != search_query
            )
            query = exact_matches.union(fuzzy_matches)
    
    pagination = query.order_by(Category.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/categories.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    name = request.form.get('name')
    description = request.form.get('description')
    
    if Category.query.filter_by(name=name).first():
        return jsonify({'error': '分类已存在'}), 400
        
    category = Category(name=name, description=description)
    db.session.add(category)
    db.session.commit()
    return jsonify({'id': category.id, 'name': category.name})

@bp.route('/categories/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    if category.articles:
        return jsonify({'error': '该分类下还有文章，不能删除'}), 400
    db.session.delete(category)
    db.session.commit()
    return '', 204

@bp.route('/categories/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    name = request.form.get('name')
    description = request.form.get('description')
    
    if name != category.name and Category.query.filter_by(name=name).first():
        return jsonify({'error': '分类名称已存在'}), 400
        
    category.name = name
    category.description = description
    db.session.commit()
    
    return jsonify({
        'id': category.id,
        'name': category.name,
        'description': category.description
    })

@bp.route('/tags')
@login_required
@admin_required
def tags():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    query = Tag.query
    
    if search_query:
        if search_type == 'id':
            try:
                tag_id = int(search_query)
                query = query.filter(Tag.id == tag_id)
            except ValueError:
                flash('ID必须是数字')
        else:
            # 名称搜索
            exact_matches = query.filter(Tag.name == search_query)
            fuzzy_matches = query.filter(
                Tag.name.like(f'%{search_query}%'),
                Tag.name != search_query
            )
            query = exact_matches.union(fuzzy_matches)
    
    pagination = query.order_by(Tag.id.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/tags.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/tags/add', methods=['POST'])
@login_required
@admin_required
def add_tag():
    name = request.form.get('name')
    
    if Tag.query.filter_by(name=name).first():
        return jsonify({'error': '标签已存在'}), 400
        
    tag = Tag(name=name)
    db.session.add(tag)
    db.session.commit()
    return jsonify({'id': tag.id, 'name': tag.name})

@bp.route('/tags/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_tag(id):
    tag = Tag.query.get_or_404(id)
    db.session.delete(tag)
    db.session.commit()
    return '', 204

@bp.route('/tags/<int:id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_tag(id):
    tag = Tag.query.get_or_404(id)
    name = request.form.get('name')
    
    if name != tag.name and Tag.query.filter_by(name=name).first():
        return jsonify({'error': '标签名称已存在'}), 400
        
    tag.name = name
    db.session.commit()
    
    return jsonify({
        'id': tag.id,
        'name': tag.name
    })

@bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已存在'}), 400
        
    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
    })

@bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    
    # 检查用户名和邮箱是否已存在
    if username != user.username and User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400
    if email != user.email and User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已存在'}), 400
    
    user.username = username
    user.email = email
    if password:
        user.set_password(password)
    # 只有编辑其他用户时才允许修改角色
    if user.id != current_user.id and role:
        user.role = role
    
    db.session.commit()
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M')
    })

@bp.route('/histories')
@login_required
@admin_required
def histories():
    page = request.args.get('page', 1, type=int)
    search_type = request.args.get('search_type', '')
    search_query = request.args.get('q', '').strip()
    
    # 构建基础查询
    query = ViewHistory.query.join(ViewHistory.article).join(ViewHistory.user)
    
    if search_query:
        if search_type == 'id':
            try:
                history_id = int(search_query)
                query = query.filter(ViewHistory.id == history_id)
            except ValueError:
                flash('ID必须是数字')
        elif search_type == 'user':
            query = query.filter(User.username.like(f'%{search_query}%'))
        elif search_type == 'article':
            query = query.filter(Article.title.like(f'%{search_query}%'))
    
    # 分页
    pagination = query.order_by(ViewHistory.id.desc(),ViewHistory.viewed_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('admin/histories.html', 
                         pagination=pagination,
                         search_type=search_type,
                         search_query=search_query)

@bp.route('/histories/<int:history_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_history(history_id):
    history = ViewHistory.query.get_or_404(history_id)
    db.session.delete(history)
    db.session.commit()
    return '', 204

@bp.route('/histories/clear/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def clear_user_history(user_id):
    ViewHistory.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return '', 204

@bp.route('/themes')
@login_required
@admin_required
def themes():
    from app.models.site_config import SiteConfig
    
    themes = ThemeManager.get_available_themes()
    current_theme = SiteConfig.get_config('site_theme', 'default')
    return render_template('admin/themes.html', 
                         themes=themes,
                         current_theme=current_theme)

@bp.route('/change-theme', methods=['POST'])
@login_required
@admin_required
def change_theme():
    from app.models.site_config import SiteConfig
    
    theme = request.form.get('theme')
    if theme:
        config = SiteConfig.query.filter_by(key='site_theme').first()
        if config:
            config.value = theme
        else:
            config = SiteConfig(key='site_theme', value=theme)
            db.session.add(config)
        db.session.commit()
        flash('主题已更新')
    return redirect(url_for('admin.themes'))

@bp.route('/theme-preview/<theme>')
@login_required
@admin_required
def theme_preview(theme):
    preview_path = os.path.join(current_app.root_path, 'templates', theme, 'preview.png')
    return send_file(preview_path, mimetype='image/png')

@bp.route('/plugins')
@login_required
@admin_required
def plugins():
    """插件管理页面"""
    try:
        page = request.args.get('page', 1, type=int)
        search_query = request.args.get('q', '').strip()
        
        # 构建查询
        query = Plugin.query
        
        # 搜索
        if search_query:
            query = query.filter(
                db.or_(
                    Plugin.name.ilike(f'%{search_query}%'),
                    Plugin.description.ilike(f'%{search_query}%'),
                    Plugin.author.ilike(f'%{search_query}%')
                )
            )
        
        # 分页
        pagination = query.order_by(Plugin.installed_at.desc()).paginate(
            page=page, per_page=9, error_out=False
        )
        
        # 获取已加载的插件实例
        loaded_plugins = plugin_manager.plugins
        
        # 处理插件信息
        plugin_info = []
        for plugin in pagination.items:
            info = {
                'name': plugin.name,
                'directory': plugin.directory,
                'description': plugin.description,
                'version': plugin.version,
                'author': plugin.author,
                'author_url': plugin.author_url,
                'enabled': plugin.enabled,
                'installed_at': plugin.installed_at,
                'is_loaded': plugin.directory in loaded_plugins,
                'config': plugin.config
            }
            plugin_info.append(info)
            
        return render_template(
            'admin/plugins.html',
            plugins=plugin_info,
            pagination=pagination,
            search_query=search_query
        )
    except Exception as e:
        flash(f'加载插件列表失败: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@bp.route('/plugins/<plugin_name>/uninstall', methods=['POST'])
@login_required
@admin_required
def uninstall_plugin(plugin_name):
    """卸载插件"""
    try:
        # 先从数据库中获取插件记录
        plugin_record = Plugin.query.filter_by(name=plugin_name).first_or_404()
        plugin_dir = plugin_record.directory
        
        # 获取插件的实际目录路径
        installed_dir = os.path.join(current_app.root_path, 'plugins', 'installed')
        plugin_path = os.path.join(installed_dir, plugin_dir)
        
        # 添加调试日志
        current_app.logger.debug(f'Uninstalling plugin: {plugin_name}')
        current_app.logger.debug(f'Plugin directory: {plugin_path}')
        
        # 如果插件已加载，先卸载它
        if plugin_dir in plugin_manager.plugins:
            plugin_manager.unload_plugin(plugin_dir)
        
        # 删除插件目录
        if os.path.exists(plugin_path):
            import shutil
            shutil.rmtree(plugin_path)
        
        # 从数据库中删除插件记录
        db.session.delete(plugin_record)
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': f'插件 {plugin_name} 卸载成功'
        })
        
    except Exception as e:
        current_app.logger.error(f'Plugin uninstall error: {str(e)}')
        return jsonify({
            'status': 'error', 
            'message': f'卸载失败：{str(e)}'
        })

@bp.route('/plugins/<plugin_name>/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def plugin_settings(plugin_name):
    """插件设置页面"""
    try:
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            flash('插件不存在', 'error')
            return redirect(url_for('admin.plugins'))
            
        if request.method == 'POST':
            # 保存设置
            if hasattr(plugin, 'get_settings'):
                settings = {}
                plugin_settings = plugin.get_settings()
                
                # 处理每个设置项
                for key, setting in plugin_settings.items():
                    if setting['type'] == 'checkbox':
                        settings[key] = key in request.form
                    elif setting['type'] == 'number':
                        settings[key] = int(request.form.get(key, setting['value']))
                    else:
                        settings[key] = request.form.get(key, setting['value'])
                
                plugin.save_settings(settings)
                flash('设置已保存', 'success')
                return redirect(url_for('admin.plugin_settings', plugin_name=plugin_name))
            
            flash('该插件不支持设置', 'error')
            return redirect(url_for('admin.plugins'))
            
        # GET 请求显示设置页面
        if hasattr(plugin, 'get_settings'):
            settings = plugin.get_settings()
            # 渲染插件自定义模板或使用默认模板
            custom_template = plugin.render_settings_template(settings)
            return render_template(
                'admin/plugin_settings.html',
                plugin=plugin,
                settings=settings,
                custom_template=custom_template
            )
            
        flash('该插件没有设置项', 'info')
        return redirect(url_for('admin.plugins'))
        
    except Exception as e:
        flash(f'加载插件设置失败: {str(e)}', 'error')
        return redirect(url_for('admin.plugins'))

@bp.route('/plugins/upload', methods=['POST'])
@login_required
@admin_required
def upload_plugin():
    """上传插件"""
    import tempfile, zipfile, shutil  # 把导入移到函数开头
    
    try:
        if 'plugin' not in request.files:
            return jsonify({'status': 'error', 'message': '没有上传文件'})
            
        file = request.files['plugin']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': '没有选择文件'})
            
        if not file.filename.endswith('.zip'):
            return jsonify({'status': 'error', 'message': '只支持 zip 格式的插件包'})
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, file.filename)
        
        try:
            # 保存上传的文件
            file.save(zip_path)
            
            # 解压文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # 检查插件格式是否正确
            if not os.path.exists(os.path.join(temp_dir, 'plugin.json')):
                return jsonify({'status': 'error', 'message': '无效的插件格式'})
            
            # 读取插件信息
            with open(os.path.join(temp_dir, 'plugin.json'), 'r', encoding='utf-8') as f:
                plugin_info = json.load(f)
            
            plugin_name = plugin_info.get('name')
            if not plugin_name:
                return jsonify({'status': 'error', 'message': '插件信息不完整'})
            
            # 检查插件是否已存在
            if Plugin.query.filter_by(name=plugin_name).first():
                return jsonify({'status': 'error', 'message': '插件已存在'})
            
            # 生成目录名
            directory = plugin_info.get('directory', plugin_name.lower().replace(' ', '_'))
            plugin_dir = os.path.join(current_app.root_path, 'plugins', 'installed', directory)
            
            if os.path.exists(plugin_dir):
                return jsonify({'status': 'error', 'message': '插件目录已存在'})
            
            # 复制文件到插件目录
            shutil.copytree(temp_dir, plugin_dir)
            
            # 添加插件记录到数据库
            Plugin.add_plugin(plugin_info, directory)
            
            # 加载插件
            if plugin_manager.load_plugin(directory):
                return jsonify({'status': 'success', 'message': f'插件 {plugin_name} 安装成功'})
            else:
                # 安装失败，清理
                shutil.rmtree(plugin_dir)
                Plugin.remove_plugin(plugin_name)
                return jsonify({'status': 'error', 'message': '插件加载失败'})
                
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir)
                
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'上传插件失败: {str(e)}'})

@bp.route('/plugins/<plugin_name>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_plugin(plugin_name):
    """启用/禁用插件"""
    try:
        plugin = Plugin.query.filter_by(directory=plugin_name).first_or_404()
        plugin.enabled = not plugin.enabled
        db.session.commit()
        
        if plugin.enabled:
            # 启用插件时，尝试加载它
            if plugin_manager.load_plugin(plugin_name):
                status = '启用'
            else:
                # 加载失败时回滚状态
                plugin.enabled = False
                db.session.commit()
                return jsonify({
                    'status': 'error',
                    'message': '插件加载失败'
                })
        else:
            # 禁用插件时，卸载它
            plugin_manager.unload_plugin(plugin_name)
            status = '禁用'
        
        return jsonify({
            'status': 'success',
            'message': f'插件已{status}',
            'reload_required': False  # 不再要重启
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'操作失败：{str(e)}'
        })

@bp.route('/plugins/<plugin_name>/export')
@login_required
@admin_required
def export_plugin(plugin_name):
    """导出插件"""
    try:
        # 先从数据库获取插件记录
        plugin_record = Plugin.query.filter_by(name=plugin_name).first_or_404()
        plugin_dir = plugin_record.directory
        
        # 获取插件实例
        plugin = plugin_manager.get_plugin(plugin_dir)
        if not plugin:
            flash('插件未加载', 'error')
            return redirect(url_for('admin.plugins'))
        
        content, filename = plugin.export_plugin()
        
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
        
    except Exception as e:
        current_app.logger.error(f'Export plugin error: {str(e)}')
        flash(f'导出插件失败: {str(e)}', 'error')
        return redirect(url_for('admin.plugins'))

@bp.route('/plugins/<plugin_name>/reload', methods=['POST'])
@login_required
@admin_required
def reload_plugin(plugin_name):
    """重载插件"""
    try:
        # 先从数据库获取插件记录
        plugin_record = Plugin.query.filter_by(directory=plugin_name).first_or_404()
        
        # 如果插件已加载，先卸载它
        if plugin_name in plugin_manager.plugins:
            plugin_manager.unload_plugin(plugin_name)
        
        # 重新加载插件信息
        plugin_dir = os.path.join(current_app.root_path, 'plugins', 'installed', plugin_name)
        plugin_json = os.path.join(plugin_dir, 'plugin.json')
        
        if os.path.exists(plugin_json):
            with open(plugin_json, 'r', encoding='utf-8') as f:
                plugin_info = json.load(f)
                
            # 更新数据库记录
            plugin_record.name = plugin_info.get('name', plugin_record.name)
            plugin_record.description = plugin_info.get('description', plugin_record.description)
            plugin_record.version = plugin_info.get('version', plugin_record.version)
            plugin_record.author = plugin_info.get('author', plugin_record.author)
            plugin_record.author_url = plugin_info.get('author_url', plugin_record.author_url)
            plugin_record.config = plugin_info.get('config', plugin_record.config)
            db.session.commit()
        
        # 如果插件是启用状态，重新加载它
        if plugin_record.enabled:
            if plugin_manager.load_plugin(plugin_name):
                return jsonify({
                    'status': 'success',
                    'message': f'插件 {plugin_record.name} 重载成功'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': '插件重载失败'
                })
        
        return jsonify({
            'status': 'success',
            'message': f'插件 {plugin_record.name} 配置已更新'
        })
        
    except Exception as e:
        current_app.logger.error(f'Plugin reload error: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': f'重载失败：{str(e)}'
        })

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