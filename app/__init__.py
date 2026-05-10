# app/__init__.py
"""
Application factory.

Usage::

    from app import create_app
    app = create_app()          # uses FLASK_ENV or falls back to 'development'
    app = create_app('testing') # explicit environment
"""
import logging
import os
from datetime import datetime

from flask import Flask
from flask_wtf.csrf import generate_csrf

from app.config import config
from app.extensions import csrf, db, login_manager


def create_app(env: str = None) -> Flask:
    """Create, configure and return the Flask application."""
    env = env or os.environ.get('FLASK_ENV', 'development')
    cfg = config.get(env, config['default'])

    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )

    # ── Configuration ─────────────────────────────────────────────────
    app.config.from_object(cfg)
    cfg.init_app(app)

    # Load instance config if it exists (overrides above)
    app.config.from_pyfile(
        os.path.join(app.instance_path, 'config.py'),
        silent=True,
    )

    # ── App version ───────────────────────────────────────────────────
    app.version = os.environ.get('APP_VERSION', _read_version())

    # ── Logging ───────────────────────────────────────────────────────
    _configure_logging(app)

    # ── Extensions ────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # ── User loader ───────────────────────────────────────────────────
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(int(user_id))

    # ── Template globals ──────────────────────────────────────────────
    # Make csrf_token() and now available in every template without
    # explicitly passing them from every controller.
    @app.context_processor
    def inject_globals():
        return {
            'now':        datetime.now(),
            'csrf_token': generate_csrf,
            'version':    app.version,
        }

    # ── Blueprints ────────────────────────────────────────────────────
    _register_blueprints(app)

    # ── CLI Commands ──────────────────────────────────────────────────
    from app.commands import init_commands
    init_commands(app)

    # ── Error handlers ────────────────────────────────────────────────
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)

    # ── Database ──────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    # ── Background scheduler ──────────────────────────────────────────
    if not app.config.get('TESTING') and app.config.get('ENABLE_AUTO_CLEANUP', True):
        from app.services.scheduler import cleanup_scheduler
        cleanup_scheduler.init_app(app)
        app.logger.info('Cleanup scheduler initialised')

    app.logger.info(
        f"App created — env={env!r} version={app.version!r}"
    )
    return app


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _register_blueprints(app: Flask) -> None:
    """Import and register all blueprints."""
    from app.routes.auth   import auth
    from app.routes.main   import main
    from app.routes.report import report

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(report)


def _configure_logging(app: Flask) -> None:
    """Set up structured logging for the application."""
    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO

    # Avoid adding duplicate handlers if create_app is called more than once
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        ))
        app.logger.addHandler(handler)

    app.logger.setLevel(log_level)

    # Quieten noisy third-party loggers in production
    if not app.config.get('DEBUG'):
        for noisy in ('gspread', 'google', 'urllib3', 'matplotlib'):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def _read_version(default: str = '1.0.0') -> str:
    """Read the current version from .bumpversion.cfg if it exists."""
    cfg_path = os.path.join(
        os.path.dirname(__file__), '..', '.bumpversion.cfg'
    )
    try:
        with open(cfg_path) as fh:
            for line in fh:
                if line.strip().startswith('current_version'):
                    return line.split('=', 1)[1].strip()
    except (OSError, IndexError):
        pass
    return default