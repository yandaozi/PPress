from app import db
from datetime import datetime

class Plugin(db.Model):
    __tablename__ = 'plugins'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # 插件名称
    directory = db.Column(db.String(100), unique=True, nullable=False)  # 插件目录名
    description = db.Column(db.Text)  # 插件描述
    version = db.Column(db.String(20))  # 版本号
    author = db.Column(db.String(50))  # 作者
    author_url = db.Column(db.String(200))  # 作者网址
    enabled = db.Column(db.Boolean, default=True)  # 是否启用
    installed_at = db.Column(db.DateTime, default=datetime.now)  # 安装时间
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)  # 更新时间
    config = db.Column(db.JSON)  # 插件配置(JSON格式)

    def __repr__(self):
        return f'<Plugin {self.name}>'

    @staticmethod
    def add_plugin(plugin_info, directory, enabled=True, config=None):
        """添加插件记录"""
        plugin = Plugin(
            name=plugin_info['name'],
            directory=directory,
            description=plugin_info.get('description', ''),
            version=plugin_info.get('version', '1.0.0'),
            author=plugin_info.get('author', ''),
            author_url=plugin_info.get('author_url', ''),
            enabled=enabled,  # 使用传入的 enabled 参数
            config=config or {}
        )
        db.session.add(plugin)
        db.session.commit()
        return plugin

    @staticmethod
    def remove_plugin(name):
        """删除插件记录"""
        plugin = Plugin.query.filter_by(name=name).first()
        if plugin:
            db.session.delete(plugin)
            db.session.commit()
            return True
        return False

    def update_config(self, config):
        """更新插件配置"""
        self.config = config
        self.updated_at = datetime.now()
        db.session.commit()