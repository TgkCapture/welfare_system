# config.py
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-123'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    REPORT_FOLDER = os.path.join(basedir, 'reports')
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    
    # Google Sheets API credentials
    GSHEETS_CREDENTIALS = os.path.join(basedir, 'credentials.json')
    GSHEETS_SHEET_ID = os.environ.get('GSHEETS_SHEET_ID')