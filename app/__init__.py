# === app/__init__.py ===
__version__ = "1.2.0" 

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
import os

login_manager = LoginManager()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
   
    app.version = __version__

    # Load configuration from environment variables with defaults
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))
    app.config['REPORT_FOLDER'] = os.environ.get('REPORT_FOLDER', os.path.join(os.getcwd(), 'reports'))
    app.config['GOOGLE_CREDENTIALS_PATH'] = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials/mzugoss-welfare-5dab294def1f.json')
    app.config['GOOGLE_CREDENTIALS_JSON'] = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    app.config['DEFAULT_SHEET_URL'] = os.environ.get('DEFAULT_SHEET_URL', '')
    
    # Create directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Initialize Google Sheets service
    from .google_sheets import google_sheets_service
    google_sheets_service.init_app(app)

    from .auth.routes import auth as auth_blueprint
    from .main.routes import main as main_blueprint
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)

    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    return app