import os

# MySQL 配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'flaskiosblog',
    'password': 'flaskiosblog',
    'database': 'flaskiosblog',
    'charset': 'utf8mb4'
}

# 获取项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# SQLite 配置
SQLITE_CONFIG = {
    'path': os.path.join(BASE_DIR, 'instance'),
    'database': 'ppress.db'
}

def get_db_url(db_type='mysql'):
    """获取数据库 URL"""
    if db_type == 'mysql':
        return (f"mysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}"
                f"@{MYSQL_CONFIG['host']}/{MYSQL_CONFIG['database']}?"
                f"charset={MYSQL_CONFIG['charset']}")
    else:
        # 确保 SQLite 数据库目录存在
        os.makedirs(SQLITE_CONFIG['path'], exist_ok=True)
        db_path = os.path.join(SQLITE_CONFIG['path'], SQLITE_CONFIG['database'])
        return f"sqlite:///{db_path}" 