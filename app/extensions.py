# app/extensions.py
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

login_manager = LoginManager()
db = SQLAlchemy()

def init_extensions(app):
    """Initialize Flask extensions"""
    db.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import and create models here
    from app.models.user import get_user_model
    from app.models.setting import get_setting_model
    
    # Create the actual models
    User = get_user_model(db)
    Setting = get_setting_model(db)
    
    # Store models in app context
    app.models = {
        'User': User,
        'Setting': Setting
    }
    
    # Setup user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app.models