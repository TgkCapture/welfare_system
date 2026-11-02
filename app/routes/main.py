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
from app.controllers.workbook_controller import WorkbookController
from app.controllers.member_controller import MemberController
from app.controllers.setup_controller import SetupController

main = Blueprint('main', __name__)

# ==================== DASHBOARDS ====================
main.route('/')(DashboardController.dashboard)
main.route('/setup', endpoint='setup')(SetupController.checklist)
main.route('/setup/toggle', methods=['POST'], endpoint='toggle_setup')(SetupController.toggle)
# The old per-role dashboards now lead to the one dashboard
main.route('/admin', endpoint='admin_dashboard')(DashboardController.old_dashboard)
main.route('/clerk-dashboard', endpoint='clerk_dashboard')(DashboardController.old_dashboard)
main.route('/viewer-dashboard', endpoint='viewer_dashboard')(DashboardController.old_dashboard)

# ==================== UPLOAD ====================
main.route('/upload-dashboard')(UploadController.upload_dashboard)
main.route('/upload', methods=['POST'])(UploadController.upload)

# ==================== WORKBOOK & SYNCS (upload_data) ====================
main.route('/workbook')(WorkbookController.workbook)
main.route('/workbook/template', methods=['POST'])(WorkbookController.download_template)
main.route('/syncs/<int:run_id>')(WorkbookController.sync_run)

# ==================== SETTINGS (edit_settings) ====================
main.route('/settings', methods=['GET', 'POST'])(SettingsController.settings)
main.route('/settings/payout-purposes', methods=['GET', 'POST'])(WorkbookController.payout_purposes)
main.route('/settings/workbook-layout', methods=['GET', 'POST'], endpoint='workbook_layout')(WorkbookController.layout)
main.route('/settings/public', methods=['GET', 'POST'], endpoint='public_pages')(SettingsController.public_pages)
main.route('/settings/payout-purposes/<int:purpose_id>/rename', methods=['POST'])(WorkbookController.rename_payout_purpose)
main.route('/settings/payout-purposes/<int:purpose_id>/toggle', methods=['POST'])(WorkbookController.toggle_payout_purpose)

# ==================== WELFARE RULES (public) ====================
main.route('/welfare-rules')(WelfareController.welfare_rules)
main.route('/welfare-rules/download')(WelfareController.download_welfare_rules_pdf)
main.route('/settings/rules', methods=['GET', 'POST'], endpoint='rules_editor')(WelfareController.editor)
main.route('/settings/rules/<int:section_id>', methods=['GET', 'POST'], endpoint='edit_rule_section')(WelfareController.edit_section)
main.route('/settings/rules/<int:section_id>/delete', methods=['POST'], endpoint='delete_rule_section')(WelfareController.delete_section)
main.route('/settings/rules/<int:section_id>/move', methods=['POST'], endpoint='move_rule_section')(WelfareController.move_section)

# ==================== ADMIN — FILE MANAGEMENT ====================
main.route('/admin/cleanup', methods=['GET', 'POST'])(DashboardController.cleanup_files)
main.route('/admin/storage-status')(DashboardController.storage_status)

# ==================== OFFICER MANAGEMENT (manage_users) ====================
main.route('/admin/users')(UserController.admin_users)
main.route('/admin/users/create',                   methods=['GET', 'POST'])(UserController.create_user)
main.route('/admin/users/<int:user_id>/edit',        methods=['GET', 'POST'])(UserController.edit_user)
main.route('/admin/users/<int:user_id>/delete',      methods=['POST'])(UserController.delete_user)
main.route('/admin/users/<int:user_id>/toggle',      methods=['POST'])(UserController.toggle_user_active)

# ==================== MEMBERS (manage_members) ====================
main.route('/members')(MemberController.members)
main.route('/members/<int:member_id>')(MemberController.member)
main.route('/members/<int:member_id>/rename',   methods=['POST'])(MemberController.rename)
main.route('/members/<int:member_id>/toggle',   methods=['POST'], endpoint='toggle_member')(MemberController.toggle)
main.route('/members/<int:member_id>/merge',    methods=['POST'], endpoint='merge_member')(MemberController.merge)
main.route('/members/<int:member_id>/aliases/<int:alias_id>/delete', methods=['POST'])(MemberController.remove_alias)
main.route('/members/<int:member_id>/link',     methods=['POST'])(MemberController.regenerate_link)
main.route('/members/<int:member_id>/pin',      methods=['POST'])(MemberController.set_pin)
main.route('/members/<int:member_id>/pin/clear', methods=['POST'])(MemberController.clear_pin)

# ==================== ROLES (manage_users) ====================
main.route('/admin/roles')(RoleController.roles)
main.route('/admin/roles/create',                   methods=['GET', 'POST'])(RoleController.create_role)
main.route('/admin/roles/<int:role_id>/edit',        methods=['GET', 'POST'])(RoleController.edit_role)
main.route('/admin/roles/<int:role_id>/delete',      methods=['POST'])(RoleController.delete_role)

# ==================== UTILITY ====================
main.route('/version')(DashboardController.version)
main.route('/api/health')(DashboardController.health_check)