# app/extensions.py
"""
Flask extension instances.
"""
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

# Core ORM
db = SQLAlchemy()

# Schema migrations (Alembic). Batch mode lets SQLite ALTER existing tables.
migrate = Migrate(render_as_batch=True)

# Authentication
login_manager = LoginManager()
login_manager.login_view        = 'auth.login'      # redirect target for @login_required
login_manager.login_message     = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# CSRF protection for all forms
csrf = CSRFProtect()