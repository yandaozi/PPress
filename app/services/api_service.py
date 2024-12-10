from app.models import Article, Category, Tag, SiteConfig

class ApiService:
    @staticmethod
    def format_article_list(articles):
        """格式化文章列表数据"""
        return {
            'total': articles.total,
            'pages': articles.pages,
            'current_page': articles.page,
            'articles': [{
                'id': article.id,
                'title': article.title,
                'content': article.content,
                'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'category': article.category.name if article.category else None,
                'author': article.author.nickname if article.author else None,
                'view_count': article.view_count,
                'tags': [tag.name for tag in article.tags]
            } for article in articles.items]
        }

    @staticmethod
    def format_article_detail(article):
        """格式化文章详情数据"""
        return {
            'id': article.id,
            'title': article.title,
            'content': article.content,
            'created_at': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'category': article.category.name if article.category else None,
            'author': article.author.nickname if article.author else None,
            'view_count': article.view_count,
            'tags': [tag.name for tag in article.tags]
        }

    @staticmethod
    def format_category_list(categories):
        """格式化分类列表数据"""
        return {
            'categories': [{
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'article_count': category.article_count,
                'parent_id': category.parent_id
            } for category in categories]
        }

    @staticmethod
    def check_api_access(request):
        """检查API访问权限
        Returns:
            tuple: (is_allowed, error_response)
        """
        # 检查是否启用API
        if SiteConfig.get_config('enable_api') != 'true':
            return False, {'error': 'API功能未启用'}, 403
            
        # 检查是否需要token
        if SiteConfig.get_config('api_token_required') == 'true':
            token = request.headers.get('X-API-Token')
            if not token or token != SiteConfig.get_config('api_token'):
                return False, {'error': '无效的API Token'}, 401
                
        return True, None, None 

    @staticmethod
    def format_category_detail(category):
        """格式化分类详情数据"""
        return {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'article_count': category.article_count,
            'parent_id': category.parent_id,
            'slug': category.slug,
            'sort_order': category.sort_order,
            'created_at': category.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': category.updated_at.strftime('%Y-%m-%d %H:%M:%S') if category.updated_at else None
        }

    @staticmethod
    def format_category_with_articles(category, articles_pagination):
        """格式化带文章列表的分类数据"""
        return {
            'category': ApiService.format_category_detail(category),
            'articles': ApiService.format_article_list(articles_pagination)
        }