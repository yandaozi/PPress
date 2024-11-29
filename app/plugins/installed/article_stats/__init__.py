from flask import jsonify, render_template_string, current_app, url_for, send_from_directory
from app.plugins import PluginBase
from bs4 import BeautifulSoup
from markupsafe import Markup
import re
import os

class Plugin(PluginBase):
    def __init__(self):
        super().__init__()
        
        # 注册API路由
        @self.route('/plugin/article_stats/calculate/<int:article_id>', methods=['GET'])
        def calculate_stats(article_id):
            """获取文章统计信息"""
            from app.models import Article
            article = Article.query.get_or_404(article_id)
            stats = self.calculate_article_stats(article.content)
            return jsonify(stats)
        
        # 注册静态文件路由
        @self.route('/plugin/article_stats/static/<path:filename>', 
                   endpoint='article_stats_static',
                   methods=['GET'])
        def serve_static(filename):
            """提供静态文件访问"""
            static_folder = os.path.join(os.path.dirname(__file__), 'static')
            return send_from_directory(static_folder, filename)
    
    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 注册模板函数
        def render_article_stats():
            """渲染统计信息模板"""
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'stats.html')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = f.read()
                return Markup(render_template_string(template))
            return ''
        
        # 直接添加到 Jinja2 环境
        app.jinja_env.globals['render_article_stats'] = render_article_stats
        
        print(f"Plugin initialized with template function: render_article_stats")
    
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