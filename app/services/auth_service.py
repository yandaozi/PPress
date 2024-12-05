from datetime import datetime

from app.models import User
from flask_login import login_user
from flask import session, current_app
from app import db

class AuthService:
    @staticmethod
    def verify_captcha(captcha):
        """验证码校验"""
        stored_captcha = session.pop('captcha', '').lower()
        if not stored_captcha or stored_captcha != captcha.lower():
            return False, '验证码错误'
        return True, None

    @staticmethod
    def login(username, password, captcha):
        """用户登录"""
        try:
            # 验证码检查
            success, message = AuthService.verify_captcha(captcha)
            if not success:
                return False, message
            
            # 查询用户
            user = User.query.filter_by(username=username).first()
            if not user or not user.check_password(password):
                return False, '用户名或密码错误'
            
            # 登录用户
            login_user(user)
            user.last_login = datetime.now()  # 更新最后登录时间
            db.session.commit()
            return True, '登录成功'
            
        except Exception as e:
            current_app.logger.error(f"Login error: {str(e)}")
            return False, '登录失败，请稍后重试'
    
    @staticmethod
    def register(username, email, password, confirm_password, captcha):
        """用户注册"""
        try:
            # 验证码检查
            success, message = AuthService.verify_captcha(captcha)
            if not success:
                return False, message
            
            # 密码确认
            if password != confirm_password:
                return False, '两次输入的密码不一致'
            
            # 检查用户名
            if User.query.filter_by(username=username).first():
                return False, '用户名已存在'
            
            # 检查邮箱
            if User.query.filter_by(email=email).first():
                return False, '邮箱已被注册'
            
            # 创建新用户
            user = User(username=username, email=email, nickname=f"昵称_{username}")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            return True, '注册成功'
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Register error: {str(e)}")
            return False, '注册失败，请稍后重试' 