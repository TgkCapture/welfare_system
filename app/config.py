# app/config.py
"""
Application configuration.

Three environments are provided:

  DevelopmentConfig  — SQLite, debug on, relaxed security
  TestingConfig      — in-memory SQLite, CSRF/login disabled
  ProductionConfig   — requires env vars, strict security

Select via the FLASK_ENV environment variable (handled in create_app).

All secrets MUST be supplied through environment variables in
production — never hard-coded defaults.
"""
import os
from datetime import timedelta


class BaseConfig:
    """Shared settings inherited by all environments."""

    # ── Security ──────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')

    # ── SQLAlchemy ────────────────────────────────────────────────────
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Session ───────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = 'Lax'

    # ── File uploads ──────────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB

    _base_dir     = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    UPLOAD_FOLDER = os.path.join(_base_dir, 'uploads')
    REPORT_FOLDER = os.path.join(_base_dir, 'reports')
    LOGS_FOLDER   = os.path.join(_base_dir, 'logs')

    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

    # ── Retention / storage limits ────────────────────────────────────
    REPORT_RETENTION_DAYS     = int(os.environ.get('REPORT_RETENTION_DAYS', 7))
    UPLOAD_RETENTION_DAYS     = int(os.environ.get('UPLOAD_RETENTION_DAYS', 3))
    LOG_RETENTION_DAYS        = int(os.environ.get('LOG_RETENTION_DAYS',    30))
    MAX_UPLOAD_FOLDER_SIZE_MB = int(os.environ.get('MAX_UPLOAD_FOLDER_SIZE_MB', 1000))
    MAX_REPORT_FOLDER_SIZE_MB = int(os.environ.get('MAX_REPORT_FOLDER_SIZE_MB', 500))

    # ── Auto-cleanup scheduler ────────────────────────────────────────
    ENABLE_AUTO_CLEANUP = os.environ.get('ENABLE_AUTO_CLEANUP', 'true').lower() == 'true'
    CLEANUP_TIME        = os.environ.get('CLEANUP_TIME', '02:00')
    AUTO_CLEANUP_DAYS   = int(os.environ.get('AUTO_CLEANUP_DAYS', 3))

    # ── Google Sheets ─────────────────────────────────────────────────
    GOOGLE_CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH', '')
    GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
    DEFAULT_SHEET_URL       = os.environ.get('DEFAULT_SHEET_URL', '')
    SHEETS_CACHE_TTL        = int(os.environ.get('SHEETS_CACHE_TTL', 300))

    # ── Reports ───────────────────────────────────────────────────────
    CLERKS_SEE_ALL_REPORTS = (
        os.environ.get('CLERKS_SEE_ALL_REPORTS', 'false').lower() == 'true'
    )

    # ── Month names (convenience) ─────────────────────────────────────
    MONTH_NAMES = [
        'January', 'February', 'March', 'April',
        'May', 'June', 'July', 'August',
        'September', 'October', 'November', 'December',
    ]

    @staticmethod
    def init_app(app):
        """Create required directories on first run."""
        for key in ('UPLOAD_FOLDER', 'REPORT_FOLDER', 'LOGS_FOLDER'):
            path = app.config.get(key)
            if path:
                os.makedirs(path, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    """Local development — SQLite, debug on."""

    DEBUG = True

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BaseConfig._base_dir, 'instance', 'welfare_dev.db')}",
    )

    REPORT_RETENTION_DAYS = 3
    UPLOAD_RETENTION_DAYS = 1

    @staticmethod
    def init_app(app):
        BaseConfig.init_app(app)
        if app.config['SECRET_KEY'] == 'change-me-in-production':
            import warnings
            warnings.warn(
                'SECRET_KEY is set to the default value — '
                'set the SECRET_KEY environment variable before going to production.',
                stacklevel=2,
            )


class TestingConfig(BaseConfig):
    """Automated tests — fast, isolated, no side-effects."""

    TESTING            = True
    DEBUG              = True
    WTF_CSRF_ENABLED   = False

    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    UPLOAD_FOLDER = '/tmp/welfare_test_uploads'
    REPORT_FOLDER = '/tmp/welfare_test_reports'
    LOGS_FOLDER   = '/tmp/welfare_test_logs'

    ENABLE_AUTO_CLEANUP = False   # never start the scheduler in tests


class ProductionConfig(BaseConfig):
    """Production — all secrets from environment variables, HTTPS enforced."""

    DEBUG   = False
    TESTING = False

    # Plain assignment — missing DATABASE_URL is caught at runtime in
    # init_app(), not at class-definition / import time.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '')

    SESSION_COOKIE_SECURE = True   # only transmit cookie over HTTPS

    @staticmethod
    def init_app(app):
        BaseConfig.init_app(app)

        # Validate critical env vars at startup, not at import time
        missing = [
            var for var in ('SECRET_KEY', 'DATABASE_URL')
            if not os.environ.get(var)
        ]
        if missing:
            raise RuntimeError(
                f"Required environment variables are not set: {', '.join(missing)}\n"
                f"Set them before starting the application in production."
            )

        if app.config['SECRET_KEY'] == 'change-me-in-production':
            raise RuntimeError(
                'SECRET_KEY must not be the default value in production.'
            )

        # Send warnings/errors to stderr so the process manager captures them
        import logging
        import sys
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        app.logger.addHandler(handler)


# ── Config registry ───────────────────────────────────────────────────────
config = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}