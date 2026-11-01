# app/routes/group.py
"""
Per-group pages, under /g/<slug>/.

Holds the group's officer login now; the public member pages (paid list,
personal history, rules) are added here in Phase 4.
"""
from flask import Blueprint

from app.controllers.auth_controller import AuthController

group = Blueprint('group', __name__, url_prefix='/g/<slug>')

# ==================== AUTH ====================
group.route('/login', methods=['GET', 'POST'], endpoint='login')(AuthController.group_login)
