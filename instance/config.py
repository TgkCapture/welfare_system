# instance/config.py
"""
Instance-specific overrides — never commit this file to version control.

Values here override app/config.py for the local machine only.
Copy this file to instance/config.py and fill in real values.
"""
import os

# ── Core security ──────────────────────────────────────────────────────────
# Generate a strong key with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE-ME-USE-ENV-VAR-IN-PRODUCTION')

# ── Database ───────────────────────────────────────────────────────────────
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'DATABASE_URL',
    'sqlite:///welfare_dev.db',    # relative to the instance/ folder
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ── File storage ───────────────────────────────────────────────────────────
_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UPLOAD_FOLDER = os.path.join(_base, 'uploads')
REPORT_FOLDER = os.path.join(_base, 'reports')
LOGS_FOLDER   = os.path.join(_base, 'logs')

# ── Google Sheets credentials ──────────────────────────────────────────────
# Option A: path to the service-account JSON file (local dev only)
GOOGLE_CREDENTIALS_PATH = os.environ.get(
    'GOOGLE_CREDENTIALS_PATH',
    os.path.join(_base, 'credentials', 'service_account.json'),
)

# Option B: the JSON content as an env var (preferred for production)
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON', '')

# Pre-configured sheet URL (optional convenience)
DEFAULT_SHEET_URL = os.environ.get('DEFAULT_SHEET_URL', '')