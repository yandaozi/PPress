from flask import Blueprint, render_template, request, abort, current_app, url_for, flash, redirect, jsonify
from app.services.blog_service import BlogService
from app.utils.common import get_categories_data
from flask_login import current_user, login_required
from functools import wraps

bp = Blueprint('blog', __name__)

def handle_view_errors(f):
    """统一的视图错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"{f.__name__} error: {str(e)}")
            if request.is_xhr:  # AJAX请求
                return jsonify({'error': str(e)}), 500
            flash(str(e))
            return abort(404 if isinstance(e, NotFound) else 500)
    return decorated_function

@bp.route('/')
@handle_view_errors
def index():
    """首页路由"""
    return render_template('blog/index.html',
                         articles=BlogService.get_index_articles(
                             request.args.get('page', 1, type=int),
                             request.args.get('category', type=int)
                         ),
                         hot_articles_today=BlogService.get_hot_articles_today(),
                         hot_articles_week=BlogService.get_hot_articles_week(),
                         random_articles=BlogService.get_random_articles(),
                         random_tags=BlogService.get_random_tags(),
                         latest_comments=BlogService.get_latest_comments(),
                         **get_categories_data())

@bp.route('/article/<int:id>')
@handle_view_errors
def article(id):
    """文章详情路由"""
    article = BlogService.get_article_detail(id)
    if current_user.is_authenticated:
        BlogService.record_view(current_user.id, id)
    return render_template('blog/article.html',
                         article=article,
                         **get_categories_data())

@bp.route('/search')
@handle_view_errors
def search():
    """搜索路由"""
    query = request.args.get('q', '').strip()
    if not query:
        flash('请输入搜索内容')
        return redirect(url_for('blog.index'))
    
    if len(query) < 2:
        flash('搜索内容至少需要2个字符')
        return redirect(url_for('blog.index'))
    
    return render_template('blog/search.html',
                         query=query,
                         articles=BlogService.search_articles(
                             query,
                             request.args.get('page', 1, type=int),
                             request.args.getlist('tags'),
                             request.args.get('sort', 'recent')
                         ),
                         tags=BlogService.get_search_tags(query),
                         selected_tags=request.args.getlist('tags'),
                         sort=request.args.get('sort', 'recent'),
                         **get_categories_data())

@bp.route('/tag/<int:id>')
@handle_view_errors
def tag(id):
    """标签路由"""
    return render_template('blog/tag.html',
                         tag=BlogService.get_tag_info(id),
                         articles=BlogService.get_tag_articles(
                             id, 
                             request.args.get('page', 1, type=int)
                         ),
                         **get_categories_data())

@bp.route('/article/<int:article_id>/comment', methods=['POST'])
@login_required
@handle_view_errors
def add_comment(article_id):
    """添加评论"""
    success, message = BlogService.add_comment(
        article_id,
        current_user.id,
        request.form.get('content')
    )
    flash(message)
    return redirect(url_for('blog.article', id=article_id))

@bp.route('/comment/<int:comment_id>', methods=['DELETE'])
@login_required
@handle_view_errors
def delete_comment(comment_id):
    """删除评论"""
    success, message = BlogService.delete_comment(
        comment_id,
        current_user.id,
        current_user.role == 'admin'
    )
    if not success:
        return jsonify({'error': message}), 403
    return '', 204

@bp.route('/article/edit', methods=['GET', 'POST'])
@bp.route('/article/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@handle_view_errors
def edit(id=None):
    """编辑文章"""
    if request.method == 'POST':
        for field in ['title', 'content', 'category']:
            if not request.form.get(field):
                flash(f'请填写{field}字段')
                return redirect(url_for('blog.edit', id=id))
            
        success, message, article = BlogService.edit_article(
            id,
            request.form,
            current_user.id,
            current_user.role == 'admin'
        )
        flash(message)
        if success:
            return redirect(url_for('blog.article', id=article.id))
        return redirect(url_for('blog.edit', id=id))
        
    return render_template('blog/edit.html',
                         article=BlogService.get_article_detail(id) if id else None,
                         random_tags=BlogService.get_random_tags(),
                         **get_categories_data())

@bp.route('/tags/suggestions')
@handle_view_errors
def tag_suggestions():
    """标签建议路由"""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 1:
        return jsonify([])
        
    try:
        tags = BlogService.get_tag_suggestions(query)
        return jsonify([{
            'name': tag.name,
            'count': tag.article_count
        } for tag in tags])
    except Exception as e:
        current_app.logger.error(f"Tag suggestions error: {str(e)}")
        return jsonify([])

@bp.route('/upload/image', methods=['POST'])
@login_required
@handle_view_errors
def upload_image():
    """图片上传路由"""
    if 'upload' not in request.files:
        return jsonify({'error': '没有文件'}), 400
        
    file = request.files['upload']
    if not file.filename:
        return jsonify({'error': '没有选择文件'}), 400
        
    # 检查文件类型
    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        return jsonify({'error': '不支持的文件类型'}), 400
        
    success, result = BlogService.upload_image(file, current_user.id)
    if success:
        return jsonify({
            'location': result,  # TinyMCE 需要 location 字段
            'url': result,       # 兼容其他情况
            'uploaded': True
        })
    return jsonify({'error': f'上传失败：{result}'}), 500

@bp.route('/article/<int:article_id>', methods=['DELETE'])
@login_required
@handle_view_errors
def delete_article(article_id):
    """删除文章"""
    success, message = BlogService.delete_article(
        article_id,
        current_user.id,
        current_user.role == 'admin'
    )
    if not success:
        return jsonify({'error': message}), 403
    return '', 204

@bp.route('/search/suggestions')
@handle_view_errors
def search_suggestions():
    """搜索建议路由"""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
        
    try:
        suggestions = BlogService.get_search_suggestions(query)
        return jsonify([title[0] for title in suggestions])
    except Exception as e:
        current_app.logger.error(f"Search suggestions error: {str(e)}")
        return jsonify([])

