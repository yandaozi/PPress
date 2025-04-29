from flask_socketio import SocketIO

# 创建 SocketIO 实例，自动检测最佳模式
socketio = SocketIO(
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

def init_socketio(app):
    """初始化 SocketIO"""
    socketio.init_app(app)
    
    # 导入 WebSocket 处理模块
    from . import chat
    
    return socketio 