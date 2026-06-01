from src.extention import db
from datetime import datetime

class Contractor(db.Model):
    __tablename__ = 'contractors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    workers = db.relationship('Worker', backref='contractor', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
        }
