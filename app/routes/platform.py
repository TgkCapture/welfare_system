# app/routes/platform.py
"""
Platform administration (superadmins), under /platform/.
"""
from flask import Blueprint

from app.controllers.auth_controller import AuthController
from app.controllers.platform_controller import PlatformController

platform = Blueprint('platform', __name__, url_prefix='/platform')

# ==================== AUTH ====================
platform.route('/login', methods=['GET', 'POST'], endpoint='login')(AuthController.platform_login)

# ==================== DASHBOARD ====================
platform.route('/', endpoint='dashboard')(PlatformController.dashboard)

# ==================== GROUPS ====================
platform.route('/groups/new', methods=['GET', 'POST'], endpoint='create_group')(PlatformController.create_group)
platform.route('/groups/<int:group_id>', methods=['GET', 'POST'], endpoint='group_detail')(PlatformController.group_detail)
platform.route('/groups/<int:group_id>/toggle', methods=['POST'], endpoint='toggle_group')(PlatformController.toggle_group)
platform.route('/groups/<int:group_id>/officers', methods=['POST'], endpoint='add_officer')(PlatformController.add_officer)

# ==================== SUPPORT SESSIONS AND AUDIT LOG ====================
platform.route('/groups/<int:group_id>/support', methods=['POST'], endpoint='start_support')(PlatformController.start_support)
platform.route('/support/end', methods=['POST'], endpoint='end_support')(PlatformController.end_support)
platform.route('/audit', endpoint='audit_log')(PlatformController.audit_log)

# ==================== STORAGE ====================
platform.route('/storage', methods=['GET', 'POST'], endpoint='storage')(PlatformController.storage)
