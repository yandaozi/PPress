from app.models import User, Article, ViewHistory, Comment, Category
from datetime import datetime
from app.utils.cache_manager import cache_manager
from app import db
import os
import hashlib
from flask import current_app

class UserService:
    # 定义缓存过期时间常量
    CACHE_TIMES = {
        'ARTICLES': 1800,      # 用户文章列表缓存30分钟
        'HISTORY': 300,        # 浏览历史缓存5分钟
        'STATS': 600,         # 用户统计信息缓存10分钟
        'SENTIMENT': 3600,    # 情感分析缓存1小时
    }

    @staticmethod
    def get_user_articles(user_id, page=1):
        """获取用户的文章列表"""
        def query_articles():
            return Article.query\
                .options(
                    db.joinedload(Article.author),
                    db.joinedload(Article.category),
                    db.joinedload(Article.tags),
                    db.joinedload(Article.comments).joinedload(Comment.user)
                )\
                .filter_by(author_id=user_id)\
                .order_by(Article.id.desc(), Article.created_at.desc())\
                .paginate(page=page, per_page=10, error_out=False)
                
        return cache_manager.get(f'user:{user_id}:articles:{page}', 
                               query_articles,
                               ttl=UserService.CACHE_TIMES['ARTICLES'])
    
    @staticmethod
    def get_view_history(user_id, page=1):
        """获取用户浏览历史"""
        def query_history():
            return ViewHistory.query\
                .filter_by(user_id=user_id)\
                .order_by(ViewHistory.viewed_at.desc())\
                .paginate(page=page, per_page=10, error_out=False)
                
        return cache_manager.get(f'user:{user_id}:history:{page}', 
                               query_history,
                               ttl=UserService.CACHE_TIMES['HISTORY'])
    
    @staticmethod
    def get_user_stats(user_id):
        """获取用户统计信息"""
        def query_stats():
            return {
                'article_count': Article.query.filter_by(author_id=user_id).count(),
                'comment_count': Comment.query.filter_by(user_id=user_id).count(),
                'total_views': db.session.query(db.func.sum(Article.view_count))\
                    .filter(Article.author_id == user_id).scalar() or 0,
                'last_post': Article.query.filter_by(author_id=user_id)\
                    .order_by(Article.created_at.desc()).first(),
                'last_comment': Comment.query.filter_by(user_id=user_id)\
                    .order_by(Comment.created_at.desc()).first(),
                'top_categories': db.session.query(
                    Category.name, 
                    db.func.count(Article.id).label('count')
                ).join(Article)\
                 .filter(Article.author_id == user_id)\
                 .group_by(Category.name)\
                 .order_by(db.text('count DESC'))\
                 .limit(5).all()
            }
            
        return cache_manager.get(f'user:{user_id}:stats', 
                               query_stats,
                               ttl=UserService.CACHE_TIMES['STATS'])

    @staticmethod
    def update_profile(user_id, data, avatar_file=None):
        """更新用户资料"""
        try:
            user = User.query.get_or_404(user_id)
            
            # 更新基本信息
            if data.get('username') and data['username'] != user.username:
                if User.query.filter_by(username=data['username']).first():
                    return False, '用户名已存在'
                user.username = data['username']
                
            if data.get('email') and data['email'] != user.email:
                if User.query.filter_by(email=data['email']).first():
                    return False, '邮箱已被注册'
                user.email = data['email']
                
            # 更新昵称 - 如果为空字符串则设为 None
            nickname = data.get('nickname', '').strip()
            user.nickname = nickname if nickname else None
            
            # 更新密码
            password = data.get('password')
            if password:
                confirm_password = data.get('confirm_password')
                if not confirm_password:
                    return False, '请确认新密码'
                if password != confirm_password:
                    return False, '两次输入的密码不一致'
                # 这里是关键：调用 set_password 方法设置新密码
                user.set_password(password)
            
            # 处理头像
            if avatar_file:
                # 生成文件哈希
                file_content = avatar_file.read()
                file_hash = hashlib.md5(file_content).hexdigest()
                avatar_file.seek(0)
                
                # 检查文件类型
                if not avatar_file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    return False, '不支持的文件类型'
                
                # 保存头像
                date_path = datetime.now().strftime('%Y%m%d')
                file_ext = avatar_file.filename.rsplit('.', 1)[1].lower()
                filename = f"{file_hash}.{file_ext}"
                
                upload_folder = os.path.join(current_app.static_folder, 'uploads', 'avatars', date_path)
                os.makedirs(upload_folder, exist_ok=True)
                
                file_path = os.path.join(upload_folder, filename)
                avatar_file.save(file_path)
                
                # 更新头像路径
                user.avatar = f'/static/uploads/avatars/{date_path}/{filename}'
            
            db.session.commit()
            
            # 清除用户相关缓存
            cache_manager.delete(f'user:{user_id}:*')
            return True, '个人信息更新成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Update profile error: {str(e)}")
            return False, f'更新失败: {str(e)}'
    
    @staticmethod
    def delete_history(history_id=None, user_id=None):
        """删除浏览历史"""
        try:
            if history_id:
                # 删除单条记录
                history = ViewHistory.query.get_or_404(history_id)
                if history.user_id != user_id:
                    return False, '没有权限删除此记录'
                db.session.delete(history)
            else:
                # 删除所有记录
                ViewHistory.query.filter_by(user_id=user_id).delete()
            
            db.session.commit()
            
            # 清除相关缓存
            cache_manager.delete(f'user:{user_id}:history:*')  # 浏览历史缓存
            cache_manager.delete(f'user:{user_id}:sentiment')  # 情感分析缓存
            cache_manager.delete(f'user:{user_id}:stats')      # 用户统计缓存
            return True, '删除成功'
            
        except Exception as e:
            db.session.rollback()
            return False, f'删除失败: {str(e)}'
    
    @staticmethod
    def warmup_cache():
        """预热用户相关缓存"""
        try:
            # 获取活跃用户列表(比如最近登录的前10个用户)
            active_users = User.query.order_by(User.last_login.desc()).limit(10).all()

            with db.session.no_autoflush:  # 使用 no_autoflush 上下文
                for user in active_users:
                    # 预热每个活跃用户的基础数据
                    warmup_keys = {
                        f'user:{user.id}:articles:1': lambda: UserService.get_user_articles(user.id, 1),
                        f'user:{user.id}:stats': lambda: UserService.get_user_stats(user.id)
                    }

                    # 移除可能导致问题的预热项
                    # f'user:{user.id}:history:1': lambda: UserService.get_view_history(user.id, 1),
                    # f'user:{user.id}:sentiment': lambda: UserService.get_user_sentiment_stats(user.id)

                    cache_manager.warmup(warmup_keys)

            current_app.logger.info(f"User cache warmed up for {len(active_users)} active users")
            return True

        except Exception as e:
            current_app.logger.error(f"User cache warmup error: {str(e)}")
            return False