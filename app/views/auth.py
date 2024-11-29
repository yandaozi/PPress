from flask import Blueprint, render_template, request, flash, redirect, url_for, session, make_response
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app.utils.captcha import generate_captcha
from app import db
import io

bp = Blueprint('auth', __name__)

@bp.route('/captcha')
def captcha():
    image_io, text = generate_captcha()
    # 将验证码文本存入session
    session['captcha'] = text
    # 返回图片
    response = make_response(image_io.getvalue())
    response.headers['Content-Type'] = 'image/png'
    return response

@bp.route('/login', methods=['GET', 'POST'])
def login():
    # 如果用户已登录，重定向到首页
    if current_user.is_authenticated:
        return redirect(url_for('blog.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha = request.form['captcha']
        
        if captcha.lower() != session.get('captcha', '').lower():
            flash('验证码错误')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('blog.index'))
        flash('用户名或密码错误')
    
    return render_template('auth/login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    # 如果用户已登录，重定向到首页
    if current_user.is_authenticated:
        return redirect(url_for('blog.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password2 = request.form['confirm_password']
        email = request.form['email']
        captcha = request.form['captcha']
        
        if captcha.lower() != session.get('captcha', '').lower():
            flash('验证码错误')
            return redirect(url_for('auth.register'))
        
        if password != password2:
            flash('两次输入的密码不一致')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册')
            return redirect(url_for('auth.register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功！请登录')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('blog.index'))