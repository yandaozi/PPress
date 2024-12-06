from flask import Blueprint, render_template, request, abort, current_app, url_for, flash, redirect, jsonify
from werkzeug.exceptions import NotFound

from app.services.blog_service import BlogService
from app.utils.common import get_categories_data
from flask_login import current_user, login_required
from functools import wraps
from app.models import CommentConfig
from app.utils.article_url import ArticleUrlGenerator
from app.models import Article

bp = Blueprint('blog', __name__)

def handle_view_errors(f):
    """统一的视图错误处理装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"{f.__name__} error: {str(e)}")
            # 检查是否是 AJAX 请求
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': str(e)}), 500
            #flash(str(e))
            return abort(404 if isinstance(e, NotFound) else 500)
    return decorated_function

@bp.route('/')
@handle_view_errors
def index():
    """首页路由"""
    return render_template('blog/index.html',
                         articles=BlogService.get_index_articles(
                             request.args.get('page', 1, type=int),
                             request.args.get('category', type=int),
                             current_user
                         ),
                         hot_articles_today=BlogService.get_hot_articles_today(),
                         hot_articles_week=BlogService.get_hot_articles_week(),
                         random_articles=BlogService.get_random_articles(),
                         random_tags=BlogService.get_random_tags(),
                         latest_comments=BlogService.get_latest_comments(),
                         **get_categories_data())

@bp.route('/category/<id>')
@handle_view_errors
def category(id):
    """分类文章列表"""
    data = BlogService.get_category_articles(
        id,
        request.args.get('page', 1, type=int),
        current_user
    )
    return render_template('blog/index.html',
                           articles=data['pagination'],
                           current_category=data['current_category'],
                           endpoint='blog.category',
                           hot_articles_today=BlogService.get_hot_articles_today(),
                           hot_articles_week=BlogService.get_hot_articles_week(),
                           random_articles=BlogService.get_random_articles(),
                           random_tags=BlogService.get_random_tags(),
                           latest_comments=BlogService.get_latest_comments(),
                           **get_categories_data())

@bp.route('/<path:path>')
def article(path):
    """文章详情页"""
    try:
        # 从路径中提取文章ID
        article_id = ArticleUrlGenerator.parse(path)
        if not article_id:
            abort(404)
            
        article = Article.query.get_or_404(article_id)
        
        # 获取页码和密码
        page = request.args.get('page', 1, type=int)
        password = request.args.get('password')
        
        # 获取文章详情
        result = BlogService.get_article_detail(article.id, password, current_user)
        
        if isinstance(result, dict) and 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('blog.index'))
            
        if isinstance(result, dict) and result.get('need_password'):
            return render_template('blog/password.html', article=result['article'])
            
        # 获取评论数据
        comment_data = BlogService.get_article_comments(article.id, current_user, page)
        
        return render_template('blog/article.html',
                             article=result,
                             comment_data=comment_data,
                             comment_config=CommentConfig.get_config())
                             
    except Exception as e:
        current_app.logger.error(f"Article view error: {str(e)}")
        abort(404)

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
@handle_view_errors
def add_comment(article_id):
    """添加评论"""
    data = {
        'content': request.form.get('content'),
        'parent_id': request.form.get('parent_id'),
        'reply_to_id': request.form.get('reply_to_id'),
        'guest_name': request.form.get('guest_name'),
        'guest_email': request.form.get('guest_email'),
        'guest_contact': request.form.get('guest_contact')
    }
    
    # 获取用户ID(如果已登录)
    user_id = current_user.id if current_user.is_authenticated else None
    
    success, message = BlogService.add_comment(
        article_id=article_id,
        user_id=user_id,
        data=data
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
    """编辑文���"""
    if request.method == 'POST':
        # 验证必填字段
        required_fields = ['title', 'content']
        for field in required_fields:
            if not request.form.get(field):
                flash(f'请填写{field}字段')
                return redirect(url_for('blog.edit', id=id))
        
        # 验证分类选择
        if not request.form.getlist('categories'):
            flash('请至少选择一个分类')
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
    
    # 获取文章用于编辑
    article = None
    if id:
        try:
            article = BlogService.get_article_for_edit(id, current_user)
        except Exception as e:
            flash(str(e))
            return redirect(url_for('blog.index'))
    
    return render_template('blog/edit.html',
                         article=article,
                         # random_tags=BlogService.get_random_tags(),
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
            'location': result,  # TinyMCE 需 location 字段
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

