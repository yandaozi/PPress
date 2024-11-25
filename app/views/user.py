from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.view_history import ViewHistory
from app.models.article import Article
from app.models.comment import Comment
from app.models.user import User
from app.models.tag import Tag
from app.models.category import Category
from app import db
import pandas as pd
import plotly.express as px
import json
from collections import Counter
import numpy as np
import os
from werkzeug.utils import secure_filename
from flask import current_app
from datetime import datetime

bp = Blueprint('user', __name__, url_prefix='/user')

# 添加 JSON 编码器来处理 NumPy 类型
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

@bp.route('/profile')
@login_required
def profile():
    # 获取用户浏览历史（分页）
    page = request.args.get('page', 1, type=int)
    view_history = ViewHistory.query\
        .filter_by(user_id=current_user.id)\
        .order_by(ViewHistory.viewed_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    # 获取用户的文章
    user_articles = Article.query.filter_by(author_id=current_user.id)\
        .order_by(Article.created_at.desc())\
        .all()
    
    # 获取用户兴趣标签统计（只取前5个最常看的标签）
    tag_counts = Counter()
    for history in ViewHistory.query.filter_by(user_id=current_user.id).all():
        for tag in history.article.tags:
            tag_counts[tag.name] += 1
    
    # 获取前5个最常看的标签
    top_tags = tag_counts.most_common(5)
    
    # 生成标签统计图表
    if top_tags:
        df = pd.DataFrame(top_tags, columns=['tag', 'count'])
        total = df['count'].sum()
        df['percentage'] = df['count'] / total * 100
        
        fig = px.pie(df, 
                    values='count', 
                    names='tag', 
                    hover_data=['percentage'])
        
        # 调整图表布局
        fig.update_layout(
            height=250,  # 增加高度
            margin=dict(t=20, b=60, l=20, r=20),  # 增加底部边距
            showlegend=True,
            legend=dict(
                orientation="h",     # 水平放置图例
                yanchor="bottom",
                y=-0.4,             # 将图例位置再往下移动一点
                xanchor="center",   # 居中对齐
                x=0.5,
                font=dict(size=11)  # 保持字体大小
            ),
            hoverlabel=dict(
                bgcolor="white",
                font_size=13
            ),
            plot_bgcolor='rgba(0,0,0,0)',  # 设置绘图区背景透明
            paper_bgcolor='rgba(0,0,0,0)'  # 设置整个图表纸张背景透明
        )
        
        # 修改悬浮框文本
        fig.update_traces(
            textinfo='percent',  # 显示百分比
            hovertemplate="<b>%{label}</b><br>" +
                         "阅读次数: %{value}<br>" +
                         "占比: %{customdata[0]:.1f}%<extra></extra>"
        )
        
        interests_chart = json.dumps(fig.to_dict(), cls=NumpyEncoder)
    else:
        interests_chart = None
    
    # 获取情感倾向统计
    sentiment_data = db.session.query(
        db.func.avg(Article.sentiment_score).label('avg_sentiment')
    ).join(ViewHistory).filter(ViewHistory.user_id == current_user.id).first()
    
    avg_sentiment = sentiment_data.avg_sentiment if sentiment_data.avg_sentiment else 0
    
    return render_template('user/profile.html',
                         view_history=view_history,
                         user_articles=user_articles,
                         interests_chart=interests_chart,
                         avg_sentiment=avg_sentiment)

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        avatar = request.files.get('avatar')
        
        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                flash('用户名已存在')
                return redirect(url_for('user.edit_profile'))
            current_user.username = username
            
        if email and email != current_user.email:
            if User.query.filter_by(email=email).first():
                flash('邮箱已存在')
                return redirect(url_for('user.edit_profile'))
            current_user.email = email
            
        if avatar:
            # 检查文件大小（2MB限制）
            if len(avatar.read()) > 2 * 1024 * 1024:  # 2MB in bytes
                flash('图片大小不能超过2MB')
                return redirect(url_for('user.edit_profile'))
            avatar.seek(0)  # 重置文件指针
            
            # 检查文件类型
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if '.' not in avatar.filename:
                flash('文件名无效')
                return redirect(url_for('user.edit_profile'))
            file_extension = avatar.filename.rsplit('.', 1)[1].lower()
            if file_extension not in allowed_extensions:
                flash('不支持的文件格式，请上传 PNG、JPG、GIF 或 WebP 格式的图片')
                return redirect(url_for('user.edit_profile'))

            # 创建上传目录
            avatar_dir = os.path.join(current_app.static_folder, 'uploads', 'avatars')
            if not os.path.exists(avatar_dir):
                os.makedirs(avatar_dir)
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = secure_filename(avatar.filename)
            unique_filename = f"{timestamp}_{filename}"
            
            # 保存文件
            avatar_path = os.path.join('uploads', 'avatars', unique_filename)
            full_path = os.path.join(current_app.static_folder, avatar_path)
            avatar.save(full_path)
            
            # 更新用户头像路径（使用正斜杠）
            avatar_url = avatar_path.replace('\\', '/')
            current_user.avatar = f"/static/{avatar_url}"
            
        db.session.commit()
        flash('个人信息更新成功！')
        return redirect(url_for('user.profile'))
        
    return render_template('user/edit_profile.html')

@bp.route('/my-articles')
@login_required
def my_articles():
    page = request.args.get('page', 1, type=int)
    # 获取用户的文章列表（分页）
    articles = Article.query\
        .filter_by(author_id=current_user.id)\
        .order_by(Article.id.desc(), Article.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    return render_template('user/my_articles.html', articles=articles)

@bp.route('/author/<int:id>')
def author(id):
    page = request.args.get('page', 1, type=int)
    author = User.query.get_or_404(id)
    
    # 获取作者的文章（分页）
    articles = Article.query\
        .filter_by(author_id=id)\
        .order_by(Article.id.desc(), Article.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    
    # 获取作者的统计信息
    stats = {
        'article_count': Article.query.filter_by(author_id=id).count(),
        'comment_count': Comment.query.filter_by(user_id=id).count(),
        'total_views': db.session.query(db.func.sum(Article.view_count))\
            .filter(Article.author_id == id).scalar() or 0,
        
        # 最近活动时间
        'last_post_date': Article.query.filter_by(author_id=id)\
            .order_by(Article.created_at.desc())\
            .first().created_at.strftime('%Y-%m-%d') if Article.query.filter_by(author_id=id).first() else None,
        'last_comment_date': Comment.query.filter_by(user_id=id)\
            .order_by(Comment.created_at.desc())\
            .first().created_at.strftime('%Y-%m-%d') if Comment.query.filter_by(user_id=id).first() else None,
        
        # 获取作者最常写的分类（Top 5）
        'top_categories': db.session.query(
            Category.name, 
            db.func.count(Article.id).label('count')
        ).join(Article)\
         .filter(Article.author_id == id)\
         .group_by(Category.name)\
         .order_by(db.text('count DESC'))\
         .limit(5).all(),
        
        # 获取作者最常用的标签（Top 8）
        'top_tags': db.session.query(
            Tag.name, 
            db.func.count(Article.id).label('count')
        ).join(Article.tags)\
         .filter(Article.author_id == id)\
         .group_by(Tag.name)\
         .order_by(db.text('count DESC'))\
         .limit(8).all()
    }
    
    return render_template('user/author.html', 
                         author=author, 
                         articles=articles,
                         stats=stats) 