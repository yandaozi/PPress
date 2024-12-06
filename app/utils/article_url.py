from flask import current_app
from app.models import SiteConfig, Category
from .id_encoder import IdEncoder
from .cache_manager import cache_manager

class ArticleUrlGenerator:
    """文章URL生成器"""
    _pattern_cache = None
    _category_map = None
    
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
    def generate(cls, id, category_id=None, created_at=None):
        """生成文章URL
        :param id: 文章ID
        :param category_id: 分类ID(可选)
        :param created_at: 创建时间(可选)
        """
        try:
            pattern = cls._get_pattern()
            variables = {'id': id}
            
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
            
            # 构建正则模式
            regex_pattern = pattern
            # 替换所有变量为对应的正则
            replacements = {
                '{id}': r'(?P<id>\d+)',
                '{encodeid}': r'(?P<encodeid>[A-Za-z0-9_-]+)',
                '{year}': r'\d{4}',
                '{month}': r'\d{2}',
                '{day}': r'\d{2}',
                '{category}': r'(?P<category>[^/]+)'
            }
            
            for var, regex in replacements.items():
                regex_pattern = regex_pattern.replace(var, regex)
            
            # 编译正则表达式
            import re
            regex = re.compile(f'^{regex_pattern}$')
            
            # 匹配路径
            match = regex.match(path)
            if not match:
                return None
            
            # 如果有分类，验证访问方式
            if 'category' in match.groupdict():
                category_value = match.group('category')
                # 尝试作为ID解析
                try:
                    category_id = int(category_value)
                    # 如果是数字，检查该分类是否禁用了ID访问
                    category = Category.query.get(category_id)
                    if category and category.use_slug:
                        return None  # 该分类设置了使用slug访问，不允许用ID访问
                except ValueError:
                    # 如果不是数字，说明是slug，检查该分类是否启用了slug访问
                    category = Category.query.filter_by(slug=category_value).first()
                    if category and not category.use_slug:
                        return None  # 该分类没有设置使用slug访问，不允许用slug访问
            
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
        """清除缓存"""
        cls._pattern_cache = None
        cls._category_map = None