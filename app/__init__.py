# === app/__init__.py ===
__version__ = "0.2.0" 

from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
import os

login_manager = LoginManager()
db = SQLAlchemy()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
   
    app.version = __version__

    app.config.from_pyfile('config.py')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

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