import hashlib

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from flask_sqlalchemy.pagination import Pagination

from app.models.article import Article
from app.models.tag import Tag
from app.models.view_history import ViewHistory
from app.models.comment import Comment
from app import db, cache
from textblob import TextBlob
import os
from werkzeug.utils import secure_filename
from flask import current_app
from app.models.category import Category
from datetime import datetime, timedelta
import random
from app.models.file import File
from app.models.user import User
from app.utils.common import get_categories_data
from sqlalchemy.orm import joinedload

bp = Blueprint('blog', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def make_article_cache_key(article_id):
    return f"article_{article_id}"

@cache.memoize(timeout=3600)
def get_article(article_id):
    return Article.query.get_or_404(article_id)


@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    
    # 构建基础查询
    query = Article.query
    
    # 如果有分类参数,添加分类过滤
    current_category = None
    if category_id:
        current_category = Category.query.get(category_id)
        if not current_category:
            # 如果分类不存在，返回404
            abort(404)
        query = query.filter(Article.category_id == category_id)
    
    # 分页查询
    articles = query.order_by(Article.id.desc(), Article.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # 获取所有分类及其文章数量 - 使用长期缓存
    @cache.cached(timeout=3600, key_prefix='categories_with_count')
    def get_categories_with_count_cache():
        categories = Category.query.all()
        result = []
        for category in categories:
            count = Article.query.filter_by(category_id=category.id).count()
            result.append((category, count))
        return result
    
    # 获取今日热门文章 - 使用短期缓存
    @cache.cached(timeout=300, key_prefix='hot_articles_today')
    def get_hot_articles_today_cache():
        today = datetime.now().date()
        # 使用子查优化
        views_subquery = db.session.query(
            ViewHistory.article_id,
            db.func.count(ViewHistory.id).label('views')
        ).filter(
            db.func.date(ViewHistory.viewed_at) == today
        ).group_by(ViewHistory.article_id)\
         .subquery()
        
        return db.session.query(Article, views_subquery.c.views)\
            .join(views_subquery, Article.id == views_subquery.c.article_id)\
            .order_by(views_subquery.c.views.desc())\
            .limit(5)\
            .all()
    
    # 获取本周热门文章 - 使用中期缓存
    @cache.cached(timeout=1800, key_prefix='hot_articles_week')
    def get_hot_articles_week_cache():
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        # 使用子查询优化
        views_subquery = db.session.query(
            ViewHistory.article_id,
            db.func.count(ViewHistory.id).label('views')
        ).filter(
            db.func.date(ViewHistory.viewed_at) >= week_start
        ).group_by(ViewHistory.article_id)\
         .subquery()
        
        return db.session.query(Article, views_subquery.c.views)\
            .join(views_subquery, Article.id == views_subquery.c.article_id)\
            .order_by(views_subquery.c.views.desc())\
            .limit(5)\
            .all()
    
    # 随机文章 - 使用中期缓存
    @cache.cached(timeout=1800, key_prefix='random_articles')
    def get_random_articles_cache():
        # 使用 OFFSET 优化随机查询
        count = db.session.query(db.func.count(Article.id)).scalar()
        if count < 5:
            return Article.query.all()
            
        ids = random.sample(range(1, count + 1), min(5, count))
        return Article.query.filter(Article.id.in_(ids)).all()
    
    # 随机标签 - 使用长期缓存
    @cache.cached(timeout=3600, key_prefix='random_tags')
    def get_random_tags_cache():
        # 使用 OFFSET 优化随机查询
        count = db.session.query(db.func.count(Tag.id)).scalar()
        if count < 10:
            return Tag.query.all()
            
        ids = random.sample(range(1, count + 1), min(10, count))
        return Tag.query.filter(Tag.id.in_(ids)).all()
    
    # 最新评论 - 使用短期缓存
    @cache.cached(timeout=60, key_prefix='latest_comments')
    def get_latest_comments_cache():
        return db.session.query(
            Comment, User, Article
        ).join(User, Comment.user_id == User.id)\
         .join(Article, Comment.article_id == Article.id)\
         .order_by(Comment.created_at.desc())\
         .limit(10)\
         .all()
    
    # 使用缓存获取数据
    try:
        categories_with_count = get_categories_with_count_cache()
        categories = [cat for cat, _ in categories_with_count]
        article_counts = dict((cat.id, count) for cat, count in categories_with_count)
    except Exception:
        categories = Category.query.all()
        article_counts = {}
    
    # 获取今日热门文章 - 使用短期缓存
    try:
        hot_articles_today = get_hot_articles_today_cache()
    except Exception:
        hot_articles_today = []
        
    # 获取本周热门文章 - 使用中期缓存
    try:
        hot_articles_week = get_hot_articles_week_cache()
    except Exception:
        hot_articles_week = []
    
    # 随机文章 - 使用中期缓存
    try:
        random_articles = get_random_articles_cache()
    except Exception:
        random_articles = []
    
    # 随机标签 - 使用长期缓存
    try:
        random_tags = get_random_tags_cache()
    except Exception:
        random_tags = []
    
    # 最新评论 - 使用短期缓存
    try:
        latest_comments = get_latest_comments_cache()
    except Exception:
        latest_comments = []
    
    # 作者信息处理函数
    def get_author_info(article):
        if article.author:
            return {
                'id': article.author.id,
                'username': article.author.username,
                'avatar': article.author.avatar
            }
        return {
            'id': None,
            'username': '已注销用户',
            'avatar': url_for('static', filename='default_avatar.png')
        }
    
    return render_template('blog/index.html',
                         articles=articles,
                         categories=categories,
                         article_counts=article_counts,
                         current_category=current_category,
                         hot_articles_today=hot_articles_today,
                         hot_articles_week=hot_articles_week,
                         random_articles=random_articles,
                         random_tags=random_tags,
                         latest_comments=latest_comments,
                         get_author_info=get_author_info)

@bp.route('/article/<int:id>')
def article(id):
    # 使用缓存获取文章
    @cache.memoize(timeout=300)  # 5分钟缓存
    def get_article_with_relations(article_id):
        return Article.query.options(
            joinedload(Article.author),  # 预加载作者
            joinedload(Article.tags),    # 预加载标签
            joinedload(Article.category),  # 预加载分类
            joinedload(Article.comments).joinedload(Comment.user)  # 预加载评论及评论用户
        ).get_or_404(article_id)
    
    try:
        article = get_article_with_relations(id)
    except Exception as e:
        current_app.logger.error(f"Error loading article: {str(e)}")
        abort(404)
        
    # 获取分类数据
    categories, article_counts = get_categories_data()
    
    # 创建一个默认作者信息
    author_info = {
        'id': None,
        'username': '已注销用户',
        'avatar': url_for('static', filename='default_avatar.png')
    }
    
    # 如果作者存在，使用作者信息
    if article.author:
        author_info = {
            'id': article.author.id,
            'username': article.author.username,
            'avatar': article.author.avatar
        }
    
    # 记录浏览历史
    if current_user.is_authenticated:
        view_history = ViewHistory(user_id=current_user.id, article_id=id)
        db.session.add(view_history)
        
        # 更新浏览次数
        article.view_count += 1
        db.session.commit()
    
    return render_template('blog/article.html', 
                         article=article,
                         author_info=author_info,
                         categories=categories,
                         article_counts=article_counts)

@bp.route('/article/edit', methods=['GET', 'POST'])
@bp.route('/article/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id=None):
    article = None
    if id:
        article = Article.query.options(
            db.joinedload(Article.tags)
        ).get_or_404(id)
        
        if article.author_id != current_user.id and current_user.role != 'admin':
            flash('没有权限编辑此文章')
            return redirect(url_for('blog.article', id=id))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category_id = request.form.get('category')
        tag_names = request.form.get('tag_names', '').split()
        
        # 情感分析
        blob = TextBlob(content)
        sentiment_score = blob.sentiment.polarity
        
        try:
            if article:
                # 更新文章
                article.title = title
                article.content = content
                article.category_id = category_id
                article.sentiment_score = sentiment_score
                article.updated_at = datetime.now()
                
                # 更新标签
                article.tags.clear()
                for tag_name in tag_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    article.tags.append(tag)
                
                # 清除相关缓存
                cache.delete_many(
                    f'article_{article.id}',  # 文章详情缓存
                    'categories_with_count',  # 分类统计缓存
                    'hot_articles_today',     # 今日热门缓存
                    'hot_articles_week',      # 本周热门缓存
                    'random_articles',        # 随机文章缓存
                    'random_tags'             # 随机标签缓存
                )
            else:
                # 创建新文章
                article = Article(
                    title=title,
                    content=content,
                    author_id=current_user.id,
                    category_id=category_id,
                    sentiment_score=sentiment_score
                )
                db.session.add(article)
                
                # 处理标签
                for tag_name in tag_names:
                    tag = Tag.query.filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.session.add(tag)
                    article.tags.append(tag)
            
            db.session.commit()
            
            # 如果是新文章，清除首页相关缓存
            if not id:
                cache.delete_many(
                    'categories_with_count',
                    'hot_articles_today',
                    'hot_articles_week',
                    'random_articles',
                    'random_tags'
                )
            
            flash('文章保存成功！')
            return redirect(url_for('blog.article', id=article.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'保存失败：{str(e)}')
            return redirect(url_for('blog.edit', id=id))
    
    # 获取随机标签和分类
    all_tags = Tag.query.all()
    random_tags = random.sample(all_tags, min(10, len(all_tags)))
    categories = Category.query.all()
    
    return render_template('blog/edit.html', 
                         article=article,
                         random_tags=random_tags,
                         categories=categories)

@bp.route('/article/<int:article_id>/comment', methods=['POST'])
@login_required
def add_comment(article_id):
    content = request.form.get('content')
    if not content:
        flash('评论内容不能为空')
        return redirect(url_for('blog.article', id=article_id))
    
    comment = Comment(
        content=content,
        article_id=article_id,
        user_id=current_user.id
    )
    db.session.add(comment)
    db.session.commit()
    
    return redirect(url_for('blog.article', id=article_id))

@bp.route('/comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    # 检查权限
    if comment.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': '没有权限'}), 403
    
    db.session.delete(comment)
    db.session.commit()
    
    return '', 204

@bp.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        flash('请输入搜索内容')
        return redirect(url_for('blog.index'))
    
    if len(query) < 2:
        flash('搜索内容至少需要2个字符')
        return redirect(url_for('blog.index'))
    
    page = request.args.get('page', 1, type=int)
    selected_tags = request.args.getlist('tags')
    sort = request.args.get('sort', 'recent')
    
    try:
        # 构建基础查询 - 只查询标题
        base_query = Article.query.options(
            db.joinedload(Article.author),
            db.joinedload(Article.category)
        )
        
        # 只搜索标题，搜索内容
        base_query = base_query.filter(Article.title.ilike(f'%{query}%'))
        
        # 标签过滤 - 如果有标签筛选，使用子查询
        if selected_tags:
            tag_subquery = db.session.query(Article.id)\
                .join(Article.tags)\
                .filter(Tag.name.in_(selected_tags))\
                .group_by(Article.id)\
                .having(db.func.count(Tag.id) == len(selected_tags))\
                .subquery()
            base_query = base_query.filter(Article.id.in_(tag_subquery))
        
        # 排序优化
        if sort == 'views':
            base_query = base_query.order_by(Article.view_count.desc())
        elif sort == 'comments':
            # 使用子查询优化评论数排序
            comment_counts = db.session.query(
                Article.id,
                db.func.count(Comment.id).label('comment_count')
            ).outerjoin(Comment)\
             .group_by(Article.id)\
             .subquery()
            
            base_query = base_query.outerjoin(
                comment_counts,
                Article.id == comment_counts.c.id
            ).order_by(db.desc(comment_counts.c.comment_count))
        else:  # recent
            base_query = base_query.order_by(Article.created_at.desc())
        
        # 分页
        articles = base_query.paginate(page=page, per_page=10, error_out=False)
        
        # 获取相关标签 - 只获取搜索结果中的标签
        tags = Tag.query.join(Article.tags)\
            .filter(Article.title.ilike(f'%{query}%'))\
            .distinct()\
            .all()
        
        # 获取分类数据
        categories, article_counts = get_categories_data()
        
        # 使用缓存键
        cache_key = f'search_{query}_{page}_{",".join(sorted(selected_tags))}_{sort}'
        
        # 渲染模板
        result = render_template('blog/search.html',
                             articles=articles,
                             query=query,
                             tags=tags,
                             selected_tags=selected_tags,
                             sort=sort,
                             categories=categories,
                             article_counts=article_counts)
        
        # 缓存结果5分钟
        cache.set(cache_key, result, timeout=300)
        return result
        
    except Exception as e:
        flash(f'搜索出错：{str(e)}')
        return redirect(url_for('blog.index'))

@bp.route('/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    # 使用 memoize 替代 cached
    @cache.memoize(timeout=60)
    def get_suggestions(query):
        search_query = f'%{query}%'
        suggestions = Article.query.filter(
            db.or_(
                Article.title.like(search_query),
                Article.content.like(search_query)
            )
        ).with_entities(Article.title).limit(5).all()
        return [s.title for s in suggestions]
    
    try:
        return jsonify(get_suggestions(query))
    except Exception:
        return jsonify([])

@bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    if 'upload' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['upload']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if file and allowed_file(file.filename):
        # 获取文件扩展名
        file_ext = file.filename.rsplit('.', 1)[1].lower()

        # 生成文件内容的 MD5 哈希值
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        file.stream.seek(0)  # 重置文件指针

        # 检查是否存在相同的文件
        existing_file = File.query.filter_by(md5=file_hash).first()
        if existing_file:
            # 如果文件已存在，直返回已存在文件的URL
            return jsonify({
                'location': existing_file.file_path,
                'url': existing_file.file_path,
                'uploaded': True
            })

        filename = f"{file_hash}.{file_ext}"

        # 生成日期路径
        date_path = datetime.now().strftime('%Y%m%d')
        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'images', date_path)
        os.makedirs(upload_folder, exist_ok=True)

        # 保存文件
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        try:
            # 使用相对路径
            relative_path = f'/static/uploads/images/{date_path}/{filename}'

            # 保存文件信息到数据库
            db_file = File(
                filename=filename,
                original_filename=file.filename,
                file_path=relative_path,  # 保存相对路径
                file_type='images/'+file_ext,
                file_size=os.path.getsize(file_path),
                md5=file_hash,
                uploader_id=current_user.id
            )
            db.session.add(db_file)
            db.session.commit()

            return jsonify({
                'location': relative_path,  # TinyMCE 需要 location 字段
                'url': relative_path,       # 兼容其他情况
                'uploaded': True
            })
        except Exception as e:
            db.session.rollback()
            # 如果数据库操作失败，删除已上传的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'error': f'保存文件信息失败：{str(e)}'}), 500

    return jsonify({'error': '不支持的文件类型'}), 400

@bp.route('/article/<int:id>', methods=['DELETE'])
@login_required
def delete_article(id):
    article = get_article(id)
    
    # 检查权限
    if article.author_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': '没有权限删除此文章'}), 403
    
    # 清除相关缓存
    cache.delete_many(
        'categories_with_count',
        f'article_{id}',
        'hot_articles_today',
        'hot_articles_week',
        'random_articles'
    )
    
    db.session.delete(article)
    db.session.commit()
    return '', 204

@bp.route('/tag/<int:id>')
def tag(id):
    tag = Tag.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    
    # 使用 memoize 替代 cached
    @cache.memoize(timeout=300)
    def get_tag_articles(tag_id, page):
        return Article.query\
            .filter(Article.tags.contains(Tag.query.get(tag_id)))\
            .order_by(Article.created_at.desc())\
            .paginate(page=page, per_page=10, error_out=False)
    
    try:
        articles = get_tag_articles(id, page)
    except Exception:
        articles = Article.query\
            .filter(Article.tags.contains(tag))\
            .order_by(Article.created_at.desc())\
            .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('blog/tag.html', 
                         tag=tag,
                         articles=articles)