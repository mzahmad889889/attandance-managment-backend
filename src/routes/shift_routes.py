from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.models.worker_model import Worker
from src.models.attendance_model import AttendanceRecord
from datetime import date, datetime, timedelta
from src.apptime import now as app_now, today as app_today

shift_bp = Blueprint('shifts', __name__)

# Shift cycle: 2 Day → 2 Night → 2 Rest (repeating 6-day block)
SHIFT_CYCLE = ['Day', 'Day', 'Night', 'Night', 'Rest', 'Rest']


def get_shift_for_worker(worker, target_date=None):
    """Calculate what shift a worker should be on for a given date based on start date."""
    if target_date is None:
        target_date = app_today()
    if not worker.shift_start_date:
        return worker.shift_type

    delta = (target_date - worker.shift_start_date).days
    idx = delta % 6
    return SHIFT_CYCLE[idx]


@shift_bp.route('/schedule', methods=['GET'])
@jwt_required()
def schedule():
    """Return 7-day shift schedule for all workers (paginated per plant)."""
    plant_id = request.args.get('plant_id', type=int)
    today = app_today()
    days = [(today + timedelta(days=i)) for i in range(7)]

    q = Worker.query.filter_by(is_active=True)
    if plant_id:
        q = q.filter_by(plant_id=plant_id)
    workers = q.all()

    result = []
    for w in workers:
        schedule_row = {
            'worker_id': w.id,
            'worker_code': w.worker_code,
            'name': w.name,
            'plant': w.plant.name if w.plant else None,
            'contractor': w.contractor.name if w.contractor else None,
            'days': {}
        }
        for d in days:
            shift = get_shift_for_worker(w, d)
            schedule_row['days'][d.isoformat()] = shift
        result.append(schedule_row)

    return jsonify({
        'schedule': result,
        'date_range': [d.isoformat() for d in days],
    }), 200


@shift_bp.route('/summary', methods=['GET'])
@jwt_required()
def today_shift_summary():
    today = app_today()
    workers = Worker.query.filter_by(is_active=True).all()

    day_workers, night_workers, rest_workers = [], [], []
    for w in workers:
        shift = get_shift_for_worker(w, today)
        info = {'id': w.id, 'name': w.name, 'code': w.worker_code,
                'plant': w.plant.name if w.plant else None}
        if shift == 'Day':
            day_workers.append(info)
        elif shift == 'Night':
            night_workers.append(info)
        else:
            rest_workers.append(info)

    return jsonify({
        'date': today.isoformat(),
        'day': {'count': len(day_workers), 'workers': day_workers[:20]},
        'night': {'count': len(night_workers), 'workers': night_workers[:20]},
        'rest': {'count': len(rest_workers), 'workers': rest_workers[:20]},
    }), 200
