from flask import current_app

from app.models import Category
from app.utils.cache_manager import cache_manager

def get_categories_data():
    """获取分类数据，返回字典格式"""
    cache_key = 'category:all_categories_data'
    
    def get_data():
        # 获取所有分类
        categories = Category.query.order_by(Category.sort_order).all()
        
        # 构建分类树
        category_map = {category.id: category for category in categories}
        tree = []
        
        # 统计文章数
        article_counts = {}
        for category in categories:
            # 计算包含子分类的总文章数
            total_count = category.article_count or 0  # 处理 None 值
            for child in category.get_descendants():
                total_count += child.article_count or 0  # 处理 None 值
            article_counts[category.id] = total_count
            
            # 构建树形结构
            if category.parent_id is None:
                tree.append(category)
            else:
                parent = category_map.get(category.parent_id)
                if parent:
                    if not hasattr(parent, '_children'):
                        parent._children = []
                    parent._children.append(category)

        
        return {
            'categories': tree,
            'article_counts': article_counts,
            'all_categories': categories
        }
    
    return cache_manager.get(
        cache_key,
        default_factory=get_data,
        ttl=3600  # 缓存1小时
    )

