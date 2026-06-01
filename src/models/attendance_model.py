from src.extention import db
from datetime import datetime, date, time

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    shift_type = db.Column(db.Enum('Day', 'Night', 'Rest'), nullable=False)
    checkin_time = db.Column(db.Time)
    checkout_time = db.Column(db.Time)
    checkin_photo = db.Column(db.String(500))   # path to check-in snapshot
    checkout_photo = db.Column(db.String(500))

    # Calculated fields
    total_hours = db.Column(db.Float, default=0.0)
    overtime_hours = db.Column(db.Float, default=0.0)

    live_status = db.Column(db.Enum('IN', 'OUT'), default='OUT')
    status = db.Column(db.Enum('Present', 'Late', 'Absent', 'On Leave'), default='Absent')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def calculate_hours(self):
        """Calculate total and overtime hours based on shift (12hr shifts: Day 07:00-19:00, Night 19:00-07:00)"""
        if self.checkin_time and self.checkout_time:
            from datetime import datetime, timedelta
            # Convert times to datetime for arithmetic
            base = datetime(2000, 1, 1)
            cin = datetime.combine(base.date(), self.checkin_time)
            cout = datetime.combine(base.date(), self.checkout_time)
            if cout < cin:
                cout += timedelta(days=1)  # overnight shift
            total = (cout - cin).total_seconds() / 3600
            self.total_hours = round(total, 2)

            # Shift duration is 12 hours standard
            standard_hours = 12.0
            self.overtime_hours = round(max(0, total - standard_hours), 2)

    def to_dict(self):
        w = self.worker
        return {
            'id': self.id,
            'worker_id': self.worker_id,
            'worker_code': w.worker_code if w else None,
            'worker_name': w.name if w else None,
            'plant_name': w.plant.name if w and w.plant else None,
            'contractor_name': w.contractor.name if w and w.contractor else None,
            'date': self.date.isoformat() if self.date else None,
            'shift_type': self.shift_type,
            'checkin_time': self.checkin_time.strftime('%H:%M') if self.checkin_time else None,
            'checkout_time': self.checkout_time.strftime('%H:%M') if self.checkout_time else None,
            'total_hours': self.total_hours,
            'overtime_hours': self.overtime_hours,
            'live_status': self.live_status,
            'status': self.status,
            'photo_url': f'/api/attendance/{self.id}/checkin-photo' if self.checkin_photo else None,
        }
