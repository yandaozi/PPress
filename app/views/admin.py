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
from app import db
from functools import wraps
import pandas as pd
import plotly.express as px
import json
import numpy as np
from ..utils.theme_manager import ThemeManager

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
    
    # 构建基础查询
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