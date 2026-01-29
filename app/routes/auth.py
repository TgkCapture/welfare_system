# app/routes/auth.py
from flask import Blueprint
from app.controllers.auth_controller import AuthController

auth = Blueprint('auth', __name__, url_prefix='/auth')

# ==================== LOGIN/LOGOUT ====================
auth.route('/login', methods=['GET', 'POST'])(AuthController.login)
auth.route('/logout')(AuthController.logout)

# ==================== USER REGISTRATION ====================
auth.route('/register', methods=['GET', 'POST'])(AuthController.register)

# ==================== USER MANAGEMENT ====================
auth.route('/users')(AuthController.user_management)
auth.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])(AuthController.edit_user)
auth.route('/users/<int:user_id>/delete', methods=['POST'])(AuthController.delete_user)
auth.route('/users/<int:user_id>/toggle-active', methods=['POST'])(AuthController.toggle_user_active)

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