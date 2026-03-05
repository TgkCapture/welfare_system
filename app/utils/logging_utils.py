# app/utils/logging_utils.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """Setup comprehensive logging for the application"""
    
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler (for development)
    if app.debug:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(detailed_formatter)
        app.logger.addHandler(console_handler)
    
    # File handlers
    logs_dir = app.config.get('LOGS_FOLDER', 'logs')
    
    # Main application log
    app_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'app.log'),
        maxBytes=app.config.get('LOG_FILE_MAX_SIZE', 10 * 1024 * 1024),
        backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(simple_formatter)
    app.logger.addHandler(app_handler)
    
    # Error log
    error_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'error.log'),
        maxBytes=app.config.get('LOG_FILE_MAX_SIZE', 10 * 1024 * 1024),
        backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    app.logger.addHandler(error_handler)
    
    # Set overall logging level
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Suppress noisy loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)