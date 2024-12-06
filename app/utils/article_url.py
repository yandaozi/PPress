import re
from flask import current_app
from app.models import SiteConfig, Category, Article
from .id_encoder import IdEncoder

class ArticleUrlMapper:
    """文章URL映射器"""
    _pattern_cache = None
    _regex_cache = None
    _category_pattern_cache = None  # 添加分类模式缓存
    
    @classmethod
    def _get_category_pattern(cls):
        """获取分类匹配模式（缓存）"""
        if cls._category_pattern_cache is None:
            # 使用列表推导式和join，比循环拼接更快
            slug_categories = '|'.join(
                c.slug for c in Category.query.filter_by(use_slug=True).all()
            )
            id_categories = '|'.join(
                str(c.id) for c in Category.query.filter_by(use_slug=False).all()
            )
            
            # 使用列表join而不是字符串拼接
            patterns = []
            if slug_categories:
                patterns.append(f'(?:{slug_categories})')
            if id_categories:
                patterns.append(f'(?:{id_categories})')
                
            cls._category_pattern_cache = '|'.join(patterns)
        return cls._category_pattern_cache

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
            
            # 使用字典替换，比多次调用replace更快
            replacements = {
                '{id}': '(?P<id>\d+)',
                '{encodeid}': '(?P<encodeid>[A-Za-z0-9_-]+)',
                '{year}': '\d{4}',
                '{month}': '\d{2}',
                '{day}': '\d{2}'
            }
            
            # 如果包含分类，添加分类匹配
            if '{category}' in pattern:
                replacements['{category}'] = f'(?P<category>{cls._get_category_pattern()})'
            
            # 一次性替换所有变量
            for key, value in replacements.items():
                pattern = pattern.replace(key, value)
            
            cls._regex_cache = re.compile(f'^{pattern}$')
        return cls._regex_cache

    @classmethod
    def generate_url(cls, article):
        """生成文章URL"""
        pattern = cls.get_pattern()
        
        # 使用字典存储所有变量，避免多次判断
        variables = {'id': article.id}
        
        try:
            # 处理加密ID
            if '{encodeid}' in pattern:
                variables['encodeid'] = IdEncoder.encode(article.id)
            
            # 处理分类
            if '{category}' in pattern:
                if not article.category:
                    return f'/id/{article.id}'
                    
                variables['category'] = (article.category.slug 
                                       if article.category.use_slug 
                                       else str(article.category.id))
            
            # 处理日期
            if any(x in pattern for x in ('{year}', '{month}', '{day}')):
                created_at = article.created_at
                variables.update({
                    'year': created_at.strftime('%Y'),
                    'month': created_at.strftime('%m'),
                    'day': created_at.strftime('%d')
                })
            
            # 一次性格式化
            path = '/' + pattern.lstrip('/').format(**variables)
            return path
            
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
            article_id = None
            
            # 优先使用加密ID
            if 'encodeid' in groups:
                article_id = IdEncoder.decode(groups['encodeid'])
            elif 'id' in groups:
                article_id = int(groups['id'])
                
            if not article_id:
                return None
                
            article = Article.query.get(article_id)
            if not article:
                return None
                
            # 验证分类
            if 'category' in groups:
                category_value = groups['category']
                if not article.category:
                    return None
                    
                if article.category.use_slug:
                    if category_value != article.category.slug:
                        return None
                else:
                    try:
                        if int(category_value) != article.category.id:
                            return None
                    except ValueError:
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
        cls._category_pattern_cache = None