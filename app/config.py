# app/config.py
"""
Application configuration.

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
    # 16 MB hard limit — rejects oversized files before they hit the parser
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    _base_dir    = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    UPLOAD_FOLDER = os.path.join(_base_dir, 'uploads')
    REPORT_FOLDER = os.path.join(_base_dir, 'reports')
    LOGS_FOLDER   = os.path.join(_base_dir, 'logs')

    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

    # ── Retention / storage limits ────────────────────────────────────
    REPORT_RETENTION_DAYS        = int(os.environ.get('REPORT_RETENTION_DAYS', 7))
    UPLOAD_RETENTION_DAYS        = int(os.environ.get('UPLOAD_RETENTION_DAYS', 3))
    LOG_RETENTION_DAYS           = int(os.environ.get('LOG_RETENTION_DAYS',    30))
    MAX_UPLOAD_FOLDER_SIZE_MB    = int(os.environ.get('MAX_UPLOAD_FOLDER_SIZE_MB', 1000))
    MAX_REPORT_FOLDER_SIZE_MB    = int(os.environ.get('MAX_REPORT_FOLDER_SIZE_MB', 500))

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
        for folder in ('UPLOAD_FOLDER', 'REPORT_FOLDER', 'LOGS_FOLDER'):
            path = app.config.get(folder)
            if path:
                os.makedirs(path, exist_ok=True)


class DevelopmentConfig(BaseConfig):
    """Local development — SQLite, debug toolbar friendly."""

    DEBUG = True

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BaseConfig._base_dir, 'instance', 'welfare_dev.db')}",
    )

    # Shorter retention keeps dev folders tidy
    REPORT_RETENTION_DAYS = 3
    UPLOAD_RETENTION_DAYS = 1

    # Warn loudly if the default secret key is in use
    @staticmethod
    def init_app(app):
        BaseConfig.init_app(app)
        if app.config['SECRET_KEY'] == 'change-me-in-production':
            import warnings
            warnings.warn(
                "SECRET_KEY is set to the default value — "
                "set the SECRET_KEY environment variable.",
                stacklevel=2,
            )


class TestingConfig(BaseConfig):
    """Automated tests — fast, isolated, no side-effects."""

    TESTING    = True
    DEBUG      = True
    WTF_CSRF_ENABLED   = False
    LOGIN_DISABLED     = False

    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # Keep test uploads/reports in temp dirs
    UPLOAD_FOLDER = '/tmp/welfare_test_uploads'
    REPORT_FOLDER = '/tmp/welfare_test_reports'
    LOGS_FOLDER   = '/tmp/welfare_test_logs'

    ENABLE_AUTO_CLEANUP = False   # don't start the scheduler in tests


class ProductionConfig(BaseConfig):
    """Production — all secrets from environment, HTTPS enforced."""

    DEBUG   = False
    TESTING = False

    SESSION_COOKIE_SECURE = True   # only send cookie over HTTPS

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        (_ for _ in ()).throw(  # type: ignore[attr-defined]
            RuntimeError('DATABASE_URL environment variable is not set.')
        )

    @staticmethod
    def init_app(app):
        BaseConfig.init_app(app)

        # Validate critical secrets at startup
        missing = [
            var for var in ('SECRET_KEY', 'DATABASE_URL')
            if not os.environ.get(var)
        ]
        if missing:
            raise RuntimeError(
                f"Required environment variables not set: {', '.join(missing)}"
            )

        # Send errors to stderr so the process manager captures them
        import logging
        import sys
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setLevel(logging.WARNING)
        app.logger.addHandler(stream_handler)


# ── Config map ────────────────────────────────────────────────────────────
config = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}