from app import db


class CommentConfig(db.Model):
    __tablename__ = 'comment_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    require_audit = db.Column(db.Boolean, default=False)  # 是否需要审核
    require_email = db.Column(db.Boolean, default=False)  # 是否必须填写邮箱
    require_contact = db.Column(db.Boolean, default=False)  # 是否必须填写联系方式
    allow_guest = db.Column(db.Boolean, default=True)  # 是否允许游客评论
    comments_per_page = db.Column(db.Integer, default=10)  # 每页显示评论数
    
    @classmethod
    def get_config(cls):
        """获取评论配置,如果不存在则创建默认配置"""
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config 