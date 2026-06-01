from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from src.extention import db
import os

def create_app():
    app = Flask(__name__)

    # Config
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        "mysql+pymysql://root:@localhost/attandance_management_system"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET', 'super-secret-jwt-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

    # Extensions
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Register blueprints
    from src.routes.auth_routes import auth_bp
    from src.routes.worker_routes import worker_bp
    from src.routes.attendance_routes import attendance_bp
    from src.routes.face_routes import face_bp
    from src.routes.report_routes import report_bp
    from src.routes.plant_routes import plant_bp
    from src.routes.shift_routes import shift_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(worker_bp, url_prefix='/api/workers')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(face_bp, url_prefix='/api/face')
    app.register_blueprint(report_bp, url_prefix='/api/reports')
    app.register_blueprint(plant_bp, url_prefix='/api/plants')
    app.register_blueprint(shift_bp, url_prefix='/api/shifts')

    with app.app_context():
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    """Seed initial admin user and reference data."""
    from src.models.user_model import User
    from src.models.plant_model import Plant
    from src.models.contractor_model import Contractor
    import bcrypt

    # Seed admin
    if not User.query.filter_by(email='admin@system.com').first():
        hashed = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        admin = User(email='admin@system.com', password=hashed, role='admin', name='System Admin')
        db.session.add(admin)

    # Seed contractors (Fawad and Zaman)
    for name in ['Fawad', 'Zaman']:
        if not Contractor.query.filter_by(name=name).first():
            db.session.add(Contractor(name=name))

    # Seed 4 plants
    plant_names = ['Plant A', 'Plant B', 'Plant C', 'Plant D']
    for i, pname in enumerate(plant_names, 1):
        if not Plant.query.filter_by(name=pname).first():
            db.session.add(Plant(name=pname, location=f'Section {chr(64+i)}', capacity=90))

    db.session.commit()