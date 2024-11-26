import hashlib

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from flask_sqlalchemy.pagination import Pagination

from app.models.article import Article
from app.models.tag import Tag
from app.models.view_history import ViewHistory
from app.models.comment import Comment
from app import db
from textblob import TextBlob
import os
from werkzeug.utils import secure_filename
from flask import current_app
from app.models.category import Category
from datetime import datetime, timedelta
import random

bp = Blueprint('blog', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    
    # 构建基础查询
    query = Article.query
    
    # 如果有分类参数,添加分类过滤
    current_category = None
    if category_id:
        current_category = Category.query.get_or_404(category_id)
        query = query.join(Category).filter(Category.id == category_id)
    
    # 分页查询
    articles = query.order_by(Article.id.desc(),Article.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    # 获取所有分类供导航使用
    categories = Category.query.all()
    
    # 获取今日最热门文章
    today = datetime.now().date()
    hot_articles_today = db.session.query(Article, db.func.count(ViewHistory.id).label('views'))\
        .join(ViewHistory)\
        .filter(db.func.date(ViewHistory.viewed_at) == today)\
        .group_by(Article.id)\
        .order_by(db.text('views DESC'))\
        .limit(5)\
        .all()
    
    # 获取本周最热门文章
    week_start = today - timedelta(days=today.weekday())
    hot_articles_week = db.session.query(Article, db.func.count(ViewHistory.id).label('views'))\
        .join(ViewHistory)\
        .filter(db.func.date(ViewHistory.viewed_at) >= week_start)\
        .group_by(Article.id)\
        .order_by(db.text('views DESC'))\
        .limit(5)\
        .all()
    
    # 随机获取5篇文章
    all_articles = Article.query.all()
    random_articles = random.sample(all_articles, min(5, len(all_articles)))
    
    # 随机获取10个标签
    all_tags = Tag.query.all()
    random_tags = random.sample(all_tags, min(10, len(all_tags)))
    
    # 获取最新10条评论
    latest_comments = Comment.query.order_by(Comment.created_at.desc()).limit(10).all()
    
    # 创建一个辅助函数来处理作者信息
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
                         current_category=current_category,
                         hot_articles_today=hot_articles_today,
                         hot_articles_week=hot_articles_week,
                         random_articles=random_articles,
                         random_tags=random_tags,
                         latest_comments=latest_comments,
                         get_author_info=get_author_info)  # 传递辅助函数到模板

@bp.route('/article/<int:id>')
def article(id):
    article = Article.query.get_or_404(id)
    
    # 创建一个默认作者信息
    author_info = {
        'id': None,  # 不提供链接
        'username': '已注销用户',
        'avatar': url_for('static', filename='default_avatar.png')  # 默认头像
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
                         author_info=author_info)

@bp.route('/article/edit', methods=['GET', 'POST'])
@bp.route('/article/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id=None):
    # 如果有id参数，则是编辑文章
    article = None
    if id:
        article = Article.query.get_or_404(id)
        # 检查权限
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
        
        if article:
            # 更新文章
            article.title = title
            article.content = content
            article.category_id = category_id
            article.sentiment_score = sentiment_score
            article.updated_at = datetime.now()
            
            # 更新标签
            article.tags.clear()
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
        flash('文章保存成功！')
        return redirect(url_for('blog.article', id=article.id))
    
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
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sort = request.args.get('sort', 'recent')
    
    # 构建基础查询
    base_query = Article.query
    
    if query:
        search_query = f'%{query}%'
        base_query = base_query.filter(
            db.or_(
                Article.title.like(search_query),
                Article.content.like(search_query)
            )
        )

    # 日期过滤
    if start_date:
        base_query = base_query.filter(Article.created_at >= start_date)
    if end_date:
        base_query = base_query.filter(Article.created_at <= end_date)

    # 在应用标签过滤之前获取所有可用的标签
    tags = Tag.query.join(Article.tags) \
        .filter(Article.id.in_([article.id for article in base_query.all()])) \
        .distinct() \
        .all()
    
    # 标签过滤
    if selected_tags:
        base_query = base_query.filter(Article.tags.any(Tag.name.in_(selected_tags)))

    # 排序
    if sort == 'views':
        base_query = base_query.order_by(Article.view_count.desc())
    elif sort == 'comments':
        # 修改评论数排序的查询
        subquery = db.session.query(
            Article.id,
            db.func.count(Comment.id).label('comment_count')
        ).outerjoin(Comment).group_by(Article.id).subquery()
        
        base_query = Article.query.join(
            subquery,
            Article.id == subquery.c.id
        ).order_by(db.desc(subquery.c.comment_count))
    else:  # recent
        base_query = base_query.order_by(Article.created_at.desc())
    
    # 分页 - 使用统一的方式
    articles = base_query.paginate(page=page, per_page=10, error_out=False)
    
    return render_template('blog/search.html',
                         articles=articles,
                         query=query,
                         tags=tags,
                         selected_tags=selected_tags,
                         sort=sort)

@bp.route('/search/suggestions')
def search_suggestions():
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    # 搜索建议
    search_query = f'%{query}%'
    suggestions = Article.query.filter(
        db.or_(
            Article.title.like(search_query),
            Article.content.like(search_query)
        )
    ).with_entities(Article.title).limit(5).all()
    
    return jsonify([s.title for s in suggestions])

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

        # 生成文件内容的 MD5 哈希值作为文件名
        file_content = file.read()
        file_hash = hashlib.md5(file_content).hexdigest()
        filename = f"{file_hash}.{file_ext}"
        file.stream.seek(0)  # 重置文件指针以保存文件

        # 生成日期路径
        date_path = datetime.now().strftime('%Y%m%d')
        upload_folder = os.path.join(current_app.static_folder, 'uploads', 'images', date_path)
        os.makedirs(upload_folder, exist_ok=True)

        # 保存文件
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # 返回文件 URL
        url = url_for('static', filename=f'uploads/images/{date_path}/{filename}', _external=True)
        return jsonify({
            'location': url,  # TinyMCE 需要 location 字段
            'url': url,       # 兼容其他情况
            'uploaded': True
        })

    return jsonify({'error': '不支持的文件类型'}), 400

@bp.route('/article/<int:id>', methods=['DELETE'])
@login_required
def delete_article(id):
    article = Article.query.get_or_404(id)
    
    # 检查权限
    if article.author_id != current_user.id and current_user.role != 'admin':
        return jsonify({'error': '没有权限删除此文章'}), 403
    
    db.session.delete(article)
    db.session.commit()
    return '', 204 

@bp.route('/tag/<int:id>')
def tag(id):
    page = request.args.get('page', 1, type=int)
    tag = Tag.query.get_or_404(id)
    
    # 获取包含此标签的文章
    articles = Article.query\
        .filter(Article.tags.contains(tag))\
        .order_by(Article.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('blog/tag.html', 
                         tag=tag,
                         articles=articles)