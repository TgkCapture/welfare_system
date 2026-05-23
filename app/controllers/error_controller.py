# app/controllers/error_controller.py
"""
Centralised error handling.

"""
import traceback

from flask import jsonify, render_template, request
import logging

logger = logging.getLogger(__name__)


class ErrorController:
    """Maps HTTP error codes to handlers and registers them with Flask."""

    # ==================== HTTP ERROR HANDLERS ====================

    @staticmethod
    def bad_request(error):
        """400 — malformed request."""
        logger.warning(f"400 Bad Request: {request.method} {request.path} — {error}")
        message = (
            str(error.description)
            if hasattr(error, 'description')
            else 'The request could not be understood.'
        )
        if ErrorController._wants_json():
            return jsonify({'error': 'Bad Request', 'message': message}), 400
        return render_template('errors/400.html', message=message), 400

    @staticmethod
    def unauthorized(error):
        """401 — authentication required."""
        logger.warning(f"401 Unauthorized: {request.method} {request.path}")
        message = 'Please log in to access this resource.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Unauthorized', 'message': message}), 401
        return render_template('errors/401.html', message=message), 401

    @staticmethod
    def forbidden(error):
        """403 — authenticated but not permitted."""
        logger.warning(
            f"403 Forbidden: {request.method} {request.path}"
        )
        message = 'You do not have permission to access this resource.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Forbidden', 'message': message}), 403
        return render_template('errors/403.html', message=message), 403

    @staticmethod
    def not_found(error):
        """404 — resource does not exist."""
        # 404s are informational, not warnings — paths are often probed
        logger.info(f"404 Not Found: {request.method} {request.path}")
        message = f'The page at {request.path} could not be found.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Not Found', 'message': message}), 404
        return render_template('errors/404.html', message=message), 404

    @staticmethod
    def method_not_allowed(error):
        """405 — wrong HTTP verb."""
        logger.warning(
            f"405 Method Not Allowed: {request.method} {request.path}"
        )
        message = f'The {request.method} method is not allowed here.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Method Not Allowed', 'message': message}), 405
        return render_template('errors/405.html', message=message), 405

    @staticmethod
    def request_entity_too_large(error):
        """413 — uploaded file exceeds MAX_CONTENT_LENGTH."""
        logger.warning(f"413 Payload Too Large: {request.path}")
        message = 'The uploaded file is too large. Please reduce its size and try again.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Payload Too Large', 'message': message}), 413
        return render_template('errors/413.html', message=message), 413

    @staticmethod
    def internal_server_error(error):
        """500 — unhandled exception surfaced by Flask."""
        # Log with full traceback so the root cause is visible in logs
        logger.error(
            f"500 Internal Server Error: {request.method} {request.path}\n"
            f"{traceback.format_exc()}"
        )
        message = 'An unexpected error occurred. Please try again later.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Internal Server Error', 'message': message}), 500
        return render_template('errors/500.html', message=message), 500

    @staticmethod
    def handle_unexpected_error(error):
        """Catch-all for any Exception not caught by Flask's own machinery.

        This fires for errors raised outside of a request context or for
        exception types that Flask does not automatically convert to 500s.
        """
        logger.error(
            f"Unhandled Exception: {type(error).__name__}: {error}\n"
            f"{traceback.format_exc()}"
        )
        message = 'An unexpected error occurred. Please try again later.'
        if ErrorController._wants_json():
            return jsonify({'error': 'Unexpected Error', 'message': message}), 500
        return render_template('errors/500.html', message=message), 500

    # ==================== HELPER ====================

    @staticmethod
    def _wants_json():
        """Return True when the client prefers a JSON response.

        Covers:
          - Explicit Accept: application/json header (API / fetch calls)
          - XHR requests that don't set Accept but set X-Requested-With
        """
        best = request.accept_mimetypes.best_match(
            ['application/json', 'text/html']
        )
        prefers_json = (
            best == 'application/json'
            and request.accept_mimetypes[best]
            > request.accept_mimetypes['text/html']
        )
        is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        return prefers_json or is_xhr

    # ==================== REGISTRATION ====================

    @staticmethod
    def register_error_handlers(app):
        """Register all handlers with the Flask application instance.

        Call once from the app factory (create_app):

            ErrorController.register_error_handlers(app)
        """
        app.register_error_handler(400, ErrorController.bad_request)
        app.register_error_handler(401, ErrorController.unauthorized)
        app.register_error_handler(403, ErrorController.forbidden)
        app.register_error_handler(404, ErrorController.not_found)
        app.register_error_handler(405, ErrorController.method_not_allowed)
        app.register_error_handler(413, ErrorController.request_entity_too_large)
        app.register_error_handler(500, ErrorController.internal_server_error)
        app.register_error_handler(Exception, ErrorController.handle_unexpected_error)