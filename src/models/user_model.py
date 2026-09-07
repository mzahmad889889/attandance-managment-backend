from src.extention import db
from datetime import datetime
from src.apptime import now as app_now, today as app_today

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'manager'), nullable=False, default='manager')
    name = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=app_now)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
