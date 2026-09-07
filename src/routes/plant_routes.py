from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from src.extention import db
from src.models.plant_model import Plant

plant_bp = Blueprint('plants', __name__)


@plant_bp.route('/', methods=['GET'])
@jwt_required()
def list_plants():
    plants = Plant.query.all()
    return jsonify({'plants': [p.to_dict() for p in plants]}), 200


@plant_bp.route('/<int:plant_id>', methods=['GET'])
@jwt_required()
def get_plant(plant_id):
    p = Plant.query.get_or_404(plant_id)
    return jsonify({'plant': p.to_dict()}), 200


@plant_bp.route('/', methods=['POST'])
@jwt_required()
def create_plant():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    p = Plant(name=name, location=data.get('location', ''), capacity=data.get('capacity', 90))
    db.session.add(p)
    db.session.commit()
    return jsonify({'plant': p.to_dict()}), 201


@plant_bp.route('/<int:plant_id>', methods=['PUT'])
@jwt_required()
def update_plant(plant_id):
    p = Plant.query.get_or_404(plant_id)
    data = request.get_json()
    p.name = data.get('name', p.name)
    p.location = data.get('location', p.location)
    p.capacity = data.get('capacity', p.capacity)
    db.session.commit()
    return jsonify({'plant': p.to_dict()}), 200


@plant_bp.route('/<int:plant_id>', methods=['DELETE'])
@jwt_required()
def delete_plant(plant_id):
    p = Plant.query.get_or_404(plant_id)
    # soft-delete if you prefer; here we fully delete
    db.session.delete(p)
    db.session.commit()
    return jsonify({'message': 'Plant deleted'}), 200
