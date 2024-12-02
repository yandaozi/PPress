from flask import jsonify, render_template_string, current_app, url_for, send_from_directory
from app import db
from app.plugins import PluginBase
from bs4 import BeautifulSoup
from markupsafe import Markup
from app.utils.cache_manager import cache_manager
import re
import os

class Plugin(PluginBase):
    # 添加默认设置
    default_settings = {
        'enabled': True,
        'words_per_minute': {
            'chinese': 300,  # 中文阅读速度
            'english': 200   # 英文阅读速度
        }
    }
    
    def __init__(self):
        super().__init__()
        
        # 注册API路由
        @self.route('/plugin/article_stats/calculate/<int:article_id>', methods=['GET'])
        def calculate_stats(article_id):
            """获取文章统计信息"""
            try:
                from app.models import Article
                article = Article.query.get_or_404(article_id)
                
                # 尝试从缓存获取统计信息
                cache_key = f'plugin_article_stats:{article_id}'
                stats = cache_manager.get(
                    cache_key,
                    default_factory=lambda: self.calculate_article_stats(article.content),
                    ttl=3600  # 缓存1小时
                )
                return jsonify(stats)
            except Exception as e:
                current_app.logger.error(f"Error calculating stats: {str(e)}")
                return jsonify({'error': str(e)}), 500
        
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
    
    def get_settings_template(self):
        """获取设置页面模板"""
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'settings.html')
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # 从数据库获取插件记录
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            
            return render_template_string(
                template, 
                settings=self.settings,
                plugin=plugin
            )
        return None
    
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
        settings = self.get_settings()  # 获取最新配置
        wpm = settings.get('words_per_minute', self.default_settings['words_per_minute'])
        read_time = round((chinese_chars / wpm['chinese'] + words / wpm['english']) * 60)
        
        return {
            'word_count': chinese_chars + words,
            'read_time': read_time,
            'code_blocks': code_blocks,
            'images': images
        }
    
    def save_settings(self, form_data):
        """保存插件设置"""
        try:
            settings = {
                'words_per_minute': {
                    'chinese': int(form_data.get('words_per_minute_chinese', 300)),
                    'english': int(form_data.get('words_per_minute_english', 200))
                }
            }
            
            # 验证设置值
            if settings['words_per_minute']['chinese'] <= 0:
                raise ValueError('中文阅读速度必须大于0')
            if settings['words_per_minute']['english'] <= 0:
                raise ValueError('英文阅读速度必须大于0')
            
            # 保存到数据库
            from app.models import Plugin as PluginModel
            plugin = PluginModel.query.filter_by(name=self.name).first()
            if plugin:
                plugin.config = settings
                db.session.commit()
                self.settings = settings
                # 清除所有统计缓存
                cache_manager.delete('plugin_article_stats:*')
                return True, '设置已保存'
            return False, '插件不存在'
            
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f'保存设置失败: {str(e)}'