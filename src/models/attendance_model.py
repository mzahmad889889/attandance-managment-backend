from src.extention import db
from datetime import datetime, date, time
from src.apptime import now as app_now, today as app_today

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    checkout_date = db.Column(db.Date)

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

    created_at = db.Column(db.DateTime, default=app_now)

    def calculate_hours(self, reference_time=None):
        """Calculate elapsed and overtime, using 8 hours as the standard day."""
        if not self.checkin_time:
            return

        from datetime import timedelta
        start_date = self.date or app_today()
        cin = datetime.combine(start_date, self.checkin_time)
        if self.checkout_time:
            end_date = self.checkout_date or start_date
            cout = datetime.combine(end_date, self.checkout_time)
        else:
            cout = reference_time or app_now()
        if cout < cin:
            cout += timedelta(days=1)

        total_minutes = max(0, round((cout - cin).total_seconds() / 60))
        overtime_minutes = max(0, total_minutes - 8 * 60)
        self.total_hours = round(total_minutes / 60, 2)
        self.overtime_hours = round(overtime_minutes / 60, 2)

    @property
    def overtime_minutes(self):
        return round((self.overtime_hours or 0) * 60)

    def to_dict(self):
        if self.checkin_time and (self.checkout_time or self.live_status == 'IN'):
            self.calculate_hours()
        w = self.worker
        return {
            'id': self.id,
            'worker_id': self.worker_id,
            'worker_code': w.worker_code if w else None,
            'worker_name': w.name if w else None,
            'plant_name': w.plant.name if w and w.plant else None,
            'contractor_name': w.contractor.name if w and w.contractor else None,
            'date': self.date.isoformat() if self.date else None,
            'checkin_date': self.date.isoformat() if self.date else None,
            'checkout_date': self.checkout_date.isoformat() if self.checkout_date else (
                self.date.isoformat() if self.checkout_time and self.date else None
            ),
            'shift_type': self.shift_type,
            'checkin_time': self.checkin_time.strftime('%H:%M') if self.checkin_time else None,
            'checkout_time': self.checkout_time.strftime('%H:%M') if self.checkout_time else None,
            'total_hours': self.total_hours,
            'overtime_hours': self.overtime_hours,
            'overtime_minutes': self.overtime_minutes,
            'live_status': self.live_status,
            'status': self.status,
            'photo_url': f'/api/attendance/{self.id}/checkin-photo' if self.checkin_photo else None,
        }
