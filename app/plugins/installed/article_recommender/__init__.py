from flask import jsonify, render_template_string, current_app, url_for, send_from_directory
from app import db, ArticleUrlGenerator
from app.plugins import PluginBase
from app.models import Article, Tag
from sqlalchemy import func
from markupsafe import Markup
from app.utils.cache_manager import cache_manager
import os

class Plugin(PluginBase):
    # 添加默认设置
    default_settings = {
        'recommend_count': 3  # 默认推荐3篇文章
    }
    
    def __init__(self):
        super().__init__()
        
        # 注册API路由
        @self.route('/plugin/article_recommender/recommend/<int:article_id>', methods=['GET'])
        def get_recommendations(article_id):
            """获取文章推荐"""
            try:
                # 尝试从缓存获取推荐
                cache_key = f'plugin_article_recommendations:{article_id}'
                recommendations = cache_manager.get(
                    cache_key,
                    default_factory=lambda: self._get_recommendations(article_id),
                    ttl=3600  # 缓存1小时
                )
                return jsonify(recommendations)
            except Exception as e:
                current_app.logger.error(f"Error in get_recommendations: {str(e)}")
                return jsonify({'error': str(e)}), 500

        # 注册静态文件路由
        @self.route('/plugin/article_recommender/static/<path:filename>', 
                   endpoint='article_recommender_static',
                   methods=['GET'])
        def serve_static(filename):
            """提供静态文件访问"""
            static_folder = os.path.join(os.path.dirname(__file__), 'static')
            return send_from_directory(static_folder, filename)

    def _get_recommendations(self, article_id):
        """获取推荐文章的具体实现"""
        current_article = Article.query.get_or_404(article_id)
        
        # 获取当前文章的标签和分类
        current_tags = current_article.tags
        current_category = current_article.category
        settings = self.get_settings()  # 获取最新配置
        # 基于标签和分类查找相关文章
        related_articles = Article.query\
            .filter(Article.id != article_id)\
            .filter(
                (Article.category_id == current_category.id) |
                (Article.tags.any(Tag.id.in_([tag.id for tag in current_tags]))
            ))\
            .order_by(func.random())\
            .limit(settings.get('recommend_count', self.default_settings['recommend_count']))\
            .all()
        
        # 构建推荐数据
        return [{
            'id': article.id,
            'title': article.title,
            'summary': article.content[:100] if article.content else '',
            'category': article.category.name,
            'tags': [tag.name for tag in article.tags],
            'url': ArticleUrlGenerator.generate(article.id, article.category_id, article.created_at) 
        } for article in related_articles]

    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 注册模板函数
        def render_recommendations():
            """渲染推荐模板"""
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'recommendations.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                return Markup(render_template_string(template))
            return ''
        
        # 直接添加到 Jinja2 环境
        app.jinja_env.globals['render_recommendations'] = render_recommendations
        
        print(f"Plugin initialized with template function: render_recommendations")
    
    def get_settings_template(self):
        """获取设置页面模板"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'settings.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            return render_template_string(template, settings=self.settings)
        return None
    
    def save_settings(self, form_data):
        """保存插件设置"""
        try:
            recommend_count = int(form_data.get('recommend_count', 3))
            
            # 验证设置值
            if recommend_count <= 0:
                raise ValueError('推荐文章数量必须大于0')
            if recommend_count > 100:
                raise ValueError('推荐文章数量不能超过100')
            
            settings = {
                'recommend_count': recommend_count
            }
            
            # 保存到数据库
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            if plugin:
                plugin.config = settings
                db.session.commit()
                self.settings = settings
                # 清除所有推荐缓存
                cache_manager.delete('plugin_article_recommendations:*')
                return True, '设置已保存'
            return False, '插件不存在'
            
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f'保存设置失败: {str(e)}'