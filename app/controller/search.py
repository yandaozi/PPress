from flask import Blueprint, render_template, request, jsonify
from app.services.search_service import search_posts, create_indices
from app.utils.common import get_categories_data

bp = Blueprint('search', __name__)

@bp.route('/search')
def search():
    """搜索页面"""
    # 获取搜索参数
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    category = request.args.get('category')
    tag = request.args.get('tag')
    author = request.args.get('author')
    
    # 构建过滤条件
    filters = {}
    if category:
        filters['category'] = int(category)
    if tag:
        filters['tag'] = int(tag)
    if author:
        filters['author'] = int(author)
    
    # 执行搜索
    results = {}
    if query:
        results = search_posts(query, page, 10, filters)
    
    # 渲染模板
    return render_template(
        'search.html',
        query=query,
        results=results,
        **get_categories_data()
    )

@bp.route('/api/search')
def api_search():
    """搜索 API"""
    # 获取搜索参数
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    category = request.args.get('category')
    tag = request.args.get('tag')
    author = request.args.get('author')
    
    # 构建过滤条件
    filters = {}
    if category:
        filters['category'] = int(category)
    if tag:
        filters['tag'] = int(tag)
    if author:
        filters['author'] = int(author)
    
    # 执行搜索
    if not query:
        return jsonify({'success': False, 'message': '请提供搜索关键词'})
    
    results = search_posts(query, page, limit, filters)
    return jsonify({'success': True, 'data': results})

@bp.route('/api/init_search')
def init_search():
    """初始化搜索索引"""
    success = create_indices()
    if success:
        return jsonify({'success': True, 'message': '搜索索引初始化成功'})
    return jsonify({'success': False, 'message': '搜索索引初始化失败'}) 