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
            pattern = pattern.lstrip('/')  # 移除开头的斜杠
            
            # 如果模式中包含分类，需要根据分类设置生成正则
            if '{category}' in pattern:
                from app.models import Category
                # 获取所有使用 slug 的分类的 slug
                slug_categories = '|'.join(c.slug for c in Category.query.filter_by(use_slug=True).all())
                # 获取所有不使用 slug 的分类的 id
                id_categories = '|'.join(str(c.id) for c in Category.query.filter_by(use_slug=False).all())
                
                # 构建分类匹配模式
                category_pattern = ''
                if slug_categories:
                    category_pattern += f'(?:{slug_categories})'
                if id_categories:
                    if category_pattern:
                        category_pattern += '|'
                    category_pattern += f'(?:{id_categories})'
                
                # 替换 {category} 为具体的匹配模式
                pattern = pattern.replace('{category}', f'(?P<category>{category_pattern})')
            
            # 其他变量的替换
            cls._regex_cache = re.compile(
                '^' +  # 添加开头匹配
                pattern.replace('{id}', '(?P<id>\d+)')
                      .replace('{encodeid}', '(?P<encodeid>[A-Za-z0-9_-]+)')
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
                    # 根据分类设置使用 slug 或 id
                    variables['category'] = (article.category.slug 
                                           if article.category.use_slug 
                                           else str(article.category.id))
                else:
                    # 如果没有分类，返回默认的 ID 格式
                    return f'/id/{article.id}'
            except Exception as e:
                current_app.logger.error(f"Error loading category: {str(e)}")
                return f'/id/{article.id}'
        
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
            
            # 获取当前 URL 模式的正则表达式
            regex = cls.get_regex()
            
            # 匹配路径
            match = regex.match(path)
            
            if match:
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
                    category_slug_or_id = match.group('category')
                    article = Article.query.get(article_id)
                    
                    if article and article.category:
                        # 检查分类是否匹配
                        if article.category.use_slug:
                            # 如果分类设置了使用 slug，只能通过 slug 访问
                            if category_slug_or_id != article.category.slug:
                                return None
                        else:
                            # 如果分类没有设置使用 slug，只能通过 ID 访问
                            try:
                                if int(category_slug_or_id) != article.category.id:
                                    return None
                            except ValueError:
                                return None
                    else:
                        # 如果文章没有分类，不允许通过分类访问
                        return None
                
                if article_id:
                    return Article.query.get(article_id)
                    
            return None
                
        except Exception as e:
            current_app.logger.error(f"Error parsing article path: {str(e)}")
            return None