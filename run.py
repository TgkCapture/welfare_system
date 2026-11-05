# run.py
"""
Development entry point.

For production use a proper WSGI server:
    gunicorn "app:create_app()" --workers 4 --bind 0.0.0.0:8000
"""
import os
from app import create_app

# Honour FLASK_ENV; default to development so DEBUG is on locally
env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    app.run(
        host=os.environ.get('FLASK_HOST', '127.0.0.1'),
        port=int(os.environ.get('FLASK_PORT', 5000)),
        debug=app.debug,
    )