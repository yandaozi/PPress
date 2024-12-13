from flask import Blueprint, render_template, request, abort, current_app, url_for, flash, redirect, jsonify, \
    render_template_string
from werkzeug.exceptions import NotFound

from app.services.blog_service import BlogService
from app.utils.common import get_categories_data
from flask_login import current_user, login_required
from functools import wraps
from app.models import CommentConfig
from app.utils.article_url import ArticleUrlGenerator
from app.models import Article
from app.models import CustomPage
from app.models import SiteConfig
from app.services.api_service import ApiService

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

def api_response_if_requested(data):
    """检查是否请求API响应"""
    # 检查Accept头
    if request.headers.get('Accept') == 'application/json':
        # 检查API访问权限
        is_allowed, error_response, status_code = ApiService.check_api_access(request)
        if not is_allowed:
            if error_response:
                return jsonify(error_response), status_code
            return None
        return jsonify(data)
    return None

@bp.route('/')
@handle_view_errors
def index():
    """首页路由"""
    template = 'blog/index.html'
    
    # 获取模板对象
    template_obj = current_app.jinja_env.get_template(template)
    
    # 从模板对象获取源码
    # template_source = current_app.jinja_loader.get_source(current_app.jinja_env, template_obj.name)[0]
    #
    # # 检查模板是否定义了 api_only
    # if '{% set api_only = true %}' in template_source:
    #     return render_template(template)
    
    # 获取文章列表
    articles = BlogService.get_index_articles(
        request.args.get('page', 1, type=int),
        request.args.get('category', type=int),
        current_user
    )

    # 检查是否需要返回API响应
    api_response = api_response_if_requested(
        ApiService.format_article_list(articles)
    )
    if api_response:
        return api_response

    # 定义区块和对应的数据键名映射
    block_map = {
        'hot_today': 'hot_articles_today',
        'hot_week': 'hot_articles_week',
        'random_articles': 'random_articles',
        'random_tags': 'random_tags',
        'latest_comments': 'latest_comments'
    }

    # 获取模板中定义的区块与需要的数据的交集
    needed_widgets = set(block_map.keys()) & set(template_obj.blocks.keys())

    # 只获取需要的侧边栏数据
    sidebar_data = BlogService.get_sidebar_data(needed_widgets)

    return render_template(template,
                           articles=articles,
                           **sidebar_data,
                           **get_categories_data())

