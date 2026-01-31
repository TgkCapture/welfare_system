# app/routes/auth.py
from flask import Blueprint
from app.controllers.auth_controller import AuthController

auth = Blueprint('auth', __name__, url_prefix='/auth')

# ==================== LOGIN/LOGOUT ====================
auth.route('/login', methods=['GET', 'POST'])(AuthController.login)
auth.route('/logout')(AuthController.logout)

# ==================== USER PROFILE ====================
auth.route('/profile', methods=['GET', 'POST'])(AuthController.profile)
auth.route('/change-password', methods=['POST'])(AuthController.change_password)
auth.route('/update-profile', methods=['POST'])(AuthController.update_profile)

# ==================== ACTIVITY LOG ====================
auth.route('/activity-log')(AuthController.activity_log)

# ==================== DATA EXPORT ====================
auth.route('/export-data', methods=['POST'])(AuthController.export_data)

# ==================== ACCOUNT DELETION ====================
auth.route('/delete-account', methods=['POST'])(AuthController.delete_account)