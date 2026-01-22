# app/models/user.py
from flask_login import UserMixin
from app.extensions import db
from sqlalchemy.dialects.postgresql import ENUM

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # role types
    ROLES = ('admin', 'clerk', 'viewer')
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    
    role = db.Column(
        db.String(20),
        nullable=False,
        default='viewer',
        server_default='viewer'
    )
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    last_login = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'
    
    # Role check methods
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_clerk(self):
        return self.role == 'clerk'
    
    @property
    def is_viewer(self):
        return self.role == 'viewer'
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        role_permissions = {
            'admin': ['manage_users', 'upload_files', 'view_reports', 
                     'download_reports', 'manage_settings', 'cleanup_files'],
            'clerk': ['upload_files', 'view_reports', 'download_reports'],
            'viewer': ['view_reports']
        }
        return permission in role_permissions.get(self.role, [])