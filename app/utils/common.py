from app.models import Category
from app.utils.cache_manager import cache_manager

def get_categories_data():
    """获取分类数据，返回字典格式"""
    cache_key = 'category:all_categories_data'

    # 打印调用栈，看看是谁在调用这个函数
    # for frame in inspect.stack()[1:]:
    #     print(f"Called from {frame.filename}:{frame.lineno}")

    def get_data():
        #print("get_data() 被调用")  # 添加调试信息
        # 获取所有分类
        categories = Category.query.order_by(Category.sort_order).all()

        # 构建分类树
        tree = []

        # 统计文章数
        article_counts = {}
        for category in categories:
            # 计算包含子分类的总文章数
            total_count = category.article_count or 0  # 处理 None 值
            for child in category.get_descendants():
                total_count += child.article_count or 0  # 处理 None 值
            article_counts[category.id] = total_count

            # 重新构建树形结构
            if category.parent_id is None:
                # 只添加顶级分类到树中
                tree.append(category)
                # 清理并重新添加子分类
                category._children = []
                # 只添加直接子分类
                for child in categories:
                    if child.parent_id == category.id:
                        category._children.append(child)
        #print(f"树形结构构建完成，顶级分类数量: {len(tree)}")  # 更有意义的调试信息
        return {
            'categories': tree,
            'article_counts': article_counts,
            'all_categories': categories
        }

    #print(f"缓存键: {cache_key}")  # 添加缓存键调试信息
    return cache_manager.get(
        cache_key,
        default_factory=get_data,
        ttl=3600  # 缓存1小时
    )

