from elasticsearch import Elasticsearch
import logging

# Elasticsearch 客户端
es_client = Elasticsearch("http://192.168.153.130:9200")

# 索引名称
POST_INDEX = 'ppress_posts'
COMMENT_INDEX = 'ppress_comments'

def create_indices():
    """创建必要的索引"""
    try:
        # 创建文章索引
        if not es_client.indices.exists(index=POST_INDEX):
            es_client.indices.create(
                index=POST_INDEX,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "analysis": {
                            "analyzer": {
                                "text_analyzer": {
                                    "type": "custom",
                                    "tokenizer": "standard",
                                    "filter": ["lowercase", "stop", "snowball"]
                                }
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {
                                "type": "text",
                                "analyzer": "text_analyzer",
                                "fields": {
                                    "keyword": {"type": "keyword"}
                                }
                            },
                            "content": {"type": "text", "analyzer": "text_analyzer"},
                            "summary": {"type": "text", "analyzer": "text_analyzer"},
                            "author": {
                                "properties": {
                                    "id": {"type": "integer"},
                                    "username": {"type": "keyword"}
                                }
                            },
                            "category": {
                                "properties": {
                                    "id": {"type": "integer"},
                                    "name": {"type": "keyword"}
                                }
                            },
                            "tags": {
                                "type": "nested",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "name": {"type": "keyword"}
                                }
                            },
                            "created_at": {"type": "date"},
                            "updated_at": {"type": "date"},
                            "published": {"type": "boolean"}
                        }
                    }
                }
            )
            
        # 创建评论索引
        if not es_client.indices.exists(index=COMMENT_INDEX):
            es_client.indices.create(
                index=COMMENT_INDEX,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    },
                    "mappings": {
                        "properties": {
                            "id": {"type": "integer"},
                            "content": {"type": "text", "analyzer": "standard"},
                            "author": {
                                "properties": {
                                    "id": {"type": "integer"},
                                    "username": {"type": "keyword"}
                                }
                            },
                            "post_id": {"type": "integer"},
                            "post_title": {"type": "keyword"},
                            "created_at": {"type": "date"}
                        }
                    }
                }
            )
        return True
    except Exception as e:
        logging.error(f"创建索引失败: {e}")
        return False

def index_post(post):
    """索引单篇文章"""
    try:
        # 准备文章数据
        post_data = {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "summary": post.summary if hasattr(post, 'summary') else '',
            "author": {
                "id": post.author_id,
                "username": post.author.username if hasattr(post, 'author') else ''
            },
            "category": {
                "id": post.category_id if hasattr(post, 'category_id') else None,
                "name": post.category.name if hasattr(post, 'category') and post.category else ''
            },
            "tags": [{"id": tag.id, "name": tag.name} for tag in post.tags] if hasattr(post, 'tags') else [],
            "created_at": post.created_at.isoformat() if hasattr(post, 'created_at') else None,
            "updated_at": post.updated_at.isoformat() if hasattr(post, 'updated_at') else None,
            "published": post.published if hasattr(post, 'published') else True
        }
        
        # 索引文章
        es_client.index(index=POST_INDEX, id=post.id, body=post_data)
        return True
    except Exception as e:
        logging.error(f"索引文章失败 [ID={post.id}]: {e}")
        return False

def index_posts(posts):
    """批量索引文章"""
    try:
        if not posts:
            return True
            
        # 准备批量操作
        bulk_data = []
        for post in posts:
            # 索引操作的元数据
            bulk_data.append({"index": {"_index": POST_INDEX, "_id": post.id}})
            
            # 索引的文档数据
            post_data = {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "summary": post.summary if hasattr(post, 'summary') else '',
                "author": {
                    "id": post.author_id,
                    "username": post.author.username if hasattr(post, 'author') else ''
                },
                "category": {
                    "id": post.category_id if hasattr(post, 'category_id') else None,
                    "name": post.category.name if hasattr(post, 'category') and post.category else ''
                },
                "tags": [{"id": tag.id, "name": tag.name} for tag in post.tags] if hasattr(post, 'tags') else [],
                "created_at": post.created_at.isoformat() if hasattr(post, 'created_at') else None,
                "updated_at": post.updated_at.isoformat() if hasattr(post, 'updated_at') else None,
                "published": post.published if hasattr(post, 'published') else True
            }
            bulk_data.append(post_data)
        
        # 执行批量操作
        if bulk_data:
            es_client.bulk(body=bulk_data)
        return True
    except Exception as e:
        logging.error(f"批量索引文章失败: {e}")
        return False

