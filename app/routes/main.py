# app/routes/main.py
from flask import Blueprint
from app.controllers.dashboard_controller import DashboardController
from app.controllers.report_controller import ReportController
from app.controllers.upload_controller import UploadController
from app.controllers.settings_controller import SettingsController
from app.controllers.welfare_controller import WelfareController
from app.controllers.user_controller import UserController

main = Blueprint('main', __name__)

# ==================== DASHBOARD ROUTES ====================
main.route('/')(DashboardController.dashboard)
main.route('/admin')(DashboardController.admin_dashboard)
main.route('/clerk-dashboard')(DashboardController.clerk_dashboard)
main.route('/viewer-dashboard')(DashboardController.viewer_dashboard)

# ==================== UPLOAD ROUTES ====================
main.route('/upload-dashboard')(UploadController.upload_dashboard)
main.route('/upload', methods=['POST'])(UploadController.upload)

# ==================== REPORT ROUTES ====================
main.route('/report-preview')(ReportController.report_preview)
main.route('/download-report')(ReportController.download_report)
main.route('/download-paid-members')(ReportController.download_paid_members)
main.route('/reports')(ReportController.reports_list)
main.route('/paid-members')(ReportController.paid_members_view)

# ==================== SETTINGS ROUTES ====================
main.route('/settings', methods=['GET', 'POST'])(SettingsController.settings)

# ==================== WELFARE RULES ROUTES ====================
main.route('/welfare-rules')(WelfareController.welfare_rules)
main.route('/download-welfare-rules-pdf')(ReportController.download_welfare_rules_pdf)

# ==================== ADMIN CLEANUP ROUTES ====================
main.route('/admin/cleanup', methods=['GET', 'POST'])(DashboardController.cleanup_files)
main.route('/admin/storage-status')(DashboardController.storage_status)

# ==================== USER MANAGEMENT ROUTES ====================
main.route('/admin/users')(UserController.admin_users)
main.route('/admin/users/create', methods=['GET', 'POST'])(UserController.create_user)

# ==================== HEALTH CHECK ROUTES ====================
main.route('/version')(DashboardController.version)
main.route('/api/health')(DashboardController.health_check)

# ==================== MIDDLEWARE ====================
main.after_request(DashboardController.after_request)
