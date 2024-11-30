from app import cache, db
from app.models import Category, Article

def make_cache_key(*args, **kwargs):
    """生成可读的缓存键"""
    return f"categories_count"  # 直接使用固定的描述性名称

@cache.cached(timeout=3600, key_prefix=make_cache_key)  # 使用 cached 替代 memoize
def get_categories_with_count():
    """获取所有分类及其文章数量"""
    categories = Category.query.all()
    result = []
    for category in categories:
        count = Article.query.filter_by(category_id=category.id).count()
        result.append((category, count))
    return result

@cache.cached(timeout=3600, key_prefix=make_cache_key)
def get_categories_data():
    """获取分类数据，返回字典格式"""
    categories = Category.query.all()
    article_counts = {}
    for category in categories:
        article_counts[category.id] = category.article_count
        
    return {
        'categories': categories,
        'article_counts': article_counts
    } 