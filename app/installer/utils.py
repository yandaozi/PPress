import os
import shutil
from flask import current_app

class Installer:
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
                import re
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
            return False, str(e) 