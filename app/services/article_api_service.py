import json
import requests
import logging
from datetime import datetime
from app.models import Article as Post, User, Category
from app.extensions import db
from slugify import slugify
from app.services.admin_service import AdminService
from collections import defaultdict

# API 配置
API_URL = 'https://api.coze.cn/v1/workflow/run'
API_KEY = 'xxxx'
WORKFLOW_ID = 'xxx'

def fetch_and_save_articles(query="热门"):
    """获取文章内容并保存到数据库"""
    try:
        # 调用 API 获取文章
        articles = fetch_articles_from_api(query)
        
        # 保存文章到数据库
        saved_count = 0
        for article in articles:
            if save_article_to_db(article):
                saved_count += 1
            
        return True, f"成功获取并保存了 {saved_count} 篇文章"
    except Exception as e:
        logging.error(f"获取文章失败: {str(e)}")
        return False, str(e)

def fetch_articles_from_api(query="热门"):
    """从 API 获取文章内容"""
    # 准备请求头
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 准备请求体
    payload = {
        "parameters": {
            "input": query
        },
        "workflow_id": WORKFLOW_ID
    }
    
    # 发送请求
    response = requests.post(API_URL, headers=headers, json=payload)
    
    # 检查响应
    if response.status_code != 200:
        raise Exception(f"API 请求失败，状态码: {response.status_code}，响应内容: {response.text}")
    
    # 解析响应
    try:
        result = response.json()
        
        # 检查响应是否成功
        if result.get('code') != 0:
            raise Exception(f"API 返回错误，错误码: {result.get('code')}，错误信息: {result.get('msg')}")
        
        # 获取文章内容
        data = json.loads(result.get('data', '{}'))
        output = data.get('output', '')
        
        # 将返回的单篇文章内容转换为列表
        articles = [parse_article_content(output)]
        
        return articles
    except json.JSONDecodeError as e:
        raise Exception(f"解析 API 响应失败: {str(e)}")

def parse_article_content(content):
    """解析文章内容，提取标题和正文"""
    # 查找第一个 \n\n 的位置，前面的内容作为标题
    parts = content.split('\\n\\n', 1)
    
    title = parts[0].strip()
    body = content.replace(f"{title}\\n\\n", "").replace('\\n', '\n')
    print(title)
    
    return {
        'title': title,
        'content': body,
        'source': 'API自动获取'
    }

# 创建一个模拟表单数据的类
class DictToForm:
    def __init__(self, dict_data):
        self.data = dict_data
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def getlist(self, key):
        value = self.data.get(key)
        if value is None:
            return []
        if not isinstance(value, list):
            return [value]
        return value

def save_article_to_db(article_data):
    """将文章保存到数据库"""
    try:
        # 获取 admin 用户
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            logging.error("未找到 admin 用户，无法保存文章")
            return False
        
        # 创建文章 slug
        slug = slugify(article_data['title'])
        
        # 检查文章是否已存在
        existing_post = Post.query.filter_by(slug=slug).first()
        if existing_post:
            # 更新现有文章
            existing_post.title = article_data['title']
            existing_post.content = article_data['content']
            existing_post.updated_at = datetime.now()
        else:
            # 创建类似表单的数据对象
            # 获取默认分类
            default_category = Category.query.first()
            if not default_category:
                logging.error("未找到默认分类，无法保存文章")
                return False
                
            form_data = DictToForm({
                'title': article_data['title'],
                'content': article_data['content'],
                'status': 'public',
                'categories': [default_category.id],
                'tag_names': '',
                'allow_comment': 'on',
                'created_at': datetime.now().strftime('%Y-%m-%dT%H:%M'),
                'slug': slug
            })
            
            # 调用 AdminService 保存文章
            success, message, new_post = AdminService.save_article(None, form_data)
            if not success:
                logging.error(f"通过AdminService保存文章失败: {message}")
                return False
                
            return True
        
        # 提交现有文章的变更
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logging.error(f"保存文章到数据库失败: {str(e)}")
        raise e 