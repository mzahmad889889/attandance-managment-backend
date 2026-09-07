from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from src.extention import db
from src.models.attendance_model import AttendanceRecord
from src.models.worker_model import Worker
from sqlalchemy import or_
from datetime import date, datetime, time

attendance_bp = Blueprint('attendance', __name__)


@attendance_bp.route('/', methods=['GET'])
@jwt_required()
def list_attendance():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    date_str = request.args.get('date')
    date_from_str = request.args.get('date_from')
    date_to_str = request.args.get('date_to')
    plant_id = request.args.get('plant_id', type=int)
    contractor_id = request.args.get('contractor_id', type=int)
    shift = request.args.get('shift')
    status = request.args.get('status')
    search = request.args.get('search', '')

    q = AttendanceRecord.query.join(Worker)

    if date_from_str or date_to_str:
        try:
            date_from = date.fromisoformat(date_from_str) if date_from_str else date.min
            date_to = date.fromisoformat(date_to_str) if date_to_str else date.max
            q = q.filter(
                AttendanceRecord.date <= date_to,
                or_(AttendanceRecord.checkout_date.is_(None), AttendanceRecord.checkout_date >= date_from),
            )
        except ValueError:
            pass
    elif date_str:
        try:
            d = date.fromisoformat(date_str)
            q = q.filter(or_(AttendanceRecord.date == d, AttendanceRecord.checkout_date == d))
        except ValueError:
            pass

    if plant_id:
        q = q.filter(Worker.plant_id == plant_id)
    if contractor_id:
        q = q.filter(Worker.contractor_id == contractor_id)
    if shift:
        q = q.filter(AttendanceRecord.shift_type == shift)
    if status:
        q = q.filter(AttendanceRecord.status == status)
    if search:
        q = q.filter(Worker.name.ilike(f'%{search}%') | Worker.worker_code.ilike(f'%{search}%'))

    total = q.count()
    records = q.order_by(AttendanceRecord.checkin_time.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'records': [r.to_dict() for r in records.items],
        'total': total,
        'page': page,
        'pages': records.pages,
    }), 200


@attendance_bp.route('/today-stats', methods=['GET'])
@jwt_required()
def today_stats():
    today = date.today()
    total_workers = Worker.query.filter_by(is_active=True).count()
    records_today = AttendanceRecord.query.filter_by(date=today).all()
    present = sum(1 for r in records_today if r.status in ('Present', 'Late'))
    live_in = sum(1 for r in records_today if r.live_status == 'IN')
    for record in records_today:
        if record.checkin_time and (record.checkout_time or record.live_status == 'IN'):
            record.calculate_hours()
    overtime = sum(r.overtime_hours or 0 for r in records_today)

    return jsonify({
        'total_workers': total_workers,
        'present_today': present,
        'absent_today': total_workers - present,
        'live_in': live_in,
        'total_overtime_hours': round(overtime, 2),
        'date': today.isoformat(),
    }), 200


@attendance_bp.route('/checkin', methods=['POST'])
@jwt_required()
def manual_checkin():
    """Manual check-in by worker code."""
    data = request.get_json()
    worker_code = data.get('worker_code', '').upper()

    worker = Worker.query.filter_by(worker_code=worker_code, is_active=True).first()
    if not worker:
        return jsonify({'error': 'Worker not found'}), 404

    # Lock the worker row so concurrent camera/manual requests cannot create
    # multiple open attendance records for the same worker.
    worker = Worker.query.filter_by(id=worker.id).with_for_update().first()
    record = AttendanceRecord.query.filter_by(worker_id=worker.id, live_status='IN').order_by(AttendanceRecord.id.asc()).first()

    if record:
        return jsonify({'error': 'Already checked in', 'record': record.to_dict()}), 409

    today = date.today()
    now = datetime.now().time()
    record = AttendanceRecord(
        worker_id=worker.id,
        date=today,
        shift_type=worker.shift_type,
        checkin_time=now,
        live_status='IN',
        status='Present',
    )
    db.session.add(record)

    db.session.commit()
    
    # Auto-cleanup old records (older than 1 month) on every check-in check
    cleanup_old_history()
    
    return jsonify({'message': 'Checked in', 'record': record.to_dict(), 'worker': worker.to_dict()}), 200


@attendance_bp.route('/checkout', methods=['POST'])
@jwt_required()
def manual_checkout():
    """Manual check-out by worker code."""
    data = request.get_json()
    worker_code = data.get('worker_code', '').upper()

    worker = Worker.query.filter_by(worker_code=worker_code, is_active=True).first()
    if not worker:
        return jsonify({'error': 'Worker not found'}), 404

    worker = Worker.query.filter_by(id=worker.id).with_for_update().first()
    record = AttendanceRecord.query.filter_by(worker_id=worker.id, live_status='IN').order_by(AttendanceRecord.id.asc()).first()

    if not record:
        return jsonify({'error': 'Worker not checked in'}), 409

    now = datetime.now().time()
    record.checkout_time = now
    record.checkout_date = today
    record.live_status = 'OUT'
    record.calculate_hours()

    db.session.commit()
    return jsonify({'message': 'Checked out', 'record': record.to_dict(), 'worker': worker.to_dict()}), 200


@attendance_bp.route('/live-feed', methods=['GET'])
@jwt_required()
def live_feed():
    """Return recent 20 check-in/out events."""
    records = AttendanceRecord.query.filter_by(date=date.today()).order_by(
        AttendanceRecord.id.desc()
    ).limit(20).all()
    return jsonify({'records': [r.to_dict() for r in records]}), 200


@attendance_bp.route('/monitoring-active', methods=['GET'])
@jwt_required()
def monitoring_active():
    """Returns all workers currently 'IN', grouped by plant."""
    today = date.today()
    active_now = AttendanceRecord.query.filter_by(live_status='IN').all()
    
    plants = {}
    for r in active_now:
        p_name = r.worker.plant.name if r.worker and r.worker.plant else "Unknown"
        if p_name not in plants:
            plants[p_name] = []
        plants[p_name].append({
            'worker_name': r.worker.name,
            'worker_code': r.worker.worker_code,
            'checkin_time': r.checkin_time.strftime('%H:%M') if r.checkin_time else None,
            'contractor': r.worker.contractor.name if r.worker.contractor else None
        })
    
    return jsonify({'plants': plants}), 200


def cleanup_old_history():
    """Remove attendance records older than 30 days."""
    try:
        from datetime import date, timedelta
        limit = date.today() - timedelta(days=30)
        deleted = AttendanceRecord.query.filter(AttendanceRecord.date < limit).delete()
        db.session.commit()
        if deleted > 0:
            print(f"[CLEANUP] Automatically removed {deleted} records older than 1 month.")
    except Exception as e:
        print(f"[CLEANUP] Error: {e}")

