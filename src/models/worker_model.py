from src.extention import db
from datetime import datetime
import json

class Worker(db.Model):
    __tablename__ = 'workers'
    id = db.Column(db.Integer, primary_key=True)
    worker_code = db.Column(db.String(20), unique=True, nullable=False)  # e.g. W0001
    name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer)
    cnic = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    photo_path = db.Column(db.String(500))  # stored image path
    face_embedding = db.Column(db.Text)      # JSON-encoded list of floats

    # Shift info: Day/Night/Rest cycle
    shift_type = db.Column(db.Enum('Day', 'Night', 'Rest'), default='Day')
    shift_start_date = db.Column(db.Date)   # when current shift cycle started

    plant_id = db.Column(db.Integer, db.ForeignKey('plants.id'), nullable=False)
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendance = db.relationship('AttendanceRecord', backref='worker', lazy=True)

    def get_embedding(self):
        if self.face_embedding:
            return json.loads(self.face_embedding)
        return None

    def set_embedding(self, embedding_list):
        self.face_embedding = json.dumps(embedding_list)

    def to_dict(self, include_today=False):
        d = {
            'id': self.id,
            'worker_code': self.worker_code,
            'name': self.name,
            'age': self.age,
            'cnic': self.cnic,
            'phone': self.phone,
            'photo_url': f'/api/workers/{self.id}/photo' if self.photo_path else None,
            'shift_type': self.shift_type,
            'plant_id': self.plant_id,
            'plant_name': self.plant.name if self.plant else None,
            'contractor_id': self.contractor_id,
            'contractor_name': self.contractor.name if self.contractor else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'has_face': self.face_embedding is not None,
        }
        if include_today:
            from src.models.attendance_model import AttendanceRecord
            from datetime import date
            today = date.today()
            att = AttendanceRecord.query.filter_by(worker_id=self.id, date=today).first()
            if att:
                d['live_status'] = att.live_status
                d['checkin_time'] = att.checkin_time.strftime('%H:%M') if att.checkin_time else None
                d['checkout_time'] = att.checkout_time.strftime('%H:%M') if att.checkout_time else None
            else:
                d['live_status'] = 'OUT'
                d['checkin_time'] = None
                d['checkout_time'] = None
        return d
