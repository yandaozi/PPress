import os
import shutil
import re
from flask import current_app

class Installer:
    @staticmethod
    def update_db_config(config):
        """更新数据库配置文件"""
        try:
            config_path = os.path.join(current_app.root_path, '..', 'config', 'database.py')
            
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新数据库类型
            content = re.sub(
                r'DB_TYPE\s*=\s*["\'].*["\']',
                f'DB_TYPE = "{config["db_type"]}"',
                content
            )
            
            # 如果是 MySQL,更新 MySQL 配置
            if config['db_type'] == 'mysql':
                mysql_config = {
                    'host': config['mysql_host'],
                    'port': config['mysql_port'],
                    'database': config['mysql_database'],
                    'user': config['mysql_user'],
                    'password': config['mysql_password'],
                    'charset': 'utf8mb4'
                }
                
                # 更新 MySQL 配置
                mysql_config_str = "MYSQL_CONFIG = {\n"
                for key, value in mysql_config.items():
                    if key == 'port':
                        mysql_config_str += f"    '{key}': {value},\n"
                    else:
                        mysql_config_str += f"    '{key}': '{value}',\n"
                mysql_config_str += "}"
                
                content = re.sub(
                    r'MYSQL_CONFIG\s*=\s*{[^}]+}',
                    mysql_config_str,
                    content
                )
            
            # 写入更新后的配置
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True, None
            
        except Exception as e:
            current_app.logger.error(f"Error updating database config: {str(e)}")
            return False, str(e)

    @staticmethod
    def cleanup_installer():
        """清理安装文件"""
        try:
            # 获取installer目录路径
            installer_dir = os.path.join(current_app.root_path, 'installer')
            
            # 删除installer目录
            if os.path.exists(installer_dir):
                shutil.rmtree(installer_dir)
            
            # 修改 __init__.py,删除安装检测代码
            init_file = os.path.join(current_app.root_path, '__init__.py')
            if os.path.exists(init_file):
                with open(init_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 删除安装相关代码
                content = re.sub(
                    r'from .installer import init_installer.*?init_installer\(app\)',
                    '',
                    content,
                    flags=re.DOTALL
                )
                
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
            return True, None
            
        except Exception as e:
            current_app.logger.error(f"Error cleaning up installer: {str(e)}")
            return False, str(e) 