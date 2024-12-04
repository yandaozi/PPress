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
        
        # 调试输出
        print("Debug - All categories:", [c.name for c in categories])
        
        # 统计文章数和构建树
        article_counts = {}
        for category in categories:
            # 计算包含子分类的总文章数
            total_count = category.article_count
            for child in category.get_descendants():
                total_count += child.article_count
            article_counts[category.id] = total_count
            
            # 构建树形结构
            if category.parent_id is None:
                tree.append(category)
                print(f"Debug - Added root category: {category.name}")
            else:
                parent = category_map.get(category.parent_id)
                if parent:
                    if not hasattr(parent, '_children'):
                        parent._children = []
                        print(f"Debug - Created _children list for: {parent.name}")
                    parent._children.append(category)
                    print(f"Debug - Added {category.name} as child of {parent.name}")
        
        # 最终调试输出
        print("Debug - Tree structure:", [(c.name, getattr(c, '_children', [])) for c in tree])
        
        return {
            'categories': tree,
            'article_counts': article_counts,
            'all_categories': categories,
            'debug_info': {
                'tree_structure': [(c.name, [child.name for child in getattr(c, '_children', [])]) for c in tree],
                'article_counts': article_counts
            }
        }
    
    return cache_manager.get(
        cache_key,
        default_factory=get_data,
        ttl=3600  # 缓存1小时
    )

