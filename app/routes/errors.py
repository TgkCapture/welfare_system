# app/routes/errors.py
"""
Error handler registration.
"""
from app.controllers.error_controller import ErrorController


def register_error_handlers(app):
    """Register all HTTP error handlers with *app*."""
    ErrorController.register_error_handlers(app)