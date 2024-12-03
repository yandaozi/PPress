from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response, session
from flask_login import logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.utils.captcha import generate_captcha
from app.utils.common import get_categories_data

bp = Blueprint('auth', __name__)

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
        success, message = AuthService.register(
            request.form.get('username'),
            request.form.get('email'),
            request.form.get('password'),
            request.form.get('confirm_password'),
            request.form.get('captcha')
        )
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