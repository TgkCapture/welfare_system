# ./instance/config.py
import os

SECRET_KEY = 'supersecretkey'
SQLALCHEMY_DATABASE_URI = 'sqlite:///db.sqlite3'
SQLALCHEMY_TRACK_MODIFICATIONS = False
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
REPORT_FOLDER = os.path.join(os.getcwd(), 'reports')

GOOGLE_CREDENTIALS_PATH='C:\\Users\\tawon\\OneDrive\\Documents\\CODE-BASE\\welfare_system\\credentials\\mzugoss-welfare-5dab294def1f.json'
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')
DEFAULT_SHEET_URL = os.environ.get('DEFAULT_SHEET_URL', '')