# app/__init__.py
"""
Application factory.

Usage::

    from app import create_app
    app = create_app()          # uses FLASK_ENV or falls back to 'development'
    app = create_app('testing') # explicit environment
    app = create_app('testing', {'SQLALCHEMY_DATABASE_URI': ...})
"""
import logging
import os
from datetime import datetime

from flask import Flask
from flask_wtf.csrf import generate_csrf

from app.config import config
from app.extensions import csrf, db, limiter, login_manager, migrate

__version__ = "2.0.2"


def create_app(env: str = None, test_config: dict = None) -> Flask:
    """Create, configure and return the Flask application.

    *test_config* is applied last, overriding every other source.
    """
    env = env or os.environ.get('FLASK_ENV', 'development')
    cfg = config.get(env, config['default'])

    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
    )

    # ── Configuration ─────────────────────────────────────────────────
    app.config.from_object(cfg)

    # Load instance config if it exists (overrides above). Skipped under
    # test so a local instance/config.py can never point tests at a real DB.
    if not app.config.get('TESTING'):
        app.config.from_pyfile(
            os.path.join(app.instance_path, 'config.py'),
            silent=True,
        )

    if test_config:
        app.config.update(test_config)

    # Runs after every config source so it creates the folders actually in use
    cfg.init_app(app)

    # ── App version ───────────────────────────────────────────────────
    app.version = os.environ.get('APP_VERSION', __version__)

    # ── Logging ───────────────────────────────────────────────────────
    _configure_logging(app)

    # ── Extensions ────────────────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # ── User loader ───────────────────────────────────────────────────
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id: str):
        user = db.session.get(User, int(user_id))
        # A suspended group signs out all of its officers
        if user and user.group and not user.group.is_active:
            return None
        return user

    # ── Template globals ──────────────────────────────────────────────
    # Make csrf_token() and now available in every template without
    # explicitly passing them from every controller.
    # ── Platform support sessions (read-only, logged) ─────────────────
    from app.services import support
    app.before_request(support.guard)

    @app.context_processor
    def inject_globals():
        from app.services.branding import current_brand
        return {
            'now':        datetime.now(),
            'csrf_token': generate_csrf,
            'version':    app.version,
            'brand':      current_brand(),
            'support':    support.info(),
        }

    @app.template_filter('intcomma')
    def intcomma(value):
        """Format a number with thousands separators: 12345 → 12,345."""
        try:
            return f'{int(value):,}'
        except (TypeError, ValueError):
            return value

    # ── Blueprints ────────────────────────────────────────────────────
    _register_blueprints(app)

    # ── CLI Commands ──────────────────────────────────────────────────
    from app.commands import init_commands
    init_commands(app)

    # ── Error handlers ────────────────────────────────────────────────
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)

    # ── Database ──────────────────────────────────────────────────────
    # The schema is managed by Flask-Migrate — run `flask db upgrade`.

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
    from app.routes.auth     import auth
    from app.routes.group    import group
    from app.routes.main     import main
    from app.routes.platform import platform
    from app.routes.report   import report

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(group)
    app.register_blueprint(platform)
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