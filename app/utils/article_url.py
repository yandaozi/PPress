import re
from flask import current_app
from app.models import SiteConfig, Category, Article
from .id_encoder import IdEncoder
from app import db
from sqlalchemy.orm import joinedload

class ArticleUrlMapper:
    """文章URL映射器"""
    _pattern_cache = None
    _regex_cache = None
    _category_map = None
    
    @classmethod
    def _get_category_map(cls):
        """获取分类映射（缓存）"""
        if cls._category_map is None:
            cls._category_map = {}
            categories = Category.query.all()
            for cat in categories:
                cls._category_map[cat.id] = cat.slug if cat.use_slug else str(cat.id)
        return cls._category_map

    @classmethod
    def get_pattern(cls):
        """获取当前URL模式（缓存）"""
        if cls._pattern_cache is None:
            cls._pattern_cache = SiteConfig.get_article_url_pattern()
        return cls._pattern_cache

    @classmethod
    def get_regex(cls):
        """获取URL匹配正则（缓存）"""
        if cls._regex_cache is None:
            pattern = cls.get_pattern().lstrip('/')
            
            # 基本变量替换
            replacements = {
                '{id}': r'(?P<id>\d+)',
                '{encodeid}': r'(?P<encodeid>[A-Za-z0-9_-]+)',
                '{year}': r'\d{4}',
                '{month}': r'\d{2}',
                '{day}': r'\d{2}'
            }
            
            # 分类匹配
            if '{category}' in pattern:
                category_values = set(cls._get_category_map().values())
                replacements['{category}'] = f'(?P<category>{"|".join(map(re.escape, category_values))})'
            
            # 一次性替换所有变量
            for key, value in replacements.items():
                pattern = pattern.replace(key, value)
            
            cls._regex_cache = re.compile(f'^{pattern}$')
        return cls._regex_cache

    @classmethod
    def generate_url(cls, article):
        """生成文章URL"""
        pattern = cls.get_pattern()
        
        try:
            # 基本变量
            variables = {'id': article.id}
            
            # 加密ID
            if '{encodeid}' in pattern:
                variables['encodeid'] = IdEncoder.encode(article.id)
            
            # 分类
            if '{category}' in pattern:
                # 使用新的会话查询文章和分类
                article = Article.query.options(joinedload(Article.category)).get(article.id)
                if not article or not article.category_id:
                    return f'/id/{article.id}'
                
                category_map = cls._get_category_map()
                if article.category_id not in category_map:
                    return f'/id/{article.id}'
                variables['category'] = category_map[article.category_id]
            
            # 日期
            if '{year}' in pattern or '{month}' in pattern or '{day}' in pattern:
                dt = article.created_at
                variables.update({
                    'year': dt.strftime('%Y'),
                    'month': dt.strftime('%m'),
                    'day': dt.strftime('%d')
                })
            
            return '/' + pattern.lstrip('/').format(**variables)
            
        except Exception as e:
            current_app.logger.error(f"Error generating URL: {str(e)}")
            return f'/id/{article.id}'

    @classmethod
    def get_article_from_path(cls, path):
        """从路径中获取文章"""
        try:
            match = cls.get_regex().match(path.lstrip('/'))
            if not match:
                return None
                
            groups = match.groupdict()
            
            # 获取文章ID
            article_id = None
            if 'encodeid' in groups:
                article_id = IdEncoder.decode(groups['encodeid'])
            elif 'id' in groups:
                article_id = int(groups['id'])
            
            if not article_id:
                return None
            
            # 获取文章（使用 joinedload 预加载分类）
            article = Article.query.options(joinedload(Article.category)).get(article_id)
            if not article:
                return None
            
            # 验证分类
            if 'category' in groups:
                if not article.category_id:
                    return None
                    
                category_map = cls._get_category_map()
                if article.category_id not in category_map:
                    return None
                if groups['category'] != category_map[article.category_id]:
                    return None
            
            return article
            
        except Exception as e:
            current_app.logger.error(f"Error parsing article path: {str(e)}")
            return None

    @classmethod
    def clear_cache(cls):
        """清除所有缓存"""
        cls._pattern_cache = None
        cls._regex_cache = None
        cls._category_map = None