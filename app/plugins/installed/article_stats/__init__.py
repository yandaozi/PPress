from flask import jsonify, render_template_string, send_from_directory, current_app, Blueprint
from app.plugins import PluginBase
from bs4 import BeautifulSoup
from markupsafe import Markup
import re
import os

class Plugin(PluginBase):
    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 创建蓝图
        self.bp = Blueprint(
            'article_stats',
            __name__,
            static_folder='static',
            static_url_path='/article-stats/static'
        )
        
        # 注册计算统计信息的路由
        @self.bp.route('/calculate/<int:article_id>')
        def calculate_stats(article_id):
            from app.models import Article
            article = Article.query.get_or_404(article_id)
            stats = self.calculate_article_stats(article.content)
            return jsonify(stats)
        
        # 注册模板函数
        def render_article_stats():
            """渲染文章统计模板"""
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'stats.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                return Markup(render_template_string(template))
            return ''
        
        # 注册模板函数到应用的全局上下文
        def inject_article_stats():
            return {'render_article_stats': render_article_stats}
        
        # 添加到应用的上下文处理器列表
        if inject_article_stats not in app.template_context_processors[None]:
            app.template_context_processors[None].append(inject_article_stats)
        
        # 注册蓝图
        app.register_blueprint(self.bp, url_prefix='/article-stats')
        
        print(f"Plugin initialized with template function: render_article_stats")
        print(f"Template path exists: {os.path.exists(os.path.join(os.path.dirname(__file__), 'templates', 'stats.html'))}")
    
    def calculate_article_stats(self, content):
        """计算文章统计信息"""
        if not content:
            return {
                'word_count': 0,
                'read_time': 0,
                'code_blocks': 0,
                'images': 0
            }
        
        # 使用BeautifulSoup解析HTML内容
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        # 计算统计信息
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        code_blocks = len(soup.find_all('pre'))
        images = len(soup.find_all('img'))
        
        # 计算阅读时间
        total_words = chinese_chars + words
        wpm = self.settings.get('words_per_minute', {'chinese': 300, 'english': 200})
        read_time = round((chinese_chars / wpm['chinese'] + words / wpm['english']) * 60)
        
        return {
            'word_count': total_words,
            'read_time': read_time,
            'code_blocks': code_blocks,
            'images': images
        }