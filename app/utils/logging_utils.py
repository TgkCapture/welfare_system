# app/utils/logging_utils.py
"""
Logging configuration.

Call ``setup_logging(app)`` from the app factory after the app object
is created but before the first request arrives.

Two rotating file handlers are created:
  app.log    — INFO and above (daily operations, uploaded files, etc.)
  error.log  — ERROR and above (full tracebacks for post-mortem debugging)

A console handler is added in DEBUG mode so developers see output
directly without tailing a file.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(app) -> None:
    """Attach handlers to *app.logger* and configure third-party loggers.

    Safe to call multiple times — existing handlers are cleared first so
    calling ``create_app()`` twice in tests does not duplicate output.
    """
    # Clear any handlers added by Flask's default bootstrap
    app.logger.handlers.clear()

    logs_dir = app.config.get('LOGS_FOLDER', 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    max_bytes    = app.config.get('LOG_FILE_MAX_SIZE',  10 * 1024 * 1024)  # 10 MB
    backup_count = app.config.get('LOG_BACKUP_COUNT',   10)

    # ── Formatters ────────────────────────────────────────────────────
    detailed = logging.Formatter(
        '%(asctime)s %(levelname)-8s [%(name)s] %(message)s '
        '(%(filename)s:%(lineno)d)'
    )
    simple = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s'
    )

    # ── Console (debug only) ──────────────────────────────────────────
    if app.debug:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console.setFormatter(detailed)
        app.logger.addHandler(console)

    # ── app.log — general operational log ─────────────────────────────
    app_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'app.log'),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(simple)
    app.logger.addHandler(app_handler)

    # ── error.log — errors + tracebacks ───────────────────────────────
    error_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'error.log'),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed)
    app.logger.addHandler(error_handler)

    # ── Overall level ─────────────────────────────────────────────────
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)

    # ── Quieten noisy third-party loggers ─────────────────────────────
    _noisy = {
        'werkzeug':         logging.WARNING,
        'sqlalchemy.engine':logging.WARNING,
        'gspread':          logging.WARNING,
        'google':           logging.WARNING,
        'urllib3':          logging.WARNING,
        'matplotlib':       logging.WARNING,
    }
    for name, level in _noisy.items():
        logging.getLogger(name).setLevel(level)

    app.logger.info(
        f"Logging configured — "
        f"level={'DEBUG' if app.debug else 'INFO'}, "
        f"log_dir={logs_dir!r}"
    )