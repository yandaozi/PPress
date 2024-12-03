from app.models import Category
from app.utils.cache_manager import cache_manager

def get_categories_data():
    """获取分类数据，返回字典格式"""
    # 使用 cache_manager 获取缓存
    cache_key = 'category:all_categories_data'
    
    def get_data():
        categories = Category.query.all()
        article_counts = {}
        for category in categories:
            article_counts[category.id] = category.article_count
        return {
            'categories': categories,
            'article_counts': article_counts
        }
    
    return cache_manager.get(
        cache_key,
        default_factory=get_data,
        ttl=3600  # 缓存1小时
    )

