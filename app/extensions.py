# app/extensions.py
"""
Flask extension instances.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData

# Core ORM. Named constraints let Alembic batch migrations alter them on SQLite.
db = SQLAlchemy(metadata=MetaData(naming_convention={
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}))

# Schema migrations (Alembic). Batch mode lets SQLite ALTER existing tables.
migrate = Migrate(render_as_batch=True)

# Rate limiting — only routes that opt in with @limiter.limit are limited.
# Storage comes from RATELIMIT_STORAGE_URI (in-memory by default).
limiter = Limiter(key_func=get_remote_address)

# Authentication
login_manager = LoginManager()
login_manager.login_view        = 'auth.login'      # group finder; redirects to the group's login
login_manager.login_message     = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# CSRF protection for all forms
csrf = CSRFProtect()