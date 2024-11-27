from flask import jsonify, send_from_directory
from app.plugins import PluginBase
from bs4 import BeautifulSoup
import re
import os

class Plugin(PluginBase):
    # 自定义默认设置
    default_settings = {
        'enabled': True,
        'position': 'content',
        'priority': 100,
        'cache_time': 3600,
        'show_word_count': True,  # 显示字数
        'show_read_time': True,   # 显示阅读时间
        'show_code_blocks': True, # 显示代码块数量
        'show_images': True,      # 显示图片数量
        'words_per_minute': {     # 每分钟阅读字数
            'chinese': 300,       # 中文
            'english': 200        # 英文
        }
    }
    
    def init_app(self, app):
        """初始化插件"""
        super().init_app(app)
        
        # 确保设置已加载
        if not self.settings:
            self.load_settings()
        
        # 注册路由
        @self.route('/article-stats/calculate/<int:article_id>', methods=['GET'])
        def calculate_stats(article_id):
            from app.models import Article
            article = Article.query.get_or_404(article_id)
            stats = self.calculate_article_stats(article.content)
            return jsonify(stats)
        
        @self.route('/article-stats/static/<path:filename>', methods=['GET'])
        def static(filename):
            static_path = os.path.join(os.path.dirname(__file__), 'static')
            return send_from_directory(static_path, filename)
        
        # 注册模板过滤器
        app.jinja_env.filters['article_stats'] = self.calculate_article_stats
        
        # 注册静态资源路径
        app.config['ARTICLE_STATS_JS'] = '/article-stats/static/js/article_stats.js'
        
        # 注册所有路由
        self.register_routes()
    
    def teardown(self):
        """清理插件"""
        # 移除模板过滤器
        if 'article_stats' in self.app.jinja_env.filters:
            del self.app.jinja_env.filters['article_stats']
        
        # 移除配置
        if 'ARTICLE_STATS_JS' in self.app.config:
            del self.app.config['ARTICLE_STATS_JS']
        
        # 移除路由
        self.unregister_routes()
    
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
        
        # 获取纯文本内容
        text = soup.get_text()
        
        # 计算中文字数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        
        # 计算英文单词数
        words = len(re.findall(r'\b[a-zA-Z]+\b', text))
        
        # 统计代码块数量
        code_blocks = len(soup.find_all('pre'))
        
        # 统计图片数量
        images = len(soup.find_all('img'))
        
        # 计算总字数（中文字数 + 英文单词数）
        total_words = chinese_chars + words
        
        # 从设置中获取阅读速度
        wpm = self.settings['words_per_minute']
        read_time = round((chinese_chars / wpm['chinese'] + words / wpm['english']) * 60)
        
        stats = {}
        if self.settings['show_word_count']:
            stats['word_count'] = total_words
        if self.settings['show_read_time']:
            stats['read_time'] = read_time
        if self.settings['show_code_blocks']:
            stats['code_blocks'] = code_blocks
        if self.settings['show_images']:
            stats['images'] = images
            
        return stats 
    
    def get_settings(self):
        """获取插件设置"""
        return {
            'show_word_count': {
                'type': 'checkbox',
                'label': '显示字数统计',
                'value': self.settings.get('show_word_count', True)
            },
            'show_read_time': {
                'type': 'checkbox',
                'label': '显示阅读时间',
                'value': self.settings.get('show_read_time', True)
            },
            'show_code_blocks': {
                'type': 'checkbox',
                'label': '显示代码块数量',
                'value': self.settings.get('show_code_blocks', True)
            },
            'show_images': {
                'type': 'checkbox',
                'label': '显示图片数量',
                'value': self.settings.get('show_images', True)
            },
            'words_per_minute_chinese': {
                'type': 'number',
                'label': '中文阅读速度（字/分钟）',
                'value': self.settings.get('words_per_minute', {}).get('chinese', 300)
            },
            'words_per_minute_english': {
                'type': 'number',
                'label': '英文阅读速度（词/分钟）',
                'value': self.settings.get('words_per_minute', {}).get('english', 200)
            }
        }
    
    def get_settings_template(self):
        """获取设置页面模板"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates/settings.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def save_settings(self, settings):
        """保存插件设置"""
        # 处理特殊的阅读速度设置
        if 'words_per_minute_chinese' in settings:
            settings['words_per_minute'] = {
                'chinese': settings.pop('words_per_minute_chinese'),
                'english': settings.pop('words_per_minute_english')
            }
        
        # 调用父类的保存方法
        super().save_settings(settings)