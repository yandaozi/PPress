import redis
import json
from datetime import datetime
from config.database import REDIS_CONFIG

# Redis 客户端
redis_client = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    password=REDIS_CONFIG['password'],
    db=REDIS_CONFIG['db'],
    decode_responses=True
)

# 缓存键值常量
POST_VIEW_COUNT_KEY = 'post:view_count'  # Hash结构: post_id -> view_count
HOT_POSTS_KEY = 'hot:posts'  # Sorted Set结构: post_id -> score(view_count)
RECENT_COMMENTS_KEY = 'recent:comments'  # List结构，最新评论
TAG_CLOUD_KEY = 'tag:cloud'  # Sorted Set结构: tag_name -> 使用次数
CACHE_TIMEOUT = 60 * 60 * 24  # 24小时

def increment_post_view(post_id):
    """增加文章浏览量"""
    # 增加永久计数
    redis_client.hincrby(POST_VIEW_COUNT_KEY, post_id, 1)
    
    # 增加热门文章排行榜分数
    redis_client.zincrby(HOT_POSTS_KEY, 1, post_id)
    
    # 获取当前浏览量
    return int(redis_client.hget(POST_VIEW_COUNT_KEY, post_id) or 0)

def get_post_view_count(post_id):
    """获取文章浏览量"""
    count = redis_client.hget(POST_VIEW_COUNT_KEY, post_id)
    return int(count) if count else 0

def get_hot_posts(limit=10):
    """获取热门文章ID列表"""
    return redis_client.zrevrange(HOT_POSTS_KEY, 0, limit-1, withscores=True)

def add_recent_comment(comment_data):
    """添加最新评论"""
    redis_client.lpush(RECENT_COMMENTS_KEY, json.dumps(comment_data))
    redis_client.ltrim(RECENT_COMMENTS_KEY, 0, 19)  # 保留最新的20条

def get_recent_comments(limit=10):
    """获取最新评论"""
    comments = []
    data = redis_client.lrange(RECENT_COMMENTS_KEY, 0, limit-1)
    for item in data:
        comments.append(json.loads(item))
    return comments

def increment_tag_usage(tag_name):
    """增加标签使用次数"""
    redis_client.zincrby(TAG_CLOUD_KEY, 1, tag_name)

def get_tag_cloud(limit=30):
    """获取标签云数据"""
    return redis_client.zrevrange(TAG_CLOUD_KEY, 0, limit-1, withscores=True)

def cache_object(key, obj, expire=CACHE_TIMEOUT):
    """缓存任意对象"""
    redis_client.setex(f'cache:{key}', expire, json.dumps(obj))

def get_cached_object(key):
    """获取缓存的对象"""
    data = redis_client.get(f'cache:{key}')
    if data:
        return json.loads(data)
    return None

def delete_cache(key):
    """删除缓存"""
    redis_client.delete(f'cache:{key}')

def clear_cache_by_pattern(pattern):
    """清除匹配模式的所有缓存"""
    for key in redis_client.scan_iter(f'cache:{pattern}*'):
        redis_client.delete(key) 