@bp.route('/category/<id>')
@handle_view_errors
def category(id):


    # 从模板对象获取源码
    # template_source = current_app.jinja_loader.get_source(current_app.jinja_env, template_obj.name)[0]
    #
    # # 检查模板是否定义了 api_only
    # if '{% set api_only = true %}' in template_source:
    #     return render_template(template)

    """分类文章列表"""
    data = BlogService.get_category_articles(
        id,
        request.args.get('page', 1, type=int),
        current_user
    )

    # 检查是否需要返回API响应
    api_data = {
        'category': {
            'id': data['current_category'].id,
            'name': data['current_category'].name,
            'description': data['current_category'].description,
            'article_count': data['current_category'].article_count
        },
        'articles': ApiService.format_article_list(data['pagination'])
    }
    api_response = api_response_if_requested(api_data)
    if api_response:
        return api_response


    # 定义区块和对应的数据键名映射
    block_map = {
        'hot_today': 'hot_articles_today',
        'hot_week': 'hot_articles_week',
        'random_articles': 'random_articles',
        'random_tags': 'random_tags',
        'latest_comments': 'latest_comments'
    }


    # 使用分类指定的模板或默认模板
    template = data['template']

    # 获取模板对象
    template_obj = current_app.jinja_env.get_template(template)

    # 获取模板中定义的区块与需要的数据的交集
    needed_widgets = set(block_map.keys()) & set(template_obj.blocks.keys())

    # 只获取需要的侧边栏数据
    sidebar_data = BlogService.get_sidebar_data(needed_widgets)

    return render_template(template,
                           articles=data['pagination'],
                           current_category=data['current_category'],
                           endpoint='blog.category',
                           **sidebar_data,
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
        
        # 检查是否需要返回API响应
        api_response = api_response_if_requested(
            ApiService.format_article_detail(article)
        )
        if api_response:
            return api_response
        
        # 获取页码和密码
        page = request.args.get('page', 1, type=int)
        password = request.args.get('password')
        
        # 获取文章详情
        result = BlogService.get_article_detail(article.id, password, current_user)

        # 获取上一篇和下一篇文章
        prev_article, next_article = BlogService.get_adjacent_articles(article)
        
        if isinstance(result, dict) and 'error' in result:
            flash(result['error'], 'error')
            return redirect(url_for('blog.index'))
            
        if isinstance(result, dict) and result.get('need_password'):
            return render_template('blog/password.html', 
                                article=result['article'],
                                prev_article=prev_article,
                                next_article=next_article)
            
        # 获取评论数据
        comment_data = BlogService.get_article_comments(article.id, current_user, page)

        # 记录浏览历史（如果用户已登录）
        if current_user.is_authenticated:
            BlogService.record_view(current_user.id, article.id)
        
        return render_template('blog/article.html',
                             article=result,
                             comment_data=comment_data,
                             prev_article=prev_article,
                             next_article=next_article,
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

@bp.route('/tag/<tag_id_or_slug>')
@handle_view_errors
def tag(tag_id_or_slug):
    """标签文章列表"""
    page = request.args.get('page', 1, type=int)
    
    articles = BlogService.get_tag_articles(
        tag_id_or_slug,
        page=page
    )
    
    # 检查是否需要返回API响应
    api_response = api_response_if_requested(
        ApiService.format_article_list(articles)
    )
    if api_response:
        return api_response
        
    return render_template('blog/tag.html',
                         articles=articles,
                         tag=BlogService.get_tag_info(tag_id_or_slug))

@bp.route('/article/<int:article_id>/comment', methods=['POST'])
@handle_view_errors
def add_comment(article_id):
    """添加评论"""
    try:
        # 获取文章对象
        article = Article.query.get_or_404(article_id)
        
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
        
        # 检查是否是 AJAX 请求
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if success:
                return jsonify({
                    'message': message,
                    'url': ArticleUrlGenerator.generate(
                        article.id, 
                        article.category_id, 
                        article.created_at
                    )
                })
            return jsonify({'error': message}), 400
            
        # 普通表单提交
        flash(message)
        return redirect(ArticleUrlGenerator.generate(
            article.id, 
            article.category_id, 
            article.created_at
        ))
        
    except Exception as e:
        current_app.logger.error(f"add_comment error: {str(e)}")
        abort(500)

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
        # 验证必填字段
        required_fields = ['title', 'content']
        for field in required_fields:
            if not request.form.get(field):
                if request.headers.get('Accept') == 'application/json':
                    return jsonify({'error': f'请填写{field}字段'}), 400
                flash(f'请填写{field}字段')
                return redirect(url_for('blog.edit', id=id))
        
        # 验证分类选择
        if not request.form.getlist('categories'):
            if request.headers.get('Accept') == 'application/json':
                return jsonify({'error': '请至少选择一个分类'}), 400
            flash('请至少选择一个分类')
            return redirect(url_for('blog.edit', id=id))
            
        success, message, result = BlogService.edit_article(
            id,
            request.form,
            current_user.id,
            current_user.role == 'admin'
        )
        
        # 根据请求类型返回不同的响应
        if request.headers.get('Accept') == 'application/json':
            if success:
                return jsonify({
                    'message': message,
                    'url': result['url']
                })
            return jsonify({'error': message}), 400
            
        # 普通表单提交
        flash(message)
        if success:
            return redirect(result['url'])
        return redirect(url_for('blog.edit', id=id))
    
    # GET 请求处理保持不变
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
        
    # 获取允许的文件类型
    allowed_types = SiteConfig.get_config('upload_allowed_types', '.jpg,.jpeg,.png,.gif,.webp').split(',')
    max_size = int(SiteConfig.get_config('upload_max_size', '10')) * 1024 * 1024  # 转换为字节
    
    # 检查文件类型
    if not any(file.filename.lower().endswith(ext.lower()) for ext in allowed_types):
        return jsonify({'error': '不支持的文件类型'}), 400
        
    # 检查文件大小 - 使用 seek 和 tell 来获取实际大小
    file.seek(0, 2)  # 移动到文件末尾
    file_size = file.tell()  # 获取文件大小
    file.seek(0)  # 重置文件指针到开头
    
    if file_size > max_size:
        return jsonify({'error': f'文件大小超过限制({max_size/1024/1024:.0f}MB)'}), 400
        
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

@bp.route('/custom_page/<int:page_id>/comment', methods=['POST'])
@handle_view_errors
def add_custom_page_comment(page_id):
    """添加自定义页面评论"""
    try:
        # 获取页面对象
        page = CustomPage.query.get_or_404(page_id)
        
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
        
        success, message = BlogService.add_custom_page_comment(
            page_id=page_id,
            user_id=user_id,
            data=data
        )

        # 检查是否是 AJAX 请求
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if success:
                return jsonify({
                    'message': message,
                    'url': page.route
                })
            return jsonify({'error': message}), 400
        
        flash(message)
        return redirect(page.route)
        
    except Exception as e:
        current_app.logger.error(f"add_custom_page_comment error: {str(e)}")
        abort(500)

