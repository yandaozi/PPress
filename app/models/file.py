from app import db
from datetime import datetime

class File(db.Model):
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    md5 = db.Column(db.String(32), unique=True, nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.now)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    uploader = db.relationship(
        'User',
        foreign_keys=[uploader_id],
        backref=db.backref('uploaded_files', lazy=True, cascade='all, delete-orphan')
    )

    def __repr__(self):
        return f'<File {self.filename}>'

    @property
    def relative_path(self):
        """获取相对于static目录的路径"""
        static_index = self.file_path.find('static/')
        if static_index != -1:
            return self.file_path[static_index + 7:]  # 7 是 'static/' 的长度
        return self.file_path 