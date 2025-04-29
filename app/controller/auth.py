from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response, session, jsonify
from flask_login import logout_user, login_required, current_user

from app.models import User
from app.services.auth_service import AuthService
from app.utils.captcha import generate_captcha
from app.utils.common import get_categories_data
import redis
import random
import smtplib
from email.mime.text import MIMEText
from config.database import REDIS_CONFIG, SMTP_CONFIG

bp = Blueprint('auth', __name__)

# 创建 Redis 连接
redis_client = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    password=REDIS_CONFIG['password'],
    db=REDIS_CONFIG['db'],
    decode_responses=True
)

def send_email(to_email, code):
    """发送验证码邮件"""
    try:
        msg = MIMEText(f'您的注册验证码是：{code}，5分钟内有效。', 'plain', 'utf-8')
        msg['Subject'] = 'PPress注册验证码'
        msg['From'] = SMTP_CONFIG['username']
        msg['To'] = to_email

        server = smtplib.SMTP(SMTP_CONFIG['host'], SMTP_CONFIG['port'])
        server.starttls()
        server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"发送邮件失败: {str(e)}")
        return False

@bp.route('/auth/send_email_code', methods=['POST'])
def send_email_code():
    """发送邮箱验证码"""
    data = request.get_json()
    email = data.get('email')

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': '邮箱已被注册'})

    if not email:
        return jsonify({'success': False, 'message': '请提供邮箱地址'})
    
    # 生成6位验证码
    code = ''.join(random.choices('0123456789', k=6))
    
    # 将验证码存储到Redis，设置5分钟过期
    redis_key = f'email_code:{email}'
    redis_client.setex(redis_key, 300, code)
    
    # 发送验证码邮件
    if send_email(email, code):
        return jsonify({'success': True, 'message': '验证码已发送'})
    return jsonify({'success': False, 'message': '验证码发送失败'})

@bp.route('/captcha')
def captcha():
    """生成验证码"""
    image_io, text = generate_captcha()
    session['captcha'] = text
    response = make_response(image_io.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('blog.index'))
        
    if request.method == 'POST':
        success, message = AuthService.login(
            request.form.get('username'),
            request.form.get('password'),
            request.form.get('captcha')
        )
        flash(message)
        if success:
            return redirect(url_for('blog.index'))
            
    return render_template('auth/login.html',
                         **get_categories_data())

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('blog.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        email_code = request.form.get('email_code')
        
        # 验证邮箱验证码
        redis_key = f'email_code:{email}'
        stored_code = redis_client.get(redis_key)
        
        if not stored_code or stored_code != email_code:
            flash('邮箱验证码错误或已过期')
            return render_template('auth/register.html', **get_categories_data())
            
        success, message = AuthService.register(
            request.form.get('username'),
            email,
            request.form.get('password'),
            request.form.get('confirm_password'),
            request.form.get('captcha')
        )
        
        if success:
            # 删除已使用的验证码
            redis_client.delete(redis_key)
            
        flash(message)
        if success:
            return redirect(url_for('auth.login'))
            
    return render_template('auth/register.html',
                         **get_categories_data())

@bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    return redirect(url_for('blog.index'))