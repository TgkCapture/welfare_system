# app/config.py
import os
from datetime import timedelta

class Config:
    # Basic Flask config
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///welfare.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File storage
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    REPORT_FOLDER = os.path.join(os.getcwd(), 'reports')
    LOGS_FOLDER = os.path.join(os.getcwd(), 'logs')
    
    # Google Sheets
    GOOGLE_CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH')
    GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    DEFAULT_SHEET_URL = os.environ.get('DEFAULT_SHEET_URL')
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Security
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # File logging
        if not os.path.exists(cls.LOGS_FOLDER):
            os.makedirs(cls.LOGS_FOLDER)
        
        file_handler = RotatingFileHandler(
            os.path.join(cls.LOGS_FOLDER, 'welfare.log'),
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}