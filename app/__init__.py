# app/__init__.py
from flask import Flask
import os

from app.config import Config

__version__ = "1.3.0"

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    
    # Load instance config if exists
    instance_config_path = os.path.join(app.instance_path, 'config.py')
    if os.path.exists(instance_config_path):
        app.config.from_pyfile('config.py')
    
    app.version = __version__
    
    # Create necessary directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    if 'LOGS_FOLDER' in app.config:
        os.makedirs(app.config['LOGS_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    from app.extensions import db, login_manager, init_extensions
    init_extensions(app)
    
    # Import models AFTER extensions are initialized
    from app.models.user import User
    from app.models.setting import Setting
    
    # Setup login manager
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints - FIXED HERE
    from app.routes.auth import auth as auth_blueprint
    from app.routes.main import main as main_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    
    # Register error handlers
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app