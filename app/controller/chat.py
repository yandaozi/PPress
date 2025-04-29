from flask import Blueprint, render_template
from app.utils.common import get_categories_data

bp = Blueprint('chat', __name__)

@bp.route('/chat')
def chat():
    """聊天室页面"""
    return render_template('chat.html', **get_categories_data()) 