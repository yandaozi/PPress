from flask import request, session
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room, Namespace
import redis
import json
from datetime import datetime
from . import socketio
from config.database import REDIS_CONFIG

# Redis 客户端
redis_client = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    password=REDIS_CONFIG['password'],
    db=REDIS_CONFIG['db'],
    decode_responses=True
)

# 最大聊天记录保存数量
MAX_CHAT_HISTORY = 100
# 聊天室 Redis Key
CHAT_HISTORY_KEY = 'chat:history'
# 在线用户 Redis Key
ONLINE_USERS_KEY = 'chat:online_users'

# 聊天室 WebSocket 命名空间
class ChatNamespace(Namespace):
    def on_connect(self):
        """处理连接"""
        user_id = current_user.id if current_user.is_authenticated else None
        username = current_user.username if current_user.is_authenticated else f'游客_{request.sid[:6]}'
        
        # 加入聊天室
        join_room('chat_room')
        
        # 记录在线用户
        if user_id:
            redis_client.hset(ONLINE_USERS_KEY, request.sid, json.dumps({
                'user_id': user_id,
                'username': username,
                'connected_at': datetime.now().isoformat()
            }))
        else:
            redis_client.hset(ONLINE_USERS_KEY, request.sid, json.dumps({
                'username': username,
                'connected_at': datetime.now().isoformat()
            }))
        
        # 获取在线用户列表
        online_users = self.get_online_users()
        emit('user_list', online_users, to='chat_room')
        
        # 发送系统消息
        system_message = {
            'type': 'system',
            'content': f'{username} 加入聊天室',
            'timestamp': datetime.now().isoformat()
        }
        emit('message', system_message, to='chat_room')
        
        # 获取历史消息
        history = self.get_chat_history()
        emit('chat_history', history)

    def on_disconnect(self):
        """处理断开连接"""
        user_data = json.loads(redis_client.hget(ONLINE_USERS_KEY, request.sid) or '{}')
        username = user_data.get('username', f'游客_{request.sid[:6]}')
        
        # 移除在线用户
        redis_client.hdel(ONLINE_USERS_KEY, request.sid)
        
        # 发送系统消息
        system_message = {
            'type': 'system',
            'content': f'{username} 离开聊天室',
            'timestamp': datetime.now().isoformat()
        }
        emit('message', system_message, to='chat_room')
        
        # 更新在线用户列表
        online_users = self.get_online_users()
        emit('user_list', online_users, to='chat_room')
        
        # 离开聊天室
        leave_room('chat_room')

    def on_send_message(self, data):
        """处理发送消息"""
        content = data.get('content', '').strip()
        if not content:
            return
        
        if current_user.is_authenticated:
            username = current_user.username
            user_id = current_user.id
        else:
            username = f'游客_{request.sid[:6]}'
            user_id = None
        
        # 创建消息
        message = {
            'user_id': user_id,
            'username': username,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'type': 'user'
        }
        
        # 存储消息历史
        self.save_message(message)
        
        # 广播消息
        emit('message', message, to='chat_room')

    def get_online_users(self):
        """获取在线用户列表"""
        users = []
        for user_data in redis_client.hvals(ONLINE_USERS_KEY):
            users.append(json.loads(user_data))
        return users

    def save_message(self, message):
        """保存消息到历史记录"""
        # 使用列表存储历史记录，限制数量
        redis_client.lpush(CHAT_HISTORY_KEY, json.dumps(message))
        redis_client.ltrim(CHAT_HISTORY_KEY, 0, MAX_CHAT_HISTORY - 1)

    def get_chat_history(self, limit=50):
        """获取聊天历史记录"""
        history = []
        messages = redis_client.lrange(CHAT_HISTORY_KEY, 0, limit - 1)
        for msg in messages:
            history.append(json.loads(msg))
        return history[::-1]  # 逆序返回，最新的消息在最后

# 注册聊天室命名空间
socketio.on_namespace(ChatNamespace('/chat')) 