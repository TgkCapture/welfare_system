# app/models/user.py
from flask_login import UserMixin
# Don't import db here

class User(UserMixin):
    """Base User class without SQLAlchemy"""
    pass

def get_user_model(db):
    class UserModel(User, db.Model):
        __tablename__ = 'users'
        
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(100), unique=True, nullable=False)
        password = db.Column(db.String(100), nullable=False)
        is_active = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
        
        def __repr__(self):
            return f'<User {self.email}>'
    
    return UserModel