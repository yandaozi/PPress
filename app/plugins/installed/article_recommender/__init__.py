from flask import jsonify, render_template_string, current_app, url_for, send_from_directory
from app.plugins import PluginBase
from app.models import Article, Tag
from sqlalchemy import func
from markupsafe import Markup
import os

class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        
        # 注册路由时添加前缀
        @self.route('/plugin/article_recommender/recommend/<int:article_id>', methods=['GET'])
        def get_recommendations(article_id):
            """获取文章推荐"""
            try:
                current_article = Article.query.get_or_404(article_id)
                
                # 获取当前文章的标签和分类
                current_tags = current_article.tags
                current_category = current_article.category
                
                # 基于标签和分类查找相关文章
                related_articles = Article.query\
                    .filter(Article.id != article_id)\
                    .filter(
                        (Article.category_id == current_category.id) |
                        (Article.tags.any(Tag.id.in_([tag.id for tag in current_tags]))
                    ))\
                    .order_by(func.random())\
                    .limit(3)\
                    .all()
                
                return jsonify([{
                    'id': article.id,
                    'title': article.title,
                    'summary': article.content[:100] if article.content else '',
                    'category': article.category.name,
                    'tags': [tag.name for tag in article.tags],
                    'url': url_for('blog.article', id=article.id)
                } for article in related_articles])
            except Exception as e:
                current_app.logger.error(f"Error in get_recommendations: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
        # 注册静态文件路由
        @self.route('/plugin/article_recommender/static/<path:filename>')
        def serve_static(filename):
            """提供静态文件访问"""
            static_folder = os.path.join(os.path.dirname(__file__), 'static')
            return send_from_directory(static_folder, filename)
    
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