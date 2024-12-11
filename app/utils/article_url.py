from flask import current_app
from app.models import SiteConfig, Category, Article
from .id_encoder import IdEncoder

class ArticleUrlGenerator:
    """文章URL生成器"""
    _pattern_cache = None
    _category_map = None
    _regex_cache = {}  # 正则缓存
    _category_validation_cache = {}  # 分类验证缓存
    
    @classmethod
    def _get_pattern(cls):
        """获取URL模式(缓存)"""
        if cls._pattern_cache is None:
            cls._pattern_cache = SiteConfig.get_article_url_pattern()
        return cls._pattern_cache
    
    @classmethod
    def _get_category_key(cls, category_id):
        """获取分类URL键(缓存)"""
        if cls._category_map is None:
            cls._category_map = {}
            categories = Category.query.all()
            for cat in categories:
                cls._category_map[cat.id] = cat.slug if cat.use_slug else str(cat.id)
        return cls._category_map.get(category_id)

    @classmethod
    def _validate_category(cls, category_value):
        """验证分类访问方式(缓存)"""
        if category_value in cls._category_validation_cache:
            return cls._category_validation_cache[category_value]
            
        try:
            category_id = int(category_value)
            category = Category.query.get(category_id)
            result = not (category and category.use_slug)
        except ValueError:
            category = Category.query.filter_by(slug=category_value).first()
            result = bool(category and category.use_slug)
            
        cls._category_validation_cache[category_value] = result
        return result

    @classmethod
    def generate(cls, id, category_id=None, created_at=None):
        """生成文章URL"""
        try:
            pattern = cls._get_pattern()
            variables = {'id': id}
            
            # 如果需要使用 slug
            if '{slug}' in pattern:
                article = Article.query.get(id)
                if article and article.slug:
                    variables['slug'] = article.slug
                else:
                    return f'/article/{id}'  # 改为默认的 article/{id} 格式
            
            # 加密ID
            if '{encodeid}' in pattern:
                variables['encodeid'] = IdEncoder.encode(id)
            
            # 分类
            if '{category}' in pattern:
                if not category_id:
                    return f'/id/{id}'
                category_key = cls._get_category_key(category_id)
                if not category_key:
                    return f'/id/{id}'
                variables['category'] = category_key
            
            # 日期
            if any(x in pattern for x in ('{year}', '{month}', '{day}')):
                if not created_at:
                    return f'/id/{id}'
                variables.update({
                    'year': created_at.strftime('%Y'),
                    'month': created_at.strftime('%m'),
                    'day': created_at.strftime('%d')
                })
            
            return '/' + pattern.lstrip('/').format(**variables)
            
        except Exception as e:
            current_app.logger.error(f"Error generating URL: {str(e)}")
            return f'/id/{id}'

    @classmethod
    def parse(cls, path):
        """解析URL路径获取文章ID"""
        try:
            path = path.lstrip('/')
            pattern = cls._get_pattern().lstrip('/')
            
            # 使用缓存的正则表达式
            if pattern not in cls._regex_cache:
                regex_pattern = pattern
                replacements = {
                    '{id}': r'(?P<id>\d+)',
                    '{encodeid}': r'(?P<encodeid>[A-Za-z0-9_-]+)',
                    '{year}': r'\d{4}',
                    '{month}': r'\d{2}',
                    '{day}': r'\d{2}',
                    '{category}': r'(?P<category>[^/]+)',
                    '{slug}': r'(?P<slug>[^/]+)'  # 添加 slug 支持
                }
                
                for var, regex in replacements.items():
                    regex_pattern = regex_pattern.replace(var, regex)
                
                import re
                cls._regex_cache[pattern] = re.compile(f'^{regex_pattern}$')
            
            match = cls._regex_cache[pattern].match(path)
            if not match:
                return None
            
            # 如果匹配到 slug,通过 slug 查找文章
            if 'slug' in match.groupdict():
                article = Article.query.filter_by(slug=match.group('slug')).first()
                if article:
                    return article.id
            
            # 如果有分类，验证访问方式
            if 'category' in match.groupdict():
                category_value = match.group('category')
                if not cls._validate_category(category_value):
                    return None
            
            # 获取ID
            if 'encodeid' in match.groupdict():
                return IdEncoder.decode(match.group('encodeid'))
            elif 'id' in match.groupdict():
                return int(match.group('id'))
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error parsing URL: {str(e)}")
            return None

    @classmethod
    def clear_cache(cls):
        """清除所有缓存"""
        cls._pattern_cache = None
        cls._category_map = None
        cls._regex_cache.clear()
        cls._category_validation_cache.clear()