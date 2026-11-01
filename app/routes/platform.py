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
