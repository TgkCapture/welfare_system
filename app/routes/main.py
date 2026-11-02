# app/routes/main.py
"""
Main blueprint — covers everything that is not auth or report-specific.
"""
from flask import Blueprint

from app.controllers.dashboard_controller import DashboardController
from app.controllers.upload_controller import UploadController
from app.controllers.settings_controller import SettingsController
from app.controllers.welfare_controller import WelfareController
from app.controllers.user_controller import UserController
from app.controllers.role_controller import RoleController

main = Blueprint('main', __name__)

# ==================== DASHBOARDS ====================
main.route('/')(DashboardController.dashboard)
main.route('/admin')(DashboardController.admin_dashboard)
main.route('/clerk-dashboard')(DashboardController.clerk_dashboard)
main.route('/viewer-dashboard')(DashboardController.viewer_dashboard)

# ==================== UPLOAD ====================
main.route('/upload-dashboard')(UploadController.upload_dashboard)
main.route('/upload', methods=['POST'])(UploadController.upload)

# ==================== SETTINGS (admin only) ====================
main.route('/settings', methods=['GET', 'POST'])(SettingsController.settings)

# ==================== WELFARE RULES (public) ====================
main.route('/welfare-rules')(WelfareController.welfare_rules)
main.route('/welfare-rules/download')(WelfareController.download_welfare_rules_pdf)

# ==================== ADMIN — FILE MANAGEMENT ====================
main.route('/admin/cleanup', methods=['GET', 'POST'])(DashboardController.cleanup_files)
main.route('/admin/storage-status')(DashboardController.storage_status)

# ==================== OFFICER MANAGEMENT (manage_users) ====================
main.route('/admin/users')(UserController.admin_users)
main.route('/admin/users/create',                   methods=['GET', 'POST'])(UserController.create_user)
main.route('/admin/users/<int:user_id>/edit',        methods=['GET', 'POST'])(UserController.edit_user)
main.route('/admin/users/<int:user_id>/delete',      methods=['POST'])(UserController.delete_user)
main.route('/admin/users/<int:user_id>/toggle',      methods=['POST'])(UserController.toggle_user_active)

# ==================== ROLES (manage_users) ====================
main.route('/admin/roles')(RoleController.roles)
main.route('/admin/roles/create',                   methods=['GET', 'POST'])(RoleController.create_role)
main.route('/admin/roles/<int:role_id>/edit',        methods=['GET', 'POST'])(RoleController.edit_role)
main.route('/admin/roles/<int:role_id>/delete',      methods=['POST'])(RoleController.delete_role)

# ==================== UTILITY ====================
main.route('/version')(DashboardController.version)
main.route('/api/health')(DashboardController.health_check)