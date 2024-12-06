import re
from flask import url_for, current_app
from app.models import SiteConfig
from .id_encoder import IdEncoder

class ArticleUrlMapper:
    """文章URL映射器"""
    _pattern_cache = None
    _regex_cache = None
    
    @classmethod
    def get_pattern(cls):
        """获取当前URL模式"""
        if cls._pattern_cache is None:
            cls._pattern_cache = SiteConfig.get_article_url_pattern()
        return cls._pattern_cache
    
    @classmethod
    def get_regex(cls):
        """获取URL匹配正则"""
        if cls._regex_cache is None:
            pattern = cls.get_pattern()
            # 将模式转换为正则表达式，并缓存
            pattern = pattern.lstrip('/')  # 移除开头的斜杠
            cls._regex_cache = re.compile(
                '^' +  # 添加开头匹配
                pattern.replace('{id}', '(?P<id>\d+)')
                      .replace('{encodeid}', '(?P<encodeid>[A-Za-z0-9_-]+)')
                      .replace('{category}', '[^/]+')
                      .replace('{year}', '\d{4}')
                      .replace('{month}', '\d{2}')
                      .replace('{day}', '\d{2}') +
                '$'  # 添加结尾匹配
            )
        return cls._regex_cache
    
    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        cls._pattern_cache = None
        cls._regex_cache = None
        
    @classmethod
    def generate_url(cls, article):
        """生成文章URL"""
        pattern = cls.get_pattern()
        
        # 预处理变量
        variables = {'id': article.id}
        
        if '{encodeid}' in pattern:
            variables['encodeid'] = IdEncoder.encode(article.id)
        
        if '{category}' in pattern:
            try:
                # 使用新的 session 查询分类信息
                from app import db
                from app.models import Article
                article = db.session.merge(article)  # 确保对象在当前session中
                
                if article.category:
                    variables['category'] = (article.category.slug 
                                           if article.category.use_slug 
                                           else article.category.id)
                else:
                    variables['category'] = 'uncategorized'
            except Exception as e:
                current_app.logger.error(f"Error loading category: {str(e)}")
                variables['category'] = 'uncategorized'
        
        if any(x in pattern for x in ('{year}', '{month}', '{day}')):
            created_at = article.created_at
            variables.update({
                'year': created_at.strftime('%Y'),
                'month': created_at.strftime('%m'),
                'day': created_at.strftime('%d')
            })
        
        try:
            path = pattern.format(**variables)
            if not path.startswith('/'):
                path = '/' + path
            return path
        except Exception as e:
            current_app.logger.error(f"Error generating URL: {str(e)}")
            return f'/id/{article.id}'
    
    @classmethod
    def get_article_from_path(cls, path):
        """从路径中获取文章"""
        from app.models import Article, Category
        
        try:
            # 移除开头的斜杠
            path = path.lstrip('/')
            current_app.logger.info(f"Processing path: {path}")
            
            # 获取当前 URL 模式的正则表达式
            regex = cls.get_regex()
            current_app.logger.info(f"Using regex pattern: {regex.pattern}")
            
            # 匹配路径
            match = regex.match(path)
            current_app.logger.info(f"Regex match result: {match}")
            
            if match:
                current_app.logger.info(f"Match groups: {match.groupdict()}")
                
                # 获取文章ID
                article_id = None
                
                # 优先尝试获取加密ID
                if 'encodeid' in match.groupdict():
                    encoded_id = match.group('encodeid')
                    article_id = IdEncoder.decode(encoded_id)
                # 尝试普通ID
                elif 'id' in match.groupdict():
                    article_id = int(match.group('id'))
                
                # 如果有分类信息，验证分类是否匹配
                if article_id and 'category' in match.groupdict():
                    category_slug = match.group('category')
                    article = Article.query.get(article_id)
                    
                    if article:
                        # 检查分类是否匹配
                        if category_slug == 'uncategorized':
                            if article.category is not None:
                                return None
                        else:
                            # 通过 slug 或 id 查找分类
                            category = Category.query.filter(
                                (Category.slug == category_slug) | 
                                (Category.id == category_slug)
                            ).first()
                            
                            if not category or article.category_id != category.id:
                                return None
                
                if article_id:
                    return Article.query.get(article_id)
                    
            return None
                
        except Exception as e:
            current_app.logger.error(f"Error parsing article path: {str(e)}")
            return None