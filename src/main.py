import os
import sys
from datetime import timedelta
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.models.database import db
from src.routes.auth import auth_bp
from src.routes.users import users_bp
from src.routes.pharmacies import pharmacies_bp
from src.routes.products import products_bp
from src.routes.search import search_bp
from src.routes.cart import cart_bp
from src.routes.orders import orders_bp
from src.routes.admin import admin_bp

def create_app():
    app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-dawaksahl-2025')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key-dawaksahl-2025')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=7)
    
    # Database Configuration
    database_url = os.getenv('DATABASE_URL', 'sqlite:///dawaksahl_dev.db')
    if database_url.startswith('sqlite:///'):
        # For SQLite, use absolute path
        db_path = database_url.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(__file__), 'database', db_path)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # File Upload Configuration
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 16777216))  # 16MB
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
    
    # Email Configuration
    app.config['SENDGRID_API_KEY'] = os.getenv('SENDGRID_API_KEY')
    app.config['FROM_EMAIL'] = os.getenv('FROM_EMAIL', 'noreply@dawaksahl.com')
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    jwt = JWTManager(app)
    
    # CORS Configuration
    cors_origins = os.getenv('CORS_ORIGINS', '*')
    if cors_origins == '*':
        CORS(app, origins='*', supports_credentials=True)
    else:
        CORS(app, origins=cors_origins.split(','), supports_credentials=True)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(pharmacies_bp, url_prefix='/api/pharmacies')
    app.register_blueprint(products_bp, url_prefix='/api/products')
    app.register_blueprint(search_bp, url_prefix='/api/search')
    app.register_blueprint(cart_bp, url_prefix='/api/cart')
    app.register_blueprint(orders_bp, url_prefix='/api/orders')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    
    # JWT Error Handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'message': 'Token has expired', 'error': 'token_expired'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'message': 'Invalid token', 'error': 'invalid_token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'message': 'Authorization token is required', 'error': 'authorization_required'}), 401
    
    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy', 'service': 'DawakSahl API'})
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app

# Frontend serving routes
app = create_app()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return jsonify({'message': 'DawakSahl API is running', 'version': '1.0.0'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_DEBUG', 'True').lower() == 'true')
