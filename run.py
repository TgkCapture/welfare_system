# run.py
import os
from app import create_app
from app.config import config

app = create_app(config[os.getenv('FLASK_ENV') or 'default'])

if __name__ == '__main__':
    app.run(debug=True)
