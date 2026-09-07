from src.extention import db
from datetime import datetime
from src.apptime import now as app_now, today as app_today

class Plant(db.Model):
    __tablename__ = 'plants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    location = db.Column(db.String(200))
    capacity = db.Column(db.Integer, default=90)
    created_at = db.Column(db.DateTime, default=app_now)

    workers = db.relationship('Worker', backref='plant', lazy=True)

    def to_dict(self, include_count=True):
        d = {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'capacity': self.capacity,
        }
        if include_count:
            from src.models.worker_model import Worker
            d['total_workers'] = Worker.query.filter_by(plant_id=self.id).count()
        return d
