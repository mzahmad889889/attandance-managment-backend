from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from src.extention import db
from src.models.user_model import User
import bcrypt

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    if not bcrypt.checkpw(password.encode(), user.password.encode()):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({
        'token': token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    """Admin-only: create manager accounts."""
    current_id = int(get_jwt_identity())
    current = User.query.get(current_id)
    if not current or current.role != 'admin':
        return jsonify({'error': 'Admin only'}), 403

    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    role = data.get('role', 'manager')
    name = data.get('name', '').strip()

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 409

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password=hashed, role=role, name=name)
    db.session.add(user)
    db.session.commit()
    return jsonify({'user': user.to_dict()}), 201
