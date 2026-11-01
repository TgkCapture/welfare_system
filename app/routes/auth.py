# app/routes/auth.py
"""
Authentication and profile routes.
"""
from flask import Blueprint

from app.controllers.auth_controller import AuthController
from app.controllers.profile_controller import ProfileController

auth = Blueprint('auth', __name__, url_prefix='/auth')

# ==================== AUTH ====================
auth.route('/login',  methods=['GET', 'POST'])(AuthController.login)
auth.route('/logout')(AuthController.logout)

# No public registration: officer accounts are created by other officers
# or the platform superadmin. Members do not have accounts.

# ==================== PROFILE ====================
auth.route('/profile', methods=['GET'])(ProfileController.profile)
auth.route('/change-password', methods=['POST'])(ProfileController.change_password)
auth.route('/update-profile',  methods=['POST'])(ProfileController.update_profile)

# ==================== ACTIVITY & DATA ====================
auth.route('/activity-log')(ProfileController.activity_log)
auth.route('/export-data', methods=['POST'])(ProfileController.export_data)

# ==================== ACCOUNT DELETION ====================
auth.route('/delete-account', methods=['POST'])(ProfileController.delete_account)