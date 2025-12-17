# app/routes/errors.py
from flask import render_template, jsonify, request
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors"""
        logger.warning(f"Bad request: {str(error)}")
        if request_wants_json():
            return jsonify({
                'error': 'Bad request',
                'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
            }), 400
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors"""
        logger.warning(f"Unauthorized access: {str(error)}")
        if request_wants_json():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Please log in to access this resource'
            }), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors"""
        logger.warning(f"Forbidden access: {str(error)}")
        if request_wants_json():
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource'
            }), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors"""
        logger.info(f"Page not found: {request.path}")
        if request_wants_json():
            return jsonify({
                'error': 'Not found',
                'message': f'The requested URL {request.path} was not found'
            }), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors"""
        logger.warning(f"Method not allowed: {request.method} {request.path}")
        if request_wants_json():
            return jsonify({
                'error': 'Method not allowed',
                'message': f'The {request.method} method is not allowed for this endpoint'
            }), 405
        return render_template('errors/405.html'), 405
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle 413 Request Entity Too Large errors"""
        logger.warning(f"Request too large: {request.path}")
        if request_wants_json():
            return jsonify({
                'error': 'Request too large',
                'message': 'The uploaded file is too large'
            }), 413
        return render_template('errors/413.html'), 413
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error"""
        logger.error(f"Internal server error: {str(error)}", exc_info=True)
        if request_wants_json():
            return jsonify({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred. Please try again later.'
            }), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Catch-all for unexpected errors"""
        logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        if request_wants_json():
            return jsonify({
                'error': 'Unexpected error',
                'message': 'An unexpected error occurred. Please try again later.'
            }), 500
        return render_template('errors/500.html'), 500

def request_wants_json():
    """Check if the request prefers JSON response"""
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
           request.accept_mimetypes[best] > request.accept_mimetypes['text/html']