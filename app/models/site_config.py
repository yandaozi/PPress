from ..extensions import db

class SiteConfig(db.Model):
    __tablename__ = 'site_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    
    @staticmethod
    def get_config(key, default=None):
        config = SiteConfig.query.filter_by(key=key).first()
        return config.value if config else default 