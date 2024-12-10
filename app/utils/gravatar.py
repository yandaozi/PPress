import hashlib

class Gravatar:
    @staticmethod
    def get_url(email, size=100):
        """获取Gravatar头像URL
        Args:
            email: 用户邮箱
            size: 头像大小
        """
        # 延迟导入避免循环引用
        from app.models import SiteConfig
        
        # 获取镜像地址
        base_url = SiteConfig.get_config('gravatar_mirror', 'https://gravatar.com/avatar/')
        default = SiteConfig.get_config('gravatar_default', 'mp')
        
        # 如果邮箱为空,返回默认头像
        if not email:
            return f"{base_url}?d={default}&s={size}"
            
        # 计算邮箱的MD5值
        email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
        
        # 构建完整URL
        return f"{base_url}{email_hash}?d={default}&s={size}" 