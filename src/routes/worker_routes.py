from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required
from src.extention import db
from src.models.worker_model import Worker
from src.models.plant_model import Plant
from src.models.contractor_model import Contractor
import os, base64, io
from datetime import datetime

worker_bp = Blueprint('workers', __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'uploads', 'workers')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _next_worker_code():
    last = Worker.query.order_by(Worker.id.desc()).first()
    if last and last.worker_code:
        try:
            num = int(last.worker_code[1:]) + 1
        except Exception:
            num = 1
    else:
        num = 1
    return f'W{num:04d}'


@worker_bp.route('/', methods=['GET'])
@jwt_required()
def list_workers():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '')
    plant_id = request.args.get('plant_id', type=int)
    contractor_id = request.args.get('contractor_id', type=int)
    shift = request.args.get('shift')

    q = Worker.query.filter_by(is_active=True)
    if search:
        q = q.filter(Worker.name.ilike(f'%{search}%') | Worker.worker_code.ilike(f'%{search}%'))
    if plant_id:
        q = q.filter_by(plant_id=plant_id)
    if contractor_id:
        q = q.filter_by(contractor_id=contractor_id)
    if shift:
        q = q.filter_by(shift_type=shift)

    total = q.count()
    workers = q.order_by(Worker.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'workers': [w.to_dict(include_today=True) for w in workers.items],
        'total': total,
        'page': page,
        'pages': workers.pages,
    }), 200


@worker_bp.route('/<int:worker_id>', methods=['GET'])
@jwt_required()
def get_worker(worker_id):
    w = Worker.query.get_or_404(worker_id)
    return jsonify({'worker': w.to_dict(include_today=True)}), 200


@worker_bp.route('/', methods=['POST'])
@jwt_required()
def create_worker():
    data = request.get_json()

    # Log incoming payload for debugging shift assignment issues
    try:
        current_app.logger.info(f"Create worker payload: {data}")
    except Exception:
        # If current_app logger isn't available for some reason, ignore logging
        pass

    # Auto-generate worker code if not provided
    worker_code = data.get('worker_code') or _next_worker_code()
    if Worker.query.filter_by(worker_code=worker_code).first():
        return jsonify({'error': 'Worker code already exists'}), 409

    plant = Plant.query.get(data.get('plant_id'))
    contractor = Contractor.query.get(data.get('contractor_id'))
    if not plant or not contractor:
        return jsonify({'error': 'Invalid plant or contractor'}), 400

    # Determine shift assignment explicitly:
    # - If the key 'shift_type' is present in payload, use its value (even if None) => explicit nil
    # - If absent, fall back to system default 'Day'
    if 'shift_type' in data:
        chosen_shift = data['shift_type']  # may be None
    else:
        chosen_shift = 'Day'

    try:
        current_app.logger.info(f"Assigned shift (after interpret): {chosen_shift}")
    except Exception:
        pass

    w = Worker(
        worker_code=worker_code,
        name=data.get('name', ''),
        age=data.get('age'),
        cnic=data.get('cnic'),
        phone=data.get('phone'),
        shift_type=chosen_shift,
        plant_id=plant.id,
        contractor_id=contractor.id,
    )

    # Handle photo
    photo_b64 = data.get('photo')
    if photo_b64:
        try:
            if ',' in photo_b64:
                photo_b64 = photo_b64.split(',')[1]
            photo_bytes = base64.b64decode(photo_b64)
            path = os.path.join(UPLOAD_DIR, f'{worker_code}.jpg')
            with open(path, 'wb') as f:
                f.write(photo_bytes)
            w.photo_path = path
        except Exception:
            pass

    db.session.add(w)
    db.session.commit()

    # Ensure explicit nil (None) is persisted as NULL in the DB.
    # Some SQLAlchemy Enum/ORM defaults can coerce or apply defaults on insert; when the client
    # explicitly requested null, run an explicit UPDATE to set the column to NULL.
    if 'shift_type' in data and data['shift_type'] is None:
        try:
            from sqlalchemy import text
            db.session.execute(text("UPDATE workers SET shift_type = NULL WHERE id = :id"), {'id': w.id})
            db.session.commit()
        except Exception:
            # best-effort - ignore failures here but continue returning created worker
            pass

    return jsonify({'worker': w.to_dict()}), 201


@worker_bp.route('/<int:worker_id>', methods=['PUT'])
@jwt_required()
def update_worker(worker_id):
    w = Worker.query.get_or_404(worker_id)
    data = request.get_json()

    w.name = data.get('name', w.name)
    w.age = data.get('age', w.age)
    w.cnic = data.get('cnic', w.cnic)
    w.phone = data.get('phone', w.phone)

    # Track whether shift_type key was present to handle explicit nulls
    shift_present = 'shift_type' in data
    if shift_present:
        w.shift_type = data.get('shift_type')

    if data.get('plant_id'):
        w.plant_id = data['plant_id']
    if data.get('contractor_id'):
        w.contractor_id = data['contractor_id']

    photo_b64 = data.get('photo')
    if photo_b64:
        try:
            if ',' in photo_b64:
                photo_b64 = photo_b64.split(',')[1]
            photo_bytes = base64.b64decode(photo_b64)
            path = os.path.join(UPLOAD_DIR, f'{w.worker_code}.jpg')
            with open(path, 'wb') as f:
                f.write(photo_bytes)
            w.photo_path = path
        except Exception:
            pass

    db.session.commit()

    # If client explicitly sent null for shift_type, ensure NULL is persisted in DB
    if shift_present and data.get('shift_type') is None:
        try:
            from sqlalchemy import text
            db.session.execute(text("UPDATE workers SET shift_type = NULL WHERE id = :id"), {'id': w.id})
            db.session.commit()
        except Exception:
            pass

    return jsonify({'worker': w.to_dict()}), 200


@worker_bp.route('/<int:worker_id>', methods=['DELETE'])
@jwt_required()
def delete_worker(worker_id):
    w = Worker.query.get_or_404(worker_id)
    w.is_active = False
    db.session.commit()
    return jsonify({'message': 'Worker deactivated'}), 200


@worker_bp.route('/<int:worker_id>/photo', methods=['GET'])
def get_photo(worker_id):
    w = Worker.query.get_or_404(worker_id)
    if w.photo_path and os.path.exists(w.photo_path):
        return send_file(w.photo_path, mimetype='image/jpeg')
    return jsonify({'error': 'No photo'}), 404


@worker_bp.route('/meta', methods=['GET'])
@jwt_required()
def meta():
    plants = Plant.query.all()
    contractors = Contractor.query.all()
    return jsonify({
        'plants': [p.to_dict() for p in plants],
        'contractors': [c.to_dict() for c in contractors],
    }), 200