def update_post(post):
    """更新已索引的文章"""
    try:
        # 准备更新文档
        doc = {
            "title": post.title,
            "content": post.content,
            "summary": post.summary if hasattr(post, 'summary') else '',
            "category": {
                "id": post.category_id if hasattr(post, 'category_id') else None,
                "name": post.category.name if hasattr(post, 'category') and post.category else ''
            },
            "tags": [{"id": tag.id, "name": tag.name} for tag in post.tags] if hasattr(post, 'tags') else [],
            "updated_at": post.updated_at.isoformat() if hasattr(post, 'updated_at') else None,
            "published": post.published if hasattr(post, 'published') else True
        }
        
        # 更新文档
        es_client.update(index=POST_INDEX, id=post.id, body={"doc": doc})
        return True
    except Exception as e:
        logging.error(f"更新文章索引失败 [ID={post.id}]: {e}")
        # 如果文档不存在，重新创建索引
        try:
            return index_post(post)
        except:
            return False

def delete_post(post_id):
    """删除文章索引"""
    try:
        es_client.delete(index=POST_INDEX, id=post_id)
        return True
    except Exception as e:
        logging.error(f"删除文章索引失败 [ID={post_id}]: {e}")
        return False

def search_posts(query, page=1, limit=10, filters=None):
    """搜索文章"""
    try:
        start = (page - 1) * limit
        
        # 构建查询体
        search_body = {
            "from": start,
            "size": limit,
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^3", "content", "summary^2", "tags.name^2"],
                            "type": "best_fields"
                        }
                    },
                    "filter": [
                        {"term": {"published": True}}
                    ]
                }
            },
            "highlight": {
                "fields": {
                    "title": {"number_of_fragments": 0},
                    "content": {"number_of_fragments": 3, "fragment_size": 150},
                    "summary": {"number_of_fragments": 1, "fragment_size": 150}
                },
                "pre_tags": ["<em class='highlight'>"],
                "post_tags": ["</em>"]
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"created_at": {"order": "desc"}}
            ]
        }
        
        # 添加过滤条件
        if filters:
            if 'category' in filters and filters['category']:
                search_body["query"]["bool"]["filter"].append({
                    "term": {"category.id": filters['category']}
                })
            if 'tag' in filters and filters['tag']:
                search_body["query"]["bool"]["filter"].append({
                    "nested": {
                        "path": "tags",
                        "query": {
                            "term": {"tags.id": filters['tag']}
                        }
                    }
                })
            if 'author' in filters and filters['author']:
                search_body["query"]["bool"]["filter"].append({
                    "term": {"author.id": filters['author']}
                })
        
        # 执行搜索
        result = es_client.search(index=POST_INDEX, body=search_body)
        
        # 处理结果
        total = result['hits']['total']['value']
        posts = []
        
        for hit in result['hits']['hits']:
            post_data = hit['_source']
            
            # 处理高亮
            highlight = {}
            if 'highlight' in hit:
                highlight = hit['highlight']
            
            posts.append({
                'id': post_data['id'],
                'title': highlight.get('title', [post_data['title']])[0] if 'title' in highlight else post_data['title'],
                'content': highlight.get('content', []) if 'content' in highlight else [],
                'summary': highlight.get('summary', [post_data.get('summary', '')])[0] if 'summary' in highlight else post_data.get('summary', ''),
                'author': post_data['author'],
                'category': post_data['category'],
                'created_at': post_data['created_at'],
                'score': hit['_score']
            })
        
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'pages': (total + limit - 1) // limit,
            'posts': posts
        }
    except Exception as e:
        logging.error(f"搜索文章失败: {e}")
        return {
            'total': 0,
            'page': page,
            'limit': limit,
            'pages': 0,
            'posts': []
        } 