# app/routes/group.py
"""
Per-group pages, under /g/<slug>/.

Holds the group's officer login and a member's personal history page; the
other public pages (landing, paid list, PIN lookup, rules) come in Phase 4.
"""
from flask import Blueprint

from app.controllers.auth_controller import AuthController
from app.controllers.member_controller import MemberController
from app.controllers.welfare_controller import WelfareController

group = Blueprint('group', __name__, url_prefix='/g/<slug>')

# ==================== AUTH ====================
group.route('/login', methods=['GET', 'POST'], endpoint='login')(AuthController.group_login)

# ==================== PUBLIC ====================
group.route('/m/<token>', endpoint='member_history')(MemberController.public_history)
group.route('/rules', endpoint='rules')(WelfareController.public_rules)
group.route('/rules.pdf', endpoint='rules_pdf')(WelfareController.public_rules_pdf)
