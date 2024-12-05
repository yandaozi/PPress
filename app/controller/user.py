from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user

from app.models import User
from app.services.user_service import UserService
from app.utils.common import get_categories_data

bp = Blueprint('user', __name__, url_prefix='/user')

@bp.route('/profile')
@login_required
def profile():
    """用户资料页"""
    page = request.args.get('page', 1, type=int)
    return render_template('user/profile.html',
                         view_history=UserService.get_view_history(current_user.id, page),
                         user_articles=UserService.get_user_articles(current_user.id),
                         **get_categories_data())

@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """编辑个人资料"""
    if request.method == 'POST':
        data = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'confirm_password': request.form.get('confirm_password'),
            'nickname': request.form.get('nickname'),
        }
        
        success, message = UserService.update_profile(
            current_user.id,
            data,
            request.files.get('avatar')
        )
        flash(message)
        if success:
            return redirect(url_for('user.profile'))
            
    return render_template('user/edit_profile.html',
                         **get_categories_data())

@bp.route('/my-articles')
@login_required
def my_articles():
    """我的文章"""
    page = request.args.get('page', 1, type=int)
    return render_template('user/my_articles.html',
                         articles=UserService.get_user_articles(
                             current_user.id,
                             page
                         ),
                         **get_categories_data())

@bp.route('/author/<int:id>')
def author(id):
    """作者主页"""
    page = request.args.get('page', 1, type=int)
    return render_template('user/author.html',
                         author=User.query.get_or_404(id),
                         articles=UserService.get_user_articles(id, page),
                         stats=UserService.get_user_stats(id),
                         **get_categories_data())

@bp.route('/history/<int:history_id>', methods=['DELETE'])
@login_required
def delete_history(history_id):
    """删除浏览历史"""
    success, message = UserService.delete_history(history_id, current_user.id)
    if not success:
        return jsonify({'error': message}), 403
    return '', 204

@bp.route('/history/all', methods=['DELETE'])
@login_required
def delete_all_history():
    """删除所有浏览历史"""
    success, message = UserService.delete_history(user_id=current_user.id)
    if not success:
        return jsonify({'error': message}), 403
    return '', 204